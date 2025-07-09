import Foundation
import os.log

/// Logging categories
enum AppLogCategory: String, CaseIterable {
    case network = "Network"
    case camera = "Camera"
    case detection = "Detection"
    case vision = "Vision"
    case ui = "UI"
    case general = "General"
}

/// Log levels
enum LogLevel: String {
    case debug = "DEBUG"
    case info = "INFO"
    case warning = "WARNING"
    case error = "ERROR"
    
    var emoji: String {
        switch self {
        case .debug: return "🔍"
        case .info: return "ℹ️"
        case .warning: return "⚠️"
        case .error: return "❌"
        }
    }
}

/// Application logger
class Logger {
    /// Shared instance
    static let shared = Logger()
    
    /// OS Logger instances
    private var loggers: [AppLogCategory: OSLog] = [:]
    
    /// Debug logging enabled
    private let debugEnabled = DebugConfig.enableNetworkLogs ||
                             DebugConfig.enableProcessingLogs ||
                             DebugConfig.enablePerformanceMetrics
    
    private init() {
        // Initialize loggers for each category
        AppLogCategory.allCases.forEach { category in
            loggers[category] = OSLog(
                subsystem: Bundle.main.bundleIdentifier ?? "com.orion",
                category: category.rawValue
            )
        }
    }
    
    /// Log a message
    func log(
        _ message: String,
        level: LogLevel = .info,
        category: AppLogCategory = AppLogCategory.general,
        file: String = #file,
        function: String = #function,
        line: Int = #line
    ) {
        // Skip debug messages if debug logging is disabled
        if level == .debug && !debugEnabled {
            return
        }
        
        // Create log message with metadata
        let timestamp = Date().formatted(date: .omitted, time: .standard)
        let filename = (file as NSString).lastPathComponent
        let metadata = "[\(filename):\(line)] \(function)"
        
        let fullMessage = """
        \(level.emoji) \(timestamp) [\(category.rawValue)] \(level.rawValue)
        \(message)
        \(metadata)
        """
        
        // Get appropriate logger
        let logger = loggers[category] ?? loggers[AppLogCategory.general]!
        
        // Log with appropriate level
        switch level {
        case .debug:
            os_log(.debug, log: logger, "%{public}@", fullMessage)
        case .info:
            os_log(.info, log: logger, "%{public}@", fullMessage)
        case .warning:
            os_log(.error, log: logger, "%{public}@", fullMessage)
        case .error:
            os_log(.fault, log: logger, "%{public}@", fullMessage)
        }
        
        // Print to console in debug builds
        #if DEBUG
        print(fullMessage)
        #endif
    }
    
    /// Log network activity
    func network(_ message: String, level: LogLevel = .debug) {
        log(message, level: level, category: AppLogCategory.network)
    }
    
    /// Log camera activity
    func camera(_ message: String, level: LogLevel = .debug) {
        log(message, level: level, category: AppLogCategory.camera)
    }
    
    /// Log detection activity
    func detection(_ message: String, level: LogLevel = .debug) {
        log(message, level: level, category: AppLogCategory.detection)
    }
    
    /// Log vision analysis
    func vision(_ message: String, level: LogLevel = .debug) {
        log(message, level: level, category: AppLogCategory.vision)
    }
    
    /// Log UI activity
    func ui(_ message: String, level: LogLevel = .debug) {
        log(message, level: level, category: AppLogCategory.ui)
    }
    
    /// Log performance metrics
    func performance(_ metrics: PerformanceMetrics) {
        guard DebugConfig.enablePerformanceMetrics else { return }
        
        let message = """
        Performance Metrics:
        - FPS: \(String(format: "%.1f", metrics.fps))
        - Processing Time: \(String(format: "%.3f", metrics.processingTime))s
        - Memory Usage: \(String(format: "%.1f", metrics.memoryUsage))MB
        - Battery Level: \(String(format: "%.0f", metrics.batteryLevel * 100))%
        - Temperature: \(String(format: "%.1f", metrics.temperature))°C
        """
        
        log(message, level: LogLevel.debug, category: AppLogCategory.general)
    }
    
    /// Log error with full context
    func error(
        _ error: Error,
        category: AppLogCategory = AppLogCategory.general,
        file: String = #file,
        function: String = #function,
        line: Int = #line
    ) {
        let message: String
        
        if let appError = error as? AppError {
            message = appError.description
        } else {
            message = error.localizedDescription
        }
        
        log(
            message,
            level: LogLevel.error,
            category: category,
            file: file,
            function: function,
            line: line
        )
    }
}

// MARK: - Convenience logging functions
func logDebug(
    _ message: String,
    category: AppLogCategory = AppLogCategory.general,
    file: String = #file,
    function: String = #function,
    line: Int = #line
) {
    Logger.shared.log(
        message,
        level: LogLevel.debug,
        category: category,
        file: file,
        function: function,
        line: line
    )
}

func logInfo(
    _ message: String,
    category: AppLogCategory = AppLogCategory.general,
    file: String = #file,
    function: String = #function,
    line: Int = #line
) {
    Logger.shared.log(
        message,
        level: LogLevel.info,
        category: category,
        file: file,
        function: function,
        line: line
    )
}

func logWarning(
    _ message: String,
    category: AppLogCategory = AppLogCategory.general,
    file: String = #file,
    function: String = #function,
    line: Int = #line
) {
    Logger.shared.log(
        message,
        level: LogLevel.warning,
        category: category,
        file: file,
        function: function,
        line: line
    )
}

func logError(
    _ error: Error,
    category: AppLogCategory = AppLogCategory.general,
    file: String = #file,
    function: String = #function,
    line: Int = #line
) {
    Logger.shared.error(
        error,
        category: category,
        file: file,
        function: function,
        line: line
    )
}
