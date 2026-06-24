//
//  SettingsTabView.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Main settings tab for configuring Orion Live app preferences.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//
import SwiftUI
import Combine
import Supabase
import SafariServices

struct SettingsTabView: View {
    @StateObject private var settings = SettingsManager.shared
    @EnvironmentObject var appState: AppStateManager
    @EnvironmentObject var wsManager: WebSocketManager
    @EnvironmentObject var cameraManager: CameraManager
    @EnvironmentObject var deviceManager: DeviceManager
    @EnvironmentObject var compatibilityManager: SystemCompatibilityManager
    @EnvironmentObject var authManager: AuthManager

    @State private var showingPairingSheet = false
    @State private var pollingTimer: Timer? = nil

    // In-app browser state
    @State private var showingSafari = false
    @State private var safariURL: URL? = nil

    // Log out alert state (bottom section)
    @State private var showingSignOutAlert = false
    // (Removed) API key management state since we now read from Info.plist

    var body: some View {
        NavigationStack {
            Form {
                // In production, AccountSection uses its own @StateObject view model.
                // In previews, we can override with a mock via environment.
                AccountSection()
                modelProviderSection
                chatSection
                processingModeSection
                connectionSettingsSection
                cameraAndDetectionSection
                devicePairingSection
                systemCompatibilitySection
                aboutSection

                // Bottom unnamed logout section
                Section {
                    Button(role: .destructive) {
                        showingSignOutAlert = true
                    } label: {
                        HStack(spacing: 8) {
                            Image(systemName: "rectangle.portrait.and.arrow.right")
                            Text("Log Out")
                        }
                    }
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.automatic)
            .onAppear(perform: startPolling)
            .onDisappear(perform: stopPolling)
            .alert("Log Out", isPresented: $showingSignOutAlert) {
                Button("Cancel", role: .cancel) { }
                Button("Log Out", role: .destructive) {
                    Task { await authManager.signOut() }
                }
            } message: {
                Text("Are you sure you want to log out of \(authManager.session?.user.email ?? "your account")?")
            }
        }
        .sheet(isPresented: $showingPairingSheet) {
            PairingView(authManager: authManager)
        }
        .sheet(isPresented: $showingSafari) {
            if let url = safariURL {
                SafariView(url: url)
                    .ignoresSafeArea()
            }
        }
        // API key is now read from Info.plist; no in-app editor presented
    }
    private var modelProviderSection: some View {
        Section(header: Label("Model & Provider", systemImage: "brain.head.profile")) {
            Picker("Provider", selection: $settings.llmProvider) {
                Text("Gateway/Proxy").tag("proxy")
                Text("Google (Gemini)").tag("google")
                Text("OpenAI").tag("openai")
                Text("Local Orion Server").tag("local")
            }
            .pickerStyle(.segmented)

            TextField("Model (e.g., gemini-2.5-flash-lite)", text: $settings.llmModel)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled(true)

            if settings.llmProvider == "proxy" {
                TextField("Proxy URL (e.g., https://ai.orionlive.ai/v1/chat)", text: $settings.llmProxyURL)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.URL)
                    .autocorrectionDisabled(true)
            }

            if settings.llmProvider == "local" {
                TextField("Local URL (e.g., http://orion-server.local:8787/v1/chat)", text: $settings.llmLocalURL)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.URL)
                    .autocorrectionDisabled(true)
            }

            Text("These settings control where chat requests are routed: a hosted gateway, direct to Google/OpenAI, or to a local Orion Server.")
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }

    private var cameraAndDetectionSection: some View {
        Section(header: Label("Camera & Detection", systemImage: "camera.fill")) {
            Toggle("Show detection boxes", isOn: $settings.showDetectionBoxes)
            Toggle("Show detection labels", isOn: $settings.showDetectionLabels)
                .disabled(!settings.showDetectionBoxes)
        }
    }

