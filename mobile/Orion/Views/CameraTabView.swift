
//
//  CameraTabView.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 6/16/25.
//  Main camera tab view with live feed, overlays, and controls for Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//

import SwiftUI
import Combine
import WebRTC

struct CameraTabView: View {
    @Environment(\.colorScheme) var colorScheme
    @EnvironmentObject var cameraManager: CameraManager
    @EnvironmentObject var appState: AppStateManager
    @EnvironmentObject var signalingClient: SignalingClient
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var deviceManager: DeviceManager
    @EnvironmentObject var compatibilityManager: SystemCompatibilityManager

    @Binding var latestAnalysis: SceneAnalysis?
    @Binding var analysisTimestamp: TimeInterval

    @State private var isCameraActive = false
    @State private var showingSettingsSheet = false
    @State private var showingCameraSwitcher = false
    @State private var isDisconnecting = false
    // @State private var showSceneAnalysis = false // Temporarily disabled

    // Namespace for smooth camera switcher animation
    @Namespace private var cameraAnimation

    private var safeAreaTopInset: CGFloat {
        let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene
        return windowScene?.windows.first?.safeAreaInsets.top ?? 0
    }

    var body: some View {
        ZStack {
            Group {
                if isCameraActive {
                    NavigationView {
                        ZStack(alignment: .top) {
                            // Camera view with detection overlays
                            CameraView()
                                .environmentObject(cameraManager)
                                .ignoresSafeArea()

                            // Top overlay with status and controls
                            HStack {
                                connectionStatusView
                                disconnectButton
                                Spacer()
                                // The camera switcher is now in its own VStack for positioning
                            }
                            .padding(.top, (safeAreaTopInset == 0 ? -35 : safeAreaTopInset - 35))
                            .padding(.horizontal)

                            // Position the entire camera switcher UI in the top right
                            VStack(spacing: 12) {
                                if showingCameraSwitcher {
                                    CameraSwitcherOverlay(
                                        showingCameraSwitcher: $showingCameraSwitcher,
                                        animation: cameraAnimation
                                    )
                                    .environmentObject(cameraManager)
                                }
                                cameraSwitchButton
                            }
                            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
                            .padding(.top, (safeAreaTopInset == 0 ? -35 : safeAreaTopInset - 35))
                            .padding(.trailing)

                            VStack {
                                Spacer()
                                // Bottom overlay with detection stats
                                if !cameraManager.lastDetections.isEmpty {
                                    detectionStatsView
                                        .padding(.horizontal)
                                        .padding(.bottom, 20)
                                }
                            }
                        }
                        .navigationBarHidden(true)
                    }
                    .navigationViewStyle(StackNavigationViewStyle())
                    .sheet(isPresented: $showingSettingsSheet) {
                        // Pass all necessary environment objects to the settings view
                        SettingsTabView()
                            .environmentObject(appState)
                            .environmentObject(cameraManager)
                            .environmentObject(signalingClient)
                            .environmentObject(webRTCManager)
                            .environmentObject(deviceManager)
                            .environmentObject(compatibilityManager)
                    }
                } else {
                    StartView(isCameraActive: $isCameraActive, onStart: { completion in
                        // Run heavy tasks in background
                        DispatchQueue.global(qos: .userInitiated).async {
                            cameraManager.startStreaming()
                            // Switch back to main thread to call completion
                            DispatchQueue.main.async {
                                completion()
                            }
                        }
                    })
                }
            }
            .disabled(isDisconnecting)

            // Disconnecting overlay
            if isDisconnecting {
                Color.black.opacity(0.6).edgesIgnoringSafeArea(.all)
                VStack(spacing: 20) {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        .scaleEffect(2.0)
                    Text("Disconnecting...")
                        .font(.title3)
                        .foregroundColor(.white.opacity(0.8))
                }
                .transition(.opacity)
            }
        }
    }

    // MARK: - Disconnect Button
    private var disconnectButton: some View {
        Button(action: {
            let haptic = UIImpactFeedbackGenerator(style: .medium)
            haptic.impactOccurred()

            withAnimation {
                isDisconnecting = true
            }

            // Perform cleanup in the background
            DispatchQueue.global(qos: .userInitiated).async {
                cameraManager.stopStreaming()
                webRTCManager.disconnect() // Disconnect WebRTC

                // Switch back to main thread to update UI
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { // Small delay for animation
                    withAnimation(.easeOut(duration: 0.3)) {
                        isCameraActive = false
                    }
                    isDisconnecting = false
                }
            }
        }) {
            Image(systemName: "phone.down.fill")
                .font(.system(size: 20))
                .foregroundColor(.white)
                .frame(width: 44, height: 44)
                .background(Color.red)
                .padding(.horizontal, 12)
                .clipShape(Circle())
                .shadow(radius: 5)
        }
        .accessibilityLabel("Disconnect")
        .disabled(isDisconnecting)
    }

