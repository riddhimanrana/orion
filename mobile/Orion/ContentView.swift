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
            .environmentObject(cameraManager)
            .environmentObject(appState)
            .tabItem {
                Image(systemName: "camera.fill")
                Text("Camera")
            }

            // Tab 2: Debug
            DebugTabView()
                .environmentObject(wsManager)
                .environmentObject(appState)
                .environmentObject(cameraManager)
                .tabItem {
                    Image(systemName: "ladybug.fill")
                    Text("Debug")
                }

            // Tab 3: Settings
            SettingsTabView()
                .environmentObject(appState)
                .environmentObject(wsManager)
                .environmentObject(cameraManager) // Pass cameraManager here
                .tabItem {
                    Image(systemName: "gear")
                    Text("Settings")
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
                if !self.showErrorAlert || !self.alertMessage.starts(with: "Camera Error:") {
                    self.alertMessage = "WebSocket Error: \(wsError.localizedDescription)"
                    self.showErrorAlert = true
                }
                Logger.shared.log("WebSocketManager reported error: \(wsError.localizedDescription)", level: .error, category: .network)
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
                    vlmDescription: nil,
                    vlmConfidence: nil
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
