
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
}
