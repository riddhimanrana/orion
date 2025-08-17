//
//  OrionApp.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Main app entry point and app state management for Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//
import SwiftUI
import Combine
import MLXVLM

@main
struct OrionApp: App {
    // Environment object to share app state
    @StateObject private var appState: AppStateManager
    @StateObject private var cameraManager: CameraManager
    @StateObject private var webSocketManager: WebSocketManager
    @StateObject private var authManager: AuthManager
    @StateObject private var deviceManager: DeviceManager
    @StateObject private var compatibilityManager: SystemCompatibilityManager
    @StateObject private var webRTCManager: WebRTCManager
    @StateObject private var signalingClient: SignalingClient
    @StateObject private var apiService: APIService

    // Lazily initialize model-related objects
    @State private var objectDetector: ObjectDetector?
    @State private var fastVLMModel: FastVLMModel?
    @State private var showCompatibilityCheck = false

    init() {
        // Initialize all managers first
        let auth = AuthManager()
        let device = DeviceManager(supabase: auth.supabase)
        let api = APIService(supabase: auth.supabase)
        let signaling = SignalingClient(apiService: api, deviceManager: device)
        let webrtc = WebRTCManager(signalingClient: signaling)
        let camera = CameraManager()

        // Set state objects
        _authManager = StateObject(wrappedValue: auth)
        _deviceManager = StateObject(wrappedValue: device)
        _apiService = StateObject(wrappedValue: api)
        _signalingClient = StateObject(wrappedValue: signaling)
        _webRTCManager = StateObject(wrappedValue: webrtc)
        _cameraManager = StateObject(wrappedValue: camera)

        // App-level managers
        _appState = StateObject(wrappedValue: AppStateManager())
        _webSocketManager = StateObject(wrappedValue: WebSocketManager()) // Note: This is for the old flow, might be deprecated
        _compatibilityManager = StateObject(wrappedValue: SystemCompatibilityManager())

        // Now that all managers are initialized, inject dependencies
        camera.setup(webRTCManager: webrtc)

        // Configure app appearance
        configureAppearance()

        // Setup logging
        setupLogging()

        // Log app launch
        logInfo("Orion Vision launched", category: .general)
    }

    var body: some Scene {
        WindowGroup {
            Group {
                if authManager.session == nil {
                    LoginView()
                } else {
                    ContentView()
                        .onAppear {
                            if objectDetector == nil { objectDetector = ObjectDetector() }
                            if fastVLMModel == nil { fastVLMModel = FastVLMModel() }

                            // Connect signaling and WebRTC
                            Task { await signalingClient.connect() }
                            Task { await webRTCManager.connect() }

                            #if DEBUG
                            WebSocketManager.enableLogging = DebugConfig.enableNetworkLogs
                            #endif
                        }
                }
            }
            .environmentObject(appState)
            .environmentObject(cameraManager)
            .environmentObject(webSocketManager)
            .environmentObject(authManager)
            .environmentObject(deviceManager)
            .environmentObject(compatibilityManager)
            .environmentObject(webRTCManager)
            .environmentObject(signalingClient)
            .environmentObject(apiService)
            .environmentObject(objectDetector ?? ObjectDetector()) // Provide a default instance
            .environmentObject(fastVLMModel ?? FastVLMModel()) // Provide a default instance
            .onOpenURL { url in
                Task {
                    await authManager.handleSessionCallback(from: url)
                }
            }
            .onChange(of: authManager.session) { _, newSession in
                if newSession != nil && deviceManager.deviceId == nil {
                    Task {
                        await deviceManager.registerDeviceIfNeeded(type: "ios")
                    }
                }
            }
            .onAppear {
                // Show compatibility check on first launch or if not yet shown
                let hasShownCompatibilityCheck = UserDefaults.standard.bool(forKey: "hasShownCompatibilityCheck")
                if !hasShownCompatibilityCheck {
                    showCompatibilityCheck = true
                }
            }
            .sheet(isPresented: $showCompatibilityCheck) {
                CompatibilityCheckView()
                    .environmentObject(compatibilityManager)
                    .onDisappear {
                        UserDefaults.standard.set(true, forKey: "hasShownCompatibilityCheck")
                    }
            }
            // Enable/disable idle timer when streaming starts/stops (iOS17+ style)
            .onChange(of: appState.isStreaming) { _, newStreaming in
                UIApplication.shared.isIdleTimerDisabled = newStreaming
            }
            // Handle background transition
            .onReceive(
                NotificationCenter.default.publisher(
                    for: UIApplication.willResignActiveNotification
                )
            ) { _ in
                appState.handleBackgroundTransition()
            }
            // Handle foreground transition
            .onReceive(
                NotificationCenter.default.publisher(
                    for: UIApplication.willEnterForegroundNotification
                )
            ) { _ in
                appState.handleForegroundTransition()
            }
        }
    }

