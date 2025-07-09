import Foundation
import ImageIO
import UIKit

/// Server configuration
enum ServerConfig {
    // Update these values to match your server
    static let host = "192.168.86.49"  // Your Mac's local IP
    static let port = 8000
    static let wsURL = "ws://\(host):\(port)/ios"
    
    // WebSocket configuration
    static let reconnectDelay = 60.0  // Seconds
    static let pingInterval = 30.0    // Seconds
    static let connectionTimeout = 5.0 // Seconds
}

/// Camera configuration
enum CameraConfig {
    // Frame processing
    static let maxFPS = 30
    static let processingQuality = 0.5  // JPEG compression (0-1)
    static let minimumProcessingInterval = 1.0 / Double(maxFPS)
    
    // Image settings
    static let imageSize = CGSize(width: 640, height: 640)  // YOLOv11n input size
    static let aspectRatio: CGFloat = 16.0 / 9.0
    static let orientation = CGImagePropertyOrientation.right
    
    // Detection settings
    static let confidenceThreshold: Float = 0.5
    static let iouThreshold: Float = 0.45
    static let maxDetections = 20
}

/// UI Configuration
enum UIConfig {
    // Detection visualization
    static let boxColor = UIColor.green
    static let boxLineWidth: CGFloat = 2.0
    static let boxCornerRadius: CGFloat = 4.0
    static let labelBackgroundOpacity: CGFloat = 0.6
    static let labelFontSize: CGFloat = 12.0
    
    // Scene understanding view
    static let maxVisibleInsights = 5
    static let maxTrackedObjects = 10
    static let maxHistorySeconds = 5.0
    
    // Animation
    static let standardAnimationDuration = 0.3
    static let statusTransitionDuration = 0.2
}

/// Debug configuration
//enum DebugConfig {
//    // Logging
//    static let enableNetworkLogs = true
//    static let enableProcessingLogs = true
//    static let enablePerformanceMetrics = true
//
//    // Performance monitoring
//    static let trackFrameRate = true
//    static let trackMemoryUsage = true
//    static let trackBatteryImpact = true
//
//    // Development
//    static let showDebugOverlay = false
//    static let simulateDetections = false
//}

struct DebugConfig {
    static var enableNetworkLogs = false
    static var enableProcessingLogs = false
    static var enablePerformanceMetrics = false
    
    // Performance monitoring
    static let trackFrameRate = true
    static let trackMemoryUsage = true
    static let trackBatteryImpact = true
    
    // Development
    static let showDebugOverlay = false
    static let simulateDetections = false
}



/// Application state
enum AppState {
    case initializing
    case connecting
    case streaming
    case error(String)
    case disconnected
    
    var description: String {
        switch self {
        case .initializing:
            return "Initializing..."
        case .connecting:
            return "Connecting to server..."
        case .streaming:
            return "Streaming"
        case .error(let message):
            return "Error: \(message)"
        case .disconnected:
            return "Disconnected"
        }
    }
}

/// Performance metrics
struct PerformanceMetrics {
    var fps: Double = 0
    var processingTime: TimeInterval = 0
    var memoryUsage: Double = 0
    var batteryLevel: Float = 0
    var temperature: Float = 0
    
    static let empty = PerformanceMetrics()
}

/// Error handling
enum AppError: Error {
    case serverConnection(String)
    case cameraSetup(String)
    case modelLoading(String)
    case detection(String)
    case configuration(String)
    
    var description: String {
        switch self {
        case .serverConnection(let msg):
            return "Server Error: \(msg)"
        case .cameraSetup(let msg):
            return "Camera Error: \(msg)"
        case .modelLoading(let msg):
            return "Model Error: \(msg)"
        case .detection(let msg):
            return "Detection Error: \(msg)"
        case .configuration(let msg):
            return "Config Error: \(msg)"
        }
    }
}

/// Notification names
extension Notification.Name {
    static let serverConnected = Notification.Name("serverConnected")
    static let serverDisconnected = Notification.Name("serverDisconnected")
    static let detectionComplete = Notification.Name("detectionComplete")
    static let analysisReceived = Notification.Name("analysisReceived")
    static let errorOccurred = Notification.Name("errorOccurred")
}

/// UserDefaults keys
enum UserDefaultsKeys {
    static let serverHost = "serverHost"
    static let serverPort = "serverPort"
    static let confidenceThreshold = "confidenceThreshold"
    static let showLabels = "showLabels"
    static let sendImages = "sendImages"
    static let maxFPS = "maxFPS"
    static let processingMode = "processingMode"
}

