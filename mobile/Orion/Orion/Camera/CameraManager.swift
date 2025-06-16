import Combine // Ensure this is at the top
import AVFoundation
import CoreImage
import Vision
import UIKit

// Helper for logging within CameraManager
private func logCM(_ message: String) {
    // Assuming Logger.shared.log handles the [CameraManager] prefix or it's desired here.
    // If Logger.shared.log is meant to take a category, this might need adjustment
    // For now, keeping it as is, as the main issue is the content of `message`
    Logger.shared.log("[CameraManager] \(message)", category: .camera)
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
    
    /// Detection callback for other purposes (e.g., network)
    private var detectionCallback: ((Data?, [Detection]) -> Void)?
    
    /// Published state for SwiftUI UI updates
    @Published private(set) var isStreaming = false
    @Published private(set) var error: String?
    @Published var lastDetections: [Detection] = [] // <<< FIX: Added for UI updates

    private var currentFrameImageDataForCallback: Data?

    override init() {
        super.init()
        logCM("Initializing...")
        setupCamera()
        setupYOLO()
        logCM("Initialization complete. Final error state: \(error ?? "None")")
    }
    
    /// **FIX: Creates the preview layer for the CameraView**
    func getPreviewLayer() -> AVCaptureVideoPreviewLayer {
        logCM("getPreviewLayer called.")
        let previewLayer = AVCaptureVideoPreviewLayer(session: session)
        previewLayer.videoGravity = .resizeAspectFill
        // It's good practice to set the connection's videoOrientation if you know the UI orientation.
        // However, for a basic preview, often not strictly necessary if UI handles rotation.
        // If orientation issues arise with the preview, this is a place to investigate.
        // Example: if let connection = previewLayer.connection, connection.isVideoOrientationSupported {
        // connection.videoOrientation = .portrait // or landscape, based on UI
        // }
        return previewLayer
    }
    
    func startStreaming() {
        logCM("startStreaming called. Current isStreaming: \(isStreaming), session.isReallyRunning: \(session.isRunning)")
        guard !isStreaming || !session.isRunning else { // Check both our flag and actual session state
            logCM("Already streaming or session is already running. isStreaming: \(isStreaming), session.isReallyRunning: \(session.isRunning)")
            if session.isRunning && !self.isStreaming { // Correct our flag if out of sync
                 DispatchQueue.main.async { self.isStreaming = true }
            }
            return
        }

        logCM("Attempting to start streaming session...")
        if session.inputs.isEmpty {
            let errMsg = "No inputs in session. Cannot start."
            logCM(errMsg)
            DispatchQueue.main.async { self.error = errMsg }
            return
        }
        if session.outputs.isEmpty {
            let errMsg = "No outputs in session. Cannot start."
            logCM(errMsg)
            DispatchQueue.main.async { self.error = errMsg }
            return
        }

        logCM("Session has inputs and outputs. Proceeding to start.")
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            logCM("Calling session.startRunning() on background thread.")
            self.session.startRunning() // This can take time
            DispatchQueue.main.async {
                self.isStreaming = self.session.isRunning
                if self.isStreaming {
                    logCM("Session started successfully. isStreaming = true, session.isReallyRunning: \(self.session.isRunning)")
                } else {
                    let errMsg = "Session failed to start. session.isReallyRunning is false."
                    logCM(errMsg)
                    self.error = errMsg // This will be picked up by ContentView
                }
            }
        }
    }
    
    func stopStreaming() {
        logCM("stopStreaming called. Current isStreaming: \(isStreaming), session.isReallyRunning: \(session.isRunning)")
        
        guard isStreaming || session.isRunning else {
            logCM("Not streaming or session not running. isStreaming=\(isStreaming), session.isReallyRunning=\(session.isRunning). Nothing to do.")
            if !session.isRunning && self.isStreaming { // Correct our flag if out of sync
                 DispatchQueue.main.async { self.isStreaming = false }
            }
            return
        }
        
        logCM("Attempting to stop streaming session...")
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            logCM("Calling session.stopRunning() on background thread.")
            self.session.stopRunning()
            DispatchQueue.main.async {
                self.isStreaming = self.session.isRunning // Should be false
                if !self.isStreaming {
                    logCM("Session stopped successfully. isStreaming = false, session.isReallyRunning: \(self.session.isRunning)")
                } else {
                    logCM("Session failed to stop. session.isReallyRunning is still true.")
                    // self.error = "Failed to stop camera session." // Optional
                }
            }
        }
    }
    
    func setDetectionCallback(_ callback: @escaping (Data?, [Detection]) -> Void) {
        self.detectionCallback = callback
    }
    
    private func setupCamera() {
        logCM("Setting up camera...")
        session.beginConfiguration() // Good practice to batch configuration changes
        session.sessionPreset = .hd1920x1080
        
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
            let errMsg = "Failed to access the back camera. Ensure permissions are granted and device has a suitable camera."
            logCM(errMsg)
            DispatchQueue.main.async { self.error = errMsg }
            session.commitConfiguration()
            return
        }
        logCM("Camera device found: \(device.localizedName)")
        
        do {
            let input = try AVCaptureDeviceInput(device: device)
            if session.canAddInput(input) {
                session.addInput(input)
                logCM("Camera input added.")
            } else {
                let errMsg = "Cannot add camera input to session."
                logCM(errMsg)
                DispatchQueue.main.async { self.error = errMsg }
                session.commitConfiguration()
                return
            }
        } catch {
            let errMsg = "Failed to create camera input: \(error.localizedDescription)"
            logCM(errMsg)
            DispatchQueue.main.async { self.error = errMsg }
            session.commitConfiguration()
            return
        }
        
        let localVideoOutput = AVCaptureVideoDataOutput() // Renamed to avoid confusion with self.videoOutput before assignment
        localVideoOutput.setSampleBufferDelegate(self, queue: processingQueue)
        localVideoOutput.videoSettings = [
            kCVPixelBufferPixelFormatTypeKey as String: Int(kCVPixelFormatType_32BGRA)
        ]
        // localVideoOutput.alwaysDiscardsLateVideoFrames = true // Consider this to reduce latency if processing is slow
        
        if session.canAddOutput(localVideoOutput) {
            session.addOutput(localVideoOutput)
            self.videoOutput = localVideoOutput // Assign to the class property
            logCM("Video output added.")
        } else {
            let errMsg = "Cannot add video output to session."
            logCM(errMsg)
            DispatchQueue.main.async { self.error = errMsg }
            session.commitConfiguration()
            return
        }
        session.commitConfiguration() // Commit configuration changes
        logCM("Camera setup complete. Inputs: \(session.inputs.count), Outputs: \(session.outputs.count)")
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
    
    private func shouldProcessFrame() -> Bool {
        let currentTime = CACurrentMediaTime()
        let timeSinceLastFrame = currentTime - lastFrameTime
        
        if timeSinceLastFrame >= 1.0 / Double(maxFPS) {
            lastFrameTime = currentTime
            return true
        }
        return false
    }
}

