//
//  KeyframePipeline.swift
//  Orion
//
//  Created by Riddhiman Rana on 8/14/25.
//  Manages the stateful pipeline for capturing, encoding, and sending keyframes.
//

import Foundation
import AVFoundation
import Combine

@MainActor
class KeyframePipeline: NSObject, ObservableObject, WebRTCManagerDelegate {
    enum State {
        case idle
        case capturing
        case encoding
        case sending
        case waitingForAck
    }
    
    @Published private(set) var state: State = .idle
    
    private var captureTrigger: Timer?
    private let interval: TimeInterval = 3.0
    
    private weak var cameraManager: CameraManager?
    private weak var webRTCManager: WebRTCManager?
    private var videoEncoder: H264Encoder?
    
    init(cameraManager: CameraManager, webRTCManager: WebRTCManager) {
        self.cameraManager = cameraManager
        self.webRTCManager = webRTCManager
        super.init()
        self.webRTCManager?.delegate = self
        // Assuming a standard resolution for now. This could be made dynamic.
        self.videoEncoder = H264Encoder(width: 1920, height: 1080)
        self.videoEncoder?.onEncodedFrame = { [weak self] encodedBuffer in
            self?.sendEncodedFrame(encodedBuffer)
        }
    }
    
    func start() {
        guard state == .idle else { return }
        print("KeyframePipeline: Starting...")
        requestNextKeyframe()
    }
    
    func stop() {
        print("KeyframePipeline: Stopping...")
        captureTrigger?.invalidate()
        captureTrigger = nil
        state = .idle
    }
    
    func serverDidAcknowledgeFrame() {
        if state == .waitingForAck {
            print("KeyframePipeline: Frame acknowledged by server.")
            state = .idle
            requestNextKeyframe()
        }
    }
    
    private func requestNextKeyframe() {
        guard state == .idle else { return }
        captureTrigger?.invalidate()
        captureTrigger = Timer.scheduledTimer(withTimeInterval: interval, repeats: false) { [weak self] _ in
            self?.captureFrame()
        }
    }
    
    private func captureFrame() {
        guard state == .idle else { return }
        state = .capturing
        print("KeyframePipeline: Capturing frame...")
        // The CameraManager's delegate will call processCapturedFrame
    }
    
    func processCapturedFrame(_ sampleBuffer: CMSampleBuffer) {
        guard state == .capturing else { return }
        state = .encoding
        print("KeyframePipeline: Encoding frame...")
        videoEncoder?.encode(sampleBuffer: sampleBuffer)
    }
    
    private func sendEncodedFrame(_ sampleBuffer: CMSampleBuffer) {
        guard state == .encoding else { return }
        state = .sending
        print("KeyframePipeline: Sending frame...")
        webRTCManager?.sendKeyframe(sampleBuffer: sampleBuffer)
        state = .waitingForAck
        print("KeyframePipeline: Waiting for acknowledgement...")
    }
    
    // MARK: - WebRTCManagerDelegate
    func webRTCManager(_ manager: WebRTCManager, didReceiveAck: Bool) {
        if didReceiveAck {
            serverDidAcknowledgeFrame()
        }
    }
}