//
//  MenuBarManager.swift
//  Orion Server
//
//  Created by Riddhiman Rana on 8/10/25.
//  Manages menu bar functionality including launch at login.
//

import SwiftUI
import ServiceManagement

@MainActor
class MenuBarManager: ObservableObject {
    @Published var launchAtLogin: Bool = false
    
    init() {
        // Check current launch at login status
        checkLaunchAtLoginStatus()
    }
    
    func checkLaunchAtLoginStatus() {
        // Check if the app is set to launch at login
        if #available(macOS 13.0, *) {
            launchAtLogin = SMAppService.mainApp.status == .enabled
        } else {
            // Fallback for older macOS versions
            launchAtLogin = false
        }
    }
    
    func setLaunchAtLogin(enabled: Bool) {
        if #available(macOS 13.0, *) {
            do {
                if enabled {
                    try SMAppService.mainApp.register()
                } else {
                    try SMAppService.mainApp.unregister()
                }
                launchAtLogin = enabled
            } catch {
                print("Failed to \(enabled ? "enable" : "disable") launch at login: \(error)")
                // Revert the toggle if it failed
                launchAtLogin = !enabled
            }
        } else {
            // For macOS versions below 13.0, launch at login is not supported
            print("Launch at login requires macOS 13.0 or later")
            launchAtLogin = false
        }
    }
    
    func openSettings(userViewModel: UserProfileViewModel, authManager: AuthManager) {
        // Find existing settings window or create new one
        if let settingsWindow = NSApplication.shared.windows.first(where: { $0.title == "Settings" }) {
            settingsWindow.makeKeyAndOrderFront(nil)
        } else {
            // Create a new settings window
            let settingsView = SettingsWindow(userViewModel: userViewModel, authManager: authManager)
            let hostingController = NSHostingController(rootView: settingsView)
            
            let window = NSWindow(contentViewController: hostingController)
            window.title = "Settings"
            window.setContentSize(NSSize(width: 600, height: 500))
            window.center()
            window.makeKeyAndOrderFront(nil)
        }
    }
}
