//
//  WebRTCManager.swift
//  Orion Server
//
//  Created by Gemini on 8/15/25.
//

import Foundation
import WebRTC

@MainActor
class WebRTCManager: NSObject, ObservableObject {
    @Published var connectionState: RTCIceConnectionState = .new {
        didSet {
            print("WebRTC connection state changed to: \(connectionState.description)")
        }
    }
    @Published var videoTrack: RTCVideoTrack?
    @Published var receivedMessage: String = ""
    
    private var peerConnection: RTCPeerConnection?
    private var dataChannel: RTCDataChannel?
    private let peerConnectionFactory: RTCPeerConnectionFactory
    private let signalingClient: SignalingClient
    private var pendingCandidates: [RTCIceCandidate] = []

    init(signalingClient: SignalingClient) {
        let videoEncoderFactory = RTCDefaultVideoEncoderFactory()
        let videoDecoderFactory = RTCDefaultVideoDecoderFactory()
        self.peerConnectionFactory = RTCPeerConnectionFactory(encoderFactory: videoEncoderFactory, decoderFactory: videoDecoderFactory)
        self.signalingClient = signalingClient
        super.init()
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
    
    private func setupPeerConnection() {
        let configuration = RTCConfiguration()
        configuration.iceServers = [RTCIceServer(urlStrings: ["stun:stun.l.google.com:19302"])]
        configuration.sdpSemantics = .unifiedPlan
        
        let constraints = RTCMediaConstraints(mandatoryConstraints: nil, optionalConstraints: ["DtlsSrtpKeyAgreement": "true"])
        
        self.peerConnection = peerConnectionFactory.peerConnection(with: configuration, constraints: constraints, delegate: self)
        
        let config = RTCDataChannelConfiguration()
        if let channel = self.peerConnection?.dataChannel(forLabel: "control", configuration: config) {
            channel.delegate = self
            self.dataChannel = channel
        }
    }
}

// MARK: - SignalingClientDelegate
extension WebRTCManager: SignalingClientDelegate {
    nonisolated func signalingClientDidConnect(_ client: SignalingClient) {
        Task { @MainActor in
            print("WebRTCManager: Signaling connected. Setting up PeerConnection.")
            self.setupPeerConnection()
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
        Task { @MainActor in self.connectionState = state }
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

// MARK: - RTCDataChannelDelegate
extension WebRTCManager: RTCDataChannelDelegate {
    nonisolated func dataChannelDidChangeState(_ dataChannel: RTCDataChannel) {
        print("macOS: Data channel state changed to: \(dataChannel.readyState)")
    }
    
    nonisolated func dataChannel(_ dataChannel: RTCDataChannel, didReceiveMessageWith buffer: RTCDataBuffer) {
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
