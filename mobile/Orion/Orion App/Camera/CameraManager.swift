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
    /// Camera session
    let session = AVCaptureSession()
    private var videoOutput: AVCaptureVideoDataOutput?
    
    /// YOLO detection model
    private var yoloModel: VNCoreMLModel?
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
    }
    @Published private(set) var processingState: ProcessingState = .idle
    
    /// Detection callback for other purposes (e.g., network)
    private var detectionCallback: ((Data?, [NetworkDetection], String?, Float?) -> Void)?
    let detectionLogPublisher = PassthroughSubject<DetectionLogEntry, Never>()
    let frameAnalysisLogPublisher = PassthroughSubject<FrameAnalysisLog, Never>()
    
    /// Published state for SwiftUI UI updates
    @Published private(set) var isStreaming = false
    @Published private(set) var error: String?
    @Published var lastDetections: [NetworkDetection] = []
    @Published private(set) var availableCameraOptions: [CameraOption] = []
    @Published private(set) var currentCameraOption: CameraOption?
    @Published private(set) var lastVLMDescription: String? = "FastVLM model not implemented yet"
    @Published private(set) var lastVLMConfidence: Float? = 0.0
    @Published var lastFrameImageData: Data?
    
    // Dependencies
    private let objectDetector = ObjectDetector()
    private let vlmModel = FastVLMModel()
    private weak var wsManager: WebSocketManager?

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
        Task {
            try? await vlmModel.load()
        }
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
            yoloModel = nil
            logCM("YOLO model unloaded for full processing mode.")
        } else {
            // Ensure model is loaded for split processing mode
            if yoloModel == nil {
                setupYOLO()
            }
        }
    }
    
    func serverDidAcknowledgeFrame() {
        // Allow processing of next frame in full mode
        if processingState == .sent {
            processingState = .idle
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
        let backCameraDeviceTypes: [AVCaptureDevice.DeviceType] = [.builtInWideAngleCamera, .builtInUltraWideCamera, .builtInTelephotoCamera]
        let discoverySession = AVCaptureDevice.DiscoverySession(deviceTypes: backCameraDeviceTypes, mediaType: .video, position: .back)

        for device in discoverySession.devices {
            let cameraType: CameraType
            let zoomFactor: Double?

            switch device.deviceType {
            case .builtInWideAngleCamera:
                cameraType = .wide
                zoomFactor = 1.0
            case .builtInUltraWideCamera:
                cameraType = .ultraWide
                zoomFactor = 0.5
            case .builtInTelephotoCamera:
                cameraType = .telephoto
                if device.localizedName.contains("5x") { zoomFactor = 5.0 }
                else if device.localizedName.contains("3x") { zoomFactor = 3.0 }
                else { zoomFactor = 2.0 }
            default:
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
            self.yoloModel = try VNCoreMLModel(for: model)
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
        guard processingState == .idle, let pixelBuffer = sampleBuffer.imageBuffer else { return }
        
        processingState = .processing

        // In full mode, send image and finish
        if SettingsManager.shared.processingMode == "full" {
            let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
            let orientedImage = ciImage.oriented(.right)
            if let cgImage = CIContext().createCGImage(orientedImage, from: orientedImage.extent) {
                let imageData = UIImage(cgImage: cgImage).jpegData(compressionQuality: 0.7)
                DispatchQueue.main.async { self.lastFrameImageData = imageData }
                self.detectionCallback?(imageData, [], nil, nil)
                processingState = .sent
                processingState = .idle // Immediately ready for next frame
            }
            return
        }

        // In "split" mode, perform local detection
        guard let yoloModel = self.yoloModel else {
            logCM("YOLO model is nil, cannot process in split mode.")
            processingState = .idle
            return
        }
        
        let request = VNCoreMLRequest(model: yoloModel) { [weak self] request, error in
            guard let self = self else { return }
            self.handleDetections(pixelBuffer: pixelBuffer, request: request, error: error)
        }
        request.imageCropAndScaleOption = .scaleFit

        processingQueue.async {
            do {
                try VNImageRequestHandler(cvPixelBuffer: pixelBuffer, orientation: .right, options: [:]).perform([request])
            } catch {
                logCM("Failed to perform VNImageRequestHandler: \(error.localizedDescription)")
                DispatchQueue.main.async {
                    self.error = "VNImageRequestHandler failed: \(error.localizedDescription)"
                    self.lastDetections = []
                    self.processingState = .idle
                }
            }
        }
    }
}

// MARK: - Detection handling
extension CameraManager {
    private func handleDetections(
        pixelBuffer: CVPixelBuffer,
        request: VNRequest,
        error: Error?
    ) {
        autoreleasepool {
            let startTime = Date()
            
            if let visionError = error {
                logCM("Detection error from Vision request: \(visionError.localizedDescription)")
                DispatchQueue.main.async { self.error = "Vision detection error: \(visionError.localizedDescription)"; self.lastDetections = []; self.processingState = .idle }
                return
            }
            
            guard let results = request.results else {
                logCM("Vision request returned no results.")
                DispatchQueue.main.async { self.lastDetections = []; self.processingState = .idle }
                return
            }
            
            let detections: [NetworkDetection] = results
                .compactMap { result -> NetworkDetection? in
                    guard let observation = result as? VNRecognizedObjectObservation, let label = observation.labels.first else { return nil }
                    let bboxArray = [Float(observation.boundingBox.minX), Float(observation.boundingBox.minY), Float(observation.boundingBox.maxX), Float(observation.boundingBox.maxY)]
                    var detection = NetworkDetection(label: label.identifier, confidence: label.confidence, bbox: bboxArray, trackId: observation.uuid.hashValue)
                    detection.contextualLabel = getSpatialLabel(from: bboxArray)
                    return detection
                }
            
            let yoloProcessingTime = Date().timeIntervalSince(startTime)
            let frameWidth = CVPixelBufferGetWidth(pixelBuffer)
            let vlmPrompt = self.objectDetector.createVLMPrompt(from: detections.map { Detection(from: $0) }, frameWidth: frameWidth)
            
            Task {
                let vlmResult = await self.vlmModel.generate(prompt: vlmPrompt, image: pixelBuffer)
               
                let frameId = UUID().uuidString
                let timestamp = Date()
                
                let analysisLog = FrameAnalysisLog(
                    frameId: frameId, timestamp: timestamp, yoloDetections: detections.map { Detection(from: $0) },
                    yoloProcessingTime: yoloProcessingTime, vlmPrompt: vlmPrompt, vlmResult: vlmResult,
                    cpuUsage: 0.65, gpuUsage: 0.45, aneUsage: 0.80, batteryLevel: UIDevice.current.batteryLevel
                )
                self.frameAnalysisLogPublisher.send(analysisLog)

                self.detectionCallback?(self.lastFrameImageData, detections, vlmResult.description, nil)
                
                DispatchQueue.main.async {
                    self.lastDetections = detections
                    self.lastVLMDescription = vlmResult.description
                    self.processingState = .idle
                }
            }
        }
    }
    
    private func getSpatialLabel(from bbox: [Float]) -> String? {
        guard bbox.count >= 4 else { return nil }
        let centerX = (bbox[0] + bbox[2]) / 2.0
        let centerY = (bbox[1] + bbox[3]) / 2.0
        let horizontalPosition = centerX < 0.33 ? "left" : (centerX > 0.67 ? "right" : "center")
        let verticalPosition = centerY < 0.33 ? "bottom" : (centerY > 0.67 ? "top" : "middle")
        return "\(horizontalPosition) \(verticalPosition)"
    }
}

fileprivate extension Detection {
    init(from networkDetection: NetworkDetection) {
        self.init(label: networkDetection.label, confidence: networkDetection.confidence, bbox: networkDetection.bbox, trackId: networkDetection.trackId, contextualLabel: networkDetection.contextualLabel)
    }
}