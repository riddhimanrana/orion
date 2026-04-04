//
//  ChatView.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 8/18/25.
//  A new view for chat functionality.
//

import SwiftUI
import UIKit
import AVFoundation
import Combine

// A custom button style for a modern, clean look.
// This gives the buttons a background, padding, and a nice press effect.
private struct ActionButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.body)
            .padding(8)
            .background(
                Group {
                    if configuration.isPressed {
                        Color(UIColor.systemGray4).opacity(0.25)
                    } else {
                        Color.clear
                    }
                }
            )
            .clipShape(Circle())
            .scaleEffect(configuration.isPressed ? 0.96 : 1.0)
            .animation(.spring(response: 0.3, dampingFraction: 0.7), value: configuration.isPressed)
            .onChange(of: configuration.isPressed) { _, pressed in
                if pressed {
                    let generator = UIImpactFeedbackGenerator(style: .light)
                    generator.impactOccurred()
                }
            }
    }
}

struct ChatView: View {
    @EnvironmentObject var wsManager: WebSocketManager
    @EnvironmentObject var deviceManager: DeviceManager

    @State private var messageText: String = ""
    @State private var messages: [ChatMessage] = []
    @State private var isTyping: Bool = false
    @FocusState private var isInputFocused: Bool
    @Environment(\.scenePhase) private var scenePhase
    
    // Streaming response state
    @State private var streamingMessageID: UUID? = nil
    @State private var streamingProgress: Int = 0
    @State private var streamingTimer: Timer? = nil
    
    // Copy feedback & toasts
    @State private var copiedMessageID: UUID? = nil
    @State private var toastMessage: String? = nil
    
    // Speaking state
    @State private var speakingMessageID: UUID? = nil
    @State private var speakingStartDate: Date? = nil
    @State private var speakingElapsed: TimeInterval = 0
    @State private var speechSynthesizer = AVSpeechSynthesizer()
    
    // Scroll to bottom affordance
    @State private var isScrolledUp: Bool = false
    // How close to the bottom counts as "at bottom" (points) - increased sensitivity
    private let bottomProximityThreshold: CGFloat = 200
    @State private var isRequestInFlight: Bool = false
    @State private var scrollToBottomTrigger: Int = 0
    
    @State private var scrollViewHeight: CGFloat = 0
    @State private var contentHeight: CGFloat = 0
    @State private var pendingResponseWorkItem: DispatchWorkItem? = nil
    @State private var promptTimeoutWorkItem: DispatchWorkItem? = nil
    @State private var inputBarHeight: CGFloat = 0
    
