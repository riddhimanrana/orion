//
//  WebRTCManager.swift
//  Orion Server
//
//  Created by Gemini on 8/15/25.
//

import Foundation
import WebRTC
// Shared P2P message contract
// Uses top-level Models/P2PMessage.swift available to both targets

@MainActor
class WebRTCManager: NSObject, ObservableObject {
    @Published var connectionState: RTCIceConnectionState = .new {
        didSet {
            print("WebRTC connection state changed to: \(connectionState.description)")
        }
    }
    @Published var videoTrack: RTCVideoTrack?
    @Published var receivedMessage: String = ""
// Ephemeral TURN TTL remaining (seconds). Published for UI.
    @Published var ephemeralTTLRemaining: Int? = nil
    
    private var peerConnection: RTCPeerConnection?
    private var dataChannel: RTCDataChannel?
    private var peerConnectionFactory: RTCPeerConnectionFactory?
    private let signalingClient: SignalingClient
    private var pendingCandidates: [RTCIceCandidate] = []
    @Published var iceStatus: ICEStatus = ICEStatus()
    private var statsTimer: Timer?
    private var iceTTLTimer: Timer?

    init(signalingClient: SignalingClient) {
        self.signalingClient = signalingClient
        super.init()
        print("WebRTCManager: Initialized (factory will be created lazily).")
    }

    private func ensureFactory() {
        if peerConnectionFactory == nil {
            let videoEncoderFactory = RTCDefaultVideoEncoderFactory()
            let videoDecoderFactory = RTCDefaultVideoDecoderFactory()
            self.peerConnectionFactory = RTCPeerConnectionFactory(encoderFactory: videoEncoderFactory, decoderFactory: videoDecoderFactory)
            print("WebRTCManager: Created RTCPeerConnectionFactory.")
        }
    }

    func connect() {
        self.signalingClient.delegate = self
        self.signalingClient.connect()
    }

    func disconnect() {
        signalingClient.disconnect()
        peerConnection?.close()
        peerConnection = nil
        self.connectionState = .closed
    }

    private func setupPeerConnection(iceServers: [RTCIceServer]) {
        ensureFactory()
        guard let factory = peerConnectionFactory else {
            print("WebRTCManager: ERROR – peerConnectionFactory not available.")
            return
        }
        let configuration = RTCConfiguration()
        configuration.iceServers = iceServers
        configuration.sdpSemantics = .unifiedPlan

        let constraints = RTCMediaConstraints(mandatoryConstraints: nil, optionalConstraints: ["DtlsSrtpKeyAgreement": "true"])

        self.peerConnection = factory.peerConnection(with: configuration, constraints: constraints, delegate: self)

        // Ensure we can receive a remote video track (Unified Plan requires a recv transceiver)
        let recvOnly = RTCRtpTransceiverInit()
        recvOnly.direction = .recvOnly
        _ = self.peerConnection?.addTransceiver(of: .video, init: recvOnly)

        let config = RTCDataChannelConfiguration()
        config.isOrdered = true // reliable ordered control/data
        if let channel = self.peerConnection?.dataChannel(forLabel: "orion-data", configuration: config) {
            channel.delegate = self
            self.dataChannel = channel
        }
    }

    private func setupPeerConnectionWithEphemeralICE() async {
        var servers = Self.buildIceServersFromInfoPlist()
        do {
            if let id = signalingClient.webrtcDeviceId() {
                let apiService = signalingClient.webrtcAPI()
                let token = try await apiService.fetchWebRTCToken(deviceId: id)
                let ice = try await apiService.fetchEphemeralICE(token: token)
                let turn = RTCIceServer(urlStrings: ice.urls, username: ice.username, credential: ice.credential)
                servers = [turn]
                // Publish TTL for UI and start countdown
                if let exp = ice.expiresAt {
                    startEphemeralTTLCountdown(expiresAt: exp)
                } else {
                    self.ephemeralTTLRemaining = ice.ttl
                    startEphemeralTTLCountdown(seconds: ice.ttl)
                }
            }
        } catch {
            print("Ephemeral ICE fetch failed, using Info.plist: \(error.localizedDescription)")
        }
        self.setupPeerConnection(iceServers: servers)
    }