    private var devicePairingSection: some View {
        Section(header: Label("Device Pairing", systemImage: "link")) {
            if deviceManager.pairedDevices.isEmpty {
                Text("No devices paired.")
            } else {
                List {
                    ForEach(deviceManager.pairedDevices) { pair in
                        HStack {
                            VStack(alignment: .leading) {
                                Text(pair.serverDevice.name)
                                    .font(.headline)
                                Text("Paired on \(pair.createdAt, style: .date)")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            Spacer()
                            Button("Revoke") {
                                Task {
                                    await deviceManager.revokePair(pairId: pair.id)
                                }
                            }
                            .foregroundColor(.red)
                        }
                    }
                }
            }

            Button("Pair a New Device") {
                showingPairingSheet = true
            }
            .disabled(deviceManager.deviceId == nil || !deviceManager.pairedDevices.isEmpty)

            if !deviceManager.pairedDevices.isEmpty {
                Text("You can only have one active pair at a time. Revoke the existing pair to pair a new device.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
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
            Button {
                safariURL = URL(string: "https://orionlive.ai/terms")
                showingSafari = (safariURL != nil)
            } label: {
                HStack {
                    Text("Terms of Use")
                    Spacer()
                    Image(systemName: "arrow.up.right.square")
                        .foregroundColor(.secondary)
                }
            }

            Button {
                safariURL = URL(string: "https://orionlive.ai/privacy")
                showingSafari = (safariURL != nil)
            } label: {
                HStack {
                    Text("Privacy Policy")
                    Spacer()
                    Image(systemName: "arrow.up.right.square")
                        .foregroundColor(.secondary)
                }
                
            

            
            }
        }
    }

    private var chatSection: some View {
        Section(header: Label("Chat", systemImage: "message")) {
            Toggle("Stats for Nerds", isOn: $settings.showChatStats)
            let info = Bundle.main.infoDictionary ?? [:]
            let provider = (info["AI_PROVIDER"] as? String) ?? "google"
            let model = (info["AI_MODEL"] as? String) ?? (provider.lowercased() == "google" ? "gemini-2.5-flash-lite" : "gpt-4.1-mini")
            HStack {
                Text("Provider: \(provider.uppercased())")
                Spacer()
                Text("Model: \(model)")
                    .foregroundColor(.secondary)
            }
            .font(.caption)
        }
    }

    private var systemCompatibilitySection: some View {
        Section(header: Label("Device Compatibility", systemImage: "iphone.gen3")) {
            CompatibilityExpandableView()
                .environmentObject(compatibilityManager)
        }
    }

    private var processingModeSection: some View {
        Section(header: Label("Processing Mode", systemImage: "gearshape.2.fill")) {
            Picker("Mode", selection: $settings.processingMode) {
                Text("Hybrid").tag("hybrid")
                Text("Server").tag("server")
            }
            .pickerStyle(.segmented)
            .onChange(of: settings.processingMode) { _, newMode in
                wsManager.sendConfiguration(mode: newMode)
                cameraManager.configure(for: newMode)
            }
        }
    }

    private var connectionSettingsSection: some View {
        Section(header: Label("Connection Settings", systemImage: "server.rack")) {
            Picker("Mode", selection: $settings.connectionMode) {
                Text("Direct Wi-Fi").tag("direct")
                Text("Remote P2P").tag("webrtc")
            }
            .pickerStyle(.segmented)
            
            if settings.connectionMode == "direct" {
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
                    Text(wsManager.status == .connected ? "Connected" : (wsManager.status == .connecting ? "Connecting" : "Disconnected"))
                        .foregroundColor(wsManager.status == .connected ? .green : .yellow)
                }
            } else {
                Button("Pair with macOS Server") {
                    showingPairingSheet = true
                }
                
                HStack {
                    Text("P2P Status")
                    Spacer()
                    if UserDefaults.standard.string(forKey: "paired_server_device_id") != nil {
                        Text("Ready")
                            .foregroundColor(.green)
                    } else {
                        Text("Not Paired")
                            .foregroundColor(.yellow)
                    }
                }
            }
        }
    }

    private func updateConnection() {
        wsManager.updateServerURL(host: settings.serverHost, port: settings.serverPort)
        wsManager.disconnect()
        wsManager.connect()
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

// MARK: - Account Section
struct AccountSection: View {
    @EnvironmentObject var authManager: AuthManager

    // Default runtime view model
    @StateObject private var viewModel = AccountViewModel()
    @State private var showingSignOutAlert = false

    // Upgrade/Manage sheet
    @State private var showingUpgradeSheet = false

    // Preview-only injected model support
    @Environment(\.previewAccountViewModel) private var previewVM

    var body: some View {
        // Use injected preview model in previews if supplied, otherwise the runtime @StateObject
        let vm = previewVM ?? viewModel

        Section(header: Label("Account", systemImage: "person.crop.circle")) {
            if vm.isLoading {
                HStack {
                    Spacer()
                    ProgressView()
                        .scaleEffect(0.8)
                    Spacer()
                }
                .padding(.vertical, 24)
                .onAppear {
                    if let user = authManager.session?.user {
                        Task {
                            await vm.fetchAccountDetails(for: user)
                        }
                    } else {
                        // If there is no session (e.g., previews), end loading so UI shows placeholders
                        vm.isLoading = false
                    }
                }
            } else {
                VStack(spacing: 8) {
                    // Profile Header
                    HStack {
                        // Profile Picture - Left aligned
                        AsyncImage(url: vm.profilePictureURL) { image in
                            image
                                .resizable()
                                .aspectRatio(contentMode: .fill)
                        } placeholder: {
                            ZStack {
                                Circle()
                                    .fill(
                                        LinearGradient(
                                            colors: [Color.gray.opacity(0.8), Color.gray],
                                            startPoint: .topLeading,
                                            endPoint: .bottomTrailing
                                        )
                                    )
                                Text(vm.getInitials(from: vm.fullName))
                                    .font(.system(size: 20, weight: .semibold, design: .rounded))
                                    .foregroundColor(.white)
                            }
                        }
                        .frame(width: 54, height: 54)
                        .clipShape(Circle())
                        .overlay(
                            Circle()
                                .stroke(Color.primary.opacity(0.08), lineWidth: 1)
                        )
                        .shadow(color: .black.opacity(0.08), radius: 3, x: 0, y: 1)

                        // User Info with Pro badge when applicable
                        VStack(alignment: .leading, spacing: 6) {
                            HStack(spacing: 6) {
                                Text(vm.fullName)
                                    .font(.system(size: 17, weight: .semibold))
                                    .foregroundColor(.primary)
                                    .lineLimit(1)
                                if vm.subscriptionTier == "Pro" {
                                    HStack(spacing: 4) {
                                        Text("Pro")
                                            .font(.caption).bold()
                                            .foregroundColor(.yellow)
                                    }
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 2)
                                    .background(Color.yellow.opacity(0.15))
                                    .clipShape(Capsule())
                                }
                            }

                            Text(vm.email)
                                .font(.system(size: 14))
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                                .truncationMode(.middle)
                        }

                        Spacer(minLength: 0)
                    }

                    // Visual separation before action
                    Divider()
                        .padding(.top, 8)
                        .padding(.bottom, 4)

                    // Conditional subscription action as a proper button
                    Button {
                        // Present in-app sheet for both cases; different content
                        showingUpgradeSheet = true
                    } label: {
                        HStack(spacing: 10) {
                            Image(systemName: vm.subscriptionTier == "Pro" ? "person.text.rectangle.fill" : "sparkles")
                                .font(.system(size: 16, weight: .semibold))
                                .foregroundColor(vm.subscriptionTier == "Pro" ? .gray : .yellow)

                            Text(vm.subscriptionTier == "Pro" ? "Manage Subscription" : "Upgrade to Orion Pro")
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundColor(.primary)
                            Spacer()
                        }
                        .padding(.vertical, 10)
                        .padding(.horizontal, 12)
                        .background(
                            RoundedRectangle(cornerRadius: 12, style: .continuous)
                                .fill(Color(UIColor.secondarySystemBackground))
                        )
                    }
                    .buttonStyle(PressableScaleStyle())
                    .sheet(isPresented: $showingUpgradeSheet) {
                        ProUpgradeSheet(
                            mode: vm.subscriptionTier == "Pro" ? .manage : .upgrade,
                            priceString: "$19.99",
                            features: ProUpgradeSheet.defaultFeatures,
                            onUpgradeTapped: {
                                // TODO: Wire to stripe purchase flow
                                if let url = URL(string: "https://orionlive.ai/pro") {
                                    UIApplication.shared.open(url)
                                }
                            },
                            onManageTapped: {
                                // TODO: Wire to subscription management (StoreKit manageSubscriptionsSheet if used)
                                if let url = URL(string: "https://orionlive.ai/dashboard/account") {
                                    UIApplication.shared.open(url)
                                }
                            }
                        )
                        .presentationDetents([.fraction(0.8)])
                        .presentationDragIndicator(.visible)
                        .presentationCornerRadius(24) // iOS 17+
                    }
                }
            }
        }
        .alert("Log Out", isPresented: $showingSignOutAlert) {
            Button("Cancel", role: .cancel) { }
            Button("Log Out", role: .destructive) {
                Task {
                    await authManager.signOut()
                }
            }
        } message: {
            Text("Are you sure you want to log out of \( (previewVM ?? viewModel).email )?")
        }
    }
}

// MARK: - Preview Support
private struct PreviewAccountViewModelKey: EnvironmentKey {
    static let defaultValue: AccountViewModel? = nil
}

extension EnvironmentValues {
    var previewAccountViewModel: AccountViewModel? {
        get { self[PreviewAccountViewModelKey.self] }
        set { self[PreviewAccountViewModelKey.self] = newValue }
    }
}

#if DEBUG
private extension AccountViewModel {
    static func previewSample(
        fullName: String = "Bob Jones",
        email: String = "bobjones@gmail.com",
        memberSince: String = "July 15, 2025",
        subscriptionTier: String = "Free",
        profilePictureURL: URL? = URL(string: "https://orionlive.ai/logo.png")
    ) -> AccountViewModel {
        let vm = AccountViewModel()
        vm.fullName = fullName
        vm.email = email
        vm.memberSince = memberSince
        vm.subscriptionTier = subscriptionTier
        vm.profilePictureURL = profilePictureURL
        vm.isLoading = false
        return vm
    }
}

struct SettingsTabView_Previews: PreviewProvider {
    static var previews: some View {
        // Real managers as in app previews, but we inject a preview AccountViewModel
        let auth = AuthManager()
        let device = DeviceManager(supabase: auth.supabase)
        let camera = CameraManager()
        let ws = WebSocketManager()
        let compat = SystemCompatibilityManager()
        let appState = AppStateManager()

        // Pre-populated preview data for the account section
        let previewVM = AccountViewModel.previewSample()

        return SettingsTabView()
            .environmentObject(appState)
            .environmentObject(ws)
            .environmentObject(camera)
            .environmentObject(device)
            .environmentObject(compat)
            .environmentObject(auth)
            // Inject the preview AccountViewModel so AccountSection skips loading state
            .environment(\.previewAccountViewModel, previewVM)
    }
}
#endif

// MARK: - In-app Safari Wrapper
private struct SafariView: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> SFSafariViewController {
        let config = SFSafariViewController.Configuration()
        config.entersReaderIfAvailable = false
        let vc = SFSafariViewController(url: url, configuration: config)
        vc.preferredBarTintColor = UIColor.systemBackground
        vc.preferredControlTintColor = UIColor.label
        return vc
    }

    func updateUIViewController(_ uiViewController: SFSafariViewController, context: Context) {}
}

// MARK: - Shared Components

/// A pressable button style with subtle scale on press to feel more like a native button.
struct PressableScaleStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .opacity(configuration.isPressed ? 0.9 : 1.0)
            .scaleEffect(configuration.isPressed ? 0.98 : 1.0)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

/// Upgrade/Manage subscription sheet for Orion Pro.
/// 80% height sheet, simple solid background, centered header, comparison table, and adaptive CTA.
struct ProUpgradeSheet: View {
    enum Mode { case upgrade, manage }

    let mode: Mode
    let priceString: String
    let features: [FeatureRowModel]
    var onUpgradeTapped: (() -> Void)?
    var onManageTapped: (() -> Void)?

    @Environment(\.dismiss) private var dismiss
    @Environment(\.colorScheme) private var colorScheme

    // Default feature set
    static let defaultFeatures: [FeatureRowModel] = [
        .init(name: "Cloud access", freeHas: false, proHas: true),
        .init(name: "Intelligence level", freeHas: false, proHas: true),
        .init(name: "Priority analysis", freeHas: false, proHas: true),
        .init(name: "Server-side VLM + LLM", freeHas: false, proHas: true)
    ]

    var body: some View {
        ZStack {
            // Simple solid background: white in light mode, black in dark mode
            (colorScheme == .dark ? Color.black : Color.white)
                .ignoresSafeArea()

            VStack(spacing: 0) {
                // Close button row
                HStack {
                    Spacer()
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .font(.system(size: 22, weight: .semibold))
                            .symbolRenderingMode(.hierarchical)
                            .foregroundStyle(.secondary)
                            .contentShape(Rectangle())
                    }
                    .padding(.trailing, 16)
                    .padding(.top, 12)
                }

                ScrollView(showsIndicators: false) {
                    VStack(spacing: 22) {
                        header
                        comparisonTable
                        ctaSection
                        renewNote
                    }
                    .padding(.horizontal, 20)
                    .padding(.bottom, 32)
                }
            }
        }
        .background(Color.clear)
    }

    // MARK: - Subviews

    private var header: some View {
        VStack(spacing: 10) {
            Image(systemName: "sparkles")
                .font(.system(size: 48, weight: .bold))
                .foregroundColor(.yellow)
                .padding(16)
                .background(
                    Circle().fill((colorScheme == .dark) ? Color.white.opacity(0.1) : Color.black.opacity(0.05))
                )
                .overlay(Circle().stroke(Color.yellow.opacity(0.25), lineWidth: 1))

            Text("Orion Pro")
                .font(.system(size: 34, weight: .bold, design: .rounded))
                .multilineTextAlignment(.center)

            Text(mode == .upgrade ? "Get more advanced cloud access and increased intelligence." : "Manage your Orion Pro subscription.")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 10)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 6)
    }