    @ViewBuilder
    private var messagesListView: some View {
        ScrollViewReader { proxy in
            GeometryReader { outerGeo in
                ScrollView {
                    LazyVStack(spacing: 14) {
                        if messages.isEmpty {
                            emptyStateView
                                .padding(.top, 50)
                        } else {
                            // Show messages in normal order with extra padding for latest conversation
                            ForEach(Array(messages.enumerated()), id: \.element.id) { index, message in
                                ChatMessageRow(
                                    message: message,
                                    overrideText: overrideText(for: message),
                                    isCopied: isCopied(message),
                                    isSpeaking: isSpeaking(message),
                                    streamingMessageID: streamingMessageID,
                                    onCopy: handleCopy,
                                    onSpeak: toggleSpeaking
                                )
                                .id(message.id)
                                // Add extra spacing after the latest user message to provide space for AI response
                                .padding(.bottom, (index == messages.count - 1 && message.isFromUser) ? 24 : 0)
                            }
                        }
                        
                        if isTyping {
                            TypingIndicator()
                                .id("typing")
                        }
                        
                        // Simple visibility detector at the bottom
                        Color.clear
                            .frame(height: 1)
                            .id("bottomAnchor")
                            .onAppear {
                                isScrolledUp = false
                            }
                            .onDisappear {
                                if !messages.isEmpty {
                                    isScrolledUp = true
                                }
                            }
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
                    .padding(.bottom, 16)
                    .background(
                        GeometryReader { contentGeo in
                            Color.clear
                                .preference(key: ContentHeightKey.self, value: contentGeo.size.height)
                        }
                    )
                }
                .scrollDismissesKeyboard(.immediately)
                .onAppear { scrollViewHeight = outerGeo.size.height }
                .onChange(of: outerGeo.size.height) { _, newH in scrollViewHeight = newH }
                .onPreferenceChange(ContentHeightKey.self) { height in
                    contentHeight = height
                }
                // Down button overlay centered horizontally, positioned above input bar
                .overlay(alignment: .bottom) {
                    if isScrolledUp && !messages.isEmpty {
                        ScrollToBottomButton(action: {
                            withAnimation(.easeOut(duration: 0.25)) {
                                let targetID: AnyHashable = (messages.last?.id as AnyHashable?) ?? AnyHashable("bottomAnchor")
                                proxy.scrollTo(targetID, anchor: .bottom)
                                isScrolledUp = false
                            }
                        }, inputBarHeight: inputBarHeight)
                        .transition(.asymmetric(
                            insertion: .move(edge: .bottom).combined(with: .opacity).combined(with: .scale(scale: 0.9)),
                            removal: .move(edge: .bottom).combined(with: .opacity).combined(with: .scale(scale: 0.9))
                        ))
                        .animation(.spring(response: 0.3, dampingFraction: 0.7), value: isScrolledUp)
                    }
                }
                .onAppear {
                    DispatchQueue.main.async {
                        withAnimation(.easeOut(duration: 0.25)) {
                            proxy.scrollTo("bottomAnchor", anchor: .bottom)
                        }
                    }
                }
                .onChange(of: scrollToBottomTrigger) { _, _ in
                    let targetID: AnyHashable = (messages.last?.id as AnyHashable?) ?? AnyHashable("bottomAnchor")
                    withAnimation(.easeOut(duration: 0.25)) {
                        proxy.scrollTo(targetID, anchor: .bottom)
                    }
                }
                .onChange(of: messages.count) { _, _ in
                    let targetID: AnyHashable = (messages.last?.id as AnyHashable?) ?? AnyHashable("bottomAnchor")
                    withAnimation(.easeOut(duration: 0.25)) {
                        proxy.scrollTo(targetID, anchor: .bottom)
                    }
                }
                .onChange(of: streamingProgress) { _, _ in
                    if !isScrolledUp {
                        let targetID: AnyHashable = (messages.last?.id as AnyHashable?) ?? AnyHashable("bottomAnchor")
                        withAnimation(.easeOut(duration: 0.18)) {
                            proxy.scrollTo(targetID, anchor: .bottom)
                        }
                    }
                }
                // Keep view pinned to bottom when focusing the input, but only if already near bottom
                .onChange(of: isInputFocused) { _, focused in
                    if focused && !isScrolledUp {
                        let targetID: AnyHashable = (messages.last?.id as AnyHashable?) ?? AnyHashable("bottomAnchor")
                        // Faster, smoother animation for keyboard opening
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { // Reduced delay for responsiveness
                            withAnimation(.easeInOut(duration: 0.2)) { // Faster, smoother animation
                                proxy.scrollTo(targetID, anchor: .bottom)
                            }
                        }
                    }
                }
            }
        }
    }
        
    var body: some View {
        NavigationStack {
            ZStack {
                // Background
                Color(UIColor.systemGroupedBackground)
                    .ignoresSafeArea(edges: [.top])
                    .onTapGesture {
                        // Dismiss keyboard when tapping outside
                        isInputFocused = false
                    }
                
                messagesListView
                
                // Floating toasts (top-aligned)
                VStack(spacing: 8) {
                    if speakingMessageID != nil {
                        HStack(spacing: 10) {
                            Image(systemName: "speaker.wave.2.fill")
                                .foregroundStyle(.primary)
                            Text("Speaking… \(String(format: "%.2f", speakingElapsed))s")
                                .font(.callout)
                                .foregroundStyle(.primary)
                            Spacer(minLength: 0)
                            Button {
                                stopSpeaking()
                            } label: {
                                Image(systemName: "stop.circle.fill")
                                    .symbolRenderingMode(.palette)
                                    .foregroundStyle(.white, .red)
                                    .frame(width: 44, height: 44, alignment: .center)
                                    .contentShape(Rectangle())
                                    .accessibilityLabel("Stop speaking")
                            }
                            .buttonStyle(.plain)
                            .padding(.trailing, -8)
                        }
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                        .modifier(GlassCapsuleBackground())
                        .transition(.move(edge: .top).combined(with: .opacity))
                    } else if let toast = toastMessage {
                        HStack(spacing: 10) {
                            Text(toast)
                                .font(.callout)
                                .foregroundStyle(.primary)
                            Spacer(minLength: 0)
                            Button {
                                withAnimation(.easeOut(duration: 0.2)) { toastMessage = nil }
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .font(.title3)
                                    .symbolRenderingMode(.palette)
                                    .foregroundStyle(.white, .gray)
                                    .accessibilityLabel("Dismiss")
                            }
                            .buttonStyle(.plain)
                        }
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                        .modifier(GlassCapsuleBackground())
                        .transition(.move(edge: .top).combined(with: .opacity))
                    }
                }
                .animation(.easeOut(duration: 0.25), value: speakingMessageID)
                .animation(.easeOut(duration: 0.25), value: toastMessage)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                .padding(.top, 8)
                
            }
            // Native input bar anchored to the bottom safe area with a subtle glass effect
            .safeAreaInset(edge: .bottom) {
                ChatInputBar(
                    text: $messageText,
                    isFocused: $isInputFocused,
                    onSend: {
                        sendMessage()
                    },
                    onCancel: {
                        cancelCurrentRequest()
                    },
                    isBusy: isRequestInFlight,
                    scrollToBottomTrigger: $scrollToBottomTrigger
                )
                .background(
                    GeometryReader { geo in
                        Color.clear
                            .preference(key: InputBarHeightKey.self, value: geo.size.height)
                    }
                )
                .overlay(alignment: .top) { Divider().opacity(0) }
            }
            .onPreferenceChange(InputBarHeightKey.self) { h in
                inputBarHeight = h
            }
            .navigationTitle("Chat with Orion")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        if !messages.isEmpty {
                            // Provide haptic feedback for successful clear
                            let generator = UIImpactFeedbackGenerator(style: .medium)
                            generator.impactOccurred()
                            messages.removeAll()
                        } else {
                            // Provide error haptic feedback when disabled but tapped
                            let generator = UINotificationFeedbackGenerator()
                            generator.notificationOccurred(.error)
                        }
                    } label: {
                        Label("Clear", systemImage: "trash")
                    }
                    .disabled(messages.isEmpty)
                    .accessibilityLabel("Clear conversation")
                }
            }
            .onChange(of: scenePhase) { _, newPhase in
                // Dismiss keyboard and reset any stuck accessory when leaving or returning to the app
                if newPhase != .active {
                    isInputFocused = false
                } else {
                    // Also clear on becoming active to ensure a clean state
                    isInputFocused = false
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.willResignActiveNotification)) { _ in
                // Ensure keyboard and accessory are dismissed when app is backgrounding
                isInputFocused = false
                UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
            }
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
                // Clean up any stuck input accessory on return
                isInputFocused = false
                UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
            }
            .onAppear {
                wsManager.onPromptResponse = { response in
                    DispatchQueue.main.async {
                        guard isRequestInFlight else { return }

                        promptTimeoutWorkItem?.cancel()
                        promptTimeoutWorkItem = nil

                        withAnimation(.easeOut(duration: 0.25)) {
                            isTyping = false
                        }

                        if let error = response.error, !error.isEmpty {
                            isRequestInFlight = false
                            showToast("Server error: \(error)")
                            return
                        }

                        startStreamingResponse(fullText: response.answer)
                    }
                }
            }
            .onDisappear {
                promptTimeoutWorkItem?.cancel()
                promptTimeoutWorkItem = nil
                if wsManager.onPromptResponse != nil {
                    wsManager.onPromptResponse = nil
                }
            }
            .onReceive(Timer.publish(every: 0.05, on: .main, in: .common).autoconnect()) { _ in
                if let start = speakingStartDate, speakingMessageID != nil {
                    speakingElapsed = Date().timeIntervalSince(start)
                    if !speechSynthesizer.isSpeaking {
                        speakingMessageID = nil
                        speakingStartDate = nil
                        speakingElapsed = 0
                    }
                }
            }
        }
    }
    
    // Close any previously opened view builder scope
    private func startStreamingResponse(fullText: String) {
        pendingResponseWorkItem?.cancel()
        pendingResponseWorkItem = nil
        guard isRequestInFlight else { return }
        // Append a new assistant message (content already full, display will be overridden during streaming)
        let assistant = ChatMessage(content: fullText, isFromUser: false)
        withAnimation(.easeOut(duration: 0.25)) {
            messages.append(assistant)
        }
        // Capture the id of the appended message for override
        guard let id = messages.last?.id else { return }
        streamingMessageID = id
        streamingProgress = 0
        streamingTimer?.invalidate()
        let total = fullText.count
        let step = max(1, total / 40) // ~40 steps
        streamingTimer = Timer.scheduledTimer(withTimeInterval: 0.03, repeats: true) { timer in
            streamingProgress = min(total, streamingProgress + step)
            if streamingProgress >= total {
                timer.invalidate()
                streamingTimer = nil
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
                    withAnimation(.easeOut(duration: 0.2)) {
                        streamingMessageID = nil
                    }
                    isRequestInFlight = false
                    // Dismiss keyboard after response completion
                    isInputFocused = false
                }
            }
        }
    }
    
    private func handleCopy(for message: ChatMessage) {
        UIPasteboard.general.string = message.content
        copiedMessageID = message.id
        showToast("Message copied")
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) {
            withAnimation(.easeOut(duration: 0.2)) {
                if copiedMessageID == message.id { copiedMessageID = nil }
            }
        }
    }
    
    private func showToast(_ text: String) {
        toastMessage = text
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.4) {
            withAnimation(.easeOut(duration: 0.2)) {
                if toastMessage == text { toastMessage = nil }
            }
        }
    }
    
    private func startSpeaking(message: ChatMessage) {
        // Stop current speaking if any
        if speechSynthesizer.isSpeaking {
            speechSynthesizer.stopSpeaking(at: .immediate)
        }
        speakingMessageID = message.id
        speakingStartDate = Date()
        speakingElapsed = 0
        
        let utterance = AVSpeechUtterance(string: message.content)
        utterance.voice = AVSpeechSynthesisVoice(language: Locale.current.identifier)
        speechSynthesizer.speak(utterance)
    }
    
    private func stopSpeaking() {
        speechSynthesizer.stopSpeaking(at: .immediate)
        speakingMessageID = nil
        speakingStartDate = nil
        speakingElapsed = 0
    }
    
    private func overrideText(for message: ChatMessage) -> String? {
        if streamingMessageID == message.id {
            return String(message.content.prefix(streamingProgress))
        } else {
            return nil
        }
    }
    
    private func isCopied(_ message: ChatMessage) -> Bool {
        return copiedMessageID == message.id
    }
    
    private func isSpeaking(_ message: ChatMessage) -> Bool {
        return speakingMessageID == message.id
    }
    
    private func toggleSpeaking(for message: ChatMessage) {
        if speakingMessageID == message.id {
            stopSpeaking()
        } else {
            startSpeaking(message: message)
        }
    }
    
    private var emptyStateView: some View {
        VStack(spacing: 20) {
            // Orion Icon
            Image(systemName: "sparkles.rectangle.stack")
                .font(.system(size: 48, weight: .thin))
                .foregroundStyle(.blue.gradient)
            
            VStack(spacing: 8) {
                Text("Welcome to Orion")
                    .font(.title2.weight(.semibold))
                    .foregroundColor(.primary)
                
                Text("Your AI assistant for understanding your surroundings")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }
            
            // Sample questions
            VStack(spacing: 12) {
                Text("Try asking:")
                    .font(.caption.weight(.medium))
                    .foregroundColor(.secondary)
                
                VStack(spacing: 8) {
                    SampleQuestionButton(question: "What do you see?") {
                        sendSampleMessage("What do you see?")
                    }
                    SampleQuestionButton(question: "Help me understand my surroundings") {
                        sendSampleMessage("Help me understand my surroundings")
                    }
                    SampleQuestionButton(question: "What can you help me with?") {
                        sendSampleMessage("What can you help me with?")
                    }
                }
            }
            .padding(.top, 8)
        }
        .padding(.horizontal, 24)
    }
    
    private func sendMessage() {
        let trimmedText = messageText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedText.isEmpty else { return }
        guard !isRequestInFlight else { return }

        guard wsManager.status == .connected else {
            showToast("Connect to Orion server to chat")
            return
        }
        
        // Add user message
        let userMessage = ChatMessage(content: trimmedText, isFromUser: true)
        withAnimation(.easeOut(duration: 0.3)) {
            messages.append(userMessage)
        }
        
        isScrolledUp = false
        scrollToBottomTrigger &+= 1
        
        // Clear input and dismiss keyboard after sending
        messageText = ""
        isInputFocused = false
        
        // Show typing indicator
        withAnimation(.easeOut(duration: 0.3)) {
            isTyping = true
            isRequestInFlight = true
        }
        DispatchQueue.main.async {
            withAnimation(.easeOut(duration: 0.2)) {
                scrollToBottomTrigger &+= 1
            }
        }
        
        DispatchQueue.main.async {
            withAnimation(.easeOut(duration: 0.25)) {
                scrollToBottomTrigger &+= 1
            }
        }
        
        // Cancel any previous queued/timeout work
        pendingResponseWorkItem?.cancel()
        pendingResponseWorkItem = nil
        promptTimeoutWorkItem?.cancel()

        // Send real prompt request to backend
        let prompt = UserPromptMessage(
            promptId: UUID().uuidString,
            question: trimmedText,
            timestamp: Date().timeIntervalSince1970,
            deviceId: deviceManager.deviceId
        )
        wsManager.sendPrompt(prompt)

        // Timeout in case backend never replies
        let timeoutWork = DispatchWorkItem {
            guard isRequestInFlight else { return }
            withAnimation(.easeOut(duration: 0.2)) {
                isTyping = false
            }
            isRequestInFlight = false
            showToast("No response from server. Please try again.")
        }
        promptTimeoutWorkItem = timeoutWork
        DispatchQueue.main.asyncAfter(deadline: .now() + 15, execute: timeoutWork)
    }
    
    private func sendSampleMessage(_ text: String) {
        messageText = text
        sendMessage()
    }
    
    private func cancelCurrentRequest() {
        pendingResponseWorkItem?.cancel()
        pendingResponseWorkItem = nil
        promptTimeoutWorkItem?.cancel()
        promptTimeoutWorkItem = nil
        // Stop typing phase
        isTyping = false
        // Stop streaming and preserve partial content if any
        streamingTimer?.invalidate()
        if let id = streamingMessageID {
            if let index = messages.firstIndex(where: { $0.id == id }) {
                let full = messages[index].content
                let prefix = String(full.prefix(streamingProgress))
                messages[index] = ChatMessage(id: id, content: prefix, isFromUser: false, timestamp: messages[index].timestamp)
            }
            streamingMessageID = nil
        }
        isRequestInFlight = false
    }
}