    // MARK: - ICE Servers
    private static func buildIceServersFromInfoPlist() -> [RTCIceServer] {
        var servers: [RTCIceServer] = []
        let defaultStuns = [
            "stun:stun.l.google.com:19302",
            "stun:global.stun.twilio.com:3478"
        ]
        servers.append(RTCIceServer(urlStrings: defaultStuns))

        if let info = Bundle.main.infoDictionary {
            if let turnURLs = info["TURN_URLS"] as? [String], !turnURLs.isEmpty {
                let turnUser = (info["TURN_USERNAME"] as? String) ?? ""
                let turnPass = (info["TURN_PASSWORD"] as? String) ?? ""
                let turn = RTCIceServer(urlStrings: turnURLs, username: turnUser, credential: turnPass)
                servers.append(turn)
            } else if let turnURL = info["TURN_URL"] as? String, !turnURL.isEmpty { // backward compat
                let turnUser = (info["TURN_USERNAME"] as? String) ?? ""
                let turnPass = (info["TURN_PASSWORD"] as? String) ?? ""
                let turn = RTCIceServer(urlStrings: [turnURL], username: turnUser, credential: turnPass)
                servers.append(turn)
            }
        }
        return servers
    }
}

// MARK: - SignalingClientDelegate
extension WebRTCManager: SignalingClientDelegate {
    nonisolated func signalingClientDidConnect(_ client: SignalingClient) {
        Task { @MainActor in
            print("WebRTCManager: Signaling connected. Setting up PeerConnection.")
            await self.setupPeerConnectionWithEphemeralICE()
        }
    }

    nonisolated func signalingClientDidDisconnect(_ client: SignalingClient) {
        Task { @MainActor in self.disconnect() }
    }

    nonisolated func signalingClient(_ client: SignalingClient, didReceiveRemoteSdp sdp: RTCSessionDescription) {
        Task { await self.handleRemoteSdp(sdp) }
    }

    private func handleRemoteSdp(_ sdp: RTCSessionDescription) async {
        guard let pc = self.peerConnection else { return }

        do {
            try await pc.setRemoteDescription(sdp)

            processPendingCandidates()

            if sdp.type == .offer {
                let answer = try await pc.answer(for: RTCMediaConstraints(mandatoryConstraints: nil, optionalConstraints: nil))
                try await pc.setLocalDescription(answer)
                self.signalingClient.sendSdp(answer)
            }
        } catch {
            print("WebRTCManager Error: Failed to set remote/local description: \(error)")
        }
    }

    nonisolated func signalingClient(_ client: SignalingClient, didReceiveCandidate candidate: RTCIceCandidate) {
        Task { @MainActor in
            if self.peerConnection?.remoteDescription != nil {
                self.add(candidate: candidate)
            } else {
                self.pendingCandidates.append(candidate)
            }
        }
    }

    private func processPendingCandidates() {
        for candidate in pendingCandidates {
            self.add(candidate: candidate)
        }
        self.pendingCandidates.removeAll()
    }

    private func add(candidate: RTCIceCandidate) {
        self.peerConnection?.add(candidate) { error in
            if let error = error {
                print("WebRTCManager Error: Failed to add ICE candidate: \(error)")
            }
        }
    }

    nonisolated func signalingClient(_ client: SignalingClient, didReceiveProcessingMode mode: String) {
        Task { @MainActor in
            print("WebRTCManager: iOS app switched to \(mode) mode")
            if mode.lowercased() == "server" {
                // iOS is in server mode, establish connection
                if self.connectionState == .disconnected {
                    await self.setupPeerConnectionWithEphemeralICE()
                }
            } else {
                // iOS is not in server mode, disconnect
                print("WebRTCManager: Disconnecting as iOS is not in server mode")
                self.disconnect()
            }
        }
    }
    
    nonisolated func signalingClient(_ client: SignalingClient, didEncounterError error: Error) {
        Task { @MainActor in
            print("WebRTCManager received error from signaling client: \(error.localizedDescription)")
            self.disconnect()
        }
    }
}

// MARK: - RTCPeerConnectionDelegate
extension WebRTCManager: RTCPeerConnectionDelegate {
    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didChange state: RTCIceConnectionState) {
        Task { @MainActor in
            self.connectionState = state
            if state == .connected { self.startICEStatsPolling() }
            if [.failed, .disconnected, .closed].contains(state) { self.stopICEStatsPolling() }
        }
    }

    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didGenerate candidate: RTCIceCandidate) {
        Task { @MainActor in self.signalingClient.sendCandidate(candidate) }
    }

    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didAdd rtpReceiver: RTCRtpReceiver, streams: [RTCMediaStream]) {
        if let track = rtpReceiver.track as? RTCVideoTrack {
            print("WebRTCManager: Received remote video track.")
            Task { @MainActor in self.videoTrack = track }
        }
    }

    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didOpen dataChannel: RTCDataChannel) {
        print("WebRTCManager: Data channel opened.")
        Task { @MainActor in
            self.dataChannel = dataChannel
            self.dataChannel?.delegate = self
        }
    }

    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didAdd stream: RTCMediaStream) {}
    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didRemove stream: RTCMediaStream) {}
    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didChange newState: RTCIceGatheringState) {}
    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didChange signalingState: RTCSignalingState) {}
    nonisolated func peerConnectionShouldNegotiate(_ peerConnection: RTCPeerConnection) {}
    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didRemove rtpReceiver: RTCRtpReceiver) {}
    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didRemove candidates: [RTCIceCandidate]) {}
}

