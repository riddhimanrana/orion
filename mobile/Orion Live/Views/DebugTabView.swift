//
//  DebugTabView.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Debug and logging tab for live system metrics and analysis logs in Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//
import SwiftUI
import Combine
import WebRTC
import UIKit

// MARK: - Main Debug View
struct DebugTabView: View {
    @EnvironmentObject var appState: AppStateManager
    @EnvironmentObject var cameraManager: CameraManager
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var signalingClient: SignalingClient
    @EnvironmentObject var deviceManager: DeviceManager
    @EnvironmentObject var batteryMonitoringManager: BatteryMonitoringManager

    // State
    @State private var frameAnalysisLogs: [FrameAnalysisLog] = []
    @State private var analysisLogCancellable: AnyCancellable? = nil
    @State private var showingDetailFor: FrameAnalysisLog?
    @State private var pingTime: String = "N/A"
    @State private var cancellables = Set<AnyCancellable>()
    @State private var showLogViewer = false
    @StateObject private var cpuMonitor = CPUUsageMonitor()

    var body: some View {
        NavigationStack {
            Form {
                Section(header: Label("P2P Connection", systemImage: "network")) {
                    p2pConnectionSection
                }

                Section(header: Label("Signaling", systemImage: "wifi")) {
                    signalingStatusSection
                }

                Section(header: Label("Packets & Relay", systemImage: "point.3.connected.trianglepath.dotted")) {
                    signalTrafficSection
                }

                Section(header: Label("Live System Metrics", systemImage: "speedometer")) {
                    systemMetricsSection
                }

                Section(header: Label("Model Route", systemImage: "server.rack")) {
                    modelRouteSection
                }
                
                Section(header: Label("Pipeline Log", systemImage: "memorychip")) {
                    analysisLogSection
                }
                
                Section(header: Label("Logs", systemImage: "terminal")) {
                    Button {
                        showLogViewer = true
                    } label: {
                        HStack {
                            Image(systemName: "doc.text.magnifyingglass")
                            Text("Open Real-time Logs")
                            Spacer()
                            Image(systemName: "chevron.right")
                                .foregroundColor(.secondary)
                        }
                    }
                }
            }
            .navigationTitle("Debug")
            .navigationBarTitleDisplayMode(.automatic)
        }
        .sheet(item: $showingDetailFor) { log in
            FrameDetailView(log: log)
        }
        .sheet(isPresented: $showLogViewer) {
            RealtimeLogViewer()
        }
        .onAppear(perform: setupSubscribers)
        .onDisappear(perform: cancelSubscribers)
        .onAppear { cpuMonitor.start() }
        .onDisappear { cpuMonitor.stop() }
        .onReceive(cpuMonitor.$systemCPUPercent) { pct in
            batteryMonitoringManager.updateSystemCPUUsage(pct)
        }
        .onChange(of: cameraManager.isStreaming) { _, newValue in
            batteryMonitoringManager.updateActivity(cameraOn: newValue)
        }
        .onChange(of: webRTCManager.connectionState) { _, newState in
            let connected = (newState == .connected || newState == .completed)
            batteryMonitoringManager.updateActivity(webrtcConnected: connected)
        }
    }

