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
import WebRTC

struct SettingsTabView: View {
    @StateObject private var settings = SettingsManager.shared
    @EnvironmentObject var appState: AppStateManager
    @EnvironmentObject var wsManager: WebSocketManager
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var signalingClient: SignalingClient
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
                AccountSection()

                Section(header: Label("Preferences", systemImage: "slider.horizontal.3")) {
                    Toggle("Show detection boxes", isOn: $settings.showDetectionBoxes)
                    Toggle("Show detection labels", isOn: $settings.showDetectionLabels)
                        .disabled(!settings.showDetectionBoxes)
                    Toggle("Stats for Nerds", isOn: $settings.showChatStats)
                }

                Section(header: Label("Developer", systemImage: "hammer")) {
                    Toggle("Developer Mode", isOn: $settings.developerModeEnabled)
                    Text("Enables Debug tab and Direct Local Fallback controls. Normal use stays on Signal P2P with macOS server reasoning.")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    if settings.developerModeEnabled {
                        Toggle("Network Logs", isOn: $settings.enableNetworkLogging)
                        Toggle("Processing Logs", isOn: $settings.enableProcessingLogs)
                        Toggle("Performance Metrics", isOn: $settings.enablePerformanceMetrics)
                    }
                }

                aboutSection

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
            .navigationTitle("Account")
            .navigationBarTitleDisplayMode(.large)
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
            VStack(alignment: .leading, spacing: 12) {
                Picker("Mode", selection: $settings.processingMode) {
                    Text("Hybrid Beta").tag("hybrid")
                    Text("Server").tag("server")
                }
                .pickerStyle(.segmented)
                .disabled(true)

                HStack(alignment: .top, spacing: 12) {
                    Image(systemName: "server.rack")
                        .foregroundStyle(.purple)
                        .frame(width: 28, height: 28)
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Server reasoning active")
                            .font(.headline)
                        Text("Hybrid on-device ML is paused for beta testing. Visual tracking, Re-ID, Gemma reasoning, spatial memory, and query answers run on the macOS server.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .padding(12)
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            }
        }
    }

    private var serverRuntimeSection: some View {
        Section(header: Label("Server Runtime", systemImage: "waveform.path.ecg")) {
            RuntimeStatusCard(
                wsManager: wsManager,
                webRTCManager: webRTCManager,
                signalingClient: signalingClient
            )

            Button {
                wsManager.refreshRuntimeStatus()
            } label: {
                Label("Refresh Server Status", systemImage: "arrow.clockwise")
                    .frame(maxWidth: .infinity, minHeight: 44)
            }
            .buttonStyle(.bordered)
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
                    Label(wsManager.status.description, systemImage: wsManager.status == .connected ? "checkmark.circle.fill" : "exclamationmark.circle.fill")
                        .foregroundColor(wsManager.status == .connected ? .green : .orange)
                }

                if let rtt = wsManager.lastRoundTripTime {
                    HStack {
                        Text("Frame RTT")
                        Spacer()
                        Text("\(Int(rtt * 1000)) ms")
                            .foregroundColor(.secondary)
                    }
                }

                Button {
                    updateConnection()
                    wsManager.refreshRuntimeStatus()
                } label: {
                    Label("Reconnect Local Server", systemImage: "arrow.triangle.2.circlepath")
                        .frame(maxWidth: .infinity, minHeight: 44)
                }
                .buttonStyle(.borderedProminent)
            } else {
                Button("Pair with macOS Server") {
                    showingPairingSheet = true
                }
                .frame(minHeight: 44)

                HStack {
                    Text("P2P Status")
                    Spacer()
                    Label(p2pStatusText, systemImage: p2pStatusIcon)
                        .foregroundColor(p2pStatusColor)
                }

                if let rtt = webRTCManager.lastPingRTT {
                    HStack {
                        Text("P2P RTT")
                        Spacer()
                        Text("\(Int(rtt * 1000)) ms")
                            .foregroundColor(.secondary)
                    }
                }

                Button {
                    Task { await webRTCManager.connect() }
                } label: {
                    Label("Connect P2P", systemImage: "point.3.connected.trianglepath.dotted")
                        .frame(maxWidth: .infinity, minHeight: 44)
                }
                .buttonStyle(.borderedProminent)
                .disabled(UserDefaults.standard.string(forKey: "paired_server_device_id") == nil)
            }
        }
    }

    private var p2pStatusText: String {
        if UserDefaults.standard.string(forKey: "paired_server_device_id") == nil {
            return "Not Paired"
        }
        if (webRTCManager.connectionState == .connected || webRTCManager.connectionState == .completed) && webRTCManager.dataChannelState == .open {
            return "Connected"
        }
        if signalingClient.connectionState == .connecting || webRTCManager.connectionState == .checking {
            return "Connecting"
        }
        if signalingClient.connectionState == .connected {
            return "Signaling Ready"
        }
        return "Ready"
    }

    private var p2pStatusIcon: String {
        switch p2pStatusText {
        case "Connected": return "checkmark.circle.fill"
        case "Connecting": return "clock.fill"
        case "Not Paired": return "link.badge.plus"
        default: return "antenna.radiowaves.left.and.right"
        }
    }

    private var p2pStatusColor: Color {
        switch p2pStatusText {
        case "Connected", "Signaling Ready": return .green
        case "Not Paired": return .orange
        default: return .yellow
        }
    }

    private func updateConnection() {
        wsManager.updateServerURL(host: settings.serverHost, port: settings.serverPort)
        wsManager.disconnect()
        wsManager.connect()
    }

    private func startPolling() {
        wsManager.refreshRuntimeStatus()

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
        let apiService = APIService(supabase: auth.supabase)
        let signalingClient = SignalingClient(apiService: apiService, deviceManager: device)
        let webRTCManager = WebRTCManager(signalingClient: signalingClient)

        // Pre-populated preview data for the account section
        let previewVM = AccountViewModel.previewSample()

        return SettingsTabView()
            .environmentObject(appState)
            .environmentObject(ws)
            .environmentObject(webRTCManager)
            .environmentObject(signalingClient)
            .environmentObject(camera)
            .environmentObject(device)
            .environmentObject(compat)
            .environmentObject(auth)
            // Inject the preview AccountViewModel so AccountSection skips loading state
            .environment(\.previewAccountViewModel, previewVM)
    }
}
#endif

