//
//  GeminiService.swift
//  Orion Live
//
//  Created by Copilot on 9/19/25.
//  Client for Google Gemini 2.5 Flash Lite text generation with streaming and simple metrics.
//

import Foundation

struct GeminiMetrics {
    var ttft: TimeInterval? // time-to-first-token
    var totalTokens: Int
    var duration: TimeInterval? // overall stream duration

    var tokensPerSecond: Double? {
        guard let d = duration, d > 0 else { return nil }
        return Double(totalTokens) / d
    }
}

final class GeminiService {
    static let shared = GeminiService()

    // Model and endpoint constants
    // Default model per request; change if Google updates naming
    private let model = "gemini-2.5-flash-lite"
    private let endpoint = URL(string: "https://generativelanguage.googleapis.com/v1beta/models")!

    enum GeminiError: Error, LocalizedError {
        case missingAPIKey
        case badURL
        case network(Error)
        case http(Int)
        case decoding
        case streamClosed

        var errorDescription: String? {
            switch self {
            case .missingAPIKey: return "Gemini API key not set"
            case .badURL: return "Failed to build request URL"
            case .network(let err): return err.localizedDescription
            case .http(let code): return "HTTP error: \(code)"
            case .decoding: return "Response decode error"
            case .streamClosed: return "Stream closed"
            }
        }
    }

    // Simple request model for text-only chat
    private struct GenerateContentRequest: Encodable {
        let contents: [Content]
        let generationConfig: GenerationConfig?
        let safetySettings: [SafetySetting]?
        let tools: [String]? // placeholder for future

        struct Content: Encodable {
            let role: String
            let parts: [Part]
        }
        struct Part: Encodable {
            let text: String
        }
        struct GenerationConfig: Encodable {
            let temperature: Double?
            let maxOutputTokens: Int?
        }
        struct SafetySetting: Encodable {
            let category: String
            let threshold: String
        }
    }

    // Minimal response structures for streamed deltas
    private struct StreamChunk: Decodable {
        let candidates: [Candidate]?
        struct Candidate: Decodable {
            let content: Content
        }
        struct Content: Decodable {
            let parts: [Part]
        }
        struct Part: Decodable { let text: String? }
    }

    // Streaming chat
    func streamChat(
        messages: [(role: String, text: String)],
        temperature: Double = 0.7,
        maxOutputTokens: Int = 1024,
        onFirstToken: @escaping (GeminiMetrics) -> Void,
        onDelta: @escaping (String, GeminiMetrics) -> Void,
        onComplete: @escaping (String, GeminiMetrics) -> Void,
        onError: @escaping (Error) -> Void
    ) {
        guard let apiKey = GeminiKeyManager.shared.readKey(), !apiKey.isEmpty else {
            onError(GeminiError.missingAPIKey)
            return
        }

        var url = endpoint
        url.append(path: "\(model):streamGenerateContent")

        var comps = URLComponents(url: url, resolvingAgainstBaseURL: false)
        comps?.queryItems = [
            URLQueryItem(name: "key", value: apiKey),
            URLQueryItem(name: "alt", value: "sse") // request Server-Sent Events if supported
        ]
        guard let finalURL = comps?.url else {
            onError(GeminiError.badURL)
            return
        }

        var req = URLRequest(url: finalURL)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("application/json", forHTTPHeaderField: "Accept")

        let payload = GenerateContentRequest(
            contents: messages.map { .init(role: $0.role, parts: [.init(text: $0.text)]) },
            generationConfig: .init(temperature: temperature, maxOutputTokens: maxOutputTokens),
            safetySettings: nil,
            tools: nil
        )

        do {
            req.httpBody = try JSONEncoder().encode(payload)
        } catch {
            onError(error)
            return
        }

        let start = CFAbsoluteTimeGetCurrent()
        var firstTokenTime: TimeInterval?
        var fullText = ""
        var metrics = GeminiMetrics(ttft: nil, totalTokens: 0, duration: nil)

        // Use async bytes streaming if available to process SSE "data:" lines.
        Task {
            do {
                let (bytes, response) = try await URLSession.shared.bytes(for: req)
                guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                    throw GeminiError.http((response as? HTTPURLResponse)?.statusCode ?? -1)
                }

                var iterator = bytes.lines.makeAsyncIterator()
                while let line = try await iterator.next() {
                    // SSE format: lines starting with "data: {json}"
                    guard line.hasPrefix("data:") else { continue }
                    let payload = line.dropFirst(5).trimmingCharacters(in: .whitespaces)
                    guard !payload.isEmpty, let data = payload.data(using: .utf8) else { continue }
                    if let chunk = try? JSONDecoder().decode(StreamChunk.self, from: data),
                       let delta = chunk.candidates?.first?.content.parts.compactMap({ $0.text }).joined(),
                       !delta.isEmpty {
                        if firstTokenTime == nil {
                            firstTokenTime = CFAbsoluteTimeGetCurrent() - start
                            metrics.ttft = firstTokenTime
                            DispatchQueue.main.async { onFirstToken(metrics) }
                        }
                        fullText.append(delta)
                        metrics.totalTokens = fullText.split(whereSeparator: { $0.isWhitespace || $0.isNewline }).count
                        if firstTokenTime != nil {
                            metrics.duration = CFAbsoluteTimeGetCurrent() - start
                            // tokensPerSecond computed property
                        }
                        let current = fullText
                        DispatchQueue.main.async { onDelta(current, metrics) }
                    }
                }

                metrics.duration = CFAbsoluteTimeGetCurrent() - start
                let finalText = fullText
                DispatchQueue.main.async { onComplete(finalText, metrics) }
            } catch {
                DispatchQueue.main.async { onError(error) }
            }
        }
    }
}
