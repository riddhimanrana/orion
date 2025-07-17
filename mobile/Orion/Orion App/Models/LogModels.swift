import Foundation

// MARK: - Log Entry Structures

/// A structured log entry for a network event.
struct NetworkLogEntry: Identifiable, Codable, Hashable {
    let id = UUID()
    let timestamp: Date
    let message: String
    let type: LogType
    let rtt: TimeInterval? // Optional round-trip time

    enum LogType: String, Codable {
        case sent
        case received
        case error
        case status
    }
    
    enum CodingKeys: String, CodingKey {
        case id, timestamp, message, type, rtt
    }

    var formattedTimestamp: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .medium
        return formatter.string(from: timestamp)
    }
}

/// A structured log entry for a detection event.
struct DetectionLogEntry: Identifiable, Codable, Hashable {
    let id = UUID()
    let detectionsCount: Int
    let averageConfidence: Float
    let processingTime: TimeInterval
    let timestamp: Date
    
    enum CodingKeys: String, CodingKey {
        case id, detectionsCount, averageConfidence, processingTime, timestamp
    }

    var formattedTimestamp: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .medium
        return formatter.string(from: timestamp)
    }
}