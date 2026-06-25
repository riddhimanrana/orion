//
//  MainDashboard.swift
//  Orion Server
//
//  Native macOS dashboard for the local Orion server and Signal P2P session.
//

import SwiftUI
import Supabase
import WebRTC

struct MainDashboard: View {
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var signalingClient: SignalingClient
    @EnvironmentObject var userViewModel: UserProfileViewModel

    @StateObject private var dashboardSocket = DashboardSocket.shared
    @StateObject private var processManager = ProcessManager.shared
    @State private var selection: DashboardSection? = .overview

    var body: some View {
        NavigationSplitView {
            List(selection: $selection) {
                Section("Server") {
                    DashboardSidebarRow(section: .overview)
                    DashboardSidebarRow(section: .liveStream)
                    DashboardSidebarRow(section: .connections)
                }

                Section("Pipeline") {
                    DashboardSidebarRow(section: .reasoning)
                    DashboardSidebarRow(section: .perception)
                    DashboardSidebarRow(section: .memory)
                }

                Section("Diagnostics") {
                    DashboardSidebarRow(section: .logs)
                }
            }
            .navigationTitle("Orion")
            .listStyle(.sidebar)
        } detail: {
            detailView
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color(NSColor.windowBackgroundColor))
        }
        .toolbar {
            ToolbarItemGroup {
                Label(connectionTitle, systemImage: connectionIcon)
                    .labelStyle(.titleAndIcon)

                Button(processManager.isRunning ? "Stop Server" : "Start Server") {
                    processManager.isRunning ? processManager.stop() : processManager.start()
                }

                Button("Connect") {
                    webRTCManager.connect()
                    dashboardSocket.connect()
                }
            }
        }
        .onAppear {
            dashboardSocket.connect()
        }
    }

    @ViewBuilder
    private var detailView: some View {
        switch selection ?? .overview {
        case .overview:
            OverviewPanel()
                .environmentObject(webRTCManager)
                .environmentObject(signalingClient)
                .environmentObject(userViewModel)
                .environmentObject(dashboardSocket)
                .environmentObject(processManager)
        case .liveStream:
            LiveStreamPanel()
                .environmentObject(webRTCManager)
                .environmentObject(dashboardSocket)
        case .reasoning:
            ReasoningPanel()
                .environmentObject(webRTCManager)
                .environmentObject(dashboardSocket)
        case .perception:
            PerceptionPanel()
                .environmentObject(dashboardSocket)
        case .memory:
            MemoryPanel()
                .environmentObject(dashboardSocket)
        case .connections:
            ConnectionsPanel()
                .environmentObject(webRTCManager)
                .environmentObject(signalingClient)
        case .logs:
            LogsPanel()
                .environmentObject(processManager)
                .environmentObject(webRTCManager)
        }
    }

    private var connectionTitle: String {
        if (webRTCManager.connectionState == .connected || webRTCManager.connectionState == .completed) && webRTCManager.dataChannelState == .open {
            return "Streaming"
        }
        if signalingClient.connectionState == .connected {
            return "Signal Ready"
        }
        return processManager.isRunning ? "Server Running" : "Server Stopped"
    }

    private var connectionIcon: String {
        if webRTCManager.videoTrack != nil { return "dot.radiowaves.left.and.right" }
        if signalingClient.connectionState == .connected { return "network" }
        return processManager.isRunning ? "server.rack" : "server.rack"
    }
}

private enum DashboardSection: String, CaseIterable, Identifiable {
    case overview
    case liveStream
    case reasoning
    case perception
    case memory
    case connections
    case logs

    var id: String { rawValue }

    var title: String {
        switch self {
        case .overview: return "Overview"
        case .liveStream: return "Live Stream"
        case .reasoning: return "Reasoning"
        case .perception: return "Perception"
        case .memory: return "Memory"
        case .connections: return "Connections"
        case .logs: return "Logs"
        }
    }

    var icon: String {
        switch self {
        case .overview: return "gauge.with.dots.needle.bottom.50percent"
        case .liveStream: return "video"
        case .reasoning: return "brain.head.profile"
        case .perception: return "eye"
        case .memory: return "point.3.connected.trianglepath.dotted"
        case .connections: return "network"
        case .logs: return "terminal"
        }
    }
}

