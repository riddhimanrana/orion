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

class CameraManager: NSObject, ObservableObject {
    /// Camera session
    let session = AVCaptureSession()
    private var videoOutput: AVCaptureVideoDataOutput?
    
    /// YOLO detection model
    private var detectionRequest: VNCoreMLRequest?
    private let modelConfig = MLModelConfiguration()
    
    /// Frame processing
    private let processingQueue = DispatchQueue(label: "com.orion.processing")
    private let maxFPS = 30
    private var lastFrameTime: TimeInterval = 0
    
    /// Frame processing state
    enum ProcessingState {
        case idle
        case processing
        case sent
        case waitingForServer
    }
    @Published private(set) var processingState: ProcessingState = .idle
    
    /// Detection callback for other purposes (e.g., network)
    private var detectionCallback: ((Data?, [NetworkDetection], String?, Float?) -> Void)?
    let detectionLogPublisher = PassthroughSubject<DetectionLogEntry, Never>()
    
    /// Published state for SwiftUI UI updates
    @Published private(set) var isStreaming = false
    @Published private(set) var error: String?
    @Published var lastDetections: [NetworkDetection] = []
    @Published private(set) var availableCameraOptions: [CameraOption] = []
    @Published private(set) var currentCameraOption: CameraOption?
    @Published private(set) var lastVLMDescription: String? = "FastVLM model not implemented yet"
    @Published private(set) var lastVLMConfidence: Float? = 0.0
    @Published var lastFrameImageData: Data?

    override init() {
        super.init()
        logCM("Initializing...")
        discoverCameraOptions()
        
        if let defaultOption = availableCameraOptions.first(where: { $0.type == .wide && !$0.isFrontCamera }) ?? availableCameraOptions.first(where: { !$0.isFrontCamera }) ?? availableCameraOptions.first {
            logCM("Setting initial camera to \(defaultOption.displayName)")
            self.currentCameraOption = defaultOption
            setupSession(with: defaultOption.device)
        } else {
            let errMsg = "No cameras found."
            logCM(errMsg)
            DispatchQueue.main.async { self.error = errMsg }
        }
        
        setupYOLO()
        logCM("Initialization complete. Final error state: \(error ?? "None")")
    }
    
    func getPreviewLayer() -> AVCaptureVideoPreviewLayer {
        logCM("getPreviewLayer called.")
        let previewLayer = AVCaptureVideoPreviewLayer(session: session)
        previewLayer.videoGravity = .resizeAspectFill
        return previewLayer
    }
    