private struct ChatInputBar: View {
    @Binding var text: String
    var isFocused: FocusState<Bool>.Binding
    var onSend: () -> Void
    var onCancel: () -> Void
    var isBusy: Bool
    @Binding var scrollToBottomTrigger: Int
    
    @State private var isSending: Bool = false
    
    private func hapticSend() {
        let generator = UIImpactFeedbackGenerator(style: .soft)
        generator.impactOccurred()
    }
    
    var body: some View {
        // Core content
        let content = HStack(spacing: 12) {
            HStack(spacing: 8) {
                TextField("Message Orion...", text: $text, axis: .vertical)
                    .textFieldStyle(.plain)
                    .lineLimit(1...6)
                    .font(.body)
                    .focused(isFocused)
                    .submitLabel(.return)
                    .textInputAutocapitalization(.sentences)
                    .autocorrectionDisabled(false)
                    .disabled(isBusy)
                    .onSubmit {
                        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
                        guard !trimmed.isEmpty else { return }
                        hapticSend()
                        onSend()
                    }
            }
            
            Button {
                if isBusy {
                    hapticSend()
                    onCancel()
                } else {
                    let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !trimmed.isEmpty else { return }
                    hapticSend()
                    onSend()
                }
            } label: {
                Group {
                    if isBusy {
                        Image(systemName: "stop.circle.fill")
                            .symbolRenderingMode(.palette)
                            .foregroundStyle(.white, .red)
                    } else {
                        Image(systemName: "arrow.up.circle.fill")
                            .symbolRenderingMode(.palette)
                            .foregroundStyle(.white, .blue)
                    }
                }
                .font(.system(size: 32, weight: .medium))
                .accessibilityLabel(isBusy ? "Cancel response" : "Send message")
            }
            .buttonStyle(.plain)
            .disabled(!isBusy && text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            .opacity((!isBusy && text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty) ? 0.5 : 1.0)
            .animation(.easeInOut(duration: 0.2), value: text)
        }
        
        // Compose floating container with platform-appropriate background
        Group {
            if #available(iOS 26, *) {
                // Liquid Glass with interactivity and subtle tint
                content
                    .padding(.leading, 16)
                    .padding(.trailing, 4)
                    .padding(.vertical, 5) // Reduced from 14 to decrease height
                    .glassEffect(.regular.interactive(), in: .rect(cornerRadius: 24)) // Increased from 20
                    .overlay(
                        RoundedRectangle(cornerRadius: 24, style: .continuous) // Increased from 20
                            .strokeBorder(Color.white.opacity(0.12), lineWidth: 0.5)
                    )
            } else {
                // Backward-compatible material fallback
                content
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12) // Reduced from 14 to decrease height
                    .background(.ultraThinMaterial)
                    .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous)) // Increased from 20
                    .overlay(
                        RoundedRectangle(cornerRadius: 24, style: .continuous) // Increased from 20
                            .strokeBorder(Color.primary.opacity(0.06), lineWidth: 0.5)
                    )
            }
        }
        // Floating affordances common to all versions
        .shadow(color: Color.black.opacity(0.08), radius: 20, x: 0, y: 10)
        .padding(.horizontal, 16)
        .padding(.bottom, 12) // Increased bottom padding between message input and bottom bar
        .contentShape(Rectangle())
        // Allow swipe down gesture directly on the bar to dismiss keyboard
        .gesture(
            DragGesture(minimumDistance: 5, coordinateSpace: .local)
                .onEnded { value in
                    let drag = value.translation.height
                    let predicted = value.predictedEndTranslation.height
                    // Dismiss when the user swipes down decisively or the system predicts a continued downward motion
                    if drag > 20 || predicted > 30 {
                        withAnimation(.easeOut(duration: 0.2)) {
                            isFocused.wrappedValue = false
                        }
                        // Force immediate keyboard dismissal and trigger content repositioning
                        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
                        
                        // Trigger a slight scroll to force content repositioning after keyboard dismissal
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                            withAnimation(.easeOut(duration: 0.3)) {
                                scrollToBottomTrigger &+= 1
                            }
                        }
                    }
                }
        )
        .hoverEffect(.lift)
    }
}

