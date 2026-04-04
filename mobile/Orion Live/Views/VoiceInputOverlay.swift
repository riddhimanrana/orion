//
//  VoiceInputOverlay.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 12/19/25.
//  Apple Intelligence-style hovering voice input bar for camera view
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//

import SwiftUI
import Speech
import AVFoundation
#if os(iOS)
import UIKit
#endif

#if os(iOS)
struct VoiceInputOverlay: View {
    @State private var isListening = false
    @State private var transcribedText = ""
    @State private var speechRecognizer = SFSpeechRecognizer()
    @State private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    @State private var recognitionTask: SFSpeechRecognitionTask?
    @State private var audioEngine = AVAudioEngine()
    
    @State private var permissionStatus: SFSpeechRecognizerAuthorizationStatus = .notDetermined
    @State private var showingPermissionAlert = false
    @State private var waveAnimation = false
    @State private var audioLevels: [Float] = [0.1, 0.2, 0.1] // Audio levels for waveform
    // Removed timer-based fake levels; we now compute real RMS-based levels from live audio
    
    @Environment(\.colorScheme) var colorScheme
    @Binding var isVisible: Bool
    
    var body: some View {
        VStack(spacing: 0) {
            Spacer()
            
            // Apple Intelligence-style hovering bar
            if isVisible {
                appleIntelligenceVoiceBar
                    .transition(.asymmetric(
                        insertion: .move(edge: .bottom).combined(with: .scale(scale: 0.95)).combined(with: .opacity),
                        removal: .move(edge: .bottom).combined(with: .opacity)
                    ))
                    .animation(.interpolatingSpring(stiffness: 300, damping: 25), value: isVisible)
            }
        }
        .onAppear {
            requestSpeechPermission()
        }
        .onDisappear {
            stopListening()
        }
        .alert("Speech Recognition Permission", isPresented: $showingPermissionAlert) {
            Button("Settings") {
                if let settingsURL = URL(string: UIApplication.openSettingsURLString) {
                    UIApplication.shared.open(settingsURL)
                }
            }
            Button("Cancel", role: .cancel) { }
        } message: {
            Text("Speech recognition permission is required for voice input. Please enable it in Settings.")
        }
    }
    
