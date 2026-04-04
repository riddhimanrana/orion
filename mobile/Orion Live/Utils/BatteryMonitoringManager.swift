//
//  BatteryMonitoringManager.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Background battery monitoring and thermal state tracking for Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//

import Foundation
import UIKit
import Combine

/// Enhanced battery monitoring manager with instant calculation logic
class BatteryMonitoringManager: ObservableObject {
    // MARK: - Published Properties
    @Published var batteryPercentage: Int = 0
    @Published var isCharging: Bool = false
    @Published var batteryTimeRemaining: String = ""
    @Published var thermalState: ProcessInfo.ThermalState = .nominal
    @Published var thermalStateDescription: String = "Normal"
    @Published var batteryEstimateConfidence: Double = 0.0
    @Published var estimatedActualBatteryPercent: Int? = nil
    
    // MARK: - Private Properties
    private var monitoringTimer: Timer?
    private var updateTimer: Timer? // Timer for updating countdown display
    private var batterySamples: [(date: Date, percentage: Int)] = []
    private let monitoringInterval: TimeInterval = 5.0 // Check every 5 seconds for faster detection
    private let updateInterval: TimeInterval = 5.0 // Update display every 5 seconds to reduce churn
    
    // Enhanced calculation properties
    private var lastCalculationDate: Date?
    private var calculatedSecondsRemaining: TimeInterval = 0
    private var isCalculating: Bool = true
    private var averageTimePerPercent: TimeInterval = 0
    private var hasSeededInitialSample: Bool = false
    
    // App lifecycle tracking
    private var appDidBecomeActiveDate: Date?
    private var isMonitoringActive: Bool = false
    private var didHandleInitialForeground: Bool = false

    // Virtual percent and EMA smoothing
    private var virtualBatteryPercent: Double = 0.0
    private var anchorPercent: Double = 0.0
    private var anchorDate: Date?
    // Activity/mode flags
    private var cameraOn: Bool = false
    private var webrtcConnected: Bool = false
    private var mlActiveHint: Bool = false

    // EMA per composite mode key (e.g., C1_W1_M0)
    private var emaByModeKey: [String: TimeInterval] = [:]
    private var emaTimePerPercent: TimeInterval = 0 // derived from emaByModeKey[currentModeKey]
    private let emaAlpha: Double = 0.4
    private var isLowPowerModeEnabled: Bool = ProcessInfo.processInfo.isLowPowerModeEnabled
    private var brightnessObserverAdded: Bool = false
    private var systemCPUPercent: Double = 0.0
    private var observedBucketDrops: Int = 0
    private var lastBucketIndex: Int? = nil
    private var lastThresholdLog: (mode: String, drops: Int, value: Double)? = nil

    // Snapshot and gating log throttling
    private var lastSnapshotLogDate: Date? = nil
    private let snapshotLogInterval: TimeInterval = 30.0
    private var lastSnapshotVirtual: Double? = nil
    private var lastSnapshotMinutesRemaining: Int? = nil
    private var lastSnapshotDrops: Int? = nil
    private var lastUIGatingVisible: Bool? = nil
    private var lastUIGatingMinutes: Int? = nil

    // Mode stability tracking for confidence
    private var lastModeKey: String? = nil
    private var lastModeChangeDate: Date? = nil

    // Compose a simple mode key string (camera, webrtc, ml)
    private var currentModeKey: String {
        "C\(cameraOn ? 1 : 0)_W\(webrtcConnected ? 1 : 0)_M\(mlActiveHint ? 1 : 0)"
    }

    // External hook to update activity flags
    func updateActivity(cameraOn: Bool? = nil, webrtcConnected: Bool? = nil, mlActive: Bool? = nil) {
        let oldKey = currentModeKey
        if let cameraOn = cameraOn { self.cameraOn = cameraOn }
        if let webrtcConnected = webrtcConnected { self.webrtcConnected = webrtcConnected }
        if let mlActive = mlActive { self.mlActiveHint = mlActive }
        let newKey = currentModeKey
        if oldKey != newKey {
            Logger.shared.battery("Mode changed: \(oldKey) → \(newKey)", level: .info)
            lastModeKey = newKey
            lastModeChangeDate = Date()
        }
    }
    
