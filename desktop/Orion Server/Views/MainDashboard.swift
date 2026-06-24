//
//  MainDashboard.swift
//  Orion Server
//
//  Created by Riddhiman Rana on 8/9/25.
//  Main dashboard view for authenticated users.
//

import SwiftUI
import Supabase
import WebRTC

// MARK: - Main Dashboard View
struct MainDashboard: View {
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var signalingClient: SignalingClient
    @EnvironmentObject var userViewModel: UserProfileViewModel

    @State private var remoteVideoTrack: RTCVideoTrack?

    var body: some View {
        HSplitView {
            // Main content: Video feed
            VStack {
                if let track = remoteVideoTrack {
                    RTCVideoView(videoTrack: track)
                        .background(Color(NSColor.windowBackgroundColor))
                        .clipped()
                } else {
                    ZStack {
                        Color(NSColor.windowBackgroundColor)
                        Text("Waiting for video stream...")
                            .foregroundColor(.secondary)
                    }
                }
            }
            .frame(minWidth: 500, idealWidth: 800, maxWidth: .infinity, maxHeight: .infinity)

            // Sidebar: Status and controls
            SidebarView()
                .frame(minWidth: 250, idealWidth: 300, maxWidth: 400)
        }
        .onReceive(webRTCManager.$videoTrack) { track in
            self.remoteVideoTrack = track
        }
    }
}

// MARK: - Sidebar View
struct SidebarView: View {
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var signalingClient: SignalingClient
    @EnvironmentObject var userViewModel: UserProfileViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            // User Profile Section
            HStack(spacing: 12) {
                MonogramAvatar(initials: userViewModel.getInitials(from: userViewModel.fullName))
                    .frame(width: 40, height: 40)
                VStack(alignment: .leading, spacing: 2) {
                    Text(userViewModel.fullName).font(.headline)
                    Text(userViewModel.email).font(.caption).foregroundColor(.secondary)
                }
            }

            // Connection Status Section
            VStack(alignment: .leading, spacing: 8) {
                Text("Connection Status").font(.headline).padding(.bottom, 5)
                StatusRow(label: "Signaling", status: signalingClient.connectionState.description, color: signalingStatusColor)
                StatusRow(label: "WebRTC", status: webRTCStatusString, color: webRTCStatusColor)
                StatusRow(label: "ICE Mode", status: webRTCManager.iceStatus.usingTURN ? "TURN (relay)" : "STUN/Direct", color: webRTCManager.iceStatus.usingTURN ? .orange : .gray)
                StatusRow(label: "ICE Types", status: "L: \(webRTCManager.iceStatus.localType) • R: \(webRTCManager.iceStatus.remoteType) • \(webRTCManager.iceStatus.transport)", color: .gray)
                if let ttl = webRTCManager.ephemeralTTLRemaining {
                    StatusRow(label: "ICE Creds", status: "Ephemeral (\(ttl)s)", color: ttl > 30 ? .green : .yellow)
                }
                StatusRow(label: "DataChannel", status: dataChannelStateText, color: dataChannelStatusColor)
                StatusRow(label: "Ping RTT", status: pingRTTText, color: .blue)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Signal Traffic").font(.headline).padding(.bottom, 5)
                StatusRow(label: "Packets Out", status: "\(signalingClient.packetsSent)", color: .blue)
                StatusRow(label: "Packets In", status: "\(signalingClient.packetsReceived)", color: .green)
                StatusRow(label: "Bytes Out", status: ByteCountFormatter.string(fromByteCount: Int64(signalingClient.packetBytesSent), countStyle: .binary), color: .blue)
                StatusRow(label: "Bytes In", status: ByteCountFormatter.string(fromByteCount: Int64(signalingClient.packetBytesReceived), countStyle: .binary), color: .green)
                StatusRow(label: "Last Out", status: signalingClient.lastPacketTypeSent ?? "-", color: .gray)
                StatusRow(label: "Last In", status: signalingClient.lastPacketTypeReceived ?? "-", color: .gray)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Server Health").font(.headline).padding(.bottom, 5)
                if let health = signalingClient.lastSignalHealth {
                    StatusRow(label: "Signal API", status: health.status, color: .green)
                    StatusRow(label: "Rooms", status: health.roomsActive.map(String.init) ?? "-", color: .gray)
                    StatusRow(label: "Clients", status: health.clientsConnected.map(String.init) ?? "-", color: .gray)
                } else {
                    StatusRow(label: "Signal API", status: "No sample yet", color: .gray)
                }
                if let usage = signalingClient.lastSignalAccountUsage {
                    StatusRow(label: "Relayed", status: "\(usage.usage.packetsRelayed) packets", color: .gray)
                    StatusRow(label: "Relay Bytes", status: ByteCountFormatter.string(fromByteCount: Int64(usage.usage.bytesRelayed), countStyle: .binary), color: .gray)
                }
            }

            // Logs Section
            VStack(alignment: .leading) {
                Text("Logs").font(.headline).padding(.bottom, 5)
                ScrollView {
                    Text("Log messages will appear here...")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(height: 200)
                .background(Color(NSColor.textBackgroundColor))
                .cornerRadius(8)
            }

            Spacer()
        }
        .padding()
    }

    // MARK: - Sidebar helpers
    private var signalingStatusColor: Color {
        switch signalingClient.connectionState {
        case .connected: return .green
        case .connecting: return .yellow
        case .disconnected: return .red
        }
    }

    private var webRTCStatusString: String {
        switch webRTCManager.connectionState {
        case .new: return "new"
        case .checking: return "checking"
        case .connected: return "connected"
        case .completed: return "completed"
        case .failed: return "failed"
        case .disconnected: return "disconnected"
        case .closed: return "closed"
        case .count: return "count"
        @unknown default: return "unknown"
        }
    }

    private var webRTCStatusColor: Color {
        switch webRTCManager.connectionState {
        case .connected, .completed: return .green
        case .checking: return .yellow
        case .new, .disconnected, .failed, .closed, .count: return .red
        @unknown default: return .gray
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

    private var dataChannelStatusColor: Color {
        switch webRTCManager.dataChannelState {
        case .open: return .green
        case .connecting: return .yellow
        case .closing, .closed: return .red
        @unknown default: return .gray
        }
    }

    private var pingRTTText: String {
        // Placeholder until WebRTCManager exposes a compatible property
        return "N/A"
    }
}

// MARK: - Status Row
struct StatusRow: View {
    let label: String
    let status: String
    let color: Color

    var body: some View {
        HStack {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text(label)
                .font(.subheadline)
            Spacer()
            Text(status)
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Monogram Avatar
struct MonogramAvatar: View {
    let initials: String

    var body: some View {
        ZStack {
            Circle().fill(Color.accentColor.opacity(0.15))
            Text(initials)
                .font(.headline)
                .foregroundColor(.accentColor)
        }
        .aspectRatio(1, contentMode: .fit)
    }
}

// MARK: - RTCVideoView (macOS)
/// A simple NSViewRepresentable that renders an RTCVideoTrack using RTCMTLNSVideoView.
struct RTCVideoView: NSViewRepresentable {
    let videoTrack: RTCVideoTrack

    func makeNSView(context: Context) -> RTCMTLNSVideoView {
        let view = RTCMTLNSVideoView(frame: .zero)
        return view
    }

    func updateNSView(_ nsView: RTCMTLNSVideoView, context: Context) {
        // Remove any previous renderer before adding again to avoid duplicates
        videoTrack.remove(nsView)
        videoTrack.add(nsView)
    }
}