    // MARK: - Camera Switcher Button
    private var cameraSwitchButton: some View {
        Button(action: {
            withAnimation(.interpolatingSpring(stiffness: 300, damping: 20)) {
                showingCameraSwitcher.toggle()
            }
        }) {
            // The button now shows the current zoom/camera state
            if let option = cameraManager.currentCameraOption, !showingCameraSwitcher {
                if option.isFrontCamera {
                    Image(systemName: "arrow.triangle.2.circlepath.camera.fill")
                        .font(.system(size: 18))
                        .frame(width: 44, height: 44)
                        .matchedGeometryEffect(id: "front_camera_icon", in: cameraAnimation)
                } else {
                    Text(option.displayName)
                        .font(.system(size: 14, weight: .bold))
                        .frame(width: 44, height: 44)
                        .matchedGeometryEffect(id: option.id, in: cameraAnimation)
                }
            } else {
                // Close button when switcher is open
                Image(systemName: "xmark")
                    .font(.system(size: 14, weight: .bold))
                    .frame(width: 44, height: 44)
            }
        }
        .foregroundColor(.white)
        .background(Color.black.opacity(0.5))
        .clipShape(Circle())
        .accessibilityLabel("Switch Camera")
    }

    // MARK: - Connection Status View
    private var connectionStatusView: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(p2pStatusColor)
                .frame(width: 10, height: 10)
                .animation(.easeInOut, value: webRTCManager.connectionState)

            Text(p2pStatusText)
                .font(.caption.weight(.medium))
                .foregroundColor(colorScheme == .dark ? .white : .black)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(.ultraThinMaterial)
        .cornerRadius(20)
    }

    private var p2pStatusColor: Color {
        switch webRTCManager.connectionState {
        case .connected, .completed: return .green
        case .new, .checking: return .yellow
        default: return .red
        }
    }

    private var p2pStatusText: String {
        webRTCManager.connectionState.description
    }

    // MARK: - Detection Stats View
    private var detectionStatsView: some View {
        HStack(spacing: 16) {
            VStack(spacing: 2) {
                Text("\(cameraManager.lastDetections.count)")
                    .font(.title2.weight(.bold))
                    .foregroundColor(colorScheme == .dark ? .white : .black)
                Text("Objects")
                    .font(.caption)
                    .foregroundColor(colorScheme == .dark ? .white.opacity(0.8) : .black.opacity(0.8))
            }
            Divider().frame(height: 30)
            VStack(spacing: 2) {
                Text(String(format: "%.0f%%", averageConfidence))
                    .font(.title2.weight(.bold))
                    .foregroundColor(colorScheme == .dark ? .white : .black)
                Text("Confidence")
                    .font(.caption)
                    .foregroundColor(colorScheme == .dark ? .white.opacity(0.8) : .black.opacity(0.8))
            }
            Divider().frame(height: 30)
            VStack(spacing: 2) {
                Image(systemName: processingIndicator)
                    .font(.title2.weight(.bold))
                    .foregroundColor(colorScheme == .dark ? .white : .black)
                Text("Processing")
                    .font(.caption)
                    .foregroundColor(colorScheme == .dark ? .white.opacity(0.8) : .black.opacity(0.8))
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
        .background(.ultraThinMaterial)
        .cornerRadius(16)
        .animation(.easeInOut, value: cameraManager.lastDetections.count)
    }

    private var averageConfidence: Double {
        guard !cameraManager.lastDetections.isEmpty else { return 0 }
        let total = cameraManager.lastDetections.reduce(0) { $0 + $1.confidence }
        return Double(total) / Double(cameraManager.lastDetections.count) * 100
    }

    private var processingIndicator: String {
        cameraManager.lastDetections.isEmpty ? "magnifyingglass" : "checkmark.circle.fill"
    }
}

// MARK: - Preview
struct CameraTabView_Previews: PreviewProvider {
    static var previews: some View {
        let appState = AppStateManager()
        let cameraManager = CameraManager()
        let authManager = AuthManager()
        let deviceManager = DeviceManager(supabase: authManager.supabase)
        let apiService = APIService(supabase: authManager.supabase)
        let signalingClient = SignalingClient(apiService: apiService, deviceManager: deviceManager)
        let webRTCManager = WebRTCManager(signalingClient: signalingClient)
        let compatibilityManager = SystemCompatibilityManager()

        return CameraTabView(
            latestAnalysis: .constant(nil),
            analysisTimestamp: .constant(0)
        )
        .environmentObject(appState)
        .environmentObject(cameraManager)
        .environmentObject(signalingClient)
        .environmentObject(webRTCManager)
        .environmentObject(deviceManager)
        .environmentObject(compatibilityManager)
    }
}