    // MARK: - Subviews
    private var p2pConnectionSection: some View {
        VStack(spacing: 8) {
            ConnectionStatusRow(label: "WebRTC Status", value: connectionStateDescription, color: webRTCStatusColor)
            ConnectionStatusRow(label: "Ping (RTT)", value: pingTime, color: .secondary)
            ConnectionStatusRow(label: "DataChannel", value: dataChannelStateText, color: .secondary)
            ConnectionStatusRow(label: "ICE Mode", value: webRTCManager.iceStatus.usingTURN ? "TURN (relay)" : "STUN/Direct", color: webRTCManager.iceStatus.usingTURN ? .orange : .secondary)
            ConnectionStatusRow(label: "ICE Types", value: "L: \(webRTCManager.iceStatus.localType) • R: \(webRTCManager.iceStatus.remoteType) • \(webRTCManager.iceStatus.transport)", color: .secondary)
            if let ttl = webRTCManager.ephemeralTTLRemaining {
                ConnectionStatusRow(label: "ICE Creds", value: "Ephemeral (\(ttl)s)", color: ttl > 30 ? .green : .orange)
            }
            if let usage = webRTCManager.iceUsage {
                ConnectionStatusRow(label: "ICE Requests", value: "\(usage.countInWindow)/\(usage.maxInWindow) (\(usage.windowRemainingSec)s left)", color: .secondary)
            }
            ConnectionStatusRow(label: "Peer", value: deviceManager.activePairedDevice?.name ?? "N/A", color: .secondary)
            
            // Show connection failure guidance when appropriate
            if let errorMessage = connectionErrorMessage {
                connectionErrorView(message: errorMessage)
            }
            
            HStack {
                Button("Connect") {
                    Task {
                        await webRTCManager.connect()
                    }
                }
                .buttonStyle(.bordered)
                .disabled(webRTCManager.connectionState == .connected || webRTCManager.connectionState == .checking)

                Spacer()

                Button("Ping") { webRTCManager.sendPingP2P() }
                .buttonStyle(.bordered)
                .disabled(webRTCManager.dataChannelState != .open)
            }
        }
    }
    
    private var signalingStatusSection: some View {
        VStack(spacing: 8) {
            ConnectionStatusRow(label: "Signaling Status", value: signalingClient.connectionState.description, color: signalingStatusColor)
            ConnectionStatusRow(label: "Server", value: "signal.orionlive.ai", color: .secondary)
            if let health = signalingClient.lastSignalHealth {
                ConnectionStatusRow(label: "Signal API", value: health.status, color: .green)
                ConnectionStatusRow(label: "Rooms", value: health.roomsActive.map(String.init) ?? "-", color: .secondary)
                ConnectionStatusRow(label: "Clients", value: health.clientsConnected.map(String.init) ?? "-", color: .secondary)
            }
        }
    }

    private var signalTrafficSection: some View {
        VStack(spacing: 8) {
            ConnectionStatusRow(label: "Packets Sent", value: "\(signalingClient.packetsSent)", color: .blue)
            ConnectionStatusRow(label: "Packets Received", value: "\(signalingClient.packetsReceived)", color: .green)
            ConnectionStatusRow(label: "Bytes Sent", value: ByteCountFormatter.string(fromByteCount: Int64(signalingClient.packetBytesSent), countStyle: .binary), color: .blue)
            ConnectionStatusRow(label: "Bytes Received", value: ByteCountFormatter.string(fromByteCount: Int64(signalingClient.packetBytesReceived), countStyle: .binary), color: .green)
            ConnectionStatusRow(label: "Last Sent", value: signalingClient.lastPacketTypeSent ?? "-", color: .secondary)
            ConnectionStatusRow(label: "Last Received", value: signalingClient.lastPacketTypeReceived ?? "-", color: .secondary)
            if let usage = signalingClient.lastSignalAccountUsage {
                Divider()
                ConnectionStatusRow(label: "Relay Packets", value: "\(usage.usage.packetsRelayed)", color: .secondary)
                ConnectionStatusRow(label: "Relay Bytes", value: ByteCountFormatter.string(fromByteCount: Int64(usage.usage.bytesRelayed), countStyle: .binary), color: .secondary)
                ConnectionStatusRow(label: "ICE Issued", value: "\(usage.usage.iceIssued)", color: .secondary)
                ConnectionStatusRow(label: "Est. Cost", value: String(format: "$%.5f", usage.estimatedCostUsd.totalUsd), color: .secondary)
            }
        }
    }
    
    private var systemMetricsSection: some View {
        VStack(spacing: 12) {
            // Memory with progress bar visualization
            MemoryUsageView(memoryUsage: appState.performanceMetrics.memoryUsage)

            // CPU usage (overall system)
            CPUUsageView(systemCPU: cpuMonitor.systemCPUPercent)

            // Battery with improved time remaining estimate using background manager
            BatteryUsageView(
                percentage: batteryMonitoringManager.batteryPercentage,
                isCharging: batteryMonitoringManager.isCharging,
                timeRemaining: batteryMonitoringManager.batteryTimeRemaining,
                estimatedActualPercent: batteryMonitoringManager.estimatedActualBatteryPercent,
                confidence: batteryMonitoringManager.estimatedActualBatteryPercent != nil ? batteryMonitoringManager.batteryEstimateConfidence : nil
            )
            
            // Thermal state monitoring
            ThermalStateView(
                thermalState: batteryMonitoringManager.thermalState,
                thermalStateDescription: batteryMonitoringManager.thermalStateDescription
            )
        }
    }

