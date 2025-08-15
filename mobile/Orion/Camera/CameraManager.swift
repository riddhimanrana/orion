//
//  CameraManager.swift
//  Orion
//
//  Created by Riddhiman Rana on 6/11/25.
//  Camera Manager System for Orion Live
//

import Combine
import AVFoundation
import CoreImage
import Vision
import UIKit

// Helper for logging within CameraManager
private func logCM(_ message: String) {
    Logger.shared.log("[CameraManager] \(message)", category: .camera)
}

// Define CameraOption here to be accessible by views
struct CameraOption: Identifiable, Equatable {
    var id: String { device.uniqueID }
    let type: CameraType
    let zoomFactor: Double?
    let isFrontCamera: Bool
    let device: AVCaptureDevice

    var displayName: String {
        if isFrontCamera {
            return "Front"
        }
        if let zoom = zoomFactor {
            return zoom.truncatingRemainder(dividingBy: 1) == 0 ? String(format: "%.0fx", zoom) : String(format: "%.1fx", zoom)
        }
        switch type {
        case .wide: return "1x"
        case .ultraWide: return "0.5x"
        case .telephoto: return "Tele"
        case .front: return "Front"
        }
    }

    static func == (lhs: CameraOption, rhs: CameraOption) -> Bool {
        lhs.id == rhs.id
    }
}

enum CameraType {
    case wide
    case ultraWide
    case telephoto
    case front
}

@MainActor
class CameraManager: NSObject, ObservableObject {
    let session = AVCaptureSession()
    private var videoOutput: AVCaptureVideoDataOutput?
    
    private let processingQueue = DispatchQueue(label: "com.orion.processing")
    
    // Published state for SwiftUI UI updates
    @Published private(set) var isStreaming = false
    @Published private(set) var error: String?
    @Published private(set) var availableCameraOptions: [CameraOption] = []
    @Published private(set) var currentCameraOption: CameraOption?
    @Published private(set) var lastDetections: [NetworkDetection] = []
    
    // Publishers for debug monitoring
    let frameAnalysisLogPublisher = PassthroughSubject<FrameAnalysisLog, Never>()
    
    // Keyframe Pipeline
    private var keyframePipeline: KeyframePipeline?
    private weak var webRTCManager: WebRTCManager?
    private var canSendNextFrame = true

    func setup(webRTCManager: WebRTCManager) {
        self.webRTCManager = webRTCManager
        self.keyframePipeline = KeyframePipeline(cameraManager: self, webRTCManager: webRTCManager)
        
        logCM("Initializing...")
        discoverCameraOptions()
        
        if let defaultOption = availableCameraOptions.first(where: { $0.type == .wide && !$0.isFrontCamera }) ?? availableCameraOptions.first {
            logCM("Setting initial camera to \(defaultOption.displayName)")
            self.currentCameraOption = defaultOption
            setupSession(with: defaultOption.device)
        } else {
            let errMsg = "No cameras found."
            logCM(errMsg)
            DispatchQueue.main.async { self.error = errMsg }
        }
        logCM("Initialization complete.")
    }
    
    func getPreviewLayer() -> AVCaptureVideoPreviewLayer {
        let previewLayer = AVCaptureVideoPreviewLayer(session: session)
        previewLayer.videoGravity = .resizeAspectFill
        return previewLayer
    }
    
    func startStreaming() {
        guard !isStreaming, !session.isRunning else { return }
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.session.startRunning()
            DispatchQueue.main.async {
                self?.isStreaming = self?.session.isRunning ?? false
                self?.keyframePipeline?.start()
            }
        }
    }
    
    func stopStreaming() {
        guard isStreaming, session.isRunning else { return }
        keyframePipeline?.stop()
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.session.stopRunning()
            DispatchQueue.main.async {
                self?.isStreaming = self?.session.isRunning ?? false
            }
        }
    }

    func switchCamera(to option: CameraOption) {
        guard option.id != currentCameraOption?.id else { return }
        logCM("Switching camera to \(option.displayName)...")
        
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.setupSession(with: option.device)
            DispatchQueue.main.async {
                self?.currentCameraOption = option
            }
        }
    }
    
    func serverDidAcknowledgeFrame() {
        canSendNextFrame = true
    }
    
    func configure(for mode: String) {
        logCM("Configuring camera for mode: \(mode)")
        // Configure camera settings based on processing mode
        if mode == "full" {
            canSendNextFrame = false
        } else {
            canSendNextFrame = true
        }
    }
    
    func updateDetections(_ detections: [NetworkDetection]) {
        DispatchQueue.main.async {
            self.lastDetections = detections
        }
    }
    
    func publishFrameAnalysisLog(_ log: FrameAnalysisLog) {
        frameAnalysisLogPublisher.send(log)
    }
    
    private func setupSession(with device: AVCaptureDevice) {
        session.beginConfiguration()
        defer { session.commitConfiguration() }

        session.inputs.forEach { session.removeInput($0) }
        session.outputs.forEach { session.removeOutput($0) }

        session.sessionPreset = .hd1920x1080

        do {
            let input = try AVCaptureDeviceInput(device: device)
            if session.canAddInput(input) { session.addInput(input) }
        } catch { logCM("Failed to create camera input: \(error.localizedDescription)") }

        let videoOutput = AVCaptureVideoDataOutput()
        videoOutput.setSampleBufferDelegate(self, queue: processingQueue)
        videoOutput.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: Int(kCVPixelFormatType_32BGRA)]
        
        if session.canAddOutput(videoOutput) { session.addOutput(videoOutput) }
    }
    
    private func discoverCameraOptions() {
        var options: [CameraOption] = []
        if let frontCamera = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .front) {
            options.append(CameraOption(type: .front, zoomFactor: nil, isFrontCamera: true, device: frontCamera))
        }
        let discoverySession = AVCaptureDevice.DiscoverySession(deviceTypes: [.builtInWideAngleCamera, .builtInUltraWideCamera, .builtInTelephotoCamera], mediaType: .video, position: .back)
        for device in discoverySession.devices {
            let (type, zoom) = device.deviceType == .builtInWideAngleCamera ? (CameraType.wide, 1.0) : (device.deviceType == .builtInUltraWideCamera ? (.ultraWide, 0.5) : (.telephoto, 2.0))
            options.append(CameraOption(type: type, zoomFactor: zoom, isFrontCamera: false, device: device))
        }
        self.availableCameraOptions = options.sorted { $0.zoomFactor ?? 0 < $1.zoomFactor ?? 0 }
    }
}

// MARK: - AVCaptureVideoDataOutputSampleBufferDelegate
extension CameraManager: AVCaptureVideoDataOutputSampleBufferDelegate {
    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        // Pass the captured frame to the pipeline for processing.
        keyframePipeline?.processCapturedFrame(sampleBuffer)
    }
}
