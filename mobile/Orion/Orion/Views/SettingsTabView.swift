import SwiftUI
import Combine

struct SettingsTabView: View {
    @StateObject private var settings = SettingsManager.shared
    @EnvironmentObject var appState: AppStateManager
    @EnvironmentObject var wsManager: WebSocketManager
    @EnvironmentObject var cameraManager: CameraManager

    var body: some View {
        NavigationView {
            Form {
                serverConfigurationSection
                processingModeSection
                cameraAndDetectionSection
                performanceSection
                debugSection
                aboutSection
            }
            .navigationTitle("Settings")
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
}

struct SettingsTabView_Previews: PreviewProvider {
    static var previews: some View {
        SettingsTabView()
            .environmentObject(AppStateManager())
            .environmentObject(WebSocketManager())
            .environmentObject(CameraManager())
    }
}
