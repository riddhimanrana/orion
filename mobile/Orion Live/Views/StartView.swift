//
//  StartView.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Animated start/loading view with typewriter and particle effects for Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//
import SwiftUI
import Combine
import WebRTC

struct StartView: View {
    @Environment(\.colorScheme) var colorScheme
    @EnvironmentObject var objectDetector: ObjectDetector
    @EnvironmentObject var webRTCManager: WebRTCManager
    @EnvironmentObject var signalingClient: SignalingClient
    @Binding var isCameraActive: Bool
    var onStart: (@escaping () -> Void) -> Void

    @State private var isLoading = false
    @State private var pulsating = false
    @State private var nodes: [Node] = []
    @State private var timer = Timer.publish(every: 1/60, on: .main, in: .common).autoconnect()
    @State private var displayedText = ""
    @State private var typewriterTimer: Timer?
    @State private var quoteHasBeenTyped = false


    struct Node: Identifiable {
        let id = UUID()
        var position: CGPoint
        var velocity: CGVector
        var size: CGFloat
        var speed: Double // Animation duration
        var opacity: Double
        var stretch: CGFloat = 1.0
        var angle: Double = 0.0
    }

    var body: some View {
        ZStack {
            // Background
            (colorScheme == .dark ? Color.black : Color.white).edgesIgnoringSafeArea(.all)

            // Animated particles
            ForEach(nodes) { node in
                Capsule()
                    .fill((colorScheme == .dark ? Color.white : Color.black).opacity(node.opacity))
                    .frame(width: node.size * node.stretch, height: node.size)
                    .rotationEffect(.degrees(node.angle))
                    .position(node.position)
            }
            .onAppear(perform: setupNodes)
            .onReceive(timer) { _ in
                guard !isLoading else {
                    timer.upstream.connect().cancel()
                    return
                }
                moveNodes()
            }

            VStack {
                Spacer()

                // Title
                Text(displayedText)
                    .font(.title2)
                    .fontWeight(.medium)
                    .multilineTextAlignment(.center)
                    .foregroundColor(colorScheme == .dark ? .white : .black)
                    .padding()
                    .onAppear(perform: startTypewriterEffect)

                Spacer()

                // Start Button
                ZStack {
                    // Button
                    Button(action: {
                        let haptic = UIImpactFeedbackGenerator(style: .heavy)
                        haptic.impactOccurred()
                        startLoading()
                    }) {
                        OrionEyeView(size: 60)
                            .foregroundColor(colorScheme == .dark ? .black : .white)
                            .padding(33)
                            .background(
                                Circle()
                                    .fill(colorScheme == .dark ? Color.white : Color.black)
                                    .shadow(color: (colorScheme == .dark ? Color.white : Color.black).opacity(0.4), radius: 15, x: 0, y: 10)
                            )
                    }
                }
                .onAppear {
                    self.pulsating = true
                }
                
                Spacer()
                Spacer()
            }
            .blur(radius: isLoading ? 30 : 0)
            .scaleEffect(isLoading ? 0.5 : 1.0)
            .opacity(isLoading ? 0 : 1)
            .onAppear(perform: setupNodes)
            .animation(.easeInOut(duration: 1.2), value: isLoading)
            
            // Loading Indicator
            if isLoading {
                VStack(spacing: 20) {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: colorScheme == .dark ? .white : .black))
                        .scaleEffect(2.0)
                    Text("Connecting to macOS Server...")
                        .font(.title3)
                        .foregroundColor((colorScheme == .dark ? Color.white : Color.black).opacity(0.8))
                }
                .transition(.opacity)
            }
        }
        // Place pills as an inset just above home indicator/bottom bar
        .safeAreaInset(edge: .bottom) {
            HStack {
                ServerStatusPill()
                Spacer(minLength: 16)
                ProcessingModePill()
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 10)
        }
        .onReceive(Just(isCameraActive)) { newIsCameraActive in
            if newIsCameraActive {
                let haptic = UIImpactFeedbackGenerator(style: .soft)
                haptic.impactOccurred()
            }
        }
    }
    
    private func startTypewriterEffect() {
        guard !quoteHasBeenTyped else { return }
        
        let quote = Quotes.rotatingQuotes.randomElement() ?? ""
        var charIndex = 0
        
        typewriterTimer?.invalidate()
        typewriterTimer = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { timer in
            if charIndex < quote.count {
                let index = quote.index(quote.startIndex, offsetBy: charIndex)
                displayedText.append(quote[index])
                
                let haptic = UIImpactFeedbackGenerator(style: .light)
                haptic.impactOccurred()
                
                charIndex += 1
            } else {
                timer.invalidate()
                quoteHasBeenTyped = true
            }
        }
    }


    private func setupNodes() {
        nodes = (0..<150).map { _ in
            let size = CGFloat.random(in: 1...3)
            let speed = Double.random(in: 0.6...1.0) // Animation duration
            return Node(
                position: CGPoint(x: .random(in: 0...UIScreen.main.bounds.width), y: .random(in: 0...UIScreen.main.bounds.height)),
                velocity: CGVector(dx: .random(in: -0.2...0.2), dy: .random(in: -0.2...0.2)),
                size: size,
                speed: speed,
                opacity: .random(in: 0.2...0.8)
            )
        }
    }

    private func moveNodes() {
        for i in nodes.indices {
            nodes[i].position.x += nodes[i].velocity.dx
            nodes[i].position.y += nodes[i].velocity.dy

            if nodes[i].position.x < 0 || nodes[i].position.x > UIScreen.main.bounds.width {
                nodes[i].velocity.dx *= -1
            }
            if nodes[i].position.y < 0 || nodes[i].position.y > UIScreen.main.bounds.height {
                nodes[i].velocity.dy *= -1
            }
        }
    }
    
    private func triggerHyperspeed() {
        let center = CGPoint(x: UIScreen.main.bounds.width / 2, y: UIScreen.main.bounds.height / 2)
        let screenWidth = UIScreen.main.bounds.width
        let screenHeight = UIScreen.main.bounds.height
        let maxDimension = max(screenWidth, screenHeight)

        // 1. Prepare nodes for animation by assigning them a random outward angle
        for i in nodes.indices {
            let angle = Double.random(in: 0..<360)
            nodes[i].angle = angle
            nodes[i].position = center // Start all nodes from the center
            nodes[i].stretch = 1.0
            nodes[i].opacity = 0.8 // Make them visible for the burst
        }

        // 2. Trigger the animation
        for i in nodes.indices {
            let node = nodes[i]
            let angleRad = node.angle * .pi / 180

            // Streaks will be long enough to shoot off-screen
            let streakLength: CGFloat = maxDimension * 1.5 // Ensure it goes far off-screen

            // The final position is the center of the stretched capsule.
            // If the base is at 'center', then the center of the capsule is 'streakLength / 2' away from 'center'.
            let finalPosition = CGPoint(
                x: center.x + CGFloat(cos(Double(angleRad))) * (streakLength / 2),
                y: center.y + CGFloat(sin(Double(angleRad))) * (streakLength / 2)
            )

            withAnimation(.easeOut(duration: node.speed).delay(Double.random(in: 0...0.15))) {
                nodes[i].stretch = streakLength
                nodes[i].position = finalPosition
                nodes[i].opacity = 0
            }
        }

        // 3. Transition to camera view after the animation
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            withAnimation {
                isCameraActive = true
            }
        }
    }

    private func startLoading() {
        withAnimation(.easeInOut(duration: 0.5)) {
            isLoading = true
        }
        triggerHyperspeed()
        // Local model execution is deprecated. Mark model as ready instantly and proceed to camera view.
        objectDetector.isModelReady = true
        Logger.shared.log("Bypassed local YOLO11n loading (running server-side).")
        onStart { }
    }
}