private struct ChatMessageRow: View {
    let message: ChatMessage
    let overrideText: String?
    let isCopied: Bool
    let isSpeaking: Bool
    let streamingMessageID: UUID?
    let onCopy: (ChatMessage) -> Void
    let onSpeak: (ChatMessage) -> Void
    
    var body: some View {
        HStack(alignment: .bottom, spacing: 12) {
            if message.isFromUser {
                Spacer(minLength: 50)
                
                VStack(alignment: .trailing, spacing: 4) {
                    MessageBubble(
                        text: message.content,
                        isFromUser: true
                    )
                    // No timestamp for user messages per request
                }
            } else {
                VStack(alignment: .leading, spacing: 6) {
                    // Assistant message bubble (Markdown-capable)
                    AssistantMarkdownView(text: overrideText ?? message.content)
                    
                    // Action row: speaker, copy, and timestamp (only show after streaming completes)
                    HStack(spacing: 8) {
                        // Only show action buttons after streaming completes
                        if streamingMessageID != message.id {
                            Text(message.timestamp, style: .time)
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .transition(.asymmetric(
                                    insertion: .scale(scale: 0.8).combined(with: .opacity),
                                    removal: .opacity
                                ))
                            
                            Button {
                                onCopy(message)
                            } label: {
                                ZStack {
                                    Image(systemName: "doc.on.doc")
                                        .opacity(isCopied ? 0 : 1)
                                    Image(systemName: "checkmark")
                                        .opacity(isCopied ? 1 : 0)
                                }
                                .font(.caption.weight(.semibold))
                                .frame(width: 16, height: 16)
                                .foregroundStyle(isCopied ? .green : .secondary)
                                .accessibilityLabel(isCopied ? "Copied" : "Copy response")
                            }
                            .buttonStyle(ActionButtonStyle())
                            .transition(.asymmetric(
                                insertion: .scale(scale: 0.8).combined(with: .opacity),
                                removal: .opacity
                            ))
                            
                            Button {
                                onSpeak(message)
                            } label: {
                                Image(systemName: isSpeaking ? "speaker.wave.2.fill" : "speaker.wave.2")
                                    .font(.caption)
                                    .foregroundStyle(isSpeaking ? .blue : .secondary)
                                    .accessibilityLabel(isSpeaking ? "Speaking" : "Speak response")
                            }
                            .buttonStyle(ActionButtonStyle())
                            .transition(.asymmetric(
                                insertion: .scale(scale: 0.8).combined(with: .opacity),
                                removal: .opacity
                            ))
                        }
                        
                        Spacer()
                    }
                    .padding(.leading, 4)
                    .animation(.easeOut(duration: 0.4).delay(0.2), value: streamingMessageID)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(.horizontal, 4)
    }
}

private struct MessageBubble: View {
    let text: String
    let isFromUser: Bool
    
    var body: some View {
        // Render Markdown when possible
        let textView: Text = {
            if let attributed = try? AttributedString(markdown: text) {
                return Text(attributed)
            } else {
                return Text(text)
            }
        }()
        
        return textView
            .font(.body)
            .foregroundColor(.primary)
            .padding(.horizontal, 18)
            .padding(.vertical, 14)
            .background(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .fill(isFromUser ? Color(UIColor.systemGray5) : Color(UIColor.secondarySystemBackground))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(Color.primary.opacity(0.06), lineWidth: 0.5)
            )
    }
}

private struct AssistantMarkdownView: View {
    let text: String
    
    var body: some View {
        let rendered: Text = {
            if let attributed = try? AttributedString(markdown: text) {
                return Text(attributed)
            } else {
                return Text(text)
            }
        }()
        
        return rendered
            .font(.body)
            .foregroundColor(.primary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .textSelection(.enabled)
            .accessibilityLabel("Assistant message")
    }
}

private struct TypingIndicator: View {
    @State private var animationPhase = 0
    
    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            Image("AppLogo")
                .resizable()
                .scaledToFit()
                .frame(width: 22, height: 22)
                .rotationEffect(.degrees(Double(animationPhase)))
                .onAppear {
                    withAnimation(.linear(duration: 1.2).repeatForever(autoreverses: false)) {
                        animationPhase = 360
                    }
                }
            
            Text("Working…")
                .font(.callout)
                .foregroundStyle(.secondary)
            
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 4)
    }
}


private struct ContentHeightKey: PreferenceKey {
    static var defaultValue: CGFloat = 0
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = nextValue()
    }
}

private struct InputBarHeightKey: PreferenceKey {
    static var defaultValue: CGFloat = 0
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = nextValue()
    }
}