// MARK: - ICE Stats Polling
extension WebRTCManager {
    private func startEphemeralTTLCountdown(expiresAt: Int) {
        iceTTLTimer?.invalidate()
        let targetDate = Date(timeIntervalSince1970: TimeInterval(expiresAt))
        // Seed immediately
        self.ephemeralTTLRemaining = max(0, Int(targetDate.timeIntervalSinceNow.rounded()))
        iceTTLTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            guard let self else { return }
            let remaining = Int(targetDate.timeIntervalSinceNow.rounded())
            Task { @MainActor in
                if remaining <= 0 {
                    self.ephemeralTTLRemaining = 0
                    self.iceTTLTimer?.invalidate()
                    self.iceTTLTimer = nil
                } else {
                    self.ephemeralTTLRemaining = remaining
                }
            }
        }
    }

    private func startEphemeralTTLCountdown(seconds: Int) {
        iceTTLTimer?.invalidate()
        var remaining = seconds
        self.ephemeralTTLRemaining = max(0, remaining)
        iceTTLTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] timer in
            guard let self else { return }
            remaining -= 1
            let newRemaining = remaining
            Task { @MainActor in
                if newRemaining <= 0 {
                    self.ephemeralTTLRemaining = 0
                    timer.invalidate()
                    self.iceTTLTimer = nil
                } else {
                    self.ephemeralTTLRemaining = newRemaining
                }
            }
        }
    }

    private func startICEStatsPolling() {
        statsTimer?.invalidate()
        statsTimer = Timer.scheduledTimer(withTimeInterval: 3.0, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.updateICEStatus() }
        }
    }

    private func stopICEStatsPolling() {
        statsTimer?.invalidate()
        statsTimer = nil
    }

    private func updateICEStatus() {
        // Safe no-op: avoid using KVC on opaque WebRTC statistics that can throw NSUnknownKeyException
        // We'll keep the existing iceStatus until we implement a typed stats parser compatible with this WebRTC build.
        // This prevents rare runtime crashes while still allowing the rest of the app to function.
        // DEV: Re-enable typed stats parsing once verified for the macOS WebRTC package version.
        // print("updateICEStatus: Skipping stats parsing on mac to avoid KVC crashes.")
        return
    }
}

struct ICEStatus {
    var usingTURN: Bool = false
    var localType: String = "-"
    var remoteType: String = "-"
    var transport: String = "-"
}

// MARK: - RTCDataChannelDelegate
extension WebRTCManager: RTCDataChannelDelegate {
    nonisolated func dataChannelDidChangeState(_ dataChannel: RTCDataChannel) {
        print("macOS: Data channel state changed to: \(dataChannel.readyState)")
    }

    nonisolated func dataChannel(_ dataChannel: RTCDataChannel, didReceiveMessageWith buffer: RTCDataBuffer) {
        // Try JSON P2P decode first
        if let decoded = try? P2PMessageCodec.decode(buffer.data) {
            switch decoded.data {
            case .ping(let payload):
                // Echo JSON pong
                let pong = P2PMessage(type: .pong,
                                       correlationId: decoded.id,
                                       data: .pong(PongPayload(clientTs: payload.clientTs)))
                if let bytes = try? P2PMessageCodec.encode(pong) {
                    dataChannel.sendData(RTCDataBuffer(data: bytes, isBinary: false))
                }
                Task { @MainActor in self.receivedMessage = "ping(json)" }
            default:
                break
            }
            return
        }

        // Legacy plaintext fallback
        let message = String(data: buffer.data, encoding: .utf8) ?? ""
        print("macOS: Received message: \(message)")
        Task { @MainActor in self.receivedMessage = message }
        if message == "ping" {
            let pongBuffer = RTCDataBuffer(data: "pong".data(using: .utf8)!, isBinary: false)
            dataChannel.sendData(pongBuffer)
        }
    }
}

// MARK: - RTC Enum Descriptions
extension RTCIceConnectionState {
    var description: String {
        switch self {
        case .new: return "New"
        case .checking: return "Checking"
        case .connected: return "Connected"
        case .completed: return "Completed"
        case .failed: return "Failed"
        case .disconnected: return "Disconnected"
        case .closed: return "Closed"
        case .count: return "Count"
        @unknown default: return "Unknown"
        }
    }
}