    private var modelRouteSection: some View {
        VStack(spacing: 8) {
            ConnectionStatusRow(label: "Processing", value: "Server", color: .green)
            ConnectionStatusRow(label: "iOS Local ML", value: "Not bundled", color: .secondary)
            ConnectionStatusRow(label: "Reasoning", value: "Gemma on macOS server", color: .secondary)
            ConnectionStatusRow(label: "3D Depth", value: "Depth Anything 3", color: .secondary)
            ConnectionStatusRow(label: "Tracking", value: "Server persistent memory", color: .secondary)
            ConnectionStatusRow(label: "Server Host", value: "\(SettingsManager.shared.serverHost):\(SettingsManager.shared.serverPort)", color: .secondary)
        }
    }
    
    private var analysisLogSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            if frameAnalysisLogs.isEmpty {
                Text("No analysis logs yet...")
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
            } else {
                ForEach(frameAnalysisLogs.reversed()) { log in
                    DisclosureGroup {
                        VStack(alignment: .leading, spacing: 10) {
                            if let vlmResult = log.vlmResult {
                                Text(vlmResult.description)
                                    .font(.caption)
                                    .foregroundColor(.primary)
                                vlmMetricsView(vlmResult)
                            } else {
                                Text("VLM analysis not performed or failed.")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            Button(action: { showingDetailFor = log }) {
                                Text("Show Full Details")
                                    .font(.caption.bold())
                            }
                            .padding(.top, 4)
                        }
                    } label: {
                        HStack {
                            Image(systemName: "brain.head.profile")
                                .foregroundColor(.purple)
                            Text("Frame \(log.frameId.prefix(6))")
                                .font(.headline)
                            Spacer()
                            Text(log.formattedTimestamp)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    Divider().opacity(0.1)
                }
            }
        }
    }
    
    private func vlmMetricsView(_ result: VLMAnalysisResult) -> some View {
        HStack(spacing: 16) {
            VStack(alignment: .leading) {
                Text("TTFT").font(.caption2).foregroundColor(.secondary)
                Text(String(format: "%.0f ms", result.timeToFirstToken * 1000)).font(.caption.bold())
            }
            VStack(alignment: .leading) {
                Text("Tok/s").font(.caption2).foregroundColor(.secondary)
                Text(String(format: "%.1f", result.tokensPerSecond)).font(.caption.bold())
            }
            VStack(alignment: .leading) {
                Text("Total Time").font(.caption2).foregroundColor(.secondary)
                Text(String(format: "%.2f s", result.totalGenerationTime)).font(.caption.bold())
            }
        }
    }

    // MARK: - Helper Properties & Methods
    private var connectionStateDescription: String {
        switch webRTCManager.connectionState {
        case .new: return "New"
        case .checking: return "Checking"
        case .connected: return "Connected"
        case .completed: return "Completed"
        case .failed: return "Failed"
        case .disconnected: return "Disconnected"
        case .closed: return "Closed"
        case .count: return "Count"
        @unknown default: return "Unknown"
        }
    }

    private var dataChannelStateText: String {
        switch webRTCManager.dataChannelState {
        case .connecting: return "connecting"
        case .open: return "open"
        case .closing: return "closing"
        case .closed: return "closed"
        @unknown default: return "unknown"
        }
    }
    
    // Detect and provide helpful error messages for connection failures
    private var connectionErrorMessage: String? {
        // Only show connection issues if there is no active paired device or if signaling is not connected
        if deviceManager.activePairedDevice == nil {
            return "No paired Mac device found. You need to pair with a Mac first to establish WebRTC connection."
        }
        if signalingClient.connectionState != .connected {
            return "Signaling server not connected. Check your internet connection and ensure the Mac is online."
        }
        // If both paired device and signaling are present, do not show error, regardless of WebRTC state
        return nil
    }
    
    // Show a nicely styled error message with guidance
    private func connectionErrorView(message: String) -> some View {
        VStack(spacing: 12) {
            HStack {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundColor(.orange)
                Text("Connection Issue")
                    .font(.subheadline.weight(.medium))
                    .foregroundColor(.orange)
                Spacer()
            }
            
            Text(message)
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.leading)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            // Show pairing guidance if no paired device
            if deviceManager.activePairedDevice == nil {
                pairingGuidanceView
            }
        }
        .padding(12)
        .background(Color(.secondarySystemBackground))
        .cornerRadius(8)
    }
    
