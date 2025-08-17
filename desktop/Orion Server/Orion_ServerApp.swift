//
//  Orion_ServerApp.swift
//  Orion Server
//
//  Created by Riddhiman Rana on 7/16/25.
//

import SwiftUI
import WebRTC

// MARK: - P2P Manager Container
@MainActor
class P2PManagers: ObservableObject {
    let apiService: APIService
    let signalingClient: SignalingClient
    let webRTCManager: WebRTCManager

    init(authManager: AuthManager, deviceManager: DeviceManager) {
        self.apiService = APIService(authManager: authManager)
        self.signalingClient = SignalingClient(apiService: self.apiService, deviceManager: deviceManager)
        self.webRTCManager = WebRTCManager(signalingClient: self.signalingClient)
    }

    func connect() {
        webRTCManager.connect()
    }
    
    func disconnect() {
        webRTCManager.disconnect()
    }
}


@main
struct Orion_ServerApp: App {
    // MARK: - State Objects and Environment
    @StateObject private var authManager = AuthManager()
    @StateObject private var userViewModel = UserProfileViewModel()
    @StateObject private var menuBarManager = MenuBarManager()
    
    @State private var deviceManager: DeviceManager?
    @State private var p2pManagers: P2PManagers?

    @Environment(\.openWindow) private var openWindow

    // MARK: - Body
    var body: some Scene {
        // Main application window for login and dashboard
        WindowGroup("Orion Server", id: "main") {
            Group {
                if authManager.session == nil {
                    LoginView()
                        .frame(minWidth: 400, minHeight: 600)
                } else {
                    Group {
                        if let deviceManager = deviceManager, let p2pManagers = p2pManagers {
                            let dashboard = MainDashboard()
                                .frame(minWidth: 800, minHeight: 600)
                            
                            dashboard
                                .environmentObject(deviceManager)
                                .environmentObject(p2pManagers.apiService)
                                .environmentObject(p2pManagers.signalingClient)
                                .environmentObject(p2pManagers.webRTCManager)
                        } else {
                            VStack {
                                ProgressView()
                                Text("Initializing...")
                                    .foregroundColor(.secondary)
                            }
                            .frame(minWidth: 500, minHeight: 400)
                        }
                    }
                    .task {
                        // Initialize managers when authenticated
                        if deviceManager == nil {
                            let newDeviceManager = DeviceManager(supabase: authManager.supabase)
                            self.deviceManager = newDeviceManager
                            await newDeviceManager.registerDeviceIfNeeded(type: "mac")
                            
                            let newP2PManagers = P2PManagers(authManager: authManager, deviceManager: newDeviceManager)
                            self.p2pManagers = newP2PManagers
                            newP2PManagers.connect()
                        }

                        // Fetch user details once the session is available
                        if let user = authManager.session?.user {
                            await userViewModel.fetchUserDetails(for: user)
                        }
                    }
                }
            }
            .environmentObject(authManager)
            .environmentObject(menuBarManager)
            .environmentObject(userViewModel)
            .onOpenURL { url in
                // Handle deep linking for authentication callbacks
                Task {
                    await authManager.handleSessionCallback(from: url)
                }
            }
            .onChange(of: authManager.session) { _, newSession in
                // Reset managers when user logs out
                if newSession == nil {
                    p2pManagers?.disconnect()
                    deviceManager = nil
                    p2pManagers = nil
                }
            }
        }
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentSize)
        .defaultSize(width: 400, height: 600)
        .handlesExternalEvents(matching: Set(arrayLiteral: "main"))
        .commands {
            // Replace the entire View menu to only keep "Enter Full Screen"
            CommandGroup(replacing: .toolbar) {}
            CommandGroup(replacing: .sidebar) {}

            // Disable window tabbing options
            CommandGroup(replacing: .windowArrangement) {}

            // Remove new window command (Cmd+N)
            CommandGroup(replacing: .newItem) {
                // Empty group removes the "New" commands
            }
        }

        // MARK: - Menu Bar Extra
        MenuBarExtra("Orion Server", image: "MenuBarIcon") {
            VStack {
                if authManager.session != nil {
                    Text("Orion Server")
                        .font(.headline)
                    
                    Divider()
                    
                    Button("Open Dashboard") {
                        openWindow(id: "main")
                    }
                    
                    Button("Settings...") {
                        openWindow(id: "settings")
                    }
                    
                    Divider()
                    
                    Button("Quit") {
                        NSApplication.shared.terminate(nil)
                    }
                } else {
                    Text("Orion Server")
                        .font(.headline)
                    
                    Divider()
                    
                    Button("Open App") {
                        openWindow(id: "main")
                    }
                    
                    Button("Quit") {
                        NSApplication.shared.terminate(nil)
                    }
                }
            }
        }

        // MARK: - Settings Window
        Window("Settings", id: "settings") {
            Group {
                if let deviceManager = deviceManager, let p2pManagers = p2pManagers {
                    SettingsWindow(userViewModel: userViewModel, authManager: authManager)
                        .environmentObject(deviceManager)
                        .environmentObject(p2pManagers.apiService)
                        .environmentObject(p2pManagers.signalingClient)
                        .environmentObject(p2pManagers.webRTCManager)
                } else {
                    VStack {
                        if authManager.session != nil {
                            ProgressView()
                            Text("Initializing...")
                                .foregroundColor(.secondary)
                        } else {
                            Text("Please log in to access settings")
                                .foregroundColor(.secondary)
                        }
                    }
                    .frame(minWidth: 500, minHeight: 400)
                }
            }
            .task {
                // Initialize managers if authenticated but not yet initialized
                if authManager.session != nil && deviceManager == nil {
                    let newDeviceManager = DeviceManager(supabase: authManager.supabase)
                    self.deviceManager = newDeviceManager
                    await newDeviceManager.registerDeviceIfNeeded(type: "mac")
                    
                    let newP2PManagers = P2PManagers(authManager: authManager, deviceManager: newDeviceManager)
                    self.p2pManagers = newP2PManagers
                }
            }
        }
        .defaultPosition(.center)
        .defaultSize(width: 600, height: 500)
        .handlesExternalEvents(matching: Set(arrayLiteral: "settings"))
    }
}
