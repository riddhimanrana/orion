import SwiftUI
import Combine

@main
struct OrionApp: App {
    // Environment object to share app state
    @StateObject private var appState = AppStateManager()
    @StateObject private var cameraManager = CameraManager() // Create CameraManager instance
    
    init() {
        // Configure app appearance
        configureAppearance()
        
        // Setup logging
        setupLogging()
        
        // Log app launch
        logInfo("Orion Live Vision launched", category: .general)
    }
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .environmentObject(cameraManager) // Provide CameraManager to the environment
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
        // Configure navigation bar
        let navBarAppearance = UINavigationBarAppearance()
        navBarAppearance.configureWithOpaqueBackground()
        navBarAppearance.backgroundColor = .black
        navBarAppearance.titleTextAttributes = [
            .foregroundColor: UIColor.white
        ]
        navBarAppearance.largeTitleTextAttributes = [
            .foregroundColor: UIColor.white
        ]
        
        UINavigationBar.appearance().standardAppearance = navBarAppearance
        UINavigationBar.appearance().compactAppearance = navBarAppearance
        UINavigationBar.appearance().scrollEdgeAppearance = navBarAppearance
        
        // Configure tab bar
        let tabBarAppearance = UITabBarAppearance()
        tabBarAppearance.configureWithOpaqueBackground()
        tabBarAppearance.backgroundColor = .black
        
        UITabBar.appearance().standardAppearance = tabBarAppearance
        UITabBar.appearance().scrollEdgeAppearance = tabBarAppearance
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
            var info = mach_task_basic_info()
            var count = mach_msg_type_number_t(MemoryLayout<mach_task_basic_info>.size) / 4
            let kerr: kern_return_t = withUnsafeMutablePointer(to: &info) {
                $0.withMemoryRebound(to: integer_t.self, capacity: 1) {
                    task_info(mach_task_self_, task_flavor_t(MACH_TASK_BASIC_INFO), $0, &count)
                }
            }
            if kerr == KERN_SUCCESS {
                metrics.memoryUsage = Double(info.resident_size) / 1024.0 / 1024.0
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
