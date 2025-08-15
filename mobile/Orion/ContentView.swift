//
//  ContentView.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Main SwiftUI entry point for Orion Live’s tabbed interface.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//
import SwiftUI
import Combine
import Supabase

struct ContentView: View {
    @EnvironmentObject var cameraManager: CameraManager
    @EnvironmentObject var appState: AppStateManager
    @EnvironmentObject var webRTCManager: WebRTCManager

    @State private var latestAnalysis: SceneAnalysis? // This will be populated via WebRTC data channel
    @State private var analysisTimestamp: TimeInterval = 0
    @State private var showErrorAlert = false
    @State private var alertMessage = ""

    var body: some View {
        TabView {
            // Tab 1: Camera Feed
            CameraTabView(
                latestAnalysis: $latestAnalysis,
                analysisTimestamp: $analysisTimestamp
            )
                .tabItem {
                    Label("Camera", systemImage: "camera.fill")
                }

            DebugTabView()
                .tabItem {
                    Label("Debug", systemImage: "ladybug.fill")
                }
            
            SettingsTabView()
                .tabItem {
                    Label("Settings", systemImage: "gear")
                }
            AccountView()
                .tabItem {
                    Label("Account", systemImage: "person.crop.circle")
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
            }
        }
        .alert("Application Alert", isPresented: $showErrorAlert) {
            Button("OK") { }
        } message: {
            Text(alertMessage)
        }
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
