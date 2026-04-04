
//
//  APIService.swift
//  Orion Server
//
//  Created by Gemini on 8/15/25.
//

import Foundation
import Supabase

struct WebRTCTokenResponse: Codable {
    let token: String
}

struct ICECredentials: Codable {
    let urls: [String]
    let username: String
    let credential: String
    let ttl: Int
    let realm: String
    let issuedAt: Int?
    let expiresAt: Int?
    let usage: ICEUsage?
}

struct ICEUsage: Codable {
    let countInWindow: Int
    let maxInWindow: Int
    let windowRemainingSec: Int
}

struct SignalHealthResponse: Codable {
    let status: String
    let uptimeSec: Int?
    let roomsActive: Int?
    let clientsConnected: Int?
    let trackedPairs: Int?
    let packetsRelayedByType: [String: Int]?
    let bytesRelayed: Int?
}

struct SignalDiagnosticsResponse: Codable {
    struct PairInfo: Codable {
        let id: String
        let status: String
        let hasDeviceA: Bool
        let hasDeviceB: Bool
    }

    struct RoomInfo: Codable {
        let connectedClients: Int
    }

    struct TransferInfo: Codable {
        let byType: [String: Int]
        let bytesRelayed: Int
        let lastRelayAt: Int?
    }

    struct ServerInfo: Codable {
        let uptimeSec: Int
        let roomsActive: Int
        let clientsConnected: Int
        let packetsRelayedByType: [String: Int]
        let bytesRelayed: Int
    }

    let authenticated: Bool
    let pair: PairInfo
    let room: RoomInfo
    let transfer: TransferInfo
    let server: ServerInfo
}

struct SignalAccountUsageResponse: Codable {
    struct UsageInfo: Codable {
        let packetsRelayed: Int
        let relayedByType: [String: Int]
        let bytesRelayed: Int
        let iceIssued: Int
        let connectionsStarted: Int
        let connectionMs: Int
        let lastSeenAt: Int?
    }

    struct PairTransferInfo: Codable {
        let byType: [String: Int]
        let bytesRelayed: Int
        let lastRelayAt: Int?
    }

    struct CostEstimate: Codable {
        let relayGb: Double
        let connectionMinutes: Double
        let relayCostUsd: Double
        let iceCostUsd: Double
        let connectionCostUsd: Double
        let totalUsd: Double
        let rates: [String: Double]
        let note: String
    }

    let authenticated: Bool
    let userId: String
    let pairId: String
    let usage: UsageInfo
    let pairTransfer: PairTransferInfo
    let estimatedCostUsd: CostEstimate
}

@MainActor
class APIService: ObservableObject {
    private let authManager: AuthManager
    private var apiBaseURL: URL {
        // This should match the NEXT_PUBLIC_SITE_URL in your website's .env
        return URL(string: "https://orionlive.ai/api")!
    }

    init(authManager: AuthManager) {
        self.authManager = authManager
    }

    func fetchWebRTCToken(deviceId: String) async throws -> String {
        guard let session = authManager.session else {
            print("APIService Error: No active session found. User must be authenticated.")
            throw URLError(.userAuthenticationRequired)
        }

        let url = apiBaseURL.appendingPathComponent("auth/webrtc-token")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")

        let body = ["deviceId": deviceId]
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            let errorBody = String(data: data, encoding: .utf8) ?? "No error body"
            print("Failed to fetch WebRTC token. Status: \((response as? HTTPURLResponse)?.statusCode ?? 0). Body: \(errorBody)")
            throw URLError(.badServerResponse)
        }

        let decodedResponse = try JSONDecoder().decode(WebRTCTokenResponse.self, from: data)
        return decodedResponse.token
    }

    func fetchEphemeralICE(token: String) async throws -> ICECredentials {
        let url = URL(string: "https://signal.orionlive.ai/v1/ice")!
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            let errorBody = String(data: data, encoding: .utf8) ?? "No error body"
            print("Failed to fetch ICE creds. Status: \((response as? HTTPURLResponse)?.statusCode ?? 0). Body: \(errorBody)")
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(ICECredentials.self, from: data)
    }

    func fetchSignalDiagnostics(token: String) async throws -> SignalDiagnosticsResponse {
        let url = URL(string: "https://signal.orionlive.ai/v1/diag")!
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            let errorBody = String(data: data, encoding: .utf8) ?? "No error body"
            print("Failed to fetch signal diagnostics. Status: \((response as? HTTPURLResponse)?.statusCode ?? 0). Body: \(errorBody)")
            throw URLError(.badServerResponse)
        }

        return try JSONDecoder().decode(SignalDiagnosticsResponse.self, from: data)
    }

    func fetchSignalHealth() async throws -> SignalHealthResponse {
        let url = URL(string: "https://signal.orionlive.ai/health")!
        let (data, response) = try await URLSession.shared.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            let errorBody = String(data: data, encoding: .utf8) ?? "No error body"
            print("Failed to fetch signal health. Status: \((response as? HTTPURLResponse)?.statusCode ?? 0). Body: \(errorBody)")
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(SignalHealthResponse.self, from: data)
    }

    func fetchSignalAccountUsage(token: String) async throws -> SignalAccountUsageResponse {
        let url = URL(string: "https://signal.orionlive.ai/v1/account-usage")!
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            let errorBody = String(data: data, encoding: .utf8) ?? "No error body"
            print("Failed to fetch signal account usage. Status: \((response as? HTTPURLResponse)?.statusCode ?? 0). Body: \(errorBody)")
            throw URLError(.badServerResponse)
        }

        return try JSONDecoder().decode(SignalAccountUsageResponse.self, from: data)
    }
}
