
//
//  KeyframePipeline.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 8/14/25.
//

import Foundation
import AVFoundation
import Combine

@MainActor
class KeyframePipeline: NSObject, ObservableObject {
    enum State { case idle, capturing, encoding, sending, waitingForAck }

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
        self.videoEncoder = H264Encoder(width: 1920, height: 1080)
        self.videoEncoder?.onEncodedFrame = { [weak self] encodedBuffer in
            self?.sendEncodedFrame(encodedBuffer)
        }
    }

    func start() {
        guard state == .idle else { return }
        requestNextKeyframe()
    }

    func stop() {
        captureTrigger?.invalidate()
        captureTrigger = nil
        state = .idle
    }

    func serverDidAcknowledgeFrame() {
        if state == .waitingForAck {
            state = .idle
            requestNextKeyframe()
        }
    }

    private func requestNextKeyframe() {
        guard state == .idle else { return }
        captureTrigger?.invalidate()
        captureTrigger = Timer.scheduledTimer(withTimeInterval: interval, repeats: false) { [weak self] _ in
            Task { @MainActor in
                self?.captureFrame()
            }
        }
    }

    private func captureFrame() {
        guard state == .idle else { return }
        state = .capturing
    }

    func processCapturedFrame(_ sampleBuffer: CMSampleBuffer) {
        guard state == .capturing else { return }
        state = .encoding
        videoEncoder?.encode(sampleBuffer: sampleBuffer)
    }

    private func sendEncodedFrame(_ sampleBuffer: CMSampleBuffer) {
        guard state == .encoding else { return }
        state = .sending
        webRTCManager?.sendKeyframe(sampleBuffer: sampleBuffer)
        state = .waitingForAck
    }
}

// MARK: - WebRTCManagerDelegate
extension KeyframePipeline: WebRTCManagerDelegate {
    nonisolated func webRTCManager(_ manager: WebRTCManager, didReceiveAck: Bool) {
        Task { @MainActor in
            if didReceiveAck {
                self.serverDidAcknowledgeFrame()
            }
        }
    }
}
