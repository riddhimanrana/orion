//
//  Orion_ServerApp.swift
//  Orion Server
//
//  Created by Riddhiman Rana on 7/16/25.
//

import SwiftUI

@main
struct Orion_ServerApp: App {
    // MARK: - State Objects and Environment
    @StateObject private var authManager = AuthManager()
    @StateObject private var userViewModel = UserProfileViewModel()
    @StateObject private var menuBarManager = MenuBarManager()
    @State private var deviceManager: DeviceManager?

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
                        if let deviceManager = deviceManager {
                            MainDashboard(userViewModel: userViewModel)
                                .frame(minWidth: 500, minHeight: 400)
                                .environmentObject(deviceManager)
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
                        // Initialize DeviceManager when authenticated
                        if deviceManager == nil {
                            deviceManager = DeviceManager(supabase: authManager.supabase)
                            await deviceManager?.registerDeviceIfNeeded(type: "mac")
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
            .onOpenURL { url in
                // Handle deep linking for authentication callbacks
                Task {
                    await authManager.handleSessionCallback(from: url)
                }
            }
            .onChange(of: authManager.session) { _, newSession in
                // Reset DeviceManager when user logs out
                if newSession == nil {
                    deviceManager = nil
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
        // Uses the native .menu style by default
        MenuBarExtra("Orion Server", image: "MenuBarIcon") {
            // "About" button
            Button("About Orion Server") {
                NSApplication.shared.orderFrontStandardAboutPanel()
            }

            Divider()

            // "Launch at Login" toggle. Renders as a menu item with a checkmark.
            Toggle("Launch at Login", isOn: $menuBarManager.launchAtLogin)
                .onChange(of: menuBarManager.launchAtLogin) { _, newValue in
                    menuBarManager.setLaunchAtLogin(enabled: newValue)
                }

            // "Settings" button to open the dedicated settings window
            Button("Settings...") {
                openWindow(id: "settings")
            }
            .keyboardShortcut(",", modifiers: .command)

            Divider()

            // Conditional "Sign Out" button
            if authManager.session != nil {
                Button("Sign Out") {
                    Task {
                        await authManager.signOut()
                    }
                }

                Divider()
            }

            // "Quit" button
            Button("Quit Orion Server") {
                NSApplication.shared.terminate(nil)
            }
            .keyboardShortcut("q", modifiers: .command)
        }
        // By removing `.menuBarExtraStyle(.window)`, it defaults to a native menu.

        // MARK: - Settings Window
        Window("Settings", id: "settings") {
            Group {
                if let deviceManager = deviceManager {
                    SettingsWindow(userViewModel: userViewModel, authManager: authManager)
                        .environmentObject(deviceManager)
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
                // Initialize DeviceManager if authenticated but not yet initialized
                if authManager.session != nil && deviceManager == nil {
                    deviceManager = DeviceManager(supabase: authManager.supabase)
                    await deviceManager?.registerDeviceIfNeeded(type: "mac")
                }
            }
        }
        .defaultPosition(.center)
        .defaultSize(width: 600, height: 500)
        .handlesExternalEvents(matching: Set(arrayLiteral: "settings"))
        // Note: The keyboard shortcut for the window itself is less common.
        // The shortcut on the menu item is the standard user experience.
    }
}
