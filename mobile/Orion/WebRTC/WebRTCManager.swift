
//
//  WebRTCManager.swift
//  Orion
//
//  Created by Riddhiman Rana on 8/14/25.
//  Manages the WebRTC peer-to-peer connection, data channels, and media streams.
//

import Foundation
import WebRTC
import Combine

@MainActor
class WebRTCManager: NSObject, ObservableObject {
    
    // MARK: - Published Properties
    @Published var connectionState: RTCIceConnectionState = .new
    @Published var signalingState: RTCSignalingState = .stable
    @Published private(set) var lastPingRTT: TimeInterval? = nil

    // MARK: - Private Properties
    private var peerConnection: RTCPeerConnection?
    private var peerConnectionFactory: RTCPeerConnectionFactory
    private var videoTrack: RTCVideoTrack?
    private var keyframeVideoCapturer: KeyframeVideoCapturer?
    private var dataChannel: RTCDataChannel?
    private var signalingClient: SignalingClient
    private var pingTimer: Timer?
    private var pingStartTime: Date?

    // Add a delegate to notify about data channel messages
    weak var delegate: WebRTCManagerDelegate?

    init(signalingClient: SignalingClient) {
        self.signalingClient = signalingClient
        
        let videoEncoderFactory = RTCDefaultVideoEncoderFactory()
        let videoDecoderFactory = RTCDefaultVideoDecoderFactory()
        self.peerConnectionFactory = RTCPeerConnectionFactory(encoderFactory: videoEncoderFactory, decoderFactory: videoDecoderFactory)
        
        super.init()
        self.signalingClient.delegate = self
    }
    
    func connect() {
        guard peerConnection == nil else { return }
        print("WebRTCManager: Starting connection...")
        setupPeerConnection()
        Task { await signalingClient.connect() }
    }
    
    func disconnect() {
        pingTimer?.invalidate()
        pingTimer = nil
        peerConnection?.close()
        peerConnection = nil
        signalingClient.disconnect()
        self.connectionState = .closed
        print("WebRTCManager: Disconnected.")
    }
    
    func sendPing() {
        guard dataChannel?.readyState == .open else { return }
        pingStartTime = Date()
        let message = RTCDataBuffer(data: "ping".data(using: .utf8)!, isBinary: false)
        dataChannel?.sendData(message)
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
        
        // Video track for keyframes
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
    }
}

// MARK: - SignalingClientDelegate
extension WebRTCManager: SignalingClientDelegate {
    func signalingClientDidConnect(_ client: SignalingClient) {
        print("WebRTCManager: Signaling connected. Creating offer...")
        let constraints = RTCMediaConstraints(mandatoryConstraints: ["OfferToReceiveVideo": "true"], optionalConstraints: nil)
        peerConnection?.offer(for: constraints) { [weak self] (sdp, error) in
            guard let self = self, let sdp = sdp else { return }
            self.peerConnection?.setLocalDescription(sdp) { error in
                if let error = error { print("Error setting local description: \(error)"); return }
                self.signalingClient.sendSdp(sdp: sdp.sdp, type: "offer")
            }
        }
    }
    
    func signalingClient(_ client: SignalingClient, didReceiveRemoteSdp sdp: String, type: String) {
        let rtcSdp = RTCSessionDescription(type: type == "offer" ? .offer : .answer, sdp: sdp)
        self.peerConnection?.setRemoteDescription(rtcSdp) { [weak self] error in
            guard let self = self else { return }
            if let error = error { print("Error setting remote description: \(error)"); return }
            if type == "offer" {
                let constraints = RTCMediaConstraints(mandatoryConstraints: ["OfferToReceiveVideo": "true"], optionalConstraints: nil)
                self.peerConnection?.answer(for: constraints) { (answerSdp, error) in
                    guard let answerSdp = answerSdp else { return }
                    self.peerConnection?.setLocalDescription(answerSdp) { error in
                        if let error = error { print("Error setting local desc for answer: \(error)"); return }
                        self.signalingClient.sendSdp(sdp: answerSdp.sdp, type: "answer")
                    }
                }
            }
        }
    }
    
    func signalingClient(_ client: SignalingClient, didReceiveCandidate candidate: String, sdpMLineIndex: Int32, sdpMid: String?) {
        let rtcCandidate = RTCIceCandidate(sdp: candidate, sdpMLineIndex: sdpMLineIndex, sdpMid: sdpMid)
        self.peerConnection?.add(rtcCandidate)
    }
    
