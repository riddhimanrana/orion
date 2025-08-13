//
//  SettingsTabView.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Main settings tab for configuring Orion Live app preferences.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//
import SwiftUI
import Combine

struct SettingsTabView: View {
    @StateObject private var settings = SettingsManager.shared
    @EnvironmentObject var appState: AppStateManager
    @EnvironmentObject var wsManager: WebSocketManager
    @EnvironmentObject var cameraManager: CameraManager
    @EnvironmentObject var deviceManager: DeviceManager
    @EnvironmentObject var compatibilityManager: SystemCompatibilityManager
    @State private var showingCompatibilityDetails = false
    @State private var showingPairingSheet = false
    @State private var pollingTimer: Timer? = nil

    var body: some View {
        NavigationView {
            Form {
                serverConfigurationSection
                processingModeSection
                cameraAndDetectionSection
                performanceSection
                debugSection

                devicePairingSection

                systemCompatibilitySection
                aboutSection
            }
            .navigationTitle("Settings")
            .onAppear(perform: startPolling)
            .onDisappear(perform: stopPolling)
        }
        .sheet(isPresented: $showingPairingSheet) {
            DevicePairingView()
                .environmentObject(deviceManager)
        }
        .sheet(isPresented: $showingCompatibilityDetails) {
            CompatibilityCheckView()
                .environmentObject(compatibilityManager)
        }
    }

    private var serverConfigurationSection: some View {
        Section(header: Label("Server Configuration", systemImage: "server.rack")) {
            HStack {
                Text("Host")
                Spacer()
                TextField("Host", text: $settings.serverHost)
                    .multilineTextAlignment(.trailing)
                    .foregroundColor(.secondary)
                    .onSubmit(updateConnection)
            }
            HStack {
                Text("Port")
                Spacer()
                TextField("Port", value: $settings.serverPort, formatter: NumberFormatter())
                    .multilineTextAlignment(.trailing)
                    .foregroundColor(.secondary)
                    .onSubmit(updateConnection)
            }
            HStack {
                Text("Status")
                Spacer()
                Text(wsManager.status.description)
                    .foregroundColor(wsManager.status == .connected ? .green : .yellow)
            }
            VStack(alignment: .leading) {
                Text("Reconnect Delay: \(String(format: "%.1f", settings.reconnectDelay))s")
                Slider(value: $settings.reconnectDelay, in: 1.0...60.0, step: 1.0)
            }
        }
    }

    private var cameraAndDetectionSection: some View {
        Section(header: Label("Camera & Detection", systemImage: "camera.fill")) {
            Toggle("Show detection boxes", isOn: $settings.showDetectionBoxes)
            Toggle("Show detection labels", isOn: $settings.showDetectionLabels)
                .disabled(!settings.showDetectionBoxes)
        }
    }

    private var performanceSection: some View {
        Section(header: Label("Performance", systemImage: "speedometer")) {
            HStack {
                Text("Memory Usage")
                Spacer()
                Text(String(format: "%.1f MB", appState.performanceMetrics.memoryUsage))
                    .foregroundColor(.secondary)
            }
        }
    }

    private var debugSection: some View {
        Section(header: Label("Debug Options", systemImage: "ladybug.fill")) {
            Toggle("Network Logging", isOn: $settings.enableNetworkLogging)
            Toggle("Processing Logs", isOn: $settings.enableProcessingLogs)
            Toggle("Performance Metrics", isOn: $settings.enablePerformanceMetrics)
            Toggle("Websocket Debug", isOn: $settings.enableWebsocketDebug)
        }
    }

    private var devicePairingSection: some View {
        Section(header: Label("Device Pairing", systemImage: "link")) {
            if deviceManager.pairedDevices.isEmpty {
                Text("No devices paired.")
            } else {
                List {
                    ForEach(deviceManager.pairedDevices) { pair in
                        HStack {
                            VStack(alignment: .leading) {
                                Text(pair.serverDevice.name)
                                    .font(.headline)
                                Text("Paired on \(pair.createdAt, style: .date)")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            Spacer()
                            Button("Revoke") {
                                Task {
                                    await deviceManager.revokePair(pairId: pair.id)
                                }
                            }
                            .foregroundColor(.red)
                        }
                    }
                }
            }

            Button("Link a New Device") {
                showingPairingSheet = true
            }
            .disabled(deviceManager.deviceId == nil || !deviceManager.pairedDevices.isEmpty)

            if !deviceManager.pairedDevices.isEmpty {
                Text("You can only have one active pair at a time. Revoke the existing pair to link a new device.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }

    private var aboutSection: some View {
        Section(header: Label("About", systemImage: "info.circle")) {
            HStack {
                Text("App Version")
                Spacer()
                Text("1.0.0")
                    .foregroundColor(.secondary)
            }
            HStack {
                Text("Developer")
                Spacer()
                Text("Riddhiman Rana")
                    .foregroundColor(.secondary)
            }
        }
    }

    private var systemCompatibilitySection: some View {
        Section(header: Label("Device Compatibility", systemImage: "iphone.gen3")) {
            InfoRow(icon: "iphone", label: "Model", value: compatibilityManager.deviceModel)
            InfoRow(icon: "gear", label: "iOS Version", value: compatibilityManager.iosVersion)
            InfoRow(icon: "cpu", label: "Processor", value: compatibilityManager.chipType)
            InfoRow(icon: "memorychip", label: "RAM", value: "\(compatibilityManager.ramGB) GB")

            HStack {
                Text("Overall Compatibility")
                Spacer()
                Image(systemName: compatibilityManager.isCompatible ? "checkmark.circle.fill" : "xmark.circle.fill")
                    .foregroundColor(compatibilityManager.isCompatible ? .green : .red)
            }

            Button(action: { showingCompatibilityDetails = true }) {
                Label("View Details", systemImage: "info.circle")
            }
        }
    }

    private var processingModeSection: some View {
        Section(header: Label("Processing Mode", systemImage: "gearshape.2.fill")) {
            Picker("Mode", selection: $settings.processingMode) {
                Text("Split (VLM on device)").tag("split")
                Text("Full (VLM + LLM on server)").tag("full")
            }
            .pickerStyle(.segmented)
            .onChange(of: settings.processingMode) { newMode in
                wsManager.sendConfiguration(mode: newMode)
                cameraManager.configure(for: newMode)
            }
        }
    }

    private func updateConnection() {
        wsManager.updateServerURL(host: settings.serverHost, port: settings.serverPort)
    }

    private func startPolling() {
        // Fetch immediately on appear
        Task {
            await deviceManager.fetchPairedDevices()
        }
        // Then poll every 10 seconds
        pollingTimer = Timer.scheduledTimer(withTimeInterval: 10, repeats: true) { _ in
            Task {
                print("Polling for paired devices...")
                await deviceManager.fetchPairedDevices()
            }
        }
    }

    private func stopPolling() {
        pollingTimer?.invalidate()
        pollingTimer = nil
        print("Stopped polling for paired devices.")
    }
}

struct SettingsTabView_Previews: PreviewProvider {
    static var previews: some View {
        SettingsTabView()
            .environmentObject(AppStateManager())
            .environmentObject(WebSocketManager())
            .environmentObject(CameraManager())
            .environmentObject(SystemCompatibilityManager())
    }
}