    private var pairingGuidanceView: some View {
        VStack(spacing: 8) {
            HStack {
                Image(systemName: "arrow.right")
                    .foregroundColor(.blue)
                Text("How to pair with your Mac:")
                    .font(.caption.weight(.medium))
                    .foregroundColor(.blue)
                Spacer()
            }
            
            VStack(alignment: .leading, spacing: 4) {
                Text("1. Install Orion Live on your Mac")
                Text("2. Go to Settings → Device Pairing")
                Text("3. Generate a pairing code and enter it here")
            }
            .font(.caption)
            .foregroundColor(.secondary)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
    
    private var signalingStatusColor: Color {
        switch signalingClient.connectionState {
        case .connected: .green
        case .connecting: .yellow
        case .disconnected: .red
        }
    }
    
    private var webRTCStatusColor: Color {
        switch webRTCManager.connectionState {
        case .connected, .completed: .green
        case .checking: .yellow
        case .disconnected, .failed, .closed: .red
        default: .gray
        }
    }

    private func setupSubscribers() {
        // Subscribe to frame analysis logs
        analysisLogCancellable = cameraManager.frameAnalysisLogPublisher
            .receive(on: DispatchQueue.main)
            .sink { logEntry in
                self.frameAnalysisLogs.append(logEntry)
                if self.frameAnalysisLogs.count > 50 { self.frameAnalysisLogs.removeFirst() }
            }
        
        // Subscribe to ping updates
        webRTCManager.$lastPingRTT
            .receive(on: DispatchQueue.main)
            .sink { rtt in
                if let rtt = rtt {
                    self.pingTime = "\(String(format: "%.1f", rtt * 1000)) ms"
                } else {
                    self.pingTime = "N/A"
                }
            }
            .store(in: &cancellables)
    }

    private func cancelSubscribers() {
        analysisLogCancellable?.cancel()
        analysisLogCancellable = nil
        cancellables.forEach { $0.cancel() }
        cancellables.removeAll()
    }
}

// MARK: - Supporting Views
struct FrameDetailView: View {
    let log: FrameAnalysisLog
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("Overall") {
                    InfoRow(icon: "info.circle", label: "Frame ID", value: log.frameId)
                    InfoRow(icon: "calendar", label: "Timestamp", value: log.formattedTimestamp)
                }
                
                Section("Server Detections (\(log.yoloDetections.count))") {
                    if log.yoloDetections.isEmpty {
                        Text("No objects detected.")
                    } else {
                        ForEach(log.yoloDetections, id: \.self) { det in
                            Text("• \(det.label) (Conf: \(String(format: "%.0f", det.confidence * 100))%)")
                        }
                    }
                    InfoRow(icon: "timer", label: "Processing Time", value: String(format: "%.1f ms", log.yoloProcessingTime))
                }
                
                Section("Server Visual Analysis") {
                    if let result = log.vlmResult {
                        Text(result.description).padding(.vertical, 4)
                        InfoRow(icon: "clock", label: "TTFT", value: String(format: "%.0f ms", result.timeToFirstToken * 1000))
                        InfoRow(icon: "speedometer", label: "Tokens/sec", value: String(format: "%.1f", result.tokensPerSecond))
                        InfoRow(icon: "timer", label: "Total Time", value: String(format: "%.2f s", result.totalGenerationTime))
                        DisclosureGroup("VLM Prompt") {
                            Text(log.vlmPrompt).font(.caption).foregroundColor(.secondary).padding(.top, 4)
                        }
                    } else {
                        Text("No VLM result.")
                    }
                }
                
                Section("System Metrics") {
                    InfoRow(icon: "cpu", label: "CPU / GPU / ANE", value: "\(Int(log.cpuUsage*100))% / \(Int(log.gpuUsage*100))% / \(Int(log.aneUsage*100))%")
                    InfoRow(icon: "battery.100", label: "Battery Level", value: "\(Int(log.batteryLevel * 100))%")
                }
            }
            .navigationTitle("Frame Details")
            .toolbarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

struct ConnectionStatusRow: View {
    let label: String, value: String, color: Color
    var body: some View {
        HStack {
            Text(label).font(.subheadline)
            Spacer()
            Text(value).font(.subheadline.weight(.medium)).foregroundColor(color)
        }
    }
}

struct MemoryUsageView: View {
    let memoryUsage: Double
    
    private var memoryUsageMB: Double {
        memoryUsage
    }
    
    private var isModelsLoaded: Bool {
        // Consider models loaded if memory usage is at or above the threshold
        memoryUsage >= 200 // MB - threshold between baseline (50-80MB) and loaded state (1GB+)
    }
    
    private var expectedRange: String {
        isModelsLoaded ? "1.0-1.2 GB expected" : "20-80 MB expected"
    }
    
    private var progressValue: Double {
        if isModelsLoaded {
            // Scale for loaded state: 200MB to 1200MB range
            let scaledValue = (memoryUsage - 200) / (1200 - 200)
            return min(max(scaledValue, 0), 1)
        } else {
            // Scale for baseline state: 0MB to 200MB range  
            let scaledValue = memoryUsage / 200
            return min(max(scaledValue, 0), 1)
        }
    }
    
    private var progressColor: Color {
        if isModelsLoaded {
            return memoryUsage > 1200 ? .red : .blue
        } else {
            return memoryUsage > 100 ? .orange : .green
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Memory")
                    .font(.subheadline)
                Spacer()
                Text(String(format: "%.1f MB", memoryUsageMB))
                    .font(.subheadline.weight(.medium))
            }
            
            VStack(alignment: .leading, spacing: 4) {
                ProgressView(value: progressValue)
                    .progressViewStyle(LinearProgressViewStyle(tint: progressColor))
                    .frame(height: 6)
                
                Text(expectedRange)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }
}

struct MetricRow: View {
    let label: String, value: String
    let target: String?
    
    init(label: String, value: String, target: String? = nil) {
        self.label = label
        self.value = value
        self.target = target
    }
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(label).font(.subheadline)
                if let target = target, !target.isEmpty { 
                    Text("Target: \(target)").font(.caption).foregroundColor(.secondary) 
                }
            }
            Spacer()
            Text(value).font(.subheadline.weight(.medium))
        }
    }
}