struct OrionEyeView: View {
    @Environment(\.colorScheme) private var colorScheme
    var size: CGFloat

    // Horizontal look target in the range [-1, 1]
    @State private var lookOffset: CGFloat = -1.0
    @State private var lookTask: Task<Void, Never>? = nil

    // Vertical placement: push the pupil up toward the top of the eye
    private var verticalOffset: CGFloat { -size * 0.14 }

    // Geometry helpers to keep the pupil inside the ring even when offset upward
    private var innerRadius: CGFloat { size * 0.48 } // matches sclera 0.96 * size
    private var pupilRadius: CGFloat { size * 0.175 } // matches pupil 0.35 * size

    // Max horizontal travel allowed at this vertical offset so the pupil stays inside the circle
    private var maxHorizontalTravel: CGFloat {
        let y = abs(verticalOffset)
        let r = innerRadius
        // available half-width at this y inside the circle
        let halfChord = max(0, sqrt(max(0, r * r - y * y)))
        // subtract pupil radius and a tiny margin
        return max(0, halfChord - pupilRadius - size * 0.02)
    }

    var body: some View {
        let ringColor = (colorScheme == .dark ? Color.white : Color.black)
        let scleraColor = (colorScheme == .dark ? Color.black : Color.white)

        ZStack {
            // Outer ring
            Circle()
                .stroke(ringColor.opacity(0.9), lineWidth: max(2, size * 0.05))
                .frame(width: size, height: size)
                .shadow(color: ringColor.opacity(0.25), radius: size * 0.08, x: 0, y: size * 0.04)

            // Sclera (background of the eye)
            Circle()
                .fill(scleraColor)
                .frame(width: size * 0.96, height: size * 0.96)

            // Iris + Pupil group that moves together
            ZStack {
                // Keep only the pupil for a minimalist look
                Circle()
                    .fill(ringColor)
                    .frame(width: size * 0.38, height: size * 0.38)
            }
            // Natural left-right movement constrained to the upper arc
            .offset(x: lookOffset * maxHorizontalTravel, y: verticalOffset)
        }
        .frame(width: size, height: size)
        .onAppear {
            // Kick off a natural, human-like look loop with varying saccades and dwells
            if lookTask == nil {
                lookTask = Task { await lookLoop() }
            }
        }
        .onDisappear {
            lookTask?.cancel()
            lookTask = nil
        }
        .accessibilityLabel("Orion Eye")
        .accessibilityAddTraits(.isImage)
    }

