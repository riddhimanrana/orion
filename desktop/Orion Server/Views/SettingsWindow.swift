//
//  SettingsWindow.swift
//  Orion Server
//
//  Created by Riddhiman Rana on 8/9/25.
//  Settings window for Orion Server.
//

import SwiftUI

struct SettingsWindow: View {
    @ObservedObject var userViewModel: UserProfileViewModel
    let authManager: AuthManager
    @EnvironmentObject var deviceManager: DeviceManager
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var signalingClient: SignalingClient
    
    // State for app controls
    @State private var showInMenuBar = "When App is Running"
    
    // State to control the logout confirmation alert
    @State private var showingLogoutAlert = false
    @State private var showingPairingSheet = false
    @State private var pollingTimer: Timer? = nil

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    // MARK: - Account Section
                    SettingsSection(title: "Account") {
                        SettingsInfoRow(icon: "envelope", title: "Email", value: userViewModel.email)
                        Divider().padding(.leading, 40)
                        SettingsInfoRow(icon: "crown", title: "Subscription", value: userViewModel.subscriptionTier)
                    }

                    // MARK: - App Section
                    SettingsSection(title: "App") {
                        SettingsPickerRow(icon: "menubar.rectangle", title: "Show in Menu Bar", selection: $showInMenuBar, options: ["When App is Running", "Always", "Never"])
                    }

                    // MARK: - P2P Connection Section
                    SettingsSection(title: "Peer-to-Peer Connection") {
                        SettingsInfoRow(icon: "network", title: "Signaling Status", value: signalingClient.connectionState.description)
                        SettingsInfoRow(icon: "webrtc", title: "WebRTC Status", value: webRTCStatusString)
                        Divider().padding(.leading, 40)
                        SettingsButtonRow(icon: "arrow.clockwise", title: "Reconnect Now") {
                            webRTCManager.connect()
                        }
                    }

                    // MARK: - Device Pairing Section
                    SettingsSection(title: "Device Pairing") {
                        VStack(spacing: 0) {
                            if deviceManager.pairedDevices.isEmpty {
                                SettingsSimpleInfoRow(title: "No devices paired.", value: "")
                            } else {
                                ForEach(deviceManager.pairedDevices) { pair in
                                    HStack {
                                        Image(systemName: "iphone.gen2") // Use a more specific icon
                                            .font(.callout)
                                            .foregroundColor(.secondary)
                                            .frame(width: 20, alignment: .center)

                                        VStack(alignment: .leading) {
                                            Text(pair.mobileDevice.name) // Display the mobile device's name
                                                .font(.system(size: 13, weight: .medium))
                                            Text("Paired on \(pair.createdAt, style: .date)")
                                                .font(.system(size: 11))
                                                .foregroundColor(.secondary)
                                        }
                                        Spacer()
                                        Button("Revoke") {
                                            Task {
                                                await deviceManager.revokePair(pairId: pair.id)
                                            }
                                        }
                                        .buttonStyle(.plain)
                                        .font(.system(size: 13))
                                        .foregroundColor(.red)
                                    }
                                    .padding(12)
                                    
                                    if pair.id != deviceManager.pairedDevices.last?.id {
                                        Divider().padding(.leading, 44)
                                    }
                                }
                            }
                            
                            Divider()
                            
                            SettingsButtonRow(icon: "link", title: "Pair a New Device") {
                                showingPairingSheet = true
                            }
                            .disabled(!deviceManager.pairedDevices.isEmpty)
                        }.padding(0)

                        if !deviceManager.pairedDevices.isEmpty {
                            Text("You can only have one active pair at a time. Revoke the existing pair to link a new device.")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                                .padding(.horizontal, 12)
                                .padding(.bottom, 8)
                        }
                    }

                    // MARK: - Manage Section
                    SettingsSection(title: "Manage") {
                        SettingsLinkRow(
                            icon: "creditcard",
                            title: "Manage Subscription",
                            subtitle: "Billing, plan changes, and invoices",
                            action: {
                                if let url = URL(string: "https://orionlive.ai/account") {
                                    NSWorkspace.shared.open(url)
                                }
                            }
                        )
                        Divider().padding(.leading, 40)
                        SettingsLinkRow(
                            icon: "person.circle",
                            title: "Account Settings",
                            subtitle: "Profile, security, and preferences",
                            action: {
                                if let url = URL(string: "https://orionlive.ai/settings") {
                                    NSWorkspace.shared.open(url)
                                }
                            }
                        )
                    }

                    // MARK: - About Section
                    SettingsSection(title: "About") {
                        SettingsLinkRow(
                            icon: "doc.text",
                            title: "Terms of Use",
                            subtitle: "Legal terms and conditions",
                            action: {
                                if let url = URL(string: "https://orionlive.ai/terms") {
                                    NSWorkspace.shared.open(url)
                                }
                            }
                        )
                        Divider().padding(.leading, 40)
                        SettingsLinkRow(
                            icon: "hand.raised",
                            title: "Privacy Policy",
                            subtitle: "How we handle your data",
                            action: {
                                if let url = URL(string: "https://orionlive.ai/privacy") {
                                    NSWorkspace.shared.open(url)
                                }
                            }
                        )
                        Divider().padding(.leading, 40)
                        SettingsInfoRow(icon: "info.circle", title: "Version", value: "1.0")
                        Divider().padding(.leading, 40)
                        SettingsButtonRow(icon: "arrow.down.circle", title: "Check for Updates...") {
                            // Your action to check for updates
                            print("Checking for updates...")
                        }
                    }
                    
