
import Foundation

struct Device: Codable, Identifiable, Hashable {
    let id: UUID
    let userId: UUID
    let type: String
    let name: String
    let createdAt: Date
    var lastSeen: Date?

    enum CodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case type, name
        case createdAt = "created_at"
        case lastSeen = "last_seen"
    }
}

struct DevicePair: Codable, Identifiable, Hashable {
    let id: UUID
    var status: String
    let createdAt: Date
    var revokedAt: Date?
    let serverDevice: PairedDevice

    enum CodingKeys: String, CodingKey {
        case id, status
        case createdAt = "created_at"
        case revokedAt = "revoked_at"
        case serverDevice = "server_device"
    }
}

struct PairedDevice: Codable, Identifiable, Hashable {
    let id: UUID
    let type: String
    let name: String
    var lastSeen: Date?

    enum CodingKeys: String, CodingKey {
        case id, type, name
        case lastSeen = "last_seen"
    }
}

// MARK: - API Request/Response Models

struct DeviceRegistrationResponse: Codable {
    let deviceId: UUID
    
    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
    }
}

struct PairingCodeResponse: Codable {
    let code: String
    let expiresAt: String
    
    enum CodingKeys: String, CodingKey {
        case code
        case expiresAt = "expires_at"
    }
}