private struct ScrollToBottomButton: View {
    let action: () -> Void
    let inputBarHeight: CGFloat

    var body: some View {
        Button(action: { action() }) {
            Group {
                if #available(iOS 26, *) {
                    HStack(spacing: 6) {
                        Image(systemName: "arrow.down")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundStyle(.primary)
                    }
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .glassEffect(.regular.interactive(), in: .capsule)
                    .overlay(
                        Capsule()
                            .strokeBorder(Color.white.opacity(0.12), lineWidth: 0.5)
                    )
                } else {
                    HStack(spacing: 6) {
                        Image(systemName: "arrow.down")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundStyle(.primary)
                    }
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(.ultraThinMaterial)
                    .clipShape(Capsule())
                    .overlay(
                        Capsule()
                            .strokeBorder(Color.primary.opacity(0.06), lineWidth: 0.5)
                    )
                }
            }
            .accessibilityLabel("Scroll to bottom")
        }
        .buttonStyle(.plain)
        .shadow(color: Color.black.opacity(0.1), radius: 16, x: 0, y: 8)
        .frame(maxWidth: .infinity) // Center the button
        .padding(.bottom, max(inputBarHeight + 16, 80)) // Ensure minimum spacing above input bar
    }
}

private struct GlassCapsuleBackground: ViewModifier {
    func body(content: Content) -> some View {
        Group {
            if #available(iOS 26, *) {
                content
                    .glassEffect(.regular.interactive(), in: .capsule)
                    .overlay(
                        Capsule().strokeBorder(Color.white.opacity(0.12), lineWidth: 0.5)
                    )
            } else {
                content
                    .background(.ultraThinMaterial)
                    .clipShape(Capsule())
                    .overlay(
                        Capsule().strokeBorder(Color.primary.opacity(0.06), lineWidth: 0.5)
                    )
            }
        }
        .shadow(color: Color.black.opacity(0.08), radius: 20, x: 0, y: 10)
        .padding(.horizontal, 16)
    }
}

private struct SampleQuestionButton: View {
    let question: String
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack {
                Text(question)
                    .font(.body)
                    .foregroundColor(.primary)
                
                Spacer()
                
                Image(systemName: "arrow.up.right")
                    .font(.caption.weight(.medium))
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(Color(UIColor.secondarySystemBackground))
            .overlay(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .stroke(Color.primary.opacity(0.1), lineWidth: 0.5)
            )
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

struct ChatView_Previews: PreviewProvider {
    static var previews: some View {
        ChatView()
    }
}
