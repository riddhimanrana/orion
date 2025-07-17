import Foundation

// Detection structure for sending to server
struct NetworkDetection: Codable {
    let label: String
    let confidence: Float
    let bbox: [Float]
    let trackId: Int?
    var contextualLabel: String? // e.g., "person (center)"
    
    enum CodingKeys: String, CodingKey {
        case label
        case confidence
        case bbox
        case trackId = "track_id"
        case contextualLabel = "contextual_label"
    }
}
