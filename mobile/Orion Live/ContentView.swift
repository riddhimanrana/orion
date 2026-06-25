//
//  ContentView.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Main SwiftUI entry point for Orion Live’s tabbed interface.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//
import SwiftUI
import WebRTC
import Combine
import Supabase

struct ContentView: View {
    @EnvironmentObject var cameraManager: CameraManager
    @EnvironmentObject var appState: AppStateManager
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var webSocketManager: WebSocketManager
    @EnvironmentObject var signalingClient: SignalingClient
    @EnvironmentObject var deviceManager: DeviceManager
    @EnvironmentObject var authManager: AuthManager
    @StateObject private var settings = SettingsManager.shared

    @State private var latestAnalysis: SceneAnalysis?
    @State private var analysisTimestamp: TimeInterval = 0
    @State private var showErrorAlert = false
    @State private var alertMessage = ""

    var body: some View {
        TabView {
            CameraTabView(
                wsManager: webSocketManager,
                latestAnalysis: $latestAnalysis,
                analysisTimestamp: $analysisTimestamp
            )
                .tabItem {
                    Label("Live", systemImage: "camera.fill")
                }

            ChatView()
                .tabItem {
                    Label("Ask", systemImage: "message.fill")
                }

            ServerSurfaceView()
                .tabItem {
                    Label("Server", systemImage: "server.rack")
                }

            SettingsTabView()
                .tabItem {
                    Label("Account", systemImage: "person.crop.circle")
                }

            if settings.developerModeEnabled {
                DebugTabView()
                    .tabItem {
                        Label("Debug", systemImage: "ladybug.fill")
                    }
            }
        }
        .onAppear {
            // Managers are now set up in OrionApp.swift
            // The connection logic will be triggered by the CameraTabView's onAppear
        }
        .onReceive(cameraManager.$error.compactMap { $0 }) { cameraError in
            if !cameraError.isEmpty {
                self.alertMessage = "Camera Error: \(cameraError)"
                self.showErrorAlert = true
                Logger.shared.log("CameraManager published error: \(cameraError)", level: .error, category: .camera)
                // Also show toast for immediate feedback
                ToastManager.shared.showToast(message: "Camera Error: \(cameraError)", type: .error)
            }
        }
        .alert("Application Alert", isPresented: $showErrorAlert) {
            Button("OK") { }
        } message: {
            Text(alertMessage)
        }
    }
}

private struct ServerSurfaceView: View {
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var signalingClient: SignalingClient
    @EnvironmentObject var deviceManager: DeviceManager
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var wsManager: WebSocketManager
    @StateObject private var settings = SettingsManager.shared
    @State private var showingPairingSheet = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    VStack(alignment: .leading, spacing: 14) {
                        Label(serverTitle, systemImage: serverIcon)
                            .font(.headline)
                            .foregroundStyle(serverColor)
                        Text(serverDetail)
                            .font(.callout)
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(.vertical, 4)
                }

                Section("Connection") {
                    ServerInfoRow(label: "Paired", value: pairedText, color: pairedColor)
                    ServerInfoRow(label: "Signaling", value: signalingClient.connectionState.description, color: signalingColor)
                    ServerInfoRow(label: "WebRTC", value: webRTCStateText, color: webRTCColor)
                    ServerInfoRow(label: "Data Channel", value: dataChannelText, color: dataChannelColor)
                    ServerInfoRow(label: "Streaming", value: webRTCManager.dataChannelState == .open ? "Ready" : "Waiting", color: webRTCManager.dataChannelState == .open ? .green : .secondary)
                    ServerInfoRow(label: "Signal Host", value: "signal.orionlive.ai", color: .secondary)
                }

                Section {
                    Button {
                        showingPairingSheet = true
                    } label: {
                        Label(deviceManager.pairedDevices.isEmpty ? "Pair Mac Server" : "Manage Pairing", systemImage: "link")
                            .frame(maxWidth: .infinity, minHeight: 44)
                    }
                    .buttonStyle(.borderedProminent)

                    Button {
                        Task { await webRTCManager.connect() }
                    } label: {
                        Label("Connect to Mac", systemImage: "point.3.connected.trianglepath.dotted")
                            .frame(maxWidth: .infinity, minHeight: 44)
                    }
                    .buttonStyle(.bordered)
                    .disabled(deviceManager.deviceId == nil)
                }

