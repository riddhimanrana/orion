import SwiftUI
import Combine

// MARK: - Data Models & Enums (Defined at top level to avoid ambiguity)

enum LogCategory: String, CaseIterable {
    case all = "All"
    case sent = "Sent"
    case received = "Received"
    case error = "Error"
}

enum NetworkLogType {
    case sent
    case received
    case error
}

struct NetworkLogEntry: Identifiable {
    let id = UUID()
    let type: NetworkLogType
    let message: String
    let timestamp: Date

    var formattedTimestamp: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss.SSS"
        return formatter.string(from: timestamp)
    }
}

struct DetectionLogEntry: Identifiable {
    let id = UUID()
    let detectionsCount: Int
    let averageConfidence: Float
    let processingTime: Double
    let timestamp: Date

    var formattedTimestamp: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"
        return formatter.string(from: timestamp)
    }
}

// MARK: - Main Debug View

struct DebugTabView: View {
    @EnvironmentObject var wsManager: WebSocketManager
    @EnvironmentObject var appState: AppStateManager
    @EnvironmentObject var cameraManager: CameraManager

    // State for UI and data tracking
    @State private var lastSentImageData: Data?
    @State private var imageTransferTime: TimeInterval? = nil
    @State private var imageTransferProgress: Double = 0.0

    @State private var networkLogs: [NetworkLogEntry] = []
    @State private var detectionLogs: [DetectionLogEntry] = []
    @State private var networkLogCancellable: AnyCancellable? = nil
    @State private var detectionLogCancellable: AnyCancellable? = nil

    @State private var showingRawJSONViewer = false
    @State private var showingSettingsSheet = false
    @State private var autoScrollEnabled = true

    @State private var selectedLogCategory: LogCategory = .all

    // Metrics
    @State private var avgSentPacketTime: Double = 0.0
    @State private var avgResponseTime: Double = 0.0
    @State private var keyframesPerSecond: Double = 0.0
    @State private var peakMemory: Double = 0.0

    private let startTime: Date = Date()
    private let logUpdateTimer = Timer.publish(every: 1.0, on: .main, in: .common).autoconnect()

