
//
//  APIService.swift
//  Orion
//
//  Created by Riddhiman Rana on 8/14/25.
//  Handles communication with the Orion web API.
//

import Foundation
import Supabase
import Combine // Import Combine for ObservableObject

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

class APIService: ObservableObject {
    
    private let supabase: SupabaseClient
    private var apiBaseURL: URL {
        // This should match the NEXT_PUBLIC_SITE_URL in your website's .env
        return URL(string: "https://orionlive.ai/api")!
    }
    
    init(supabase: SupabaseClient) {
        self.supabase = supabase
    }
    
    func fetchWebRTCToken(deviceId: String) async throws -> String {
        guard let session = try? await supabase.auth.session else {
            throw URLError(.userAuthenticationRequired)
        }
        
        let url = apiBaseURL.appendingPathComponent("/auth/webrtc-token")
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
        // Prefer same host as signaling gateway (HTTPS) for CORS and trust
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
}
