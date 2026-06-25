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

// Fallback stub for environments where the overlay file isn't indexed (e.g., some analyzers on macOS)
#if !canImport(UIKit)
struct VoiceInputOverlay: View { var body: some View { EmptyView() } }
#endif

// Wrapper to avoid direct dependency on external file during analysis
private struct InlineVoiceInputOverlay: View {
    @State private var isActive = false
    var body: some View {
        HStack(spacing: 12) {
            Text("Ask Orion anything…")
                .font(.body)
                .foregroundStyle(.primary.opacity(0.7))
                .frame(maxWidth: .infinity, alignment: .leading)
            Button(action: { withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) { isActive.toggle() } }) {
                Image(systemName: isActive ? "mic.fill" : "mic")
                    .font(.system(size: 20, weight: .medium))
                    .foregroundStyle(isActive ? .white : .primary)
                    .frame(width: 44, height: 44)
                    .background(Circle().fill(isActive ? Color.blue : Color.clear))
            }
            .buttonStyle(.plain)
            .accessibilityLabel(isActive ? "Stop voice input" : "Start voice input")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .strokeBorder(Color.primary.opacity(0.06), lineWidth: 0.5)
        )
        .shadow(color: Color.black.opacity(0.08), radius: 20, x: 0, y: 10)
    }
}

struct CameraTabView: View {
    @Environment(\.colorScheme) var colorScheme
    @EnvironmentObject var cameraManager: CameraManager
    @EnvironmentObject var appState: AppStateManager
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var signalingClient: SignalingClient
    @ObservedObject var wsManager: WebSocketManager

    @Binding var latestAnalysis: SceneAnalysis?
    @Binding var analysisTimestamp: TimeInterval

    @State private var isCameraActive = false
    @State private var showingSettingsSheet = false
    @State private var showingCameraSwitcher = false
    @State private var isDisconnecting = false
    @State private var showingVoiceInput = true // Always visible by default
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
                                // Camera switcher is in its own VStack for positioning
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
                                        .padding(.bottom, 8) // Reduced padding to make room for voice bar
                                }
                            }
                            
                            // Apple Intelligence Voice Input Overlay - prominent hovering bar
                            VoiceInputOverlay(isVisible: $showingVoiceInput)
                                .allowsHitTesting(true)
                        }
                        .navigationBarHidden(true)
                    }
                    .navigationViewStyle(StackNavigationViewStyle())
                } else {
                    StartView(isCameraActive: $isCameraActive, onStart: { completion in
                        // Run camera startup
                        cameraManager.startStreaming()
                        completion()
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

            // Perform cleanup using proper async/await
            Task {
                cameraManager.stopStreaming()
                wsManager.disconnect()

                // Small delay for animation
                try? await Task.sleep(nanoseconds: 500_000_000)
                
                await MainActor.run {
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
            showingCameraSwitcher.toggle()
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
                .fill(connectionStatusColor)
                .frame(width: 10, height: 10)

            Text(connectionStatusText)
                .font(.caption.weight(.medium))
                .foregroundColor(colorScheme == .dark ? .white : .black)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(.ultraThinMaterial)
        .cornerRadius(20)
    }

    private var connectionStatusColor: Color {
        if (webRTCManager.connectionState == .connected || webRTCManager.connectionState == .completed) && webRTCManager.dataChannelState == .open {
            return .green
        }

        if webRTCManager.connectionState == .checking ||
            webRTCManager.dataChannelState == .connecting ||
            signalingClient.connectionState == .connecting {
            return .yellow
        }

        if signalingClient.connectionState == .connected {
            return .blue
        }

        return .red
    }

    private var connectionStatusText: String {
        if (webRTCManager.connectionState == .connected || webRTCManager.connectionState == .completed) && webRTCManager.dataChannelState == .open {
            return "Mac Connected"
        }

        if webRTCManager.connectionState == .checking || webRTCManager.dataChannelState == .connecting {
            return "WebRTC"
        }

        switch signalingClient.connectionState {
        case .connected:
            return "Signal Ready"
        case .connecting:
            return "Signaling"
        case .disconnected:
            return "Mac Offline"
        }
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
        let wsManager = WebSocketManager()
        let authManager = AuthManager()
        let deviceManager = DeviceManager(supabase: authManager.supabase)
        let apiService = APIService(supabase: authManager.supabase)
        let signalingClient = SignalingClient(apiService: apiService, deviceManager: deviceManager)
        let webRTCManager = WebRTCManager(signalingClient: signalingClient)

        appState.performanceMetrics = PerformanceMetrics(
            fps: 29.5,
            memoryUsage: 120.3,
            batteryLevel: 0.75,
            temperature: 0
        )

        return CameraTabView(
            wsManager: wsManager,
            latestAnalysis: .constant(nil),
            analysisTimestamp: .constant(0)
        )
        .environmentObject(appState)
        .environmentObject(cameraManager)
        .environmentObject(webRTCManager)
        .environmentObject(signalingClient)
    }
}