                    // The Log Out button is in its own section for consistent spacing.
                    SettingsSection {
                        SettingsButtonRow(icon: "rectangle.portrait.and.arrow.right", title: "Log Out", role: .destructive) {
                            showingLogoutAlert = true
                        }
                    }
                }
                .padding()
            }
            .onAppear(perform: startPolling)
            .onDisappear(perform: stopPolling)
            .navigationTitle("Settings")
        }
        .frame(minWidth: 500, maxWidth: 500)
        .alert("Log out of Orion Server?", isPresented: $showingLogoutAlert) {
            Button("Log Out", role: .destructive) {
                // Add your logout logic here, e.g., authManager.logout()
                print("Logout action confirmed for \(userViewModel.email)")
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Are you sure you want to log out as \(userViewModel.email)?")
        }
        .sheet(isPresented: $showingPairingSheet) {
            PairingCodeInputView()
                .environmentObject(deviceManager)
        }
    }

    private var webRTCStatusString: String {
        switch webRTCManager.connectionState {
        case .new: return "new"
        case .checking: return "checking"
        case .connected: return "connected"
        case .completed: return "completed"
        case .failed: return "failed"
        case .disconnected: return "disconnected"
        case .closed: return "closed"
        case .count: return "count"
        @unknown default: return "unknown"
        }
    }

    private func startPolling() {
        // Fetch immediately on appear
        Task {
            await deviceManager.fetchPairedDevices()
        }
        // Then poll every 10 seconds
        pollingTimer = Timer.scheduledTimer(withTimeInterval: 10, repeats: true) { _ in
            Task {
                print("Polling for paired devices...")
                await deviceManager.fetchPairedDevices()
            }
        }
    }

    private func stopPolling() {
        pollingTimer?.invalidate()
        pollingTimer = nil
        print("Stopped polling for paired devices.")
    }
}


// MARK: - Reusable Setting Views

struct SettingsSection<Content: View>: View {
    var title: String? = nil
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let title = title {
                Text(title)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .padding(.horizontal)
            }
            
            VStack(spacing: 0, content: content)
                .background(Color(NSColor.controlBackgroundColor))
                .cornerRadius(10)
        }
    }
}

struct SettingsInfoRow: View {
    let icon: String
    let title: String
    let value: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.callout)
                .foregroundColor(.secondary)
                .frame(width: 20, alignment: .center)
            Text(title)
                .font(.system(size: 13))
            Spacer()
            Text(value)
                .font(.system(size: 13))
                .foregroundColor(.secondary)
        }
        .padding(12)
    }
}

struct SettingsSimpleInfoRow: View {
    let title: String
    let value: String

    var body: some View {
        HStack {
            Text(title)
                .font(.system(size: 13))
            Spacer()
            Text(value)
                .font(.system(size: 13))
                .foregroundColor(.secondary)
        }
        .padding(12)
    }
}

struct SettingsPickerRow<T: Hashable & CustomStringConvertible>: View {
    let icon: String
    let title: String
    @Binding var selection: T
    let options: [T]

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.callout)
                .foregroundColor(.secondary)
                .frame(width: 20, alignment: .center)
            
            Text(title)
                .font(.system(size: 13))
            
            Spacer()
            
            Picker("", selection: $selection) {
                ForEach(options, id: \.self) { option in
                    Text(option.description).tag(option)
                }
            }
            .pickerStyle(.menu)
            .fixedSize(horizontal: true, vertical: false)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 4)
    }
}

struct SettingsButtonRow: View {
    let icon: String
    let title: String
    var role: ButtonRole? = nil
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: icon)
                    .font(.callout)
                    .frame(width: 20, alignment: .center)
                
                Text(title)
                
                Spacer()
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .padding(12)
        .foregroundColor(role == .destructive ? .red : .accentColor)
    }
}

struct SettingsLinkRow: View {
    let icon: String
    let title: String
    let subtitle: String
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: icon)
                    .font(.callout)
                    .foregroundColor(.secondary)
                    .frame(width: 20, alignment: .center)

                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.system(size: 13, weight: .medium))
                        .foregroundColor(.primary)
                    Text(subtitle)
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                }
                Spacer()
                Image(systemName: "arrow.up.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(.secondary.opacity(0.7))
            }
            .padding(12)
        }
        .buttonStyle(.plain)
    }
}


// MARK: - Preview

// This mock class provides sample data for previews
class MockUserProfileViewModel: UserProfileViewModel {
    // We initialize with mock data
    override init() {
        super.init()
        Task { @MainActor in
            self.email = "riddhiman.rana@gmail.com"
            self.fullName = "Riddhiman Rana"
            self.subscriptionTier = "Pro Plan"
            self.memberSince = "August 2025"
        }
    }
}

struct SettingsWindow_Previews: PreviewProvider {
    static var previews: some View {
        let mockViewModel = MockUserProfileViewModel()

        // Since AuthManager is defined in your project, we can create a blank instance for the preview.
        SettingsWindow(
            userViewModel: mockViewModel,
            authManager: AuthManager()
        )
    }
}