    // MARK: - Initialization
    init() {
        setupBatteryMonitoring()
        // Initialize UI state
        batteryTimeRemaining = "Calculating..."
        // Seed display with current OS-reported level immediately if valid
        let lvl = UIDevice.current.batteryLevel
        if lvl >= 0 { batteryPercentage = Int(lvl * 100) }
        setupAppLifecycleObservers()
        // Do not log here to control ordering; startBackgroundMonitoring will log in desired order
        startBackgroundMonitoring()
    }
    
    deinit {
        stopMonitoring()
        NotificationCenter.default.removeObserver(self)
        Logger.shared.battery("Battery monitoring manager deinitialized")
    }
    
    // MARK: - Public Methods
    func startBackgroundMonitoring() {
        guard !isMonitoringActive else { return }
        isMonitoringActive = true

        // Log in desired order
        Logger.shared.battery("Background battery monitoring started", level: .info)
        let currentLevel = Int(max(0, UIDevice.current.batteryLevel) * 100)
        Logger.shared.battery("Battery monitoring enabled; current level=\(currentLevel)% state=\(UIDevice.current.batteryState)", level: .info)
        Logger.shared.battery("Battery monitoring manager initialized", level: .info)

        // Ensure current charging state is reflected before seeding
        updateChargingState()
        // Seed initial sample and UI state deterministically (only when not charging)
        seedInitialSample()
        updateThermalState()
        
        // Start update timer for countdown display
        updateTimer = Timer.scheduledTimer(withTimeInterval: updateInterval, repeats: true) { [weak self] _ in
            self?.updateCountdownDisplay()
        }
        if let updateTimer = updateTimer {
            RunLoop.main.add(updateTimer, forMode: .common)
        }
        
        // Removed duplicate start log
    }
    
    func stopMonitoring() {
        isMonitoringActive = false
        monitoringTimer?.invalidate()
        monitoringTimer = nil
        updateTimer?.invalidate()
        updateTimer = nil
        // Keep battery monitoring and observers active so notifications still arrive when app is foregrounded again.
        Logger.shared.battery("Background battery monitoring stopped (timers only)", level: .info)
    }
    