private struct RuntimeStatusCard: View {
    @ObservedObject var wsManager: WebSocketManager
    @ObservedObject var webRTCManager: WebRTCManager
    @ObservedObject var signalingClient: SignalingClient

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: overallStatusIcon)
                    .font(.title3)
                    .foregroundStyle(overallStatusColor)
                    .frame(width: 32, height: 32)

                VStack(alignment: .leading, spacing: 4) {
                    Text(overallStatusTitle)
                        .font(.headline)
                    Text(overallStatusDetail)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }

            Divider()

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                RuntimeMetric(label: "Gemma", value: modelText("gemma"), color: modelColor("gemma"))
                RuntimeMetric(label: "Re-ID", value: reidText, color: reidColor)
                RuntimeMetric(label: "Memory", value: memoryText, color: .blue)
                RuntimeMetric(label: "Graph", value: graphText, color: graphColor)
                RuntimeMetric(label: "Local WS", value: wsManager.status.description, color: wsManager.status == .connected ? .green : .orange)
                RuntimeMetric(label: "P2P", value: p2pText, color: p2pColor)
            }

            if let error = wsManager.runtimeStatusError {
                Label(error, systemImage: "exclamationmark.triangle.fill")
                    .font(.caption)
                    .foregroundStyle(.orange)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(14)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .strokeBorder(Color.primary.opacity(0.08), lineWidth: 0.5)
        )
    }

    private var status: ServerRuntimeStatus? { wsManager.runtimeStatus }

    private var overallStatusTitle: String {
        if wsManager.status == .connected && status?.status == "ready" {
            return "Ready for server reasoning"
        }
        if wsManager.status == .connecting {
            return "Connecting to local server"
        }
        if status == nil {
            return "Status not checked"
        }
        return "Server degraded"
    }

    private var overallStatusDetail: String {
        if let status {
            let mode = status.processingMode == "full" ? "server" : status.processingMode
            return "Mode: \(mode). Queue: \(status.queueSize). Objects remembered: \(status.memory?.persistentObjects ?? 0)."
        }
        return "Start the macOS server, then refresh status or connect over Direct Wi-Fi."
    }

    private var overallStatusIcon: String {
        wsManager.status == .connected && status?.status == "ready" ? "checkmark.seal.fill" : "server.rack"
    }

    private var overallStatusColor: Color {
        wsManager.status == .connected && status?.status == "ready" ? .green : .orange
    }

    private func modelText(_ key: String) -> String {
        guard let loaded = status?.models[key] else { return "Unknown" }
        return loaded ? "Loaded" : "Missing"
    }

    private func modelColor(_ key: String) -> Color {
        status?.models[key] == true ? .green : .orange
    }

    private var reidText: String {
        status?.services["vision_processor"] == true ? "Tracker On" : "Waiting"
    }

    private var reidColor: Color {
        status?.services["vision_processor"] == true ? .green : .orange
    }

    private var memoryText: String {
        guard let memory = status?.memory else { return "Unknown" }
        return "\(memory.persistentObjects ?? 0) objects"
    }

    private var graphText: String {
        status?.memgraphConnected == true ? "Memgraph" : "In-memory"
    }

    private var graphColor: Color {
        status?.memgraphConnected == true ? .green : .blue
    }

    private var p2pText: String {
        if (webRTCManager.connectionState == .connected || webRTCManager.connectionState == .completed) && webRTCManager.dataChannelState == .open {
            return "Connected"
        }
        if signalingClient.connectionState == .connected {
            return "Signal"
        }
        return signalingClient.connectionState.description
    }

    private var p2pColor: Color {
        p2pText == "Connected" || p2pText == "Signal" ? .green : .orange
    }
}

private struct RuntimeMetric: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Text(value)
                    .font(.caption)
                    .fontWeight(.semibold)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
            }
            Spacer(minLength: 0)
        }
        .padding(10)
        .frame(minHeight: 52)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

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