    private var comparisonTable: some View {
        VStack(spacing: 0) {
            // Header row
            HStack {
                Text("Features")
                    .font(.subheadline.weight(.semibold))
                    .frame(maxWidth: .infinity, alignment: .leading)
                Text("Free")
                    .font(.subheadline.weight(.semibold))
                    .frame(width: 60, alignment: .center)
                Text("Pro")
                    .font(.subheadline.weight(.semibold))
                    .frame(width: 60, alignment: .center)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 12)
            .background(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(Color(UIColor.systemGray5).opacity(colorScheme == .dark ? 0.35 : 0.6))
            )
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))

            // Rows
            VStack(spacing: 0) {
                ForEach(features) { row in
                    HStack(alignment: .center) {
                        Text(row.name)
                            .font(.body)
                            .frame(maxWidth: .infinity, alignment: .leading)

                        featureMark(row.freeHas)
                            .frame(width: 60, alignment: .center)

                        featureMark(row.proHas)
                            .frame(width: 60, alignment: .center)
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 12)
                    .background(
                        Rectangle()
                            .fill(
                                Color(UIColor.systemGray6)
                                    .opacity(colorScheme == .dark ? 0.28 : 0.55)
                            )
                    )

                    if row.id != features.last?.id {
                        Divider().opacity(0.25)
                    }
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .stroke(Color.primary.opacity(0.08), lineWidth: 1)
            )
        }
    }

    private func featureMark(_ has: Bool) -> some View {
        Group {
            if has {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.green)
            } else {
                Image(systemName: "minus.circle")
                    .foregroundColor(.secondary)
            }
        }
        .font(.system(size: 18, weight: .semibold))
        .accessibilityLabel(has ? "Included" : "Not included")
    }

    private var ctaSection: some View {
        // Determine colors based on current color scheme
        let isDark = colorScheme == .dark
        let backgroundColor: Color = isDark ? Color.white : Color.black
        let textColor: Color = isDark ? Color.black : Color.white
        let shadowColor: Color = (isDark ? Color.white : Color.black).opacity(isDark ? 0.4 : 0.2)

        return Button(action: {
            if mode == .upgrade {
                onUpgradeTapped?()
            } else {
                onManageTapped?()
            }
        }) {
            HStack {
                Spacer()
                Text(mode == .upgrade ? "Upgrade for \(priceString)" : "Manage Subscription")
                    .font(.headline)
                    .foregroundColor(textColor)
                Spacer()
            }
            .padding(.vertical, 16)
            .padding(.horizontal, 18)
            .background(
                Capsule(style: .continuous)
                    .fill(backgroundColor)
                    .shadow(color: shadowColor, radius: 14, x: 0, y: 6)
            )
        }
        .buttonStyle(PressableScaleStyle())
        .padding(.top, 14)
        .padding(.horizontal, 6)
        .accessibilityHint(mode == .upgrade ? "Starts a purchase flow" : "Opens subscription management")
    }

    private var renewNote: some View {
        VStack(alignment: .center, spacing: 4) {
            if mode == .upgrade {
                Text("Auto‑renews monthly. Cancel anytime.")
                    .font(.footnote)
                    .foregroundColor(.secondary)
            } else {
                Text("You can modify or cancel your plan anytime.")
                    .font(.footnote)
                    .foregroundColor(.secondary)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 6)
    }
}

