import CoreML
import Vision
import AVFoundation
import UIKit
import Combine

class ObjectDetector: ObservableObject {
    @Published var isModelReady: Bool = false

    private var model: VNCoreMLModel?
    private let modelQueue = DispatchQueue(label: "object.detection.queue", qos: .userInitiated)
    
    // YOLO class names (COCO dataset)
    private let classNames = [
        "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
        "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
        "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
        "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
        "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
        "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
        "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake",
        "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop",
        "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
        "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
    ]
    
    init() {
        // Model loading is now triggered by the StartView
    }
    
    func loadModel() {
        modelQueue.async { [weak self] in
            guard let self = self else { return }
            
            do {
                guard let modelURL = Bundle.main.url(forResource: "yolo11n", withExtension: "mlmodelc") else {
                    Logger.shared.log("YOLOv11n compiled model file not found in bundle")
                    return
                }
                
                let mlModel = try MLModel(contentsOf: modelURL)
                let visionModel = try VNCoreMLModel(for: mlModel)
                
                DispatchQueue.main.async {
                    self.model = visionModel
                    self.isModelReady = true
                    Logger.shared.log("YOLOv11n model loaded successfully")
                }
                
            } catch {
                Logger.shared.log("Failed to load YOLOv11n model: \(error)")
            }
        }
    }
    
    func detectObjects(in pixelBuffer: CVPixelBuffer, completion: @escaping ([Detection]) -> Void) {
        guard let model = model else {
            completion([])
            return
        }
        
        let request = VNCoreMLRequest(model: model) { [weak self] request, error in
            guard let self = self else { return }
            
            if let error = error {
                Logger.shared.log("Detection error: \(error)")
                completion([])
                return
            }
            
            let detections = self.processResults(request.results)
            completion(detections)
        }
        
        request.imageCropAndScaleOption = .scaleFill
        
        let handler = VNImageRequestHandler(cvPixelBuffer: pixelBuffer, orientation: .up, options: [:])
        
        modelQueue.async {
            do {
                try handler.perform([request])
            } catch {
                Logger.shared.log("Failed to perform detection: \(error)")
                completion([])
            }
        }
    }
    
    private func processResults(_ results: [VNObservation]?) -> [Detection] {
        guard let results = results else { return [] }
        
        var detections: [Detection] = []
        
        for result in results {
            if let coreMLResult = result as? VNCoreMLFeatureValueObservation {
                let processedDetections = processYOLOOutput(coreMLResult)
                detections.append(contentsOf: processedDetections)
            }
        }
        
        return applyNMS(detections, iouThreshold: 0.5)
    }
    
    private func processYOLOOutput(_ result: VNCoreMLFeatureValueObservation) -> [Detection] {
        guard let multiArray = result.featureValue.multiArrayValue else { return [] }
        
        var detections: [Detection] = []
        let numDetections = multiArray.shape[1].intValue
        let numClasses = classNames.count
        
        for i in 0..<numDetections {
            let confidence = multiArray[[0, i as NSNumber, 4]].floatValue
            if confidence < 0.5 { continue }
            
            var bestClassIndex = 0
            var bestClassScore: Float = 0.0
            
            for classIndex in 0..<numClasses {
                let score = multiArray[[0, i as NSNumber, NSNumber(value: 5 + classIndex)]].floatValue
                if score > bestClassScore {
                    bestClassScore = score
                    bestClassIndex = classIndex
                }
            }
            
            let finalConfidence = confidence * bestClassScore
            if finalConfidence < 0.5 { continue }
            
            let centerX = multiArray[[0, i as NSNumber, 0]].floatValue
            let centerY = multiArray[[0, i as NSNumber, 1]].floatValue
            let width = multiArray[[0, i as NSNumber, 2]].floatValue
            let height = multiArray[[0, i as NSNumber, 3]].floatValue
            
            let x = centerX - width / 2
            let y = centerY - height / 2
            
            let detection = Detection(
//                detectionId: UUID().uuidString,
                label: classNames[bestClassIndex],
                confidence: finalConfidence,
                bbox: [x, y, width, height],
                trackId: nil // Track ID can be assigned later if needed
                
            )
            
            detections.append(detection)
        }
        
        return detections
    }
    
    private func applyNMS(_ detections: [Detection], iouThreshold: Float) -> [Detection] {
        let sorted = detections.sorted { $0.confidence > $1.confidence }
        var result: [Detection] = []
        var suppressed = Set<Int>()
        
        for (i, det1) in sorted.enumerated() {
            if suppressed.contains(i) { continue }
            result.append(det1)
            
            for (j, det2) in sorted.enumerated() where i != j && !suppressed.contains(j) {
                if calculateIOU(det1.bbox, det2.bbox) > iouThreshold {
                    suppressed.insert(j)
                }
            }
        }
        
        return result
    }
    
    private func calculateIOU(_ box1: [Float], _ box2: [Float]) -> Float {
        guard box1.count == 4, box2.count == 4 else { return 0 }
        
        let x1 = max(box1[0], box2[0])
        let y1 = max(box1[1], box2[1])
        let x2 = min(box1[0] + box1[2], box2[0] + box2[2])
        let y2 = min(box1[1] + box1[3], box2[1] + box2[3])
        
        let interArea = max(0, x2 - x1) * max(0, y2 - y1)
        let box1Area = box1[2] * box1[3]
        let box2Area = box2[2] * box2[3]
        let unionArea = box1Area + box2Area - interArea
        
        return unionArea > 0 ? interArea / unionArea : 0
    }
    
    /// Creates a detailed text prompt for the VLM based on YOLO detections.
    func createVLMPrompt(from detections: [Detection], frameWidth: Int) -> String {
        guard !detections.isEmpty else { return "No objects were detected in the scene." }

        let objectList = detections.map { detection -> String in
            let contextualLabel = contextualize(bbox: detection.bbox, frameWidth: frameWidth)
            return "• \(detection.label) (\(contextualLabel))"
        }.joined(separator: "\n")

        return """
        The following objects were detected in the scene with bounding boxes:
        \(objectList)

        You are a vision-language model that analyzes images for context-aware reasoning. Given a visual scene, generate a rich, structured, and detailed
        description that includes:

        Main Focus – What is the primary object, person, or action in the scene?
        Surrounding Objects & Context – List and describe notable secondary objects, people, or environment details.
        Spatial Relationships – Describe where the objects are relative to one another.
        Activities & Interactions – What are people or objects doing? Are there interactions or implied motions?
        Scene Type & Time – Describe the overall type of scene (e.g. urban street, kitchen, park) and visible time of day.
        Inferences & Intent – Based on visual cues, infer what might have just happened or what might happen next.
        Style & Aesthetic – Describe the scene’s mood, lighting, or style (e.g. bright, moody, colorful).
        Your goal: make your description so complete and detailed that an image generator could reconstruct the scene with full visual accuracy from your
        output alone. Limit your response to under 256 tokens.
        """
    }

    /// Determines the spatial location of a bounding box within the frame.
    private func contextualize(bbox: [Float], frameWidth: Int) -> String {
        guard bbox.count >= 4 else { return "center" } // Return a default value
        let centerX = (bbox[0] + bbox[2]) / 2.0 * Float(frameWidth)
        let third = Float(frameWidth) / 3.0
        if centerX < third { return "left" }
        if centerX < third * 2 { return "center" }
        return "right"
    }
}

// MARK: - Helpers
extension ObjectDetector {
    func getClassNames() -> [String] {
        return classNames
    }
    
    func isModelLoaded() -> Bool {
        return model != nil
    }
}