struct CPUUsageView: View {
    let systemCPU: Double
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("CPU (Overall)")
                    .font(.subheadline)
                Spacer()
                Text(String(format: "%.0f%%", systemCPU))
                    .font(.subheadline.weight(.medium))
            }
            
            ProgressView(value: min(max(systemCPU/100.0, 0), 1))
                .progressViewStyle(LinearProgressViewStyle(tint: .blue))
        }
    }
}

// MARK: - Previews
struct DebugTabView_Previews: PreviewProvider {
    static var previews: some View {
        // Mock all necessary managers for the preview
        let appState = AppStateManager()
        let cameraManager = CameraManager()
        let authManager = AuthManager()
        let deviceManager = DeviceManager(supabase: authManager.supabase)
        let apiService = APIService(supabase: authManager.supabase)
        let signalingClient = SignalingClient(apiService: apiService, deviceManager: deviceManager)
        let webRTCManager = WebRTCManager(signalingClient: signalingClient)
        let batteryMonitoringManager = BatteryMonitoringManager()

        // Setup mock data for preview
        appState.performanceMetrics = PerformanceMetrics(fps: 29.5, memoryUsage: 180.3, batteryLevel: 0.75, temperature: 0)
        cameraManager.frameAnalysisLogPublisher.send(FrameAnalysisLog.placeholder())

        return DebugTabView()
            .environmentObject(appState)
            .environmentObject(cameraManager)
            .environmentObject(webRTCManager)
            .environmentObject(signalingClient)
            .environmentObject(deviceManager)
            .environmentObject(batteryMonitoringManager)
    }
}