    // MARK: - Private Methods
    private func setupBatteryMonitoring() {
        // Enable battery monitoring
        UIDevice.current.isBatteryMonitoringEnabled = true
        
        // Setup notification observers for immediate battery state changes
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(batteryStateDidChange),
            name: UIDevice.batteryStateDidChangeNotification,
            object: nil
        )
        
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(batteryLevelDidChange),
            name: UIDevice.batteryLevelDidChangeNotification,
            object: nil
        )

        // Low Power Mode changes
        NotificationCenter.default.addObserver(
            forName: .NSProcessInfoPowerStateDidChange,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            guard let self else { return }
            let new = ProcessInfo.processInfo.isLowPowerModeEnabled
            if new != self.isLowPowerModeEnabled {
                self.isLowPowerModeEnabled = new
                Logger.shared.battery("Low Power Mode: \(new ? "ON" : "OFF")", level: .info)
            }
        }
        
        // Screen brightness changes (affects drain slightly)
        if !brightnessObserverAdded {
            brightnessObserverAdded = true
            NotificationCenter.default.addObserver(
                self,
                selector: #selector(screenBrightnessDidChange),
                name: UIScreen.brightnessDidChangeNotification,
                object: nil
            )
        }
    }
    
    private func setupAppLifecycleObservers() {
        // Reset calculations when app goes to background
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(appDidEnterBackground),
            name: UIApplication.didEnterBackgroundNotification,
            object: nil
        )
        
        // Restart monitoring when app becomes active
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(appWillEnterForeground),
            name: UIApplication.willEnterForegroundNotification,
            object: nil
        )
    }
    
    @objc private func batteryStateDidChange() {
        DispatchQueue.main.async {
            self.updateChargingState()
            Logger.shared.battery("Notification: Battery state changed to \(UIDevice.current.batteryState)", level: .info)
        }
    }
    
    @objc private func batteryLevelDidChange() {
        DispatchQueue.main.async {
            Logger.shared.battery("Notification: Battery level now \(Int(UIDevice.current.batteryLevel * 100))%", level: .info)
            self.updateBatteryLevel()
        }
    }

    @objc private func screenBrightnessDidChange() {
        let b = UIScreen.main.brightness
        Logger.shared.battery(String(format: "Screen brightness changed: %.2f", b), level: .debug)
    }
    
    @objc private func appDidEnterBackground() {
        // Reset calculations since we can't track consumption in background
        resetCalculations()
        stopMonitoring()
        Logger.shared.battery("App entered background - resetting battery calculations", level: .info)
    }
    
    @objc private func appWillEnterForeground() {
        appDidBecomeActiveDate = Date()
        // Skip the very first foreground event to avoid duplicating startup logs
        if !didHandleInitialForeground {
            didHandleInitialForeground = true
            Logger.shared.battery("App entered foreground (initial)", level: .info)
            return
        }
        resetCalculations()
        Logger.shared.battery("App entered foreground", level: .info)
        startBackgroundMonitoring()
    }
    
    private func updateBatteryStatus() {
        updateBatteryLevel()
        updateChargingState()
    }
    
    private func updateBatteryLevel() {
        let level = UIDevice.current.batteryLevel
        
        // Handle invalid battery level readings
        guard level >= 0 else { 
            return 
        }
        
    let newPercentage = Int(level * 100)
        
        // Handle very first seed if not done yet (only when not charging)
        if !hasSeededInitialSample && batterySamples.isEmpty && !isCharging {
            // Initial path: log current level and treat as first sample
            batteryPercentage = newPercentage
            Logger.shared.battery("Initial battery level: \(newPercentage)%", level: .info)
            appendBatterySample(percentage: newPercentage)
            batteryTimeRemaining = "Calculating..."
            Logger.shared.battery("Insufficient samples for calculation", level: .debug)
            hasSeededInitialSample = true
            return
        }
        // If charging on first read, just set percentage and keep display empty (no calculations while charging)
        if !hasSeededInitialSample && batterySamples.isEmpty && isCharging {
            batteryPercentage = newPercentage
            batteryTimeRemaining = ""
            return
        }
        
        // Only update if the value actually changed
        if newPercentage != batteryPercentage {
            let oldPercentage = batteryPercentage
            batteryPercentage = newPercentage
            // Detect bucket boundary crossings (handles 1% step updates too)
            let newBucket = newPercentage / 5
            let prevBucket = lastBucketIndex ?? (oldPercentage / 5)
            if newBucket < prevBucket {
                let drops = prevBucket - newBucket
                observedBucketDrops += drops
                // Second rounding bucket anchoring at boundary: anchor to (bucket*5)+2
                let anchorActual = Double(min(100, max(0, newBucket * 5 + 2)))
                anchorPercent = anchorActual
                virtualBatteryPercent = anchorPercent
                anchorDate = Date()
                Logger.shared.battery(String(format: "Bucket drop anchor set: OS=%d%% → anchor≈%.0f%% (drops=%d)", newPercentage, anchorActual, drops), level: .debug)
            }
            lastBucketIndex = newBucket
            
            Logger.shared.battery("Battery level changed: \(oldPercentage)% → \(newPercentage)%", level: .info)
            
            // Add sample for time calculation if not charging
            if !isCharging {
                appendBatterySample(percentage: newPercentage)
                calculateInstantTimeRemaining()
                // Note: anchoring is handled above only when a bucket crossing occurs
            }
        } else {
            // No change in percent; ensure calculating state shows initially
            if isCalculating && !isCharging && batteryTimeRemaining.isEmpty {
                batteryTimeRemaining = "Calculating..."
            }
        }
    }

    private func seedInitialSample() {
        let level = UIDevice.current.batteryLevel
        guard level >= 0 else { return }
        let pct = Int(level * 100)
        if !hasSeededInitialSample && batterySamples.isEmpty && !isCharging {
            batteryPercentage = pct
            Logger.shared.battery("Initial battery level: \(pct)%", level: .info)
            appendBatterySample(percentage: pct)
            batteryTimeRemaining = "Calculating..."
            Logger.shared.battery("Insufficient samples for calculation", level: .debug)
            hasSeededInitialSample = true
            lastBucketIndex = pct / 5
        }
    }
    
    private func updateChargingState() {
        let batteryState = UIDevice.current.batteryState
        let wasCharging = isCharging
        
        switch batteryState {
        case .charging, .full:
            isCharging = true
        case .unplugged:
            isCharging = false
        case .unknown:
            // Keep previous state if unknown
            break
        @unknown default:
            break
        }
        
        // Handle charging state changes
        if wasCharging != isCharging {
            if isCharging {
                Logger.shared.battery("Device plugged in - resetting calculations", level: .info)
                resetCalculations()
                // Suppress display while charging
                batteryTimeRemaining = ""
                // Do not show estimated percent while charging
                estimatedActualBatteryPercent = nil
            } else {
                Logger.shared.battery("Device unplugged - restarting monitoring and calculation", level: .info)
                resetCalculations()
                // Seed immediately now that we're on battery
                seedInitialSample()
                // Ensure timers are running
                startBackgroundMonitoring()
            }
        }
    }
    
    private func updateThermalState() {
        let newThermalState = ProcessInfo.processInfo.thermalState
        
        if newThermalState != thermalState {
            let oldState = thermalStateString(for: thermalState)
            thermalState = newThermalState
            thermalStateDescription = thermalStateString(for: newThermalState)
            Logger.shared.battery("Thermal state changed: \(oldState) → \(thermalStateDescription)", level: .info)
        }
    }
    
    private func thermalStateString(for state: ProcessInfo.ThermalState) -> String {
        switch state {
        case .nominal:
            return "Normal"
        case .fair:
            return "Fair"
        case .serious:
            return "High"
        case .critical:
            return "Critical"
        @unknown default:
            return "Unknown"
        }
    }
    
    private func resetCalculations() {
        batterySamples.removeAll()
        lastCalculationDate = nil
        calculatedSecondsRemaining = 0
        averageTimePerPercent = 0
        isCalculating = true
        batteryTimeRemaining = "Calculating..."
        lastBucketIndex = nil
        Logger.shared.battery("Battery calculations reset", level: .debug)
    }
    
    private func appendBatterySample(percentage: Int) {
        let now = Date()
        
        // Only add if percentage has changed from the last sample
        if let lastSample = batterySamples.last {
            guard lastSample.percentage != percentage else { return }
        }
        
        batterySamples.append((now, percentage))
        Logger.shared.battery("Added battery sample: \(percentage)% at \(now)", level: .debug)
        
        // Keep only the last 50 samples for better averaging
        if batterySamples.count > 50 {
            batterySamples.removeFirst()
        }
    }
    
    private func calculateInstantTimeRemaining() {
        guard batterySamples.count >= 2 else {
            batteryTimeRemaining = "Calculating..."
            Logger.shared.battery("Insufficient samples for calculation", level: .debug)
            return
        }
        
        // Calculate time intervals between percentage drops
        var validIntervals: [TimeInterval] = []
        
        for i in 1..<batterySamples.count {
            let prevSample = batterySamples[i-1]
            let currentSample = batterySamples[i]
            
            // Only count actual drops (not increases)
            if currentSample.percentage < prevSample.percentage {
                let timeDiff = currentSample.date.timeIntervalSince(prevSample.date)
                let percentageDrop = prevSample.percentage - currentSample.percentage
                
                // Calculate time per 1% drop
                if percentageDrop > 0 && timeDiff > 0 && timeDiff < 3600 { // Ignore intervals > 1 hour
                    let timePerPercent = timeDiff / Double(percentageDrop)
                    validIntervals.append(timePerPercent)
                }
            }
        }
        
        guard !validIntervals.isEmpty else {
            batteryTimeRemaining = "Calculating..."
            Logger.shared.battery("No valid drop intervals found", level: .debug)
            return
        }
        
    // Calculate weighted average (more recent samples have higher weight)
        var weightedSum: TimeInterval = 0
        var totalWeight: Double = 0
        
        for (index, interval) in validIntervals.enumerated() {
            let weight = Double(index + 1) // More recent = higher weight
            weightedSum += interval * weight
            totalWeight += weight
        }
        
        let observedTimePerPercent = weightedSum / totalWeight
        // For the first few intervals, use raw observed rate to get on-screen estimates faster
        if validIntervals.count < 3 {
            emaTimePerPercent = observedTimePerPercent
        } else {
            // EMA smoothing per composite mode after initial stabilization
            let key = currentModeKey
            let prev = emaByModeKey[key] ?? 0
            let updated: TimeInterval = prev <= 0 ? observedTimePerPercent : (emaAlpha * observedTimePerPercent + (1 - emaAlpha) * prev)
            emaByModeKey[key] = updated
            emaTimePerPercent = updated
        }
        
        // Validate the rate is reasonable (between 10 seconds and 2 hours per percent)
        guard emaTimePerPercent >= 20 && emaTimePerPercent <= 7200 else { 
            batteryTimeRemaining = "Calculating..."
            Logger.shared.battery("Invalid time per percent (EMA): \(emaTimePerPercent)s", level: .debug)
            return
        }
        
        // Confidence model: intervals count + variance + bucket drops + mode stability
        let intervalsCount = min(10, validIntervals.count)
        let countScore = Double(intervalsCount) / 10.0 // up to 10 intervals
        let mean = validIntervals.reduce(0, +) / Double(validIntervals.count)
        let variance = validIntervals.reduce(0) { $0 + pow($1 - mean, 2) } / Double(validIntervals.count)
        let stdev = sqrt(variance)
        let variability = min(stdev / max(mean, 1), 1) // normalized variability
        // As we collect more intervals, tolerate variability more
        let variabilityWeight: Double = intervalsCount >= 5 ? 0.2 : 0.3
        let variabilityScore = 1 - variability // lower variability -> higher score
        // Bucket drop score saturates after ~3 drops
        let dropScore = min(1.0, Double(observedBucketDrops) / 3.0)
        // Mode stability based on time since last mode change (saturate at 5 minutes)
        let stabilitySeconds = Date().timeIntervalSince(lastModeChangeDate ?? Date(timeIntervalSinceNow: -600))
        let stabilityScore = min(1.0, stabilitySeconds / 300.0)
        // Combine
        let combined = 0.5*countScore + variabilityWeight*variabilityScore + 0.2*dropScore + 0.1*stabilityScore
        // Floor after multiple drops with enough intervals
        let floored = (observedBucketDrops >= 3 && intervalsCount >= 5) ? max(combined, 0.8) : combined
        batteryEstimateConfidence = max(0, min(floored, 1))
        Logger.shared.battery(String(format: "Confidence updated: %.2f (count=%.0f, stdev=%.1f, drops=%d, stability=%.2f)", batteryEstimateConfidence, Double(intervalsCount), stdev, observedBucketDrops, stabilityScore), level: .debug)
        
    // Mark as calculated; do not re-anchor here to preserve bucket-based anchoring
        lastCalculationDate = anchorDate
        isCalculating = false
        
    updateTimeDisplay()
    // Log rounding buckets for transparency
    logRoundingBucket()
        
        Logger.shared.battery("Calculation updated: \(String(format: "%.1f", emaTimePerPercent))s per % (EMA), est from \(Int(anchorPercent))%", level: .info)
    }
    
    private func updateCountdownDisplay() {
        guard !isCharging else { return }
        updateTimeDisplay()
    }
    
    private func updateTimeDisplay() {
        guard !isCharging else {
            batteryTimeRemaining = ""
            return
        }
        guard !isCalculating, let anchorDate else {
            batteryTimeRemaining = "Calculating..."
            return
        }
        guard emaTimePerPercent > 0 else {
            batteryTimeRemaining = "Calculating..."
            return
        }

    // Compute estimate regardless of UI gating, then apply gating to UI only
        let confidenceThreshold = dynamicConfidenceThreshold()
        let effectiveTPP = emaTimePerPercent

        // Update virtual percent based on elapsed time
        let elapsed = Date().timeIntervalSince(anchorDate)
        let consumedPercent = elapsed / effectiveTPP
        virtualBatteryPercent = max(0.0, anchorPercent - consumedPercent)

        // Compute estimated actual battery percent (continuous)
        let estimatedActual = max(0.0, virtualBatteryPercent)
        // Publish actual estimate when we meet the same gating threshold and at least one bucket drop, and not charging
        if !isCharging && observedBucketDrops >= 1 && batteryEstimateConfidence >= confidenceThreshold {
            estimatedActualBatteryPercent = Int(estimatedActual.rounded())
        } else {
            estimatedActualBatteryPercent = nil
        }

        // Ensure virtual does not go below zero
        let secondsRemaining = max(0, estimatedActual * effectiveTPP)
        // Throttled snapshot logging
        let now = Date()
        let minutesRemaining = Int(round(secondsRemaining / 60.0))
        var shouldLogSnapshot = false
        if let lastDate = lastSnapshotLogDate {
            if now.timeIntervalSince(lastDate) >= snapshotLogInterval { shouldLogSnapshot = true }
        } else {
            shouldLogSnapshot = true
        }
        // Significant change triggers
        if let lastV = lastSnapshotVirtual, abs(virtualBatteryPercent - lastV) >= 1.0 { shouldLogSnapshot = true }
        if let lastM = lastSnapshotMinutesRemaining, abs(minutesRemaining - lastM) >= 2 { shouldLogSnapshot = true }
        if let lastD = lastSnapshotDrops, lastD != observedBucketDrops { shouldLogSnapshot = true }
        if shouldLogSnapshot {
            Logger.shared.battery(String(format: "Estimate snapshot: anchor=%.1f%%, virtual=%.1f%%, tpp=%.1fs, remain=%.0fs (%.0fm), conf=%.2f, drops=%d, mode=%@",
                                         anchorPercent, virtualBatteryPercent, effectiveTPP, secondsRemaining, secondsRemaining/60.0, batteryEstimateConfidence, observedBucketDrops, currentModeKey), level: .debug)
            lastSnapshotLogDate = now
            lastSnapshotVirtual = virtualBatteryPercent
            lastSnapshotMinutesRemaining = minutesRemaining
            lastSnapshotDrops = observedBucketDrops
        }

        let isVisible = batteryEstimateConfidence >= confidenceThreshold
        if isVisible {
            batteryTimeRemaining = secondsRemaining > 0 ? formatTimeRemaining(secondsRemaining) : "< 1m left"
        } else {
            batteryTimeRemaining = "Calculating..."
        }
        // Throttle gating logs: only on visibility change or minute change
        if lastUIGatingVisible != isVisible || lastUIGatingMinutes != minutesRemaining {
            if isVisible {
                Logger.shared.battery(String(format: "UI gating: visible (threshold=%.2f, conf=%.2f), time=%@", confidenceThreshold, batteryEstimateConfidence, batteryTimeRemaining), level: .debug)
            } else {
                Logger.shared.battery(String(format: "UI gating: hidden (threshold=%.2f, conf=%.2f)", confidenceThreshold, batteryEstimateConfidence), level: .debug)
            }
            lastUIGatingVisible = isVisible
            lastUIGatingMinutes = minutesRemaining
        }
    }

    private func logRoundingBucket() {
        // iOS shows percent in 5% buckets; derive the current bucket and log
        let official = batteryPercentage
        let lower = max(((official / 5) * 5) - 2, 0)
        let upper = min(((official / 5) * 5) + 2, 100)
        Logger.shared.battery("Rounding bucket for official \(official)% ≈ [\(lower)-\(upper)]%", level: .debug)
        if virtualBatteryPercent > 0 {
            Logger.shared.battery(String(format: "Virtual=%.1f%% within bucket=%@", virtualBatteryPercent, (virtualBatteryPercent >= Double(lower) && virtualBatteryPercent <= Double(upper)) ? "YES" : "NO"), level: .debug)
        }
    }

    private func dynamicConfidenceThreshold() -> Double {
        // Baseline threshold
        var threshold = 0.3
        // Allow estimate after first bucket drop
        if observedBucketDrops >= 1 {
            threshold = 0.3 // keep baseline; do not raise further
        } else {
            // Before first drop, be a bit stricter in heavy modes
            if cameraOn || webrtcConnected || mlActiveHint { threshold = max(threshold, 0.7) }
            threshold = max(threshold, 0.75)
        }
        // Avoid log spam: only log when mode, drops, or value changed
        let snapshot = (mode: currentModeKey, drops: observedBucketDrops, value: threshold)
        if lastThresholdLog?.mode != snapshot.mode || lastThresholdLog?.drops != snapshot.drops || lastThresholdLog?.value != snapshot.value {
            lastThresholdLog = snapshot
            Logger.shared.battery(String(format: "Confidence threshold=%.2f (mode=%@, drops=%d)", threshold, currentModeKey, observedBucketDrops), level: .debug)
        }
        return threshold
    }

    // Public hook for CPU usage updates from DebugTab
    func updateSystemCPUUsage(_ percent: Double) {
        systemCPUPercent = max(0, min(percent, 100))
    }
    
    private func formatTimeRemaining(_ seconds: TimeInterval) -> String {
        guard seconds > 0 else { return "< 1m left" }
        
        let hours = Int(seconds / 3600)
        let minutes = Int((seconds.truncatingRemainder(dividingBy: 3600)) / 60)
        
        if hours > 0 {
            return "\(hours)h \(minutes)m left"
        } else if minutes > 0 {
            return "\(minutes)m left"
        } else {
            return "< 1m left"
        }
    }
}

