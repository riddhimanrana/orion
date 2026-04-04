
//
//  WebRTCManager.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 8/14/25.
//

import Foundation
import WebRTC
import Combine

struct ICEStatusSnapshot {
    var usingTURN: Bool = false
    var localType: String = "unknown"
    var remoteType: String = "unknown"
    var transport: String = "unknown"
}

@MainActor
class WebRTCManager: NSObject, ObservableObject {

    @Published var connectionState: RTCIceConnectionState = .new
    @Published var signalingState: RTCSignalingState = .stable
    @Published var dataChannelState: RTCDataChannelState = .closed
    @Published var iceStatus: ICEStatusSnapshot = ICEStatusSnapshot()
    @Published var ephemeralTTLRemaining: Int? = nil
    @Published var iceUsage: ICEUsage? = nil
    @Published private(set) var lastPingRTT: TimeInterval? = nil

    private var peerConnection: RTCPeerConnection?
    private var peerConnectionFactory: RTCPeerConnectionFactory
    private var videoTrack: RTCVideoTrack?
    private var keyframeVideoCapturer: KeyframeVideoCapturer?
    private var dataChannel: RTCDataChannel?
    private let signalingClient: SignalingClient
    private var pingTimer: Timer?
    private var pingStartTime: Date?

    weak var delegate: WebRTCManagerDelegate?

    init(signalingClient: SignalingClient) {
        self.signalingClient = signalingClient
        let videoEncoderFactory = RTCDefaultVideoEncoderFactory()
        let videoDecoderFactory = RTCDefaultVideoDecoderFactory()
        self.peerConnectionFactory = RTCPeerConnectionFactory(encoderFactory: videoEncoderFactory, decoderFactory: videoDecoderFactory)
        super.init()
    }

    func connect() async {
        guard peerConnection == nil else { return }
        Logger.shared.network("WebRTC: Starting connection", level: .info)
        self.signalingClient.delegate = self
        setupPeerConnection()
        await signalingClient.connect()
    }

    func disconnect() {
        pingTimer?.invalidate()
        pingTimer = nil
        peerConnection?.close()
        peerConnection = nil
        signalingClient.disconnect()
        self.connectionState = .closed
        self.dataChannelState = .closed
        Logger.shared.network("WebRTC: Disconnected", level: .info)
    }

    func sendPing() {
        guard dataChannel?.readyState == .open else { return }
        pingStartTime = Date()
        let message = RTCDataBuffer(data: "ping".data(using: .utf8)!, isBinary: false)
        dataChannel?.sendData(message)
    }

    // Backward-compatible alias used by DebugTabView
    func sendPingP2P() {
        sendPing()
    }

    private func setupPeerConnection() {
        let configuration = RTCConfiguration()
        configuration.iceServers = [RTCIceServer(urlStrings: ["stun:stun.l.google.com:19302"])]
        configuration.sdpSemantics = .unifiedPlan

        let constraints = RTCMediaConstraints(mandatoryConstraints: nil, optionalConstraints: ["DtlsSrtpKeyAgreement": "true"])
        self.peerConnection = peerConnectionFactory.peerConnection(with: configuration, constraints: constraints, delegate: self)

        createMediaSenders()
        createDataChannel()
    }

    func sendKeyframe(sampleBuffer: CMSampleBuffer) {
        keyframeVideoCapturer?.sendEncodedFrame(sampleBuffer)
    }

    private func createMediaSenders() {
        let streamId = "stream"
        let videoSource = peerConnectionFactory.videoSource()
        self.keyframeVideoCapturer = KeyframeVideoCapturer(delegate: videoSource)
        self.videoTrack = peerConnectionFactory.videoTrack(with: videoSource, trackId: "video0")
        peerConnection?.add(videoTrack!, streamIds: [streamId])
    }

    private func createDataChannel() {
        let config = RTCDataChannelConfiguration()
        config.isOrdered = false
        config.maxPacketLifeTime = 100
        self.dataChannel = peerConnection?.dataChannel(forLabel: "control", configuration: config)
        self.dataChannel?.delegate = self
        self.dataChannelState = self.dataChannel?.readyState ?? .closed
    }
}

// MARK: - SignalingClientDelegate
extension WebRTCManager: SignalingClientDelegate {
    nonisolated func signalingClientDidConnect(_ client: SignalingClient) {
        Task { @MainActor in
            Logger.shared.network("Signaling connected. Creating offer...", level: .info)
            let constraints = RTCMediaConstraints(mandatoryConstraints: ["OfferToReceiveVideo": "true"], optionalConstraints: nil)
            guard let pc = self.peerConnection else { return }

            do {
                let offer = try await pc.offer(for: constraints)
                try await pc.setLocalDescription(offer)
                self.signalingClient.sendSdp(sdp: offer.sdp, type: "offer")
            } catch {
                Logger.shared.network("Error creating offer: \(error.localizedDescription)", level: .error)
            }
        }
    }