    func startStreaming() {
        logCM("startStreaming called. Current isStreaming: \(isStreaming), session.isReallyRunning: \(session.isRunning)")
        guard !isStreaming || !session.isRunning else {
            logCM("Already streaming or session is already running.")
            if session.isRunning && !self.isStreaming {
                 DispatchQueue.main.async { self.isStreaming = true }
            }
            return
        }

        logCM("Attempting to start streaming session...")
        if session.inputs.isEmpty || session.outputs.isEmpty {
            let errMsg = "No inputs or outputs in session. Cannot start."
            logCM(errMsg)
            DispatchQueue.main.async { self.error = errMsg }
            return
        }

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            self.session.startRunning()
            DispatchQueue.main.async {
                self.isStreaming = self.session.isRunning
                if self.isStreaming {
                    logCM("Session started successfully.")
                } else {
                    let errMsg = "Session failed to start."
                    logCM(errMsg)
                    self.error = errMsg
                }
            }
        }
    }
    
    func stopStreaming() {
        logCM("stopStreaming called. Current isStreaming: \(isStreaming), session.isReallyRunning: \(session.isRunning)")
        guard isStreaming || session.isRunning else {
            logCM("Not streaming or session not running.")
            if !session.isRunning && self.isStreaming {
                 DispatchQueue.main.async { self.isStreaming = false }
            }
            return
        }
        
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            self.session.stopRunning()
            DispatchQueue.main.async {
                self.isStreaming = self.session.isRunning
                logCM(self.isStreaming ? "Session failed to stop." : "Session stopped successfully.")
            }
        }
    }
    
    func setDetectionCallback(_ callback: @escaping (Data?, [NetworkDetection], String?, Float?) -> Void) {
        self.detectionCallback = callback
    }

    func configure(for mode: String) {
        if mode == "full" {
            // Unload the model to save resources
            detectionRequest = nil
            logCM("YOLO model unloaded for full processing mode.")
        } else {
            // Ensure model is loaded for split processing mode
            if detectionRequest == nil {
                setupYOLO()
            }
        }
    }

    func switchCamera(to option: CameraOption) {
        guard option.id != currentCameraOption?.id else {
            logCM("Already using camera \(option.displayName). No switch needed.")
            return
        }
        logCM("Attempting to switch camera to \(option.displayName)...")
        
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            
            self.setupSession(with: option.device)
            
            DispatchQueue.main.async {
                self.currentCameraOption = option
            }
            
            if !self.session.isRunning {
                self.startStreaming()
            }
        }
    }
    
    func serverDidAcknowledgeFrame() {
        if self.processingState == .waitingForServer {
            logCM("Server acknowledged frame. Ready for next frame.")
            self.processingState = .idle
        }
    }

    private func setupSession(with device: AVCaptureDevice) {
        logCM("Setting up session for device: \(device.localizedName)...")
        session.beginConfiguration()
        defer { session.commitConfiguration() }

        session.inputs.forEach { session.removeInput($0) }
        session.outputs.forEach { session.removeOutput($0) }

        session.sessionPreset = .hd1920x1080

        do {
            let input = try AVCaptureDeviceInput(device: device)
            if session.canAddInput(input) {
                session.addInput(input)
                logCM("Camera input added.")
            } else {
                let errMsg = "Cannot add camera input to session."
                logCM(errMsg)
                DispatchQueue.main.async { self.error = errMsg }
                return
            }
        } catch {
            let errMsg = "Failed to create camera input: \(error.localizedDescription)"
            logCM(errMsg)
            DispatchQueue.main.async { self.error = errMsg }
            return
        }

        let localVideoOutput = AVCaptureVideoDataOutput()
        localVideoOutput.setSampleBufferDelegate(self, queue: processingQueue)
        localVideoOutput.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: Int(kCVPixelFormatType_32BGRA)]
        
        if session.canAddOutput(localVideoOutput) {
            session.addOutput(localVideoOutput)
            self.videoOutput = localVideoOutput
            logCM("Video output added.")
        } else {
            let errMsg = "Cannot add video output to session."
            logCM(errMsg)
            DispatchQueue.main.async { self.error = errMsg }
            return
        }
        logCM("Camera setup complete.")
    }
    
    private func discoverCameraOptions() {
        logCM("Discovering camera options...")
        var options: [CameraOption] = []

        // Front camera
        if let frontCamera = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .front) {
            options.append(CameraOption(type: .front, zoomFactor: nil, isFrontCamera: true, device: frontCamera))
        }

        // Back cameras
        var backCameraDeviceTypes: [AVCaptureDevice.DeviceType] = [.builtInWideAngleCamera]
        if #available(iOS 13.0, *) {
            backCameraDeviceTypes.append(contentsOf: [.builtInUltraWideCamera, .builtInTelephotoCamera])
        }
        
        let discoverySession = AVCaptureDevice.DiscoverySession(deviceTypes: backCameraDeviceTypes, mediaType: .video, position: .back)

        for device in discoverySession.devices {
            let zoomFactor: Double?
            let cameraType: CameraType
            
            let deviceType = device.deviceType
            
            if deviceType == .builtInWideAngleCamera {
                cameraType = .wide
                zoomFactor = 1.0
            } else if #available(iOS 13.0, *), deviceType == .builtInUltraWideCamera {
                cameraType = .ultraWide
                zoomFactor = 0.5
            } else if #available(iOS 13.0, *), deviceType == .builtInTelephotoCamera {
                cameraType = .telephoto
                if device.localizedName.contains("5x") { zoomFactor = 5.0 }
                else if device.localizedName.contains("3x") { zoomFactor = 3.0 }
                else { zoomFactor = 2.0 }
            } else {
                continue
            }
            
            if !options.contains(where: { $0.type == cameraType && !$0.isFrontCamera }) {
                options.append(CameraOption(type: cameraType, zoomFactor: zoomFactor, isFrontCamera: false, device: device))
            }
        }

        self.availableCameraOptions = options.sorted { (opt1, opt2) -> Bool in
            if opt1.isFrontCamera { return false }
            if opt2.isFrontCamera { return true }
            guard let zoom1 = opt1.zoomFactor, let zoom2 = opt2.zoomFactor else { return false }
            return zoom1 < zoom2
        }
        
        logCM("Discovered \(self.availableCameraOptions.count) camera options.")
        self.availableCameraOptions.forEach { logCM("  - \($0.displayName) (Front: \($0.isFrontCamera)) - Device: \($0.device.localizedName)") }
    }

    private func setupYOLO() {
        logCM("Setting up YOLO model...")
        modelConfig.computeUnits = .all // Use .cpuOnly or .cpuAndGPU for testing if .all causes issues
        
        guard let modelURL = Bundle.main.url(forResource: "yolo11n", withExtension: "mlmodelc") else {
            let errMsg = "Failed to find yolo11n.mlmodelc in the app bundle. Make sure yolo11n.mlpackage is added to the target and compiled."
            logCM(errMsg)
            DispatchQueue.main.async { self.error = errMsg }
            return
        }
        logCM("YOLO model URL: \(modelURL.path)")
        
        do {
            let model = try MLModel(contentsOf: modelURL, configuration: modelConfig)
            let visionModel = try VNCoreMLModel(for: model)
            
            let request = VNCoreMLRequest(model: visionModel) { [weak self] request, error in
                self?.handleDetections(request: request, error: error)
            }
            
            request.imageCropAndScaleOption = .scaleFit
            self.detectionRequest = request
            logCM("YOLO model and detection request setup complete.")
        } catch {
            let errMsg = "Failed to setup YOLO model: \(error.localizedDescription)"
            logCM(errMsg)
            DispatchQueue.main.async { self.error = errMsg }
        }
    }
    
    
}

