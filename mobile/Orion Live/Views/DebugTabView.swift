
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

// MARK: - Main Debug View
struct DebugTabView: View {
    @EnvironmentObject var appState: AppStateManager
    @EnvironmentObject var cameraManager: CameraManager
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var signalingClient: SignalingClient
    @EnvironmentObject var deviceManager: DeviceManager

    // State
    @State private var frameAnalysisLogs: [FrameAnalysisLog] = []
    @State private var analysisLogCancellable: AnyCancellable? = nil
    @State private var showingDetailFor: FrameAnalysisLog?
    @State private var showingSettingsSheet = false
    @State private var pingTime: String = "N/A"
    @State private var cancellables = Set<AnyCancellable>()

    var body: some View {
        NavigationView {
            Form {
                Section(header: Label("P2P Connection", systemImage: "network")) {
                    p2pConnectionSection
                }
                
                Section(header: Label("Signaling", systemImage: "wifi")) {
                    signalingStatusSection
                }

                Section(header: Label("Live System Metrics", systemImage: "speedometer")) {
                    systemMetricsSection
                }
                
                Section(header: Label("On-Device Analysis Log", systemImage: "memorychip")) {
                    analysisLogSection
                }
            }
            .navigationTitle("Debug")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Clear Logs", role: .destructive, action: clearAllLogs)
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { showingSettingsSheet = true }) {
                        Image(systemName: "gear")
                    }
                }
            }
        }
        .sheet(item: $showingDetailFor) { log in
            FrameDetailView(log: log)
        }
        .sheet(isPresented: $showingSettingsSheet) {
            DebugSettingsView()
        }
        .onAppear(perform: setupSubscribers)
        .onDisappear(perform: cancelSubscribers)
    }

    // MARK: - Subviews
    private var p2pConnectionSection: some View {
        VStack(spacing: 8) {
            ConnectionStatusRow(label: "WebRTC Status", value: connectionStateDescription, color: webRTCStatusColor)
            ConnectionStatusRow(label: "Ping (RTT)", value: pingTime, color: .secondary)
            ConnectionStatusRow(label: "Peer", value: deviceManager.activePairedDevice?.name ?? "N/A", color: .secondary)
            HStack {
                Button("Connect") {
                    Task {
                        await webRTCManager.connect()
                    }
                }
                .buttonStyle(.bordered)
                .disabled(webRTCManager.connectionState == .connected || webRTCManager.connectionState == .checking)
                
                Spacer()
                
                Button("Ping") {
                    webRTCManager.sendPing()
                }
                .buttonStyle(.bordered)
                .disabled(webRTCManager.connectionState != .connected)
            }
        }
    }
    
    private var signalingStatusSection: some View {
        VStack(spacing: 8) {
            ConnectionStatusRow(label: "Signaling Status", value: signalingClient.connectionState.description, color: signalingStatusColor)
            ConnectionStatusRow(label: "Server", value: "signal.orionlive.ai", color: .secondary)
        }
    }
    
    private var systemMetricsSection: some View {
        VStack(spacing: 8) {
            MetricRow(label: "CPU Usage", value: "--", target: "< 80%")
            MetricRow(label: "GPU Usage", value: "--", target: "< 60%")
            MetricRow(label: "Memory", value: String(format: "%.0f MB", appState.performanceMetrics.memoryUsage), target: "< 500 MB")
            MetricRow(label: "Battery", value: "\(Int(appState.performanceMetrics.batteryLevel * 100))%", target: "> 20%")
        }
    }
    
    private var analysisLogSection: some View {
        List {
            if frameAnalysisLogs.isEmpty {
                Text("No analysis logs yet...").foregroundColor(.secondary).frame(maxWidth: .infinity, alignment: .center)
            } else {
                ForEach(frameAnalysisLogs.reversed()) { log in
                    DisclosureGroup {
                        VStack(alignment: .leading, spacing: 10) {
                            if let vlmResult = log.vlmResult {
                                Text(vlmResult.description).font(.caption).foregroundColor(.primary)
                                vlmMetricsView(vlmResult)
                            } else {
                                Text("VLM analysis not performed or failed.").font(.caption).foregroundColor(.secondary)
                            }
                            Button(action: { showingDetailFor = log }) { Text("Show Full Details").font(.caption.bold()) }.padding(.top, 4)
                        }
                    } label: {
                        HStack {
                            Image(systemName: "brain.head.profile").foregroundColor(.purple)
                            Text("Frame \(log.frameId.prefix(6))").font(.headline)
                            Spacer()
                            Text(log.formattedTimestamp).font(.caption).foregroundColor(.secondary)
                        }
                    }
                }
            }
        }
    }
    
    private func vlmMetricsView(_ result: FastVLMModel.VLMResult) -> some View {
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

    private func clearAllLogs() {
        frameAnalysisLogs.removeAll()
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
        NavigationView {
            Form {
                Section("Overall") {
                    InfoRow(icon: "info.circle", label: "Frame ID", value: log.frameId)
                    InfoRow(icon: "calendar", label: "Timestamp", value: log.formattedTimestamp)
                }
                
                Section("YOLO11n Detections (\(log.yoloDetections.count))") {
                    if log.yoloDetections.isEmpty {
                        Text("No objects detected.")
                    } else {
                        ForEach(log.yoloDetections, id: \.self) { det in
                            Text("• \(det.label) (Conf: \(String(format: "%.0f", det.confidence * 100))%)")
                        }
                    }
                    InfoRow(icon: "timer", label: "Processing Time", value: String(format: "%.1f ms", log.yoloProcessingTime))
                }
                
                Section("FastVLM Analysis") {
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
            .navigationTitle("Frame Details").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Done") { dismiss() } } }
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

struct MetricRow: View {
    let label: String, value: String, target: String
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(label).font(.subheadline)
                if !target.isEmpty { Text("Target: \(target)").font(.caption).foregroundColor(.secondary) }
            }
            Spacer()
            Text(value).font(.subheadline.weight(.medium))
        }
    }
}

struct DebugSettingsView: View {
    @Environment(\.dismiss) var dismiss
    var body: some View {
        NavigationView {
            Form {
                Section("Logging") {
                    Toggle("Network Logs", isOn: .constant(true))
                    Toggle("Processing Logs", isOn: .constant(true))
                }
            }
            .navigationTitle("Debug Settings").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Done") { dismiss() } } }
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

        // Setup mock data for preview
        appState.performanceMetrics = PerformanceMetrics(fps: 29.5, memoryUsage: 180.3, batteryLevel: 0.75, temperature: 0)
        // Correctly publish a mock log entry
        cameraManager.frameAnalysisLogPublisher.send(FrameAnalysisLog.placeholder())

        return DebugTabView()
            .environmentObject(appState)
            .environmentObject(cameraManager)
            .environmentObject(webRTCManager)
            .environmentObject(signalingClient)
            .environmentObject(deviceManager)
    }
}