    var body: some View {
        NavigationView {
            Form {
                Section(header: Label("Connection", systemImage: "wifi")) {
                    webSocketStatusSection
                }

                Section(header: Label("Mode Specifics", systemImage: "arrow.left.arrow.right.circle")) {
                    if SettingsManager.shared.processingMode == "full" {
                        imageTransferSection
                    } else {
                        onDeviceAnalysisSection
                    }
                }

                Section(header: Label("Live Metrics", systemImage: "speedometer")) {
                    processingMetricsSection
                    memorySection
                }

                Section(header: Label("Logs", systemImage: "doc.text")) {
                    networkActivitySection
                    detectionLogsSection
                }

                Section(header: Label("Tools", systemImage: "wrench.and.screwdriver")) {
                    rawDataSection
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
        .sheet(isPresented: $showingRawJSONViewer) {
            RawJSONViewer().environmentObject(wsManager)
        }
        .sheet(isPresented: $showingSettingsSheet) {
            DebugSettingsView().environmentObject(wsManager)
        }
        .onReceive(logUpdateTimer) { _ in
            updateMetrics()
        }
        .onReceive(wsManager.lastRoundTripTimePublisher) { newTime in
            if SettingsManager.shared.processingMode == "full" {
                self.imageTransferTime = newTime
                self.imageTransferProgress = newTime != nil ? 1.0 : 0.0
            }
        }
        .onReceive(cameraManager.$lastFrameImageData) { imageData in
            if SettingsManager.shared.processingMode == "full", let data = imageData {
                self.lastSentImageData = data
            }
        }
        .onAppear(perform: setupLogSubscribers)
        .onDisappear(perform: cancelLogSubscribers)
    }

    // MARK: - Subviews

    private var imageTransferSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 16) {
                VStack {
                    if let data = lastSentImageData, let uiImage = UIImage(data: data) {
                        Image(uiImage: uiImage)
                            .resizable().aspectRatio(contentMode: .fit)
                            .frame(width: 100, height: 75).cornerRadius(8)
                            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.secondary, lineWidth: 1))
                    } else {
                        Rectangle().fill(Color.secondary.opacity(0.2))
                            .frame(width: 100, height: 75).cornerRadius(8)
                            .overlay(Text("No Image").font(.caption).foregroundColor(.secondary))
                    }
                    Text("Last Sent Frame").font(.caption).foregroundColor(.secondary)
                }

                VStack(alignment: .leading, spacing: 8) {
                    MetricRow(label: "Status", value: imageTransferTime != nil ? "Sent & Ack'd" : "Pending", target: "")
                    MetricRow(label: "Round-trip Time", value: imageTransferTime != nil ? String(format: "%.0f ms", imageTransferTime! * 1000) : "N/A", target: "< 500ms")
                    ProgressView(value: imageTransferProgress).progressViewStyle(LinearProgressViewStyle())
                }
            }
        }
    }

    private var onDeviceAnalysisSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            MetricRow(label: "Objects Detected", value: cameraManager.lastDetections.map { $0.label }.joined(separator: ", ").isEmpty ? "None" : cameraManager.lastDetections.map { $0.label }.joined(separator: ", "), target: "")
            MetricRow(label: "VLM Description", value: cameraManager.lastVLMDescription ?? "N/A", target: "")
            MetricRow(label: "VLM Confidence", value: String(format: "%.2f", cameraManager.lastVLMConfidence ?? 0.0), target: "> 0.5")
        }
    }

    private var webSocketStatusSection: some View {
        VStack(spacing: 8) {
            ConnectionStatusRow(label: "Status", value: wsManager.status.description, color: connectionStatusColor)
            ConnectionStatusRow(label: "Server", value: "\(SettingsManager.shared.serverHost):\(SettingsManager.shared.serverPort)", color: .secondary)
            ConnectionStatusRow(label: "Mode", value: SettingsManager.shared.processingMode.capitalized, color: .secondary)
            ConnectionStatusRow(label: "Server Queue Size", value: "\(wsManager.serverQueueSize)", color: .secondary)
        }
    }

    private var processingMetricsSection: some View {
        VStack(spacing: 8) {
            MetricRow(label: "Avg Sent Packet Time", value: String(format: "%.1f ms", avgSentPacketTime), target: "< 100 ms")
            MetricRow(label: "Avg Response Time", value: String(format: "%.1f ms", avgResponseTime), target: "< 500 ms")
            MetricRow(label: "Keyframes/s", value: String(format: "%.1f", keyframesPerSecond), target: "> 10")
        }
    }

    private var networkActivitySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Picker("Category", selection: $selectedLogCategory) {
                ForEach(LogCategory.allCases, id: \.self) { Text($0.rawValue) }
            }.pickerStyle(SegmentedPickerStyle())

            if filteredNetworkLogs.isEmpty {
                Text("No network activity").font(.subheadline).foregroundColor(.secondary).frame(maxWidth: .infinity, alignment: .center).padding(.vertical, 10)
            } else {
                LazyVStack(spacing: 4) {
                    ForEach(filteredNetworkLogs.suffix(10)) { NetworkLogRow(log: $0) }
                }
            }
        }
    }

    private var detectionLogsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            if detectionLogs.isEmpty {
                Text("No detection logs").font(.subheadline).foregroundColor(.secondary).frame(maxWidth: .infinity, alignment: .center).padding(.vertical, 10)
            } else {
                LazyVStack(spacing: 4) {
                    ForEach(detectionLogs.suffix(10)) { DetectionLogRow(log: $0) }
                }
            }
        }
    }

    private var rawDataSection: some View {
        HStack(spacing: 12) {
            Button("View Raw JSON") { showingRawJSONViewer = true }.buttonStyle(.bordered)
            Button("Export Logs") { exportLogs() }.buttonStyle(.bordered)
            Spacer()
            Toggle("Auto-scroll", isOn: $autoScrollEnabled).labelsHidden()
        }
    }

    private var memorySection: some View {
        VStack(spacing: 8) {
            MetricRow(label: "Current Memory", value: String(format: "%.1f MB", appState.performanceMetrics.memoryUsage), target: "")
            MetricRow(label: "Peak Memory", value: String(format: "%.1f MB", peakMemory), target: "")
        }
    }

    // MARK: - Helper Properties & Methods

    private var filteredNetworkLogs: [NetworkLogEntry] {
        switch selectedLogCategory {
        case .all: return networkLogs
        case .sent: return networkLogs.filter { $0.type == .sent }
        case .received: return networkLogs.filter { $0.type == .received }
        case .error: return networkLogs.filter { $0.type == .error }
        }
    }

    private var connectionStatusColor: Color {
        switch wsManager.status {
        case .connected: .green
        case .connecting: .yellow
        case .disconnected: .red
        }
    }

    private func updateMetrics() {
        // This function can be expanded to calculate real metrics from logs
        let currentRuntime = Date().timeIntervalSince(startTime)
        if currentRuntime > 0 { keyframesPerSecond = Double(detectionLogs.count) / currentRuntime }
        if appState.performanceMetrics.memoryUsage > peakMemory { peakMemory = appState.performanceMetrics.memoryUsage }
    }

    private func clearAllLogs() {
        networkLogs.removeAll()
        detectionLogs.removeAll()
    }

    private func exportLogs() {
        Logger.shared.log("Exporting debug logs", category: .general)
    }

    private func setupLogSubscribers() {
        networkLogCancellable = wsManager.networkLogPublisher
            .receive(on: DispatchQueue.main)
            .sink { logEntry in
                self.networkLogs.append(logEntry)
                // Keep log array size in check
                if self.networkLogs.count > 100 { self.networkLogs.removeFirst() }
            }

        detectionLogCancellable = cameraManager.detectionLogPublisher
            .receive(on: DispatchQueue.main)
            .sink { logEntry in
                self.detectionLogs.append(logEntry)
                // Keep log array size in check
                if self.detectionLogs.count > 100 { self.detectionLogs.removeFirst() }
            }
    }

    private func cancelLogSubscribers() {
        networkLogCancellable?.cancel()
        networkLogCancellable = nil
        detectionLogCancellable?.cancel()
        detectionLogCancellable = nil
    }
}

