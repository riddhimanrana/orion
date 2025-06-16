import SwiftUI
import Combine // Ensure Combine is imported for .onReceive

struct ContentView: View {
    @EnvironmentObject var cameraManager: CameraManager
    @EnvironmentObject var appState: AppStateManager
    @StateObject private var wsManager = WebSocketManager()
    
    @State private var latestAnalysis: SceneAnalysis?
    @State private var analysisTimestamp: TimeInterval = 0
    @State private var showErrorAlert = false
    @State private var alertMessage = ""
    @State private var showingSettingsSheet = false // Added for settings sheet

    var body: some View {
        ZStack {
            // Camera view
            CameraView()
                .environmentObject(cameraManager)
                .ignoresSafeArea()
            
            VStack {
                // Connection status, Performance Metrics & Settings Button
                HStack {
                    connectionStatusView
                    Spacer()
                    performanceMetricsView
                    // Settings Button
                    Button {
                        showingSettingsSheet = true
                    } label: {
                        Image(systemName: "gearshape.fill")
                            .imageScale(.large)
                            .foregroundColor(.white)
                            .padding(8)
                            .background(Circle().fill(.ultraThinMaterial))
                    }
                    .padding(.leading, 8)
                }
                .padding(.top, safeAreaTopInset)
                .padding(.horizontal)

                Spacer()
                
                // Scene understanding
                if let analysis = latestAnalysis {
                    SceneUnderstandingView(
                        analysis: analysis,
                        timestamp: analysisTimestamp
                    )
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .padding()
                }
            }
        }
        .onAppear {
            setupManagers()
            cameraManager.startStreaming()
        }
        .onReceive(cameraManager.$error) { cameraError in
            if let camError = cameraError, !camError.isEmpty {
                self.alertMessage = "Camera Error: \(camError)"
                self.showErrorAlert = true
                Logger.shared.log("CameraManager published error: \(camError)", level: .error, category: .camera)
            }
        }
        .alert("Application Alert", isPresented: $showErrorAlert) {
            Button("OK") { }
        } message: {
            Text(alertMessage)
        }
        .sheet(isPresented: $showingSettingsSheet) { // Added sheet presentation
            SettingsView()
                .environmentObject(wsManager)
                .environmentObject(appState) // Pass appState if SettingsView needs it
        }
    }

    private var safeAreaTopInset: CGFloat {
        let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene
        return windowScene?.windows.first?.safeAreaInsets.top ?? 0
    }
    
    private var connectionStatusView: some View {
        HStack {
            Circle()
                .fill(webSocketStatusColor)
                .frame(width: 10, height: 10)
            
            Text(webSocketStatusText)
                .font(.caption)
                .foregroundColor(.white)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(.ultraThinMaterial)
        .cornerRadius(20)
    }
    
    private var webSocketStatusColor: Color {
        switch wsManager.status {
        case .connected:
            return .green
        case .connecting:
            return .yellow
        case .disconnected:
            return .red
        }
    }
    
    private var webSocketStatusText: String {
        switch wsManager.status {
        case .connected:
            return "Connected"
        case .connecting:
            return "Connecting..."
        case .disconnected:
            return "Disconnected"
        }
    }

    private var performanceMetricsView: some View {
        VStack(alignment: .trailing, spacing: 2) {
            Text("FPS: \(String(format: "%.1f", appState.performanceMetrics.fps))")
            Text("Mem: \(String(format: "%.1f", appState.performanceMetrics.memoryUsage))MB")
        }
        .font(.caption)
        .foregroundColor(.white)
        .padding(EdgeInsets(top: 4, leading: 8, bottom: 4, trailing: 8))
        .background(.ultraThinMaterial)
        .cornerRadius(8)
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
                withAnimation(.easeInOut(duration: UIConfig.standardAnimationDuration)) {
                    self.latestAnalysis = analysis
                    self.analysisTimestamp = Date().timeIntervalSince1970
                }
            }
        }
        
        cameraManager.setDetectionCallback { imageData, detections in
            let frameData = DetectionFrame(
                frameId: UUID().uuidString,
                timestamp: Date().timeIntervalSince1970,
                imageData: imageData?.base64EncodedString(),
                detections: detections
            )
            
            if wsManager.status == .connected {
                wsManager.sendFrame(frameData)
            }
        }
        
        wsManager.connect()
        
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