    nonisolated func signalingClient(_ client: SignalingClient, didReceiveRemoteSdp sdp: String, type: String) {
        Task { @MainActor in
            let rtcSdp = RTCSessionDescription(type: type == "offer" ? .offer : .answer, sdp: sdp)
            do {
                try await self.peerConnection?.setRemoteDescription(rtcSdp)
            } catch {
                Logger.shared.network("Error setting remote description: \(error.localizedDescription)", level: .error)
            }
        }
    }

    nonisolated func signalingClient(_ client: SignalingClient, didReceiveCandidate candidate: String, sdpMLineIndex: Int32, sdpMid: String?) {
        Task { @MainActor in
            let rtcCandidate = RTCIceCandidate(sdp: candidate, sdpMLineIndex: sdpMLineIndex, sdpMid: sdpMid)
            do {
                try await self.peerConnection?.add(rtcCandidate)
            } catch {
                Logger.shared.network("Error adding ICE candidate: \(error.localizedDescription)", level: .error)
            }
        }
    }

    nonisolated func signalingClient(_ client: SignalingClient, didReceiveProcessingMode mode: String) {
        Task { @MainActor in
            Logger.shared.network("Received remote processing mode: \(mode)", level: .info)
        }
    }

    nonisolated func signalingClientDidDisconnect(_ client: SignalingClient) {
        Task { @MainActor in self.disconnect() }
    }

    nonisolated func signalingClient(_ client: SignalingClient, didEncounterError error: Error) {
        Task { @MainActor in self.disconnect() }
    }
}

// MARK: - RTCPeerConnectionDelegate
extension WebRTCManager: RTCPeerConnectionDelegate {
    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didChange newState: RTCIceConnectionState) {
        Task { @MainActor in
            self.connectionState = newState
            if newState == .connected {
                self.pingTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
                    Task { @MainActor in self?.sendPing() }
                }
            } else if [.disconnected, .failed, .closed].contains(newState) {
                self.pingTimer?.invalidate()
                self.pingTimer = nil
            }
        }
    }

    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didGenerate candidate: RTCIceCandidate) {
        Task { @MainActor in
            self.signalingClient.sendCandidate(candidate: candidate.sdp, sdpMLineIndex: candidate.sdpMLineIndex, sdpMid: candidate.sdpMid)
        }
    }

    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didOpen dataChannel: RTCDataChannel) {
        Task { @MainActor in
            self.dataChannel = dataChannel
            dataChannel.delegate = self
            self.dataChannelState = dataChannel.readyState
        }
    }

    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didChange signalingState: RTCSignalingState) {
        Task { @MainActor in self.signalingState = signalingState }
    }

    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didAdd stream: RTCMediaStream) {}
    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didRemove stream: RTCMediaStream) {}
    nonisolated func peerConnectionShouldNegotiate(_ peerConnection: RTCPeerConnection) {}
    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didRemove candidates: [RTCIceCandidate]) {}
    nonisolated func peerConnection(_ peerConnection: RTCPeerConnection, didChange gatheringState: RTCIceGatheringState) {}
}

// MARK: - RTCDataChannelDelegate
extension WebRTCManager: RTCDataChannelDelegate {
    nonisolated func dataChannelDidChangeState(_ dataChannel: RTCDataChannel) {
        Task { @MainActor in
            self.dataChannelState = dataChannel.readyState
            Logger.shared.network("Data channel state: \(dataChannel.readyState)", level: .info)
        }
    }

    nonisolated func dataChannel(_ dataChannel: RTCDataChannel, didReceiveMessageWith buffer: RTCDataBuffer) {
        Task { @MainActor in
            let message = String(data: buffer.data, encoding: .utf8) ?? ""
            if message == "pong", let startTime = self.pingStartTime {
                let rtt = Date().timeIntervalSince(startTime)
                self.lastPingRTT = rtt
            } else if message == "ack" {
                self.delegate?.webRTCManager(self, didReceiveAck: true)
            }
        }
    }

    nonisolated func dataChannel(_ dataChannel: RTCDataChannel, didChangeBufferedAmount amount: UInt64) {}
}

// MARK: - WebRTCManagerDelegate Protocol
protocol WebRTCManagerDelegate: AnyObject {
    func webRTCManager(_ manager: WebRTCManager, didReceiveAck: Bool)
}