private struct DashboardSidebarRow: View {
    let section: DashboardSection

    var body: some View {
        Label(section.title, systemImage: section.icon)
            .tag(section)
    }
}

private struct OverviewPanel: View {
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var signalingClient: SignalingClient
    @EnvironmentObject var userViewModel: UserProfileViewModel
    @EnvironmentObject var dashboardSocket: DashboardSocket
    @EnvironmentObject var processManager: ProcessManager

    var body: some View {
        ScrollView {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 260), spacing: 16)], spacing: 16) {
                StatusCard(title: "Server Process", icon: "server.rack") {
                    MetricLine("Runtime", processManager.isRunning ? "Running" : "Stopped", color: processManager.isRunning ? .green : .red)
                    MetricLine("Dashboard WS", dashboardSocket.isConnected ? "Connected" : "Disconnected", color: dashboardSocket.isConnected ? .green : .red)
                    MetricLine("CPU", String(format: "%.1f%%", processManager.cpuUsage), color: .secondary)
                    MetricLine("Memory", String(format: "%.1f MB", processManager.memoryUsage), color: .secondary)
                }

                StatusCard(title: "P2P Session", icon: "iphone.radiowaves.left.and.right") {
                    MetricLine("Signaling", signalingClient.connectionState.description, color: signalingClient.connectionState == .connected ? .green : .orange)
                    MetricLine("WebRTC", webRTCStateText, color: webRTCStateColor)
                    MetricLine("Data Channel", dataChannelText, color: webRTCManager.dataChannelState == .open ? .green : .orange)
                    MetricLine("Video", webRTCManager.videoTrack == nil ? "Waiting" : "Receiving", color: webRTCManager.videoTrack == nil ? .secondary : .green)
                }

                StatusCard(title: "User", icon: "person.crop.circle") {
                    MetricLine("Name", userViewModel.fullName.isEmpty ? "Signed in" : userViewModel.fullName, color: .secondary)
                    MetricLine("Email", userViewModel.email.isEmpty ? "-" : userViewModel.email, color: .secondary)
                    MetricLine("Plan", userViewModel.subscriptionTier.isEmpty ? "-" : userViewModel.subscriptionTier, color: .secondary)
                }

                StatusCard(title: "Pipeline", icon: "memorychip") {
                    MetricLine("Frame", dashboardSocket.frameId, color: .secondary)
                    MetricLine("Mode", dashboardSocket.processingMode == "full" ? "macOS Server" : dashboardSocket.processingMode, color: .green)
                    MetricLine("Queue", "\(dashboardSocket.queueSize)", color: dashboardSocket.queueSize == 0 ? .green : .orange)
                    MetricLine("Detections", "\(dashboardSocket.detections.count)", color: dashboardSocket.detections.isEmpty ? .secondary : .green)
                    MetricLine("Packet Events", "\(dashboardSocket.packetEventCount)", color: dashboardSocket.packetEventCount == 0 ? .secondary : .green)
                }
            }
            .padding(24)
        }
        .navigationTitle("Overview")
    }

    private var webRTCStateText: String {
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

    private var webRTCStateColor: Color {
        switch webRTCManager.connectionState {
        case .connected, .completed: return .green
        case .checking: return .orange
        case .failed, .disconnected, .closed: return .red
        default: return .secondary
        }
    }

    private var dataChannelText: String {
        switch webRTCManager.dataChannelState {
        case .connecting: return "Connecting"
        case .open: return "Open"
        case .closing: return "Closing"
        case .closed: return "Closed"
        @unknown default: return "Unknown"
        }
    }
}

private struct LiveStreamPanel: View {
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var dashboardSocket: DashboardSocket