// Table row model
struct FeatureRowModel: Identifiable, Hashable {
    let id = UUID()
    let name: String
    let freeHas: Bool
    let proHas: Bool
}

// MARK: - Compatibility Expandable View
struct CompatibilityExpandableView: View {
    @EnvironmentObject var compatibilityManager: SystemCompatibilityManager
    @State private var isExpanded = false
    
    var body: some View {
        VStack(spacing: 0) {
            // Main compatibility row
            Button(action: {
                withAnimation(.easeInOut(duration: 0.3)) {
                    isExpanded.toggle()
                }
            }) {
                HStack {
                    Image(systemName: compatibilityManager.isCompatible ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                        .foregroundColor(compatibilityManager.isCompatible ? .green : .orange)
                        .font(.system(size: 20))
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text("System Compatibility")
                            .font(.body)
                            .fontWeight(.medium)
                            .foregroundColor(.primary)
                        
                        Text(compatibilityManager.isCompatible ? "Compatible" : "Some issues detected")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    
                    Spacer()
                    
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(.secondary)
                        .font(.system(size: 12, weight: .semibold))
                        .animation(.easeInOut(duration: 0.3), value: isExpanded)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(PlainButtonStyle())
            
            // Expandable content
            if isExpanded {
                VStack(spacing: 8) {
                    Divider()
                        .padding(.vertical, 8)
                    
                    // Device information
                    VStack(spacing: 6) {
                        InfoRow(icon: "iphone", label: "Model", value: compatibilityManager.deviceModel)
                        InfoRow(icon: "gear", label: "iOS Version", value: compatibilityManager.iosVersion)
                        InfoRow(icon: "cpu", label: "Processor", value: compatibilityManager.chipType)
                        InfoRow(icon: "memorychip", label: "RAM", value: "\(compatibilityManager.ramGB) GB")
                    }
                    
                    // Compatibility details
                    if !compatibilityManager.compatibilityDetails.isEmpty {
                        Divider()
                            .padding(.vertical, 8)
                        
                        VStack(spacing: 8) {
                            HStack {
                                Text("Compatibility Checks")
                                    .font(.subheadline)
                                    .fontWeight(.semibold)
                                    .foregroundColor(.primary)
                                Spacer()
                            }
                            
                            ForEach(compatibilityManager.compatibilityDetails) { check in
                                HStack(spacing: 8) {
                                    Image(systemName: check.status ? "checkmark.circle.fill" : "xmark.circle.fill")
                                        .foregroundColor(check.status ? .green : .red)
                                        .font(.system(size: 14))
                                    
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(check.name)
                                            .font(.caption)
                                            .fontWeight(.medium)
                                        Text(check.details)
                                            .font(.caption2)
                                            .foregroundColor(.secondary)
                                            .fixedSize(horizontal: false, vertical: true)
                                    }
                                    
                                    Spacer()
                                }
                            }
                        }
                    }
                }
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
    }
}
