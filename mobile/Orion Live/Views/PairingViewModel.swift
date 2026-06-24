import Foundation
import SwiftUI
import Combine
import CommonCrypto
import Supabase

@MainActor
class PairingViewModel: ObservableObject {
    @Published var code: String = ""
    @Published var isLoading: Bool = false
    @Published var pairingStatus: String? = nil
    @Published var isPaired: Bool = false
    @Published var errorMessage: String? = nil

    private var authManager: AuthManager
    
    // Decodable struct representations for database rows
    struct PairingCodeRecord: Codable {
        let id: Int
        let device_id: String
        let hashed_code: String
        let salt: String
        let expires_at: Int
        let used: Bool
        let devices: DeviceRecord
        
        enum CodingKeys: String, CodingKey {
            case id
            case device_id
            case hashed_code
            case salt
            case expires_at
            case used
            case devices = "devices"
        }
    }
    
    struct DeviceRecord: Codable {
        let id: String
        let user_id: String
        let type: String
        let name: String
    }

    init(authManager: AuthManager) {
        self.authManager = authManager
    }

    func pairDevice() async {
        guard code.count == 6 else {
            self.errorMessage = "Please enter a valid 6-digit code"
            return
        }

        self.isLoading = true
        self.errorMessage = nil
        self.pairingStatus = "Verifying pairing code..."
        
        defer { self.isLoading = false }

        guard let userSession = authManager.session else {
            self.errorMessage = "You must be logged in to pair devices"
            return
        }

        let userId = userSession.user.id.uuidString
        
        do {
            // Query active pairing code records associated with the user
            // We use PostgREST join to filter by user_id
            let records: [PairingCodeRecord] = try await authManager.supabase
                .from("device_pairing_codes")
                .select("*, devices:device_id!inner(*)")
                .eq("devices.user_id", value: userId)
                .eq("used", value: false)
                .execute()
                .value
            
            let currentTime = Int(Date().timeIntervalSince1970)
            
            // Find the matching pairing code record by hashing the input code with their salts
            guard let matchedRecord = records.first(where: { record in
                guard record.expires_at > currentTime else { return false }
                let computedHash = sha256(code: self.code, salt: record.salt)
                return computedHash == record.hashed_code
            }) else {
                self.errorMessage = "Invalid or expired pairing code"
                return
            }

            self.pairingStatus = "Registering device pairing..."
            
            // Generate unique mobile device ID and resolve model name
            let mobileDeviceId = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
            let deviceName = UIDevice.current.name
            
            // 1. Register mobile device
            let mobileDeviceData = [
                "id": mobileDeviceId,
                "user_id": userId,
                "type": "mobile",
                "name": deviceName
            ]
            try await authManager.supabase
                .from("devices")
                .upsert(mobileDeviceData)
                .execute()
                
            // 2. Create the active device pair record
            let pairId = UUID().uuidString
            let pairData = [
                "id": pairId,
                "user_id": userId,
                "mobile_device_id": mobileDeviceId,
                "server_device_id": matchedRecord.device_id,
                "status": "active"
            ]
            try await authManager.supabase
                .from("device_pairs")
                .upsert(pairData)
                .execute()
                
            // 3. Mark the pairing code session as used
            try await authManager.supabase
                .from("device_pairing_codes")
                .update(["used": true])
                .eq("id", value: matchedRecord.id)
                .execute()
                
            // Save paired server ID locally
            UserDefaults.standard.set(matchedRecord.device_id, forKey: "paired_server_device_id")
            UserDefaults.standard.set(pairId, forKey: "paired_session_id")
            
            self.isPaired = true
            self.pairingStatus = "Success! Device paired."
            
        } catch {
            self.errorMessage = "Failed to complete pairing: \(error.localizedDescription)"
        }
    }

    private func sha256(code: String, salt: String) -> String {
        let input = code + salt
        guard let data = input.data(using: .utf8) else { return "" }
        var digest = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
        data.withUnsafeBytes {
            _ = CC_SHA256($0.baseAddress, CC_LONG(data.count), &digest)
        }
        return digest.map { String(format: "%02hhx", $0) }.joined()
    }
}