// MARK: - Supporting Views (Can be moved to a separate file)

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

struct NetworkLogRow: View {
    let log: NetworkLogEntry
    private var typeColor: Color {
        switch log.type { case .sent: .blue; case .received: .green; case .error: .red }
    }
    private var typeIcon: String {
        switch log.type { case .sent: "arrow.up.circle.fill"; case .received: "arrow.down.circle.fill"; case .error: "exclamationmark.triangle.fill" }
    }

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: typeIcon).foregroundColor(typeColor).frame(width: 16)
            VStack(alignment: .leading, spacing: 2) {
                Text(log.message).font(.caption).lineLimit(2)
                Text(log.formattedTimestamp).font(.caption2).foregroundColor(.secondary)
            }
            Spacer()
        }.padding(.vertical, 4).padding(.horizontal, 8).background(Color(.secondarySystemBackground)).cornerRadius(8)
    }
}

struct DetectionLogRow: View {
    let log: DetectionLogEntry
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "viewfinder").foregroundColor(.blue).frame(width: 16)
            VStack(alignment: .leading, spacing: 2) {
                Text("\(log.detectionsCount) objects detected").font(.caption)
                Text("Avg confidence: \(log.averageConfidence, specifier: "%.2f") • \(log.processingTime, specifier: "%.1f")ms").font(.caption2).foregroundColor(.secondary)
            }
            Spacer()
            Text(log.formattedTimestamp).font(.caption2).foregroundColor(.secondary)
        }.padding(.vertical, 4).padding(.horizontal, 8).background(Color(.secondarySystemBackground)).cornerRadius(8)
    }
}

// MARK: - Previews & Placeholder Views

struct RawJSONViewer: View {
    @EnvironmentObject var wsManager: WebSocketManager
    @Environment(\.dismiss) var dismiss
    var body: some View {
        NavigationView {
            ScrollView {
                Text("Raw JSON data will be shown here.").padding()
            }
            .navigationTitle("Raw JSON Data").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Done") { dismiss() } } }
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
                    Toggle("Network Logs", isOn: .constant(DebugConfig.enableNetworkLogs))
                    Toggle("Processing Logs", isOn: .constant(DebugConfig.enableProcessingLogs))
                }
            }
            .navigationTitle("Debug Settings").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Done") { dismiss() } } }
        }
    }
}

struct DebugTabView_Previews: PreviewProvider {
    static var previews: some View {
        let appState = AppStateManager()
        let cameraManager = CameraManager()
        let wsManager = WebSocketManager()

        appState.performanceMetrics = PerformanceMetrics(fps: 29.5, memoryUsage: 180.3, batteryLevel: 0.75, temperature: 0)

        return DebugTabView()
            .environmentObject(appState)
            .environmentObject(cameraManager)
            .environmentObject(wsManager)
    }
}