    private func configureAppearance() {
        // Configure navigation bar for dark theme
        let navBarAppearance = UINavigationBarAppearance()
        navBarAppearance.configureWithOpaqueBackground()
        navBarAppearance.backgroundColor = .systemBackground
        navBarAppearance.titleTextAttributes = [
            .foregroundColor: UIColor.label
        ]
        navBarAppearance.largeTitleTextAttributes = [
            .foregroundColor: UIColor.label
        ]

        UINavigationBar.appearance().standardAppearance = navBarAppearance
        UINavigationBar.appearance().compactAppearance = navBarAppearance
        UINavigationBar.appearance().scrollEdgeAppearance = navBarAppearance

        // Configure tab bar with proper iOS styling
        let tabBarAppearance = UITabBarAppearance()
        tabBarAppearance.configureWithOpaqueBackground()
        tabBarAppearance.backgroundColor = .systemBackground

        // Configure normal state
        tabBarAppearance.stackedLayoutAppearance.normal.iconColor = .systemGray
        tabBarAppearance.stackedLayoutAppearance.normal.titleTextAttributes = [
            .foregroundColor: UIColor.systemGray
        ]

        // Configure selected state
        tabBarAppearance.stackedLayoutAppearance.selected.iconColor = .systemBlue
        tabBarAppearance.stackedLayoutAppearance.selected.titleTextAttributes = [
            .foregroundColor: UIColor.systemBlue
        ]

        // Apply tab bar appearance
        UITabBar.appearance().standardAppearance = tabBarAppearance
        UITabBar.appearance().scrollEdgeAppearance = tabBarAppearance

        // Configure tab bar tint colors
        UITabBar.appearance().tintColor = .systemBlue
        UITabBar.appearance().unselectedItemTintColor = .systemGray
    }

    private func setupLogging() {
        #if DEBUG
        // Enable all debug logging in debug builds
        DebugConfig.enableNetworkLogs = true
        DebugConfig.enableProcessingLogs = true
        DebugConfig.enablePerformanceMetrics = true
        #endif
    }
}

/// App state management
class AppStateManager: ObservableObject {
    @Published var isStreaming = false
    @Published var currentState = AppState.initializing
    @Published var performanceMetrics = PerformanceMetrics()

    private let performanceMonitor = PerformanceMonitor()
    private var backgroundTask: UIBackgroundTaskIdentifier = .invalid

    init() {
        // Start monitoring performance if enabled
        if DebugConfig.enablePerformanceMetrics {
            performanceMonitor.startMonitoring { [weak self] metrics in
                self?.performanceMetrics = metrics
            }
        }
    }

    func handleBackgroundTransition() {
        backgroundTask = UIApplication.shared.beginBackgroundTask { [weak self] in
            self?.endBackgroundTask()
        }
        logInfo("App entering background", category: .general)
    }

    func handleForegroundTransition() {
        endBackgroundTask()
        logInfo("App entering foreground", category: .general)
    }

    private func endBackgroundTask() {
        if backgroundTask != .invalid {
            UIApplication.shared.endBackgroundTask(backgroundTask)
            backgroundTask = .invalid
        }
    }

    deinit {
        endBackgroundTask()
        performanceMonitor.stopMonitoring()
    }
}

/// Performance monitoring
class PerformanceMonitor {
    private var timer: Timer?
    private let updateInterval: TimeInterval = 1.0

    func startMonitoring(callback: @escaping (PerformanceMetrics) -> Void) {
        timer = Timer.scheduledTimer(withTimeInterval: updateInterval, repeats: true) { _ in
            var metrics = PerformanceMetrics()

            // Battery
            UIDevice.current.isBatteryMonitoringEnabled = true
            metrics.batteryLevel = UIDevice.current.batteryLevel

            // Temperature: not supported on iOS devices, default to 0
            metrics.temperature = 0

            // Memory usage
            var info = task_vm_info_data_t()
            var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size) / 4
            let kerr: kern_return_t = withUnsafeMutablePointer(to: &info) {
                $0.withMemoryRebound(to: integer_t.self, capacity: 1) {
                    task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count)
                }
            }
            if kerr == KERN_SUCCESS {
                metrics.memoryUsage = Double(info.phys_footprint) / 1024.0 / 1024.0
            }

            callback(metrics)
        }
    }

    func stopMonitoring() {
        timer?.invalidate()
        timer = nil
        UIDevice.current.isBatteryMonitoringEnabled = false
    }
}

/// Shared debug flags
