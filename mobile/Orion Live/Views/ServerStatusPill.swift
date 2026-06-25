//
//  ServerStatusPill.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Server status pill showing WebRTC and signal server status for Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//

import SwiftUI
import WebRTC

struct ServerStatusPill: View {
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var signalingClient: SignalingClient
    
    @Environment(\.colorScheme) var colorScheme
    
    var body: some View {
        StatusPill(
            title: "Server",
            status: serverStatusText,
            statusColor: serverStatusColor,
            isAnimated: isConnecting
        )
    }
    
    private var serverStatusText: String {
        if (webRTCManager.connectionState == .connected || webRTCManager.connectionState == .completed) && webRTCManager.dataChannelState == .open {
            return "Connected"
        } else if webRTCManager.connectionState == .checking || webRTCManager.dataChannelState == .connecting {
            return "Connecting"
        } else if webRTCManager.connectionState == .disconnected || webRTCManager.connectionState == .closed {
            switch signalingClient.connectionState {
            case .connected:
                return "Signaling"
            case .connecting:
                return "Connecting"
            case .disconnected:
                return "Disconnected"
            }
        } else if webRTCManager.connectionState == .failed {
            return "Failed"
        } else if webRTCManager.connectionState == .new || webRTCManager.connectionState == .count {
            return "Initializing"
        } else {
            return "Unknown"
        }
    }

    private var serverStatusColor: Color {
        if (webRTCManager.connectionState == .connected || webRTCManager.connectionState == .completed) && webRTCManager.dataChannelState == .open {
            return .green
        } else if webRTCManager.connectionState == .checking || webRTCManager.dataChannelState == .connecting {
            return .yellow
        } else if webRTCManager.connectionState == .disconnected || webRTCManager.connectionState == .closed {
            switch signalingClient.connectionState {
            case .connected:
                return .green
            case .connecting:
                return .yellow
            case .disconnected:
                return .red
            }
        } else if webRTCManager.connectionState == .failed {
            return .red
        } else if webRTCManager.connectionState == .new || webRTCManager.connectionState == .count {
            return .gray
        } else {
            return .gray
        }
    }

    private var isConnecting: Bool {
        return webRTCManager.connectionState == .checking ||
               webRTCManager.dataChannelState == .connecting ||
               signalingClient.connectionState == .connecting
    }
}

// MARK: - Preview
struct ServerStatusPill_Previews: PreviewProvider {
    static var previews: some View {
        let authManager = AuthManager()
        let deviceManager = DeviceManager(supabase: authManager.supabase)
        let apiService = APIService(supabase: authManager.supabase)
        let signalingClient = SignalingClient(apiService: apiService, deviceManager: deviceManager)
        let webRTCManager = WebRTCManager(signalingClient: signalingClient)
        
        VStack(spacing: 20) {
            ServerStatusPill()
                .environmentObject(webRTCManager)
                .environmentObject(signalingClient)
        }
        .padding()
        .preferredColorScheme(.dark)
    }
}