                if settings.developerModeEnabled {
                    Section("Developer Local Fallback") {
                        Toggle("Enable Direct Local Fallback", isOn: $settings.directLocalFallbackEnabled)
                        Text("Use only when testing the FastAPI server directly on local Wi-Fi. Normal streaming uses Signal P2P.")
                            .font(.caption)
                            .foregroundStyle(.secondary)

                        if settings.directLocalFallbackEnabled {
                            TextField("Host", text: $settings.serverHost)
                                .textInputAutocapitalization(.never)
                                .autocorrectionDisabled(true)
                            TextField("Port", value: $settings.serverPort, formatter: NumberFormatter())
                                .keyboardType(.numberPad)
                            ServerInfoRow(label: "Local WebSocket", value: wsManager.status.description, color: wsManager.status == .connected ? .green : .orange)
                            Button("Reconnect Local Fallback") {
                                wsManager.updateServerURL(host: settings.serverHost, port: settings.serverPort)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Server")
            .navigationBarTitleDisplayMode(.large)
            .task {
                await deviceManager.fetchPairedDevices()
            }
            .sheet(isPresented: $showingPairingSheet) {
                PairingView(authManager: authManager)
            }
        }
    }

    private var serverTitle: String {
        if webRTCManager.dataChannelState == .open { return "Mac server connected" }
        if signalingClient.connectionState == .connected { return "Signal ready" }
        if deviceManager.pairedDevices.isEmpty { return "Pair your Mac server" }
        return "Connect to Mac server"
    }

    private var serverDetail: String {
        if webRTCManager.dataChannelState == .open {
            return "Video and control data are routed through encrypted WebRTC. Reasoning runs on your macOS server."
        }
        if deviceManager.pairedDevices.isEmpty {
            return "Open Orion Server on macOS, generate a pairing code, then link this iPhone."
        }
        return "Use Connect to Mac when Orion Server is open on your Mac."
    }

    private var serverIcon: String {
        webRTCManager.dataChannelState == .open ? "checkmark.seal.fill" : "server.rack"
    }

    private var serverColor: Color {
        webRTCManager.dataChannelState == .open ? .green : .accentColor
    }

    private var pairedText: String {
        deviceManager.pairedDevices.isEmpty ? "Not paired" : deviceManager.pairedDevices.first?.serverDevice.name ?? "Paired"
    }

    private var pairedColor: Color {
        deviceManager.pairedDevices.isEmpty ? .orange : .green
    }

    private var signalingColor: Color {
        switch signalingClient.connectionState {
        case .connected: .green
        case .connecting: .yellow
        case .disconnected: .secondary
        }
    }

    private var webRTCColor: Color {
        switch webRTCManager.connectionState {
        case .connected, .completed: .green
        case .checking: .yellow
        case .failed, .disconnected, .closed: .orange
        default: .secondary
        }
    }

    private var dataChannelColor: Color {
        webRTCManager.dataChannelState == .open ? .green : .secondary
    }

    private var webRTCStateText: String {
        switch webRTCManager.connectionState {
        case .new: "New"
        case .checking: "Checking"
        case .connected: "Connected"
        case .completed: "Completed"
        case .failed: "Failed"
        case .disconnected: "Disconnected"
        case .closed: "Closed"
        case .count: "Count"
        @unknown default: "Unknown"
        }
    }

    private var dataChannelText: String {
        switch webRTCManager.dataChannelState {
        case .connecting: "Connecting"
        case .open: "Open"
        case .closing: "Closing"
        case .closed: "Closed"
        @unknown default: "Unknown"
        }
    }
}

private struct ServerInfoRow: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        HStack {
            Text(label)
            Spacer()
            Label(value, systemImage: "circle.fill")
                .labelStyle(.titleAndIcon)
                .font(.callout)
                .foregroundStyle(color)
                .lineLimit(1)
                .minimumScaleFactor(0.75)
        }
        .frame(minHeight: 44)
    }
}

// MARK: - Preview
struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        // Mock all necessary managers for the preview
        let appState = AppStateManager()
        let cameraManager = CameraManager()
        let authManager = AuthManager()
        let deviceManager = DeviceManager(supabase: authManager.supabase)
        let apiService = APIService(supabase: authManager.supabase)
        let signalingClient = SignalingClient(apiService: apiService, deviceManager: deviceManager)
        let webRTCManager = WebRTCManager(signalingClient: signalingClient)
        let compatibilityManager = SystemCompatibilityManager()
        let webSocketManager = WebSocketManager() // Old manager, for dependency completeness if needed elsewhere

        // Setup mock data for preview
        appState.performanceMetrics = PerformanceMetrics(fps: 29.5, memoryUsage: 120.3, batteryLevel: 0.75, temperature: 0)

        return ContentView()
            .environmentObject(appState)
            .environmentObject(cameraManager)
            .environmentObject(webRTCManager)
            .environmentObject(signalingClient)
            .environmentObject(deviceManager)
            .environmentObject(authManager)
            .environmentObject(compatibilityManager)
            .environmentObject(webSocketManager)
    }
}