    func signalingClientDidDisconnect(_ client: SignalingClient) { disconnect() }
    func signalingClient(_ client: SignalingClient, didEncounterError error: Error) { disconnect() }
}

// MARK: - RTCPeerConnectionDelegate
extension WebRTCManager: RTCPeerConnectionDelegate {
    func peerConnection(_ peerConnection: RTCPeerConnection, didChange newState: RTCIceConnectionState) {
        DispatchQueue.main.async {
            self.connectionState = newState
            if newState == .connected {
                self.pingTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in self?.sendPing() }
            } else if [.disconnected, .failed, .closed].contains(newState) {
                self.pingTimer?.invalidate()
                self.pingTimer = nil
            }
        }
    }
    
    func peerConnection(_ peerConnection: RTCPeerConnection, didGenerate candidate: RTCIceCandidate) {
        signalingClient.sendCandidate(candidate: candidate.sdp, sdpMLineIndex: candidate.sdpMLineIndex, sdpMid: candidate.sdpMid)
    }
    
    func peerConnection(_ peerConnection: RTCPeerConnection, didOpen dataChannel: RTCDataChannel) {
        self.dataChannel = dataChannel
        dataChannel.delegate = self
    }
    
    func peerConnection(_ peerConnection: RTCPeerConnection, didChange connectionState: RTCPeerConnectionState) {
        DispatchQueue.main.async {
            // Update any state tracking if needed
        }
    }
    
    func peerConnection(_ peerConnection: RTCPeerConnection, didChange signalingState: RTCSignalingState) {
        DispatchQueue.main.async {
            self.signalingState = signalingState
        }
    }
    
    func peerConnection(_ peerConnection: RTCPeerConnection, didChange gatheringState: RTCIceGatheringState) {
        // Handle ICE gathering state changes if needed
        print("ICE gathering state changed to: \(gatheringState)")
    }
    
    func peerConnection(_ peerConnection: RTCPeerConnection, didAdd stream: RTCMediaStream) {}
    func peerConnection(_ peerConnection: RTCPeerConnection, didRemove stream: RTCMediaStream) {}
    func peerConnectionShouldNegotiate(_ peerConnection: RTCPeerConnection) {}
    
    func peerConnection(_ peerConnection: RTCPeerConnection, didAdd rtpReceiver: RTCRtpReceiver, streams: [RTCMediaStream]) {}
    func peerConnection(_ peerConnection: RTCPeerConnection, didRemove rtpReceiver: RTCRtpReceiver) {}
    func peerConnection(_ peerConnection: RTCPeerConnection, didChangeLocalCandidate local: RTCIceCandidate, remoteCandidate remote: RTCIceCandidate, lastReceivedMs lastDataReceivedMs: Int32, changeReason reason: String) {}
    
    // Required method that was missing
    func peerConnection(_ peerConnection: RTCPeerConnection, didRemove candidates: [RTCIceCandidate]) {
        // Handle removal of ICE candidates if needed
        print("ICE candidates removed: \(candidates.count)")
    }
}

// MARK: - RTCDataChannelDelegate
extension WebRTCManager: RTCDataChannelDelegate {
    func dataChannelDidChangeState(_ dataChannel: RTCDataChannel) {
        print("Data channel state changed to: \(dataChannel.readyState)")
    }
    
    func dataChannel(_ dataChannel: RTCDataChannel, didReceiveMessageWith buffer: RTCDataBuffer) {
        let message = String(data: buffer.data, encoding: .utf8) ?? ""
        
        if message == "pong", let startTime = pingStartTime {
            let rtt = Date().timeIntervalSince(startTime)
            DispatchQueue.main.async {
                self.lastPingRTT = rtt
            }
        } else if message == "ack" {
            delegate?.webRTCManager(self, didReceiveAck: true)
        }
        // TODO: Handle other incoming messages (e.g., analysis results)
    }
    
    func dataChannel(_ dataChannel: RTCDataChannel, didChangeBufferedAmount amount: UInt64) {}
}

// MARK: - WebRTCManagerDelegate Protocol
protocol WebRTCManagerDelegate: AnyObject {
    func webRTCManager(_ manager: WebRTCManager, didReceiveAck: Bool)
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