struct BatteryUsageView: View {
    let percentage: Int
    let isCharging: Bool
    let timeRemaining: String
    var estimatedActualPercent: Int? = nil
    var confidence: Double? = nil

    private var rightText: String {
        // Treat "Calculating..." as not ready for display
        let timeText = (timeRemaining.isEmpty || timeRemaining == "Calculating...") ? nil : timeRemaining
        // If charging, never show estimate
        if isCharging {
            if let t = timeText { return "\(percentage)% • \(t)" }
            return "\(percentage)%"
        }
        // When estimate is available, promote it to the main value without approximation marker
        if let est = estimatedActualPercent {
            if let t = timeText { return "\(est)% • \(t)" }
            return "\(est)%"
        }
        if let t = timeText { return "\(percentage)% • \(t)" }
        return "\(percentage)%"
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Battery")
                    .font(.subheadline)
                
                if isCharging {
                    Image(systemName: "bolt.fill")
                        .foregroundColor(.green)
                        .font(.caption)
                }
                
                Spacer()
                
                Text(rightText)
                    .font(.subheadline.weight(.medium))
            }
            
            Text("Battery percentage may be slightly inaccurate due to iOS Battery API limitations")
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }
}

struct ThermalStateView: View {
    let thermalState: ProcessInfo.ThermalState
    let thermalStateDescription: String
    
    private var thermalColor: Color {
        switch thermalState {
        case .nominal:
            return .green
        case .fair:
            return .yellow
        case .serious:
            return .orange
        case .critical:
            return .red
        @unknown default:
            return .gray
        }
    }
    
