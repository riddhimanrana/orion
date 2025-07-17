import SwiftUI
import Combine

// MARK: - Main Debug View
struct DebugTabView: View {
    @EnvironmentObject var wsManager: WebSocketManager
    @EnvironmentObject var appState: AppStateManager
    @EnvironmentObject var cameraManager: CameraManager

    // State
    @State private var frameAnalysisLogs: [FrameAnalysisLog] = []
    @State private var analysisLogCancellable: AnyCancellable? = nil
    @State private var showingDetailFor: FrameAnalysisLog?
    @State private var showingSettingsSheet = false

    var body: some View {
        NavigationView {
            Form {
                Section(header: Label("Connection", systemImage: "wifi")) {
                    webSocketStatusSection
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
            DebugSettingsView().environmentObject(wsManager)
        }
        .onAppear(perform: setupLogSubscribers)
        .onDisappear(perform: cancelLogSubscribers)
    }

    // MARK: - Subviews
    private var webSocketStatusSection: some View {
        VStack(spacing: 8) {
            ConnectionStatusRow(label: "Status", value: wsManager.status.description, color: connectionStatusColor)
            ConnectionStatusRow(label: "Server", value: "\(SettingsManager.shared.serverHost):\(SettingsManager.shared.serverPort)", color: .secondary)
            ConnectionStatusRow(label: "Mode", value: SettingsManager.shared.processingMode.capitalized, color: .secondary)
            ConnectionStatusRow(label: "Server Queue", value: "\(wsManager.serverQueueSize)", color: .secondary)
        }
    }

    private var systemMetricsSection: some View {
        VStack(spacing: 8) {
            // Note: CPU/GPU/ANE metrics are non-trivial to get and require more than SwiftUI.
            // These are placeholders to illustrate the UI.
            MetricRow(label: "CPU Usage", value: "65%", target: "< 80%")
            MetricRow(label: "GPU Usage", value: "45%", target: "< 60%")
            MetricRow(label: "ANE Usage", value: "80%", target: "N/A")
            MetricRow(label: "Memory", value: String(format: "%.0f MB", appState.performanceMetrics.memoryUsage), target: "< 500 MB")
            MetricRow(label: "Battery", value: "\(Int(appState.performanceMetrics.batteryLevel * 100))%", target: "> 20%")
        }
    }
    
    private var analysisLogSection: some View {
        List {
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
                }
            }
        }
    }
    
    private func vlmMetricsView(_ result: FastVLMModel.VLMResult) -> some View {
        HStack(spacing: 16) {
            VStack(alignment: .leading) {
                Text("TTFT").font(.caption2).foregroundColor(.secondary)
                Text(String(format: "%.0f ms", result.timeToFirstToken * 1000))
                    .font(.caption.bold())
            }
            VStack(alignment: .leading) {
                Text("Tok/s").font(.caption2).foregroundColor(.secondary)
                Text(String(format: "%.1f", result.tokensPerSecond))
                    .font(.caption.bold())
            }
            VStack(alignment: .leading) {
                Text("Total Time").font(.caption2).foregroundColor(.secondary)
                Text(String(format: "%.2f s", result.totalGenerationTime))
                    .font(.caption.bold())
            }
        }
    }

    // MARK: - Helper Properties & Methods
    private var connectionStatusColor: Color {
        switch wsManager.status {
        case .connected: .green
        case .connecting: .yellow
        case .disconnected: .red
        }
    }

    private func clearAllLogs() {
        frameAnalysisLogs.removeAll()
    }

    private func setupLogSubscribers() {
        // Assumes CameraManager will publish FrameAnalysisLog entries
        analysisLogCancellable = cameraManager.frameAnalysisLogPublisher
            .receive(on: DispatchQueue.main)
            .sink { logEntry in
                self.frameAnalysisLogs.append(logEntry)
                if self.frameAnalysisLogs.count > 50 { // Keep log size manageable
                    self.frameAnalysisLogs.removeFirst()
                }
            }
    }

    private func cancelLogSubscribers() {
        analysisLogCancellable?.cancel()
        analysisLogCancellable = nil
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
                    InfoRow(label: "Frame ID", value: log.frameId)
                    InfoRow(label: "Timestamp", value: log.formattedTimestamp)
                }
                
                Section("YOLOv11n Detections (\(log.yoloDetections.count))") {
                    if log.yoloDetections.isEmpty {
                        Text("No objects detected.")
                    } else {
                        ForEach(log.yoloDetections, id: \.self) { det in
                            Text("• \(det.label) (Conf: \(String(format: "%.0f", det.confidence * 100))%)")
                        }
                    }
                    InfoRow(label: "Processing Time", value: String(format: "%.1f ms", log.yoloProcessingTime))
                }
                
                Section("FastVLM Analysis") {
                    if let result = log.vlmResult {
                        Text(result.description).padding(.vertical, 4)
                        InfoRow(label: "TTFT", value: String(format: "%.0f ms", result.timeToFirstToken * 1000))
                        InfoRow(label: "Tokens/sec", value: String(format: "%.1f", result.tokensPerSecond))
                        InfoRow(label: "Total Time", value: String(format: "%.2f s", result.totalGenerationTime))
                        DisclosureGroup("VLM Prompt") {
                            Text(log.vlmPrompt)
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .padding(.top, 4)
                        }
                    } else {
                        Text("No VLM result.")
                    }
                }
                
                Section("System Metrics") {
                    InfoRow(label: "CPU / GPU / ANE", value: "\(Int(log.cpuUsage*100))% / \(Int(log.gpuUsage*100))% / \(Int(log.aneUsage*100))%")
                    InfoRow(label: "Battery Level", value: "\(Int(log.batteryLevel * 100))%")
                }
            }
            .navigationTitle("Frame Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

struct InfoRow: View {
    let label: String
    let value: String
    
    var body: some View {
        HStack {
            Text(label).foregroundColor(.secondary)
            Spacer()
            Text(value).fontWeight(.medium)
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
    @EnvironmentObject var wsManager: WebSocketManager
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
        let appState = AppStateManager()
        let cameraManager = CameraManager()
        let wsManager = WebSocketManager()

        // Setup mock data for preview
        appState.performanceMetrics = PerformanceMetrics(fps: 29.5, memoryUsage: 180.3, batteryLevel: 0.75, temperature: 0)
        cameraManager.frameAnalysisLogPublisher.send(FrameAnalysisLog.placeholder())
        cameraManager.frameAnalysisLogPublisher.send(FrameAnalysisLog.placeholder())

        return DebugTabView()
            .environmentObject(appState)
            .environmentObject(cameraManager)
            .environmentObject(wsManager)
    }
}
