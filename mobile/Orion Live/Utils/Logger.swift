//
//  Logger.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Logging utilities and categories for Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//
import Foundation
import os.log
import Combine

/// Logging categories
enum AppLogCategory: String, CaseIterable {
    case network = "Network"
    case camera = "Camera"
    case detection = "Detection"
    case vision = "Vision"
    case ui = "UI"
    case battery = "Battery"
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
    
    /// In-app log publisher for real-time UI streaming
    let logPublisher = PassthroughSubject<AppLogEntry, Never>()
    
    /// Ring buffer of recent logs for UI
    private let maxBufferedLogs = 500
    private var bufferedLogs: [AppLogEntry] = []
    private let bufferQueue = DispatchQueue(label: "com.orion.logger.buffer", qos: .utility)
    
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
        
        // Publish to in-app stream and buffer for UI
        let entry = AppLogEntry(
            timestamp: Date(),
            category: category,
            level: level,
            message: message,
            metadata: metadata
        )
        // Buffer off-main to avoid blocking
        bufferQueue.async { [weak self] in
            guard let self = self else { return }
            self.bufferedLogs.append(entry)
            if self.bufferedLogs.count > self.maxBufferedLogs {
                self.bufferedLogs.removeFirst(self.bufferedLogs.count - self.maxBufferedLogs)
            }
            // Publish on main for UI consumers
            DispatchQueue.main.async {
                self.logPublisher.send(entry)
            }
        }
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
    
    /// Log battery activity
    func battery(_ message: String, level: LogLevel = .info) {
        log(message, level: level, category: AppLogCategory.battery)
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

// MARK: - UI-facing log entry model
struct AppLogEntry: Identifiable, Hashable {
    let id = UUID()
    let timestamp: Date
    let category: AppLogCategory
    let level: LogLevel
    let message: String
    let metadata: String
    
    var timeString: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "h:mm:ss a"
        return formatter.string(from: timestamp)
    }
}

// MARK: - Convenience accessors for buffered logs
extension Logger {
    func recentLogs() -> [AppLogEntry] {
        return bufferQueue.sync { bufferedLogs }
    }
}