// MARK: - AVCaptureVideoDataOutputSampleBufferDelegate
extension CameraManager: AVCaptureVideoDataOutputSampleBufferDelegate {
    func captureOutput(
        _ output: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        guard processingState == .idle else { return }
        
        processingState = .processing

        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else {
            logCM("Failed to get pixelBuffer from sampleBuffer.")
            processingState = .idle
            return
        }

        // Always generate image data for the callback
        let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
        let orientedImage = ciImage.oriented(.right)
        if let cgImage = CIContext().createCGImage(orientedImage, from: orientedImage.extent) {
            let imageData = UIImage(cgImage: cgImage).jpegData(compressionQuality: 0.7)
            DispatchQueue.main.async {
                self.lastFrameImageData = imageData
            }
            // In full mode, immediately call the callback with the image data and wait for server ack.
            if SettingsManager.shared.processingMode == "full" {
                self.detectionCallback?(imageData, [], nil, nil)
                processingState = .waitingForServer
                logCM("Frame sent in full mode. Waiting for server acknowledgment...")
                return
            }
        } else {
            logCM("Failed to create CGImage for callback.")
        }

        // In "split" mode, perform local detection
        guard let currentDetectionRequest = detectionRequest else {
            logCM("Detection request is nil, cannot process in split mode.")
            processingState = .idle
            return
        }

        processingQueue.async { [weak self] in
            guard let self = self else { return }
            do {
                try VNImageRequestHandler(
                    cvPixelBuffer: pixelBuffer,
                    orientation: .right,
                    options: [:]
                ).perform([currentDetectionRequest])
            } catch {
                logCM("Failed to perform VNImageRequestHandler: \(error.localizedDescription)")
                DispatchQueue.main.async {
                    self.error = "VNImageRequestHandler failed: \(error.localizedDescription)"
                    self.lastDetections = []
                }
                self.detectionCallback?(self.lastFrameImageData, [], nil, nil)
                self.processingState = .idle
            }
        }
    }
}

// MARK: - Detection handling
extension CameraManager {
    private func handleDetections(
        request: VNRequest,
        error: Error?
    ) {
        let startTime = Date()
        let imageDataToUse = self.lastFrameImageData

        if let visionError = error {
            logCM("Detection error from Vision request: \(visionError.localizedDescription)")
            DispatchQueue.main.async {
                self.error = "Vision detection error: \(visionError.localizedDescription)"
                self.lastDetections = []
            }
            self.detectionCallback?(imageDataToUse, [], nil, nil)
            return
        }
        
        guard let results = request.results else {
            logCM("Vision request returned no results.")
            DispatchQueue.main.async {
                self.lastDetections = []
            }
            self.detectionCallback?(imageDataToUse, [], nil, nil)
            return
        }
        
        let detections: [NetworkDetection] = results
            .compactMap { result -> NetworkDetection? in
                guard let observation = result as? VNRecognizedObjectObservation else {
                    return nil
                }
                guard let label = observation.labels.first else {
                    return nil
                }
                
                let boundingBox = observation.boundingBox
                let bboxArray = [
                    Float(boundingBox.minX),
                    Float(boundingBox.minY),
                    Float(boundingBox.maxX),
                    Float(boundingBox.maxY)
                ]
                
                var detection = NetworkDetection(
                    label: label.identifier,
                    confidence: label.confidence,
                    bbox: bboxArray,
                    trackId: observation.uuid.hashValue
                )
                detection.contextualLabel = getSpatialLabel(from: bboxArray)
                return detection
            }
        
        let processingTime = Date().timeIntervalSince(startTime)
        let avgConfidence = detections.map(\.confidence).reduce(0, +) / Float(detections.count)
        let logEntry = DetectionLogEntry(detectionsCount: detections.count, averageConfidence: avgConfidence, processingTime: processingTime, timestamp: Date())
        detectionLogPublisher.send(logEntry)

        DispatchQueue.main.async {
            self.lastDetections = detections
        }
        
        // Simulate FastVLM processing with a 2-second delay
        DispatchQueue.global(qos: .userInitiated).asyncAfter(deadline: .now() + 2.0) { [weak self] in
            guard let self = self else { return }
            let simulatedVLMDescription = "FastVLM model not implemented yet. Detected: \(detections.map { $0.label }.joined(separator: ", "))"
            let simulatedVLMConfidence: Float = 0.5 // Placeholder confidence
            
            DispatchQueue.main.async {
                self.lastVLMDescription = simulatedVLMDescription
                self.lastVLMConfidence = simulatedVLMConfidence
            }
            
            self.detectionCallback?(imageDataToUse, detections, simulatedVLMDescription, simulatedVLMConfidence)
            self.processingState = .sent
            self.processingState = .idle // Immediately ready for next frame
        }
    }
}