import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var wsManager: WebSocketManager
    // @EnvironmentObject var appState: AppStateManager // Uncomment if needed
    @Environment(\.dismiss) var dismiss

    // Bind to the static property in WebSocketManager
    @State private var webSocketLoggingEnabled = WebSocketManager.enableLogging
    
    // State for server settings - these would need to be fetched from wsManager or UserDefaults
    @State private var serverHost: String = UserDefaults.standard.string(forKey: UserDefaultsKeys.serverHost) ?? ServerConfig.host
    @State private var serverPortString: String = "\(UserDefaults.standard.object(forKey: UserDefaultsKeys.serverPort) as? Int ?? ServerConfig.port)"


    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("WebSocket Logging")) {
                    Toggle("Enable Debug Logs", isOn: $webSocketLoggingEnabled)
                        .onChange(of: webSocketLoggingEnabled) { newValue in
                            WebSocketManager.enableLogging = newValue
                            // Optionally, log this change
                            Logger.shared.log("WebSocket logging toggled: \(newValue)", category: .general)
                        }
                }

                Section(header: Text("Server Configuration")) {
                    HStack {
                        Text("Host:")
                        TextField("Enter server host", text: $serverHost)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                            .autocapitalization(.none)
                            .disableAutocorrection(true)
                    }
                    HStack {
                        Text("Port:")
                        TextField("Enter server port", text: $serverPortString)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                            .keyboardType(.numberPad)
                    }
                    Button("Apply Server Changes & Reconnect") {
                        if let port = Int(serverPortString) {
                            // Update UserDefaults
                            UserDefaults.standard.set(serverHost, forKey: UserDefaultsKeys.serverHost)
                            UserDefaults.standard.set(port, forKey: UserDefaultsKeys.serverPort)
                            // Tell WebSocketManager to update and reconnect
                            wsManager.updateServerURL(host: serverHost, port: port)
                            Logger.shared.log("Server configuration updated to \(serverHost):\(port)", category: .network)
                            dismiss() // Dismiss settings after applying
                        } else {
                            // Handle invalid port number, e.g., show an alert
                            Logger.shared.log("Invalid port number entered: \(serverPortString)", level: .warning, category: .ui)
                        }
                    }
                }
                
                // Add other settings sections as needed
                // For example, settings from DebugConfig
                Section(header: Text("Debug Options (App Restart May Be Required)")) {
                    Toggle("Enable Processing Logs", isOn: Binding(
                        get: { DebugConfig.enableProcessingLogs },
                        set: { DebugConfig.enableProcessingLogs = $0 }
                    ))
                    Toggle("Enable Performance Metrics", isOn: Binding(
                        get: { DebugConfig.enablePerformanceMetrics },
                        set: { DebugConfig.enablePerformanceMetrics = $0
                            // You might need to re-initialize or signal AppStateManager
                            // if performance monitoring is dynamically toggled.
                        }
                    ))
                }
            }
            .navigationTitle("Settings")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

struct SettingsView_Previews: PreviewProvider {
    static var previews: some View {
        SettingsView()
            .environmentObject(WebSocketManager()) // Provide a mock/default for preview
            .environmentObject(AppStateManager())
    }
}