    private var thermalIcon: String {
        switch thermalState {
        case .nominal:
            return "thermometer.low"
        case .fair:
            return "thermometer.medium"
        case .serious:
            return "thermometer.high"
        case .critical:
            return "thermometer.high"
        @unknown default:
            return "thermometer"
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Thermal State")
                    .font(.subheadline)
                
                Spacer()
                
                HStack(spacing: 4) {
                    Image(systemName: thermalIcon)
                        .foregroundColor(thermalColor)
                        .font(.caption)
                    
                    Text(thermalStateDescription)
                        .font(.subheadline.weight(.medium))
                        .foregroundColor(thermalColor)
                }
            }
            
//            Text("Device thermal state is monitored in real-time using iOS ProcessInfo API")
//                .font(.caption)
//                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Real-time Log Viewer
struct RealtimeLogViewer: View {
    @Environment(\.dismiss) var dismiss
    @State private var logs: [AppLogEntry] = Logger.shared.recentLogs()
    @State private var filterCategory: AppLogCategory? = nil
    @State private var filterLevel: LogLevel? = nil
    @State private var searchText: String = ""
    @State private var isPaused = false
    @State private var cancellable: AnyCancellable?
    
    private var filteredLogs: [AppLogEntry] {
        logs.filter { entry in
            let categoryOK = filterCategory == nil || entry.category == filterCategory
            let levelOK = filterLevel == nil || entry.level == filterLevel
            let searchOK = searchText.isEmpty || entry.message.localizedCaseInsensitiveContains(searchText)
            return categoryOK && levelOK && searchOK
        }.reversed() // Latest first
    }
    
    var body: some View {
        NavigationStack {
            ZStack {
                // Enhanced liquid glass background effect
                Color.clear
                    .background(.ultraThinMaterial)
                    .overlay(
                        Rectangle()
                            .fill(Color.clear)
                    )
                    .ignoresSafeArea()
                
                VStack(spacing: 0) {
                    toolbar
                    Divider()
                    logList
                }
            }
            .navigationTitle("Live Logs")
            .toolbarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .onAppear(perform: subscribe)
        .onDisappear { cancellable?.cancel() }
    }
    
    private var toolbar: some View {
        VStack(spacing: 8) {
            HStack(spacing: 8) {
                Menu {
                    Button("All Categories") { filterCategory = nil }
                    Divider()
                    ForEach(AppLogCategory.allCases, id: \.self) { cat in
                        Button(cat.rawValue) { filterCategory = cat }
                    }
                } label: {
                    labelChip(title: filterCategory?.rawValue ?? "All Categories", systemImage: "line.3.horizontal.decrease.circle")
                }
                
                Menu {
                    Button("All Levels") { filterLevel = nil }
                    Divider()
                    ForEach([LogLevel.debug, .info, .warning, .error], id: \.self) { lvl in
                        Button(lvl.rawValue) { filterLevel = lvl }
                    }
                } label: {
                    labelChip(title: filterLevel?.rawValue ?? "All Levels", systemImage: "exclamationmark.bubble")
                }
                
                Spacer()
                
                Button(action: { isPaused.toggle() }) {
                    Image(systemName: isPaused ? "play.fill" : "pause.fill")
                        .font(.system(size: 16))
                        .foregroundColor(.primary)
                        .frame(width: 32, height: 32)
                        .background(.ultraThinMaterial, in: Circle())
                }
                
                Button(action: { logs.removeAll() }) {
                    Image(systemName: "trash")
                        .font(.system(size: 16))
                        .foregroundColor(.primary)
                        .frame(width: 32, height: 32)
                        .background(.ultraThinMaterial, in: Circle())
                }
            }
            .padding(.horizontal)
            
            HStack {
                Image(systemName: "magnifyingglass").foregroundColor(.secondary)
                TextField("Search message text", text: $searchText)
                    .textFieldStyle(.plain)
                if !searchText.isEmpty {
                    Button(action: { searchText = "" }) { Image(systemName: "xmark.circle.fill").foregroundColor(.secondary) }
                }
            }
            .padding(10)
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
            .padding(.horizontal)
            .padding(.bottom, 8)
        }
        .padding(.top)
    }
    
    private var logList: some View {
        ScrollViewReader { proxy in
            List {
                ForEach(filteredLogs) { entry in
                    HStack(alignment: .top, spacing: 8) {
                        Text(entry.timeString)
                            .font(.caption2)
                            .foregroundColor(.secondary)
                            .frame(width: 80, alignment: .leading)
                        
                        VStack(alignment: .leading, spacing: 2) {
                            HStack(spacing: 6) {
                                Text(entry.level.emoji)
                                Text(entry.category.rawValue).font(.caption2).foregroundColor(.secondary)
                            }
                            Text(entry.message)
                                .font(.caption)
                                .foregroundColor(.primary)
                            if !entry.metadata.isEmpty {
                                Text(entry.metadata)
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                    .padding(.vertical, 4)
                    .listRowBackground(
                        Rectangle()
                            .fill(.ultraThinMaterial)
                            .opacity(0.3)
                    )
                }
            }
            .listStyle(.plain)
            .background(Color.clear)
        }
    }
    
    private func subscribe() {
        // Seed with recent logs and then stream new ones
        logs = Logger.shared.recentLogs()
        cancellable = Logger.shared.logPublisher
            .receive(on: DispatchQueue.main)
            .sink { entry in
                guard !isPaused else { return }
                logs.append(entry)
                if logs.count > 1000 { logs.removeFirst(logs.count - 1000) }
            }
    }
    
    private func labelChip(title: String, systemImage: String) -> some View {
        HStack(spacing: 4) {
            Image(systemName: systemImage)
            Text(title)
        }
        .font(.caption)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(.ultraThinMaterial, in: Capsule())
    }
}

// Simple blur wrapper for cross-version compatibility
struct VisualEffectBlur: UIViewRepresentable {
    let blurStyle: UIBlurEffect.Style
    func makeUIView(context: Context) -> UIVisualEffectView {
        UIVisualEffectView(effect: UIBlurEffect(style: blurStyle))
    }
    func updateUIView(_ uiView: UIVisualEffectView, context: Context) {}
}
