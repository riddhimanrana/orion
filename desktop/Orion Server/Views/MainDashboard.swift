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
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    ZStack {
                        Color(NSColor.windowBackgroundColor)
                        Text("Waiting for video stream...")
                            .foregroundColor(.secondary)
                    }
                }
            }
            .frame(minWidth: 500, idealWidth: 800, maxWidth: .infinity)

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
            HStack {
                MonogramAvatar(initials: userViewModel.getInitials(from: userViewModel.fullName))
                    .frame(width: 40, height: 40)
                VStack(alignment: .leading) {
                    Text(userViewModel.fullName).font(.headline)
                    Text(userViewModel.email).font(.caption).foregroundColor(.secondary)
                }
            }
            
            // Connection Status Section
            VStack(alignment: .leading) {
                Text("Connection Status").font(.headline).padding(.bottom, 5)
                StatusRow(label: "Signaling", status: signalingClient.connectionState.description, color: signalingStatusColor)
                StatusRow(label: "WebRTC", status: webRTCStatusString, color: webRTCStatusColor)
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
    
    private var signalingStatusColor: Color {
        switch signalingClient.connectionState {
        case .connected: .green
        case .connecting: .yellow
        case .disconnected: .red
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
        case .connected, .completed: .green
        case .checking: .yellow
        case .new, .disconnected, .failed, .closed, .count: .red
        @unknown default:
            .gray
        }
    }
}

// MARK: - Status Row
struct StatusRow: View {
    let label: String
    let status: String
    let color: Color

    var body: some View {
        HStack {
            Text(label)
            Spacer()
            HStack(spacing: 5) {
                Circle().fill(color).frame(width: 8, height: 8)
                Text(status)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(color.opacity(0.2))
            .cornerRadius(8)
        }
    }
}

// MARK: - WebRTC Video View Representable
struct RTCVideoView: NSViewRepresentable {
    var videoTrack: RTCVideoTrack

    func makeNSView(context: Context) -> NSView {
        let view = NSView(frame: .zero)
        view.wantsLayer = true
        view.layer?.backgroundColor = NSColor.black.cgColor
        return view
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        // Note: RTCMTLVideoView might not be available in all WebRTC versions
        // This is a placeholder implementation
        // You may need to implement custom video rendering or use RTCEAGLVideoView equivalent
    }
}

// MARK: - Monogram Avatar
struct MonogramAvatar: View {
    let initials: String
    
    var body: some View {
        ZStack {
            Circle()
                .fill(
                    LinearGradient(
                        colors: [Color.blue, Color.purple],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
            
            Text(initials)
                .font(.system(size: 14, weight: .semibold))
                .foregroundColor(.white)
        }
    }
}