    // MARK: - Apple Intelligence Style Voice Bar
    private var appleIntelligenceVoiceBar: some View {
        VStack(spacing: 12) {
            // Main hovering voice input bar - KEEP SAME SHAPE ALWAYS
            HStack(spacing: 16) {
                // Main content area
                HStack(spacing: 12) {
                    // Voice waveform indicator (when listening) - inline with text
                    Group {
                        if isListening {
                            waveformIndicator
                        }
                    }
                    
                    // Text prompt or status with transcription integration
        Text(
            isListening
            ? (transcribedText.isEmpty ? "Listening..." : transcribedText)
            : (transcribedText.isEmpty ? "Ask Orion anything" : transcribedText)
        )
                        .font(.system(size: 17, weight: .medium, design: .rounded))
                        .foregroundStyle(.primary)
            .fixedSize(horizontal: false, vertical: true)
                        .multilineTextAlignment(.leading)
                        .animation(.easeInOut(duration: 0.3), value: isListening)
                        .animation(.easeInOut(duration: 0.3), value: transcribedText)
                    
                    Spacer()
                    
                    // Microphone button with delightful animations - FIXED POSITION
                    microphoneButton
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 16)
            }
            .background(
                // Simplified Apple Intelligence glass background
                ZStack {
                    // Single clean gradient
                    LinearGradient(
                        colors: [
                            Color.white.opacity(colorScheme == .dark ? 0.05 : 0.8),
                            Color.white.opacity(colorScheme == .dark ? 0.02 : 0.6)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                    
                    // Ultra thin material for proper glass effect
                    Rectangle()
                        .fill(.ultraThinMaterial)
                }
            )
            .overlay(
                // Subtle border with gradient
                RoundedRectangle(cornerRadius: 28, style: .continuous)
                    .strokeBorder(
                        LinearGradient(
                            colors: [
                                Color.white.opacity(colorScheme == .dark ? 0.2 : 0.3),
                                Color.white.opacity(colorScheme == .dark ? 0.05 : 0.1)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ),
                        lineWidth: 1
                    )
            )
            .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
            .shadow(
                color: Color.black.opacity(colorScheme == .dark ? 0.3 : 0.1),
                radius: 25,
                x: 0,
                y: 8
            )
            .shadow(
                color: Color.black.opacity(colorScheme == .dark ? 0.1 : 0.05),
                radius: 8,
                x: 0,
                y: 2
            )
        }
        .padding(.horizontal, 24)
        .padding(.bottom, 32) // Position above potential bottom menu
    }
    
    // MARK: - Waveform Indicator
    private var waveformIndicator: some View {
        HStack(spacing: 3) {
            ForEach(0..<3) { index in
                RoundedRectangle(cornerRadius: 1.5)
                    .fill(Color.blue)
                    .frame(width: 3, height: max(6, CGFloat(audioLevels[index]) * 24))
                    .animation(.easeInOut(duration: 0.1), value: audioLevels[index])
            }
        }
    }
    
    // MARK: - Microphone Button
    private var microphoneButton: some View {
        Button(action: {
            if isListening {
                stopListening()
            } else {
                startListening()
            }
        }) {
            ZStack {
                // Microphone icon with solid fill when listening (no layout shift)
                ZStack {
                    Circle()
                        .fill(isListening ? Color.blue : Color.clear)
                        .frame(width: 44, height: 44)
                        .overlay(
                            Circle()
                                .strokeBorder(Color.primary.opacity(0.2), lineWidth: 1.5)
                        )
                    
                    // Keep icon consistent to avoid visual shifts
                    Image(systemName: "mic")
                        .font(.system(size: 20, weight: .medium))
                        .foregroundStyle(isListening ? .white : .primary)
                }
            }
        }
        .buttonStyle(.plain)
        .disabled(permissionStatus != .authorized)
        .accessibilityLabel(isListening ? "Stop voice input" : "Start voice input")
        .accessibilityHint(isListening ? "Tap to stop recording" : "Tap to start voice recording")
        .onChange(of: isListening) { _, listening in
            // Haptic feedback
            let generator = UIImpactFeedbackGenerator(style: listening ? .medium : .light)
            generator.impactOccurred()
        }
    }
    
    // MARK: - Speech Recognition Methods
    private func requestSpeechPermission() {
        SFSpeechRecognizer.requestAuthorization { status in
            DispatchQueue.main.async {
                permissionStatus = status
                if status != .authorized {
                    showingPermissionAlert = true
                }
            }
        }
    }
    
    private func startListening() {
        guard permissionStatus == .authorized else {
            showingPermissionAlert = true
            return
        }
        
        // Cancel any existing task
        recognitionTask?.cancel()
        recognitionTask = nil
        
        // Configure audio session
        let audioSession = AVAudioSession.sharedInstance()
        do {
            try audioSession.setCategory(.record, mode: .measurement, options: .duckOthers)
            try audioSession.setActive(true, options: .notifyOthersOnDeactivation)
        } catch {
            print("Audio session configuration failed: \(error)")
            return
        }
        
        // Create recognition request
        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        
        let inputNode = audioEngine.inputNode
        guard let recognitionRequest = recognitionRequest else {
            print("Unable to create recognition request")
            return
        }
        
        // Configure request for live recognition
        recognitionRequest.shouldReportPartialResults = true
        
        // Create recognition task
        recognitionTask = speechRecognizer?.recognitionTask(with: recognitionRequest) { result, error in
            DispatchQueue.main.async {
                if let result = result {
                    transcribedText = result.bestTranscription.formattedString
                }
                
                if let error = error {
                    print("Speech recognition error: \(error)")
                    stopListening()
                } else if result?.isFinal == true {
                    stopListening()
                }
            }
        }
        
        // Configure audio input
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
            recognitionRequest.append(buffer)

            // Calculate audio levels using RMS -> dB -> normalized [0,1]
            guard let channelData = buffer.floatChannelData?[0] else { return }
            let frameCount = Int(buffer.frameLength)
            if frameCount == 0 { return }

            // Compute RMS via mean of squares
            var sumSquares: Float = 0
            for i in 0..<frameCount {
                let s = channelData[i]
                sumSquares += s * s
            }
            let meanSquare = sumSquares / max(1, Float(frameCount))
            let rms = sqrtf(meanSquare + 1e-12) // epsilon to avoid log(0)

            // Convert to dB. Typical range: [-60, 0] (boost sensitivity a bit)
            let db = 20.0 * log10(Double(rms))
            let minDb: Double = -60.0
            let clampedDb = max(minDb, db)
            var normalized = Float((clampedDb - minDb) / -minDb) // 0 -> silence, 1 -> loud
            // Slight gamma to increase sensitivity to quieter speech
            normalized = pow(max(0.0, min(1.0, normalized)), 0.6)

            DispatchQueue.main.async {
                // Shift levels to behave like a tiny history for 3 bars (stable width)
                var newLevels = audioLevels
                newLevels.removeFirst()
                newLevels.append(max(0.05, min(1.0, normalized)))
                audioLevels = newLevels
            }
        }
        
        // Start audio engine
        audioEngine.prepare()
        do {
            try audioEngine.start()
            DispatchQueue.main.async {
                isListening = true
                transcribedText = ""
            }
        } catch {
            print("Audio engine start failed: \(error)")
        }
    }
    
    private func stopListening() {
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        
        // Reset audio levels
        audioLevels = [0.1, 0.2, 0.1]
        
        recognitionRequest?.endAudio()
        recognitionRequest = nil
        
        recognitionTask?.cancel()
        recognitionTask = nil
        
        isListening = false
    }
}

#else
// Fallback for non-iOS platforms
struct VoiceInputOverlay: View {
    @Binding var isVisible: Bool
    
    var body: some View {
        Text("Voice input not available on this platform")
            .foregroundStyle(.secondary)
    }
}
#endif

// MARK: - Preview
#if DEBUG
struct VoiceInputOverlay_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            // Mock camera background
            LinearGradient(
                colors: [
                    Color.blue.opacity(0.3),
                    Color.purple.opacity(0.3),
                    Color.pink.opacity(0.2)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            
            VoiceInputOverlay(isVisible: .constant(true))
        }
        .preferredColorScheme(.dark)
    }
}
#endif