    var body: some View {
        HSplitView {
            ZStack {
                Color.black
                if let track = webRTCManager.videoTrack {
                    RTCVideoView(videoTrack: track)
                        .background(Color.black)
                        .clipped()
                } else if let frame = dashboardSocket.currentFrame {
                    Image(nsImage: frame)
                        .resizable()
                        .scaledToFit()
                        .padding()
                } else {
                    VStack(spacing: 12) {
                        Image(systemName: "video.badge.ellipsis")
                            .font(.system(size: 44))
                        Text("Waiting for iPhone Stream")
                            .font(.title3.bold())
                        Text("Pair an iPhone and connect through Signal P2P. The dashboard frame feed is used as a fallback preview.")
                            .font(.callout)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                            .frame(maxWidth: 360)
                    }
                    .foregroundStyle(.secondary)
                }
            }
            .frame(minWidth: 540, maxWidth: .infinity, maxHeight: .infinity)

            InspectorPanel(title: "Latest Frame") {
                MetricLine("Frame", dashboardSocket.frameId, color: .secondary)
                MetricLine("Video Track", webRTCManager.videoTrack == nil ? "Waiting" : "Active", color: webRTCManager.videoTrack == nil ? .secondary : .green)
                MetricLine("Dashboard Frame", dashboardSocket.currentFrame == nil ? "No sample" : "Available", color: dashboardSocket.currentFrame == nil ? .secondary : .green)
                MetricLine("Queue", "\(dashboardSocket.queueSize)", color: dashboardSocket.queueSize == 0 ? .green : .orange)
                Divider()
                Text(dashboardSocket.sceneDescription)
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
            .frame(minWidth: 280, idealWidth: 320, maxWidth: 380)
        }
        .navigationTitle("Live Stream")
    }
}

private struct ReasoningPanel: View {
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var dashboardSocket: DashboardSocket

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                StatusCard(title: "Latest Gemma Reasoning", icon: "brain.head.profile") {
                    Text(dashboardSocket.sceneDescription)
                        .font(.body)
                        .textSelection(.enabled)
                }

                StatusCard(title: "Raw Reasoning Payload", icon: "curlybraces") {
                    Text(dashboardSocket.latestReasoningPayload)
                        .font(.system(.caption, design: .monospaced))
                        .textSelection(.enabled)
                }

                StatusCard(title: "P2P Data Channel", icon: "arrow.left.arrow.right") {
                    MetricLine("State", dataChannelText, color: webRTCManager.dataChannelState == .open ? .green : .orange)
                    Text(webRTCManager.receivedMessage.isEmpty ? "No data-channel message yet." : webRTCManager.receivedMessage)
                        .font(.system(.body, design: .monospaced))
                        .textSelection(.enabled)
                }
            }
            .padding(24)
        }
        .navigationTitle("Reasoning")
    }

    private var dataChannelText: String {
        switch webRTCManager.dataChannelState {
        case .connecting: return "Connecting"
        case .open: return "Open"
        case .closing: return "Closing"
        case .closed: return "Closed"
        @unknown default: return "Unknown"
        }
    }
}

private struct PerceptionPanel: View {
    @EnvironmentObject var dashboardSocket: DashboardSocket

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                StatusCard(title: "YOLO / Re-ID Tracks", icon: "eye") {
                    if dashboardSocket.detections.isEmpty {
                        Text("No detections in the latest dashboard event.")
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(dashboardSocket.detections) { detection in
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(detection.label)
                                        .font(.headline)
                                    Text("track \(detection.track_id.map(String.init) ?? "-")")
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                                Text("\(Int(detection.confidence * 100))%")
                                    .font(.title3.bold())
                                    .monospacedDigit()
                            }
                            Divider()
                        }
                    }
                }

                StatusCard(title: "Depth / CIS", icon: "cube.transparent") {
                    if dashboardSocket.modelHealth.isEmpty {
                        MetricLine("Model Health", "Waiting for server", color: .secondary)
                    } else {
                        ForEach(dashboardSocket.modelHealth.keys.sorted(), id: \.self) { key in
                            MetricLine(key, dashboardSocket.modelHealth[key] == true ? "Ready" : "Unavailable", color: dashboardSocket.modelHealth[key] == true ? .green : .orange)
                        }
                    }
                    Divider()
                    Text("Server diagnostics will show Depth Anything 3 maps, spatial relations, and CIS components as soon as those fields are present in dashboard events.")
                        .foregroundStyle(.secondary)
                }
            }
            .padding(24)
        }
        .navigationTitle("Perception")
    }
}