// MARK: - AVCaptureVideoDataOutputSampleBufferDelegate
extension CameraManager: AVCaptureVideoDataOutputSampleBufferDelegate {
    func captureOutput(
        _ output: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        // logCM("captureOutput called at \(CACurrentMediaTime())") // Very verbose, use for deep debugging
        guard shouldProcessFrame(), let currentDetectionRequest = detectionRequest else { // Renamed to avoid confusion
            // logCM("Skipping frame processing. shouldProcessFrame: \(shouldProcessFrame()), detectionRequest exists: \(detectionRequest != nil)")
            return
        }
        
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else {
            logCM("Failed to get pixelBuffer from sampleBuffer.")
            return
        }
        
        // Prepare image data for callback if needed
        if self.detectionCallback != nil {
            // This part seems okay, ensure CIContext().createCGImage doesn't fail often
            // and jpegData compression quality is reasonable.
            var localImageData: Data?
            let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
            // The orientation of the image sent to the server might need to match
            // what the server expects if it's doing its own rendering or analysis.
            // .right is common for landscape right.
            let orientedImage = ciImage.oriented(.right) // Match this with Vision request if consistent
            if let cgImage = CIContext().createCGImage(orientedImage, from: orientedImage.extent) {
                localImageData = UIImage(cgImage: cgImage).jpegData(compressionQuality: CameraConfig.processingQuality) // Use constant
            } else {
                logCM("Failed to create CGImage for callback.")
            }
            self.currentFrameImageDataForCallback = localImageData
        }

        do {
            // Ensure the orientation here matches the camera's physical orientation
            // or how the model was trained/expects input. .right is typical for landscape right.
            try VNImageRequestHandler(
                cvPixelBuffer: pixelBuffer,
                orientation: .right, // This should align with how the camera is held / preview is shown
                options: [:]
            ).perform([currentDetectionRequest])
        } catch {
            logCM("Failed to perform VNImageRequestHandler: \(error.localizedDescription)")
            DispatchQueue.main.async {
                self.error = "VNImageRequestHandler failed: \(error.localizedDescription)"
                self.lastDetections = [] // Clear detections on error
            }
            // Still call callback but with empty detections
            self.detectionCallback?(self.currentFrameImageDataForCallback, [])
            self.currentFrameImageDataForCallback = nil // Clear after use
        }
    }
}

