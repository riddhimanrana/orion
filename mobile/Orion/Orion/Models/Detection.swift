import Foundation

/// YOLO detection result
struct Detection: Codable {
    let label: String
    let confidence: Float
    let bbox: [Float]  // [minX, minY, maxX, maxY] in normalized coordinates
    let trackId: Int?
    
    enum CodingKeys: String, CodingKey {
        case label
        case confidence
        case bbox
        case trackId = "track_id"
    }
}

/// Frame data sent to server
struct DetectionFrame: Codable {
    let frameId: String
    let timestamp: TimeInterval
    let imageData: String?
    let detections: [Detection]
    
    enum CodingKeys: String, CodingKey {
        case frameId = "frame_id"
        case timestamp
        case imageData = "image_data"
        case detections
    }
}

/// Streaming configuration
struct StreamConfig: Codable {
    let maxFPS: Int
    let sendImages: Bool
    let imageQuality: Float  // 0.0 - 1.0
    
    static let standard = StreamConfig(
        maxFPS: 30,
        sendImages: true,
        imageQuality: 0.5
    )
    
    static let lowBandwidth = StreamConfig(
        maxFPS: 15,
        sendImages: false,
        imageQuality: 0.3
    )
}

/// Scene region of interest
struct SceneROI: Codable {
    let x: Float  // Normalized x coordinate (0-1)
    let y: Float  // Normalized y coordinate (0-1)
    let width: Float  // Normalized width (0-1)
    let height: Float  // Normalized height (0-1)
    let label: String  // Region label/name
    
    var bbox: [Float] {
        [x, y, x + width, y + height]
    }
}

/// Detection metrics
struct DetectionMetrics {
    let framesProcessed: Int
    let detectionsPerFrame: Float
    let averageConfidence: Float
    let processingTimeMS: Float
    
    static let empty = DetectionMetrics(
        framesProcessed: 0,
        detectionsPerFrame: 0,
        averageConfidence: 0,
        processingTimeMS: 0
    )
}

/// Detection settings
struct DetectionSettings {
    var confidenceThreshold: Float = 0.5
    var iouThreshold: Float = 0.45
    var maxDetections: Int = 20
    var trackingEnabled: Bool = true
    
    static let standard = DetectionSettings()
    
    static let highAccuracy = DetectionSettings(
        confidenceThreshold: 0.7,
        iouThreshold: 0.5,
        maxDetections: 30,
        trackingEnabled: true
    )
    
    static let highPerformance = DetectionSettings(
        confidenceThreshold: 0.4,
        iouThreshold: 0.4,
        maxDetections: 10,
        trackingEnabled: false
    )
}

// MARK: - Constants
enum DetectionDefaults {
    static let standardImageSize = 640
    static let supportedLabels = [
        "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
        "truck", "boat", "traffic light", "fire hydrant", "stop sign",
        "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
        "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
        "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
        "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
        "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
        "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
        "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
        "couch", "potted plant", "bed", "dining table", "toilet", "tv",
        "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
        "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
        "scissors", "teddy bear", "hair drier", "toothbrush"
    ]
    
    static let categoryMap: [String: String] = [
        "person": "human",
        "bicycle": "vehicle",
        "car": "vehicle",
        "motorcycle": "vehicle",
        "airplane": "vehicle",
        "bus": "vehicle",
        "train": "vehicle",
        "truck": "vehicle",
        "boat": "vehicle",
        "bird": "animal",
        "cat": "animal",
        "dog": "animal",
        "horse": "animal",
        "sheep": "animal",
        "cow": "animal",
        "elephant": "animal",
        "bear": "animal",
        "zebra": "animal",
        "giraffe": "animal",
        "chair": "furniture",
        "couch": "furniture",
        "bed": "furniture",
        "dining table": "furniture",
        "toilet": "furniture",
        "tv": "electronics",
        "laptop": "electronics",
        "mouse": "electronics",
        "remote": "electronics",
        "keyboard": "electronics",
        "cell phone": "electronics",
        "microwave": "appliance",
        "oven": "appliance",
        "toaster": "appliance",
        "sink": "appliance",
        "refrigerator": "appliance"
    ]
}