private struct MemoryPanel: View {
    @EnvironmentObject var dashboardSocket: DashboardSocket

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                StatusCard(title: "Persistent Memory", icon: "point.3.connected.trianglepath.dotted") {
                    MetricLine("Visible Objects", "\(dashboardSocket.detections.count)", color: dashboardSocket.detections.isEmpty ? .secondary : .green)
                    MetricLine("Server Queue", "\(dashboardSocket.queueSize)", color: dashboardSocket.queueSize == 0 ? .green : .orange)
                    Text("Persistent object history is maintained by the Python server. This view is wired to the live dashboard stream and will expand as object-memory fields are emitted.")
                        .foregroundStyle(.secondary)
                }
            }
            .padding(24)
        }
        .navigationTitle("Memory")
    }
}

private struct ConnectionsPanel: View {
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var signalingClient: SignalingClient

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                StatusCard(title: "Signal", icon: "network") {
                    MetricLine("State", signalingClient.connectionState.description, color: signalingClient.connectionState == .connected ? .green : .orange)
                    MetricLine("Packets Out", "\(signalingClient.packetsSent)", color: .secondary)
                    MetricLine("Packets In", "\(signalingClient.packetsReceived)", color: .secondary)
                    MetricLine("Bytes Out", ByteCountFormatter.string(fromByteCount: Int64(signalingClient.packetBytesSent), countStyle: .binary), color: .secondary)
                    MetricLine("Bytes In", ByteCountFormatter.string(fromByteCount: Int64(signalingClient.packetBytesReceived), countStyle: .binary), color: .secondary)
                    MetricLine("Last Out", signalingClient.lastPacketTypeSent ?? "-", color: .secondary)
                    MetricLine("Last In", signalingClient.lastPacketTypeReceived ?? "-", color: .secondary)
                }

                StatusCard(title: "WebRTC", icon: "dot.radiowaves.left.and.right") {
                    MetricLine("ICE Mode", webRTCManager.iceStatus.usingTURN ? "TURN relay" : "STUN/direct", color: webRTCManager.iceStatus.usingTURN ? .orange : .green)
                    MetricLine("ICE Types", "L: \(webRTCManager.iceStatus.localType) / R: \(webRTCManager.iceStatus.remoteType)", color: .secondary)
                    MetricLine("Transport", webRTCManager.iceStatus.transport, color: .secondary)
                    if let ttl = webRTCManager.ephemeralTTLRemaining {
                        MetricLine("ICE TTL", "\(ttl)s", color: ttl > 30 ? .green : .orange)
                    }
                }
            }
            .padding(24)
        }
        .navigationTitle("Connections")
    }
}

private struct LogsPanel: View {
    @EnvironmentObject var processManager: ProcessManager
    @EnvironmentObject var webRTCManager: WebRTCManager

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Button(processManager.isRunning ? "Stop Server" : "Start Server") {
                    processManager.isRunning ? processManager.stop() : processManager.start()
                }
                Button("Clear") {
                    // ProcessManager intentionally owns retention; restart gives a clean stream.
                }
                .disabled(true)
                Spacer()
            }
            .padding()

            Divider()

            ScrollView {
                Text(processManager.logs.isEmpty ? "Server logs will appear here after the subprocess starts." : processManager.logs)
                    .font(.system(.caption, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
                    .padding()
            }
            .background(Color(NSColor.textBackgroundColor))
        }
        .navigationTitle("Logs")
    }
}

private struct StatusCard<Content: View>: View {
    let title: String
    let icon: String
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(title, systemImage: icon)
                .font(.headline)

            VStack(alignment: .leading, spacing: 8, content: content)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .strokeBorder(Color.primary.opacity(0.08))
        )
    }
}

private struct InspectorPanel<Content: View>: View {
    let title: String
    @ViewBuilder let content: () -> Content

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text(title)
                    .font(.headline)
                content()
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(.bar)
    }
}

private struct MetricLine: View {
    let label: String
    let value: String
    let color: Color

    init(_ label: String, _ value: String, color: Color) {
        self.label = label
        self.value = value
        self.color = color
    }

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
                .foregroundStyle(color)
                .fontWeight(.medium)
                .multilineTextAlignment(.trailing)
        }
        .font(.callout)
    }
}

struct RTCVideoView: NSViewRepresentable {
    let videoTrack: RTCVideoTrack

    func makeNSView(context: Context) -> RTCMTLNSVideoView {
        RTCMTLNSVideoView(frame: .zero)
    }

    func updateNSView(_ nsView: RTCMTLNSVideoView, context: Context) {
        videoTrack.remove(nsView)
        videoTrack.add(nsView)
    }
}