    // MARK: - Natural Look Loop
    private func lookLoop() async {
        // Start by looking to the right to signal life
        await animate(to: 1.0, response: 0.55, damping: 0.85)
        await sleepRandom(0.5, 1.2)

        while !Task.isCancelled {
            // Choose a new target with some bias toward edges for cuteness
            let candidates: [CGFloat] = [-1.0, -0.6, -0.2, 0.0, 0.3, 0.7, 1.0]
            let weights: [Double] = [0.22, 0.14, 0.08, 0.08, 0.14, 0.16, 0.18]
            let next = weightedRandom(from: candidates, weights: weights)

            // Quick saccade to the next point with a soft spring
            await animate(to: next, response: .random(in: 0.35...0.65), damping: 0.88)

            // Dwell (linger) a bit, like a human gaze
            await sleepRandom(0.35, 1.0)

            // Tiny micro-adjustment for life-like motion (no more than 8% of range)
            if Bool.random() {
                let micro = max(-1, min(1, next + CGFloat.random(in: -0.08...0.08)))
                await animate(to: micro, response: .random(in: 0.28...0.5), damping: 0.9)
                await sleepRandom(0.2, 0.6)
            }
        }
    }

    @MainActor
    private func animate(to value: CGFloat, response: Double, damping: Double) async {
        await withCheckedContinuation { continuation in
            withAnimation(.spring(response: response, dampingFraction: damping, blendDuration: 0.2)) {
                lookOffset = value
            }
            // Roughly wait the animation response time before continuing
            DispatchQueue.main.asyncAfter(deadline: .now() + response) {
                continuation.resume()
            }
        }
    }

    private func sleepRandom(_ a: Double, _ b: Double) async {
        let delay = Double.random(in: a...b)
        try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
    }

    private func weightedRandom<T>(from values: [T], weights: [Double]) -> T {
        let total = weights.reduce(0, +)
        let r = Double.random(in: 0..<total)
        var sum = 0.0
        for (i, w) in weights.enumerated() {
            sum += w
            if r < sum { return values[i] }
        }
        return values.last! // Fallback
    }
}

struct StartView_Previews: PreviewProvider {
    static var previews: some View {
        let authManager = AuthManager()
        let deviceManager = DeviceManager(supabase: authManager.supabase)
        let apiService = APIService(supabase: authManager.supabase)
        let signalingClient = SignalingClient(apiService: apiService, deviceManager: deviceManager)
        let webRTCManager = WebRTCManager(signalingClient: signalingClient)
        let webSocketManager = WebSocketManager()
        let objectDetector = ObjectDetector()
        
        StartView(isCameraActive: .constant(false), onStart: { completion in completion() })
            .environmentObject(objectDetector)
            .environmentObject(webSocketManager)
            .environmentObject(webRTCManager)
            .environmentObject(signalingClient)
    }
}