// MARK: - Detection handling
extension CameraManager {
    private func handleDetections(
        request: VNRequest,
        error: Error?
    ) {
        // logCM("handleDetections called.") // Can be verbose
        let imageDataToUse = self.currentFrameImageDataForCallback
        self.currentFrameImageDataForCallback = nil // Clear after use, regardless of outcome

        if let visionError = error { // Renamed to avoid conflict
            logCM("Detection error from Vision request: \(visionError.localizedDescription)")
            DispatchQueue.main.async {
                self.error = "Vision detection error: \(visionError.localizedDescription)"
                self.lastDetections = []
            }
            self.detectionCallback?(imageDataToUse, [])
            return
        }
        
        guard let results = request.results else {
            logCM("Vision request returned no results.")
            DispatchQueue.main.async {
                // self.error = "No detection results." // This might be too aggressive if no objects is normal
                self.lastDetections = []
            }
            self.detectionCallback?(imageDataToUse, [])
            return
        }
        
        // logCM("Raw detection results count: \(results.count)")
        
        let detections: [Detection] = results
            .compactMap { result -> Detection? in
                guard let observation = result as? VNRecognizedObjectObservation else {
                    // logCM("Result was not VNRecognizedObjectObservation: \(type(of: result))")
                    return nil
                }
                guard let label = observation.labels.first else {
                    // logCM("Observation had no labels: \(observation.uuid)")
                    return nil
                }
                
                // Bounding box coordinates are normalized (0.0 to 1.0)
                // The current bbox format [minX, minY, maxX, maxY] is different from
                // what some models output (e.g. [x_center, y_center, width, height]).
                // VNRecognizedObjectObservation.boundingBox is a CGRect (origin, size) normalized.
                // So, minX, minY, maxX, maxY is correct for this.
                let boundingBox = observation.boundingBox // This is a CGRect
                let bboxArray = [
                    Float(boundingBox.minX),
                    Float(boundingBox.minY),
                    Float(boundingBox.maxX), // maxX = minX + width
                    Float(boundingBox.maxY)  // maxY = minY + height
                ]
                
                // logCM("Detected: \(label.identifier) (\(label.confidence)) at \(bboxArray)")

                return Detection(
                    label: label.identifier,
                    confidence: label.confidence,
                    bbox: bboxArray,
                    trackId: observation.uuid.hashValue // Using UUID's hashValue for a simple trackId
                )
            }
        
        // logCM("Processed detections count: \(detections.count)")
        
        DispatchQueue.main.async {
            self.lastDetections = detections
            // logCM("Updated lastDetections on main thread. Count: \(detections.count)")
            if detections.isEmpty && results.isEmpty {
                 // logCM("No objects detected in this frame.") // Log if no objects were found
            }
        }
        
        self.detectionCallback?(imageDataToUse, detections)
    }
}
