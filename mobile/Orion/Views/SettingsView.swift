
//
//  SettingsView.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Enhanced settings view for advanced configuration in Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var wsManager: WebSocketManager
    @EnvironmentObject var appState: AppStateManager
    @Environment(\.dismiss) var dismiss

    // Server Configuration
    @State private var serverHost: String = UserDefaults.standard.string(forKey: UserDefaultsKeys.serverHost) ?? ServerConfig.host
    @State private var serverPortString: String = "\(UserDefaults.standard.object(forKey: UserDefaultsKeys.serverPort) as? Int ?? ServerConfig.port)"
    
    // Camera Settings
    @State private var confidenceThreshold: Float = UserDefaults.standard.object(forKey: UserDefaultsKeys.confidenceThreshold) as? Float ?? CameraConfig.confidenceThreshold
    @State private var maxFPS: Int = UserDefaults.standard.object(forKey: UserDefaultsKeys.maxFPS) as? Int ?? CameraConfig.maxFPS
    @State private var sendImages: Bool = UserDefaults.standard.bool(forKey: UserDefaultsKeys.sendImages)
    @State private var showLabels: Bool = UserDefaults.standard.bool(forKey: UserDefaultsKeys.showLabels)
    
    // Debug Settings
    @State private var webSocketLoggingEnabled = WebSocketManager.enableLogging
    @State private var enableProcessingLogs = DebugConfig.enableProcessingLogs
    @State private var enablePerformanceMetrics = DebugConfig.enablePerformanceMetrics
    @State private var enableNetworkLogs = DebugConfig.enableNetworkLogs
    
    // Keyframe Settings
    @State private var keyframeInterval: Double = 1.0
    
    // Alert states
    @State private var showingInvalidPortAlert = false
    @State private var showingSuccessAlert = false
    
    var body: some View {
        NavigationView {
            Form {
                // Server Configuration Section
                serverConfigurationSection
                
                // Camera Settings Section
                cameraSettingsSection
                
                // Performance Section
                performanceSection
                
                // Debug Section
                debugSection
                
                // About Section
                aboutSection
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Reset") {
                        resetToDefaults()
                    }
                    .foregroundColor(.red)
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        applyChanges()
                        dismiss()
                    }
                    .fontWeight(.semibold)
                }
            }
        }
        .alert("Invalid Port", isPresented: $showingInvalidPortAlert) {
            Button("OK") { }
        } message: {
            Text("Please enter a valid port number between 1 and 65535.")
        }
        .alert("Settings Applied", isPresented: $showingSuccessAlert) {
            Button("OK") { }
        } message: {
            Text("Your settings have been successfully applied.")
        }
    }
    
    // MARK: - Server Configuration Section
    private var serverConfigurationSection: some View {
        Section {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Host")
                        .frame(width: 60, alignment: .leading)
                    
                    TextField("192.168.1.100", text: $serverHost)
                        .textFieldStyle(.roundedBorder)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                        .keyboardType(.URL)
                }
                
                HStack {
                    Text("Port")
                        .frame(width: 60, alignment: .leading)
                    
                    TextField("8000", text: $serverPortString)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.numberPad)
                }
                
                // Connection Status
                HStack {
                    Image(systemName: connectionStatusIcon)
                        .foregroundColor(connectionStatusColor)
                    
                    Text(connectionStatusText)
                        .font(.subheadline)
                        .foregroundColor(connectionStatusColor)
                    
                    Spacer()
                }
                .padding(.top, 8)
            }
        } header: {
            Label("Server Configuration", systemImage: "server.rack")
        } footer: {
            Text("Configure the server address for WebSocket connection and data streaming.")
        }
    }
    
    // MARK: - Camera Settings Section
    private var cameraSettingsSection: some View {
        Section {
            // Confidence Threshold
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Confidence Threshold")
                    Spacer()
                    Text("\(confidenceThreshold, specifier: "%.2f")")
                        .foregroundColor(.secondary)
                        .fontWeight(.medium)
                }
                
                Slider(value: $confidenceThreshold, in: 0.1...0.9, step: 0.05)
                    .accentColor(.blue)
                
                Text("Objects with confidence below this threshold will be filtered out")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(.vertical, 4)
            
            // Max FPS
            Stepper("Max FPS: \(maxFPS)", value: $maxFPS, in: 1...60, step: 5)
            
            // Toggle Options
            Toggle("Send Images to Server", isOn: $sendImages)
            Toggle("Show Detection Labels", isOn: $showLabels)
            
        } header: {
            Label("Camera & Detection", systemImage: "camera.fill")
        } footer: {
            Text("Adjust camera processing and object detection parameters for optimal performance.")
        }
    }
    
    // MARK: - Performance Section
    private var performanceSection: some View {
        Section {
            // Keyframe Interval
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Keyframe Interval")
                    Spacer()
                    Text("\(keyframeInterval, specifier: "%.1f")s")
                        .foregroundColor(.secondary)
                        .fontWeight(.medium)
                }
                
                Slider(value: $keyframeInterval, in: 0.1...5.0, step: 0.1)
                    .accentColor(.green)
                
                Text("How often to capture keyframes for scene analysis")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(.vertical, 4)
            
            // Performance Metrics
            if enablePerformanceMetrics {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Current Performance")
                        .font(.subheadline)
                        .fontWeight(.medium)
                    
                    HStack {
                        MetricLabel(title: "FPS", value: String(format: "%.1f", appState.performanceMetrics.fps))
                        MetricLabel(title: "Memory", value: String(format: "%.0f MB", appState.performanceMetrics.memoryUsage))
                    }
                }
                .padding(.vertical, 4)
            }
            
        } header: {
            Label("Performance", systemImage: "speedometer")
        } footer: {
            Text("Configure performance parameters to balance accuracy and battery life.")
        }
    }
    
    // MARK: - Debug Section
    private var debugSection: some View {
        Section {
            Toggle("Network Logging", isOn: $enableNetworkLogs)
            Toggle("Processing Logs", isOn: $enableProcessingLogs)
            Toggle("Performance Metrics", isOn: $enablePerformanceMetrics)
            Toggle("WebSocket Debug", isOn: $webSocketLoggingEnabled)
            
        } header: {
            Label("Debug Options", systemImage: "ladybug.fill")
        } footer: {
            Text("Enable debug features for troubleshooting. Some changes may require app restart.")
        }
    }
    
    // MARK: - About Section
    private var aboutSection: some View {
        Section {
            HStack {
                Text("App Version")
                Spacer()
                Text("1.0.0")
                    .foregroundColor(.secondary)
            }
            
            HStack {
                Text("YOLO11n Model")
                Spacer()
                Text("Loaded")
                    .foregroundColor(.green)
            }
            
            HStack {
                Text("Fast-VLM Model")
                Spacer()
                Text("Ready for Integration")
                    .foregroundColor(.orange)
            }
            
        } header: {
            Label("About", systemImage: "info.circle")
        }
    }
    
    // MARK: - Helper Views
    
    private var connectionStatusIcon: String {
        switch wsManager.status {
        case .connected: return "checkmark.circle.fill"
        case .connecting: return "clock.circle.fill"
        case .disconnected: return "xmark.circle.fill"
        }
    }
    
    private var connectionStatusColor: Color {
        switch wsManager.status {
        case .connected: return .green
        case .connecting: return .yellow
        case .disconnected: return .red
        }
    }
    
    private var connectionStatusText: String {
        switch wsManager.status {
        case .connected: return "Connected to \(serverHost):\(serverPortString)"
        case .connecting: return "Connecting..."
        case .disconnected: return "Disconnected"
        }
    }
    
    // MARK: - Helper Methods
    
    private func applyChanges() {
        // Validate port number
        guard let port = Int(serverPortString), port > 0, port <= 65535 else {
            showingInvalidPortAlert = true
            return
        }
        
        // Save server settings
        UserDefaults.standard.set(serverHost, forKey: UserDefaultsKeys.serverHost)
        UserDefaults.standard.set(port, forKey: UserDefaultsKeys.serverPort)
        
        // Save camera settings
        UserDefaults.standard.set(confidenceThreshold, forKey: UserDefaultsKeys.confidenceThreshold)
        UserDefaults.standard.set(maxFPS, forKey: UserDefaultsKeys.maxFPS)
        UserDefaults.standard.set(sendImages, forKey: UserDefaultsKeys.sendImages)
        UserDefaults.standard.set(showLabels, forKey: UserDefaultsKeys.showLabels)
        
        // Apply debug settings
        WebSocketManager.enableLogging = webSocketLoggingEnabled
        DebugConfig.enableProcessingLogs = enableProcessingLogs
        DebugConfig.enablePerformanceMetrics = enablePerformanceMetrics
        DebugConfig.enableNetworkLogs = enableNetworkLogs
        
        // Update WebSocket connection if needed
        if wsManager.status != .disconnected {
            wsManager.updateServerURL(host: serverHost, port: port)
        }
        
        // Log changes
        Logger.shared.log("Settings applied - Server: \(serverHost):\(port), Confidence: \(confidenceThreshold)", category: .general)
        
        showingSuccessAlert = true
    }
    
    private func resetToDefaults() {
        serverHost = ServerConfig.host
        serverPortString = "\(ServerConfig.port)"
        confidenceThreshold = CameraConfig.confidenceThreshold
        maxFPS = CameraConfig.maxFPS
        sendImages = true
        showLabels = true
        keyframeInterval = 1.0
        
        // Reset debug settings
        webSocketLoggingEnabled = false
        enableProcessingLogs = false
        enablePerformanceMetrics = false
        enableNetworkLogs = false
    }
}

// MARK: - Supporting Views

struct MetricLabel: View {
    let title: String
    let value: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
            
            Text(value)
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundColor(.primary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}