import SwiftUI
import Combine

struct ContentView: View {
    @EnvironmentObject var cameraManager: CameraManager
    @EnvironmentObject var appState: AppStateManager
    @StateObject private var wsManager = WebSocketManager()

    @State private var latestAnalysis: SceneAnalysis?
    @State private var analysisTimestamp: TimeInterval = 0
    @State private var showErrorAlert = false
    @State private var alertMessage = ""

    var body: some View {
        TabView {
            // Tab 1: Camera Feed
            CameraTabView(
                wsManager: wsManager,
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
        }
        .onAppear {
            setupManagers()
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
    
    private func setupManagers() {
        wsManager.onError = { wsError in
            DispatchQueue.main.async {
                // Only show alerts for critical, non-repetitive errors.
                switch wsError {
                case .connectionFailed:
                    // Only show alert if we were previously connected or if it's a persistent failure
                    // and not just a transient initial connection attempt.
                    if self.wsManager.status == .connected {
                        self.alertMessage = "Connection Lost: \(wsError.localizedDescription). Attempting to reconnect."
                        self.showErrorAlert = true
                    } else {
                        // For initial connection failures, log but don't alert immediately.
                        // The UI status will show "Connecting" or "Disconnected".
                        Logger.shared.log("Initial connection failed or transient error: \(wsError.localizedDescription)", level: .warning, category: .network)
                    }
                case .invalidURL:
                    self.alertMessage = "Configuration Error: Invalid server URL. Please check settings."
                    self.showErrorAlert = true
                case .serverError(let msg):
                    self.alertMessage = "Server Error: \(msg)"
                    self.showErrorAlert = true
                case .sendFailed, .invalidData:
                    // Log these but don't show an alert to the user as they might be transient.
                    Logger.shared.log("Non-critical WebSocket issue: \(wsError.localizedDescription)", level: .warning, category: .network)
                }
            }
        }
        
        wsManager.onAnalysis = { analysis in
            DispatchQueue.main.async {
                withAnimation(.easeInOut(duration: 0.2)) {
                    self.latestAnalysis = analysis
                    self.analysisTimestamp = Date().timeIntervalSince1970
                }
            }
        }
        
        // The `onFrameProcessed` closure is no longer needed as we send frames asynchronously.
        
        cameraManager.setDetectionCallback { imageData, detections, vlmDescription, vlmConfidence in
            let currentProcessingMode = SettingsManager.shared.processingMode
            
            let frameData: FrameDataMessage
            
            if currentProcessingMode == "full" {
                // In full mode, send image data, no on-device detections or VLM
                frameData = FrameDataMessage(
                    frameId: UUID().uuidString,
                    timestamp: Date().timeIntervalSince1970,
                    imageData: imageData?.base64EncodedString(),
                    detections: nil,
                    deviceId: UIDevice.current.identifierForVendor?.uuidString,
                    vlmDescription: nil, vlmConfidence: vlmConfidence
                )
            } else { // "split" mode
                // In split mode, send on-device detections and VLM, no image data
                frameData = FrameDataMessage(
                    frameId: UUID().uuidString,
                    timestamp: Date().timeIntervalSince1970,
                    imageData: nil,
                    detections: detections,
                    deviceId: UIDevice.current.identifierForVendor?.uuidString,
                    vlmDescription: vlmDescription,
                    vlmConfidence: vlmConfidence
                )
            }
            
            if wsManager.status == .connected {
                wsManager.sendFrame(frameData)
                // We no longer wait for an acknowledgment, allowing the next frame to be processed immediately.
                Logger.shared.log("Sending frame \(frameData.frameId) to server.", category: .network)
            } else {
                Logger.shared.log("WebSocket not connected, skipping frame send.", category: .network)
            }
        }
        
        wsManager.connect()
        wsManager.setCameraManager(cameraManager)
        
        #if DEBUG
        WebSocketManager.enableLogging = DebugConfig.enableNetworkLogs
        #endif
    }
}

// MARK: - Preview
struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        let appState = AppStateManager()
        let cameraManager = CameraManager()
        
        appState.performanceMetrics = PerformanceMetrics(fps: 29.5, memoryUsage: 120.3, batteryLevel: 0.75, temperature: 0)

        return ContentView()
            .environmentObject(appState)
            .environmentObject(cameraManager)
    }
}