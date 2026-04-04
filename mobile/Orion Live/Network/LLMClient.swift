//
//  LLMClient.swift
//  Orion Live
//
//  A provider-agnostic lightweight client for streaming text generation.
//  Currently implements Google Gemini streaming; structure allows adding OpenAI later.
//

import Foundation

enum LLMProvider: String {
    case google
    case openai
    case proxy
    case local
}

struct LLMConfig {
    var provider: LLMProvider
    var model: String
    var temperature: Double
    var maxOutputTokens: Int

    static func fromInfoPlist() -> LLMConfig {
        let info = Bundle.main.infoDictionary ?? [:]
        let providerStr = (info["AI_PROVIDER"] as? String)?.lowercased() ?? "google"
        let provider = LLMProvider(rawValue: providerStr) ?? .google
        let defaultModel = provider == .google ? "gemini-2.5-flash-lite" : "gpt-4.1-mini"
        let model = (info["AI_MODEL"] as? String) ?? defaultModel
        return LLMConfig(provider: provider, model: model, temperature: 0.5, maxOutputTokens: 1024)
    }
}

struct LLMetrics {
    var ttft: TimeInterval?
    var totalTokens: Int
    var duration: TimeInterval?
    var tokensPerSecond: Double? { guard let d = duration, d > 0 else { return nil }; return Double(totalTokens) / d }
}

final class LLMClient {
    static let shared = LLMClient()
    private init() {}

    // MARK: - Public API
    func streamChat(
        messages: [(role: String, text: String)],
        config: LLMConfig = .fromInfoPlist(),
        providerOverride: LLMProvider? = nil,
        modelOverride: String? = nil,
        proxyURLOverride: URL? = nil,
        localURLOverride: URL? = nil,
        onFirstToken: @escaping (LLMetrics) -> Void,
        onDelta: @escaping (String, LLMetrics) -> Void,
        onComplete: @escaping (String, LLMetrics) -> Void,
        onError: @escaping (Error) -> Void
    ) {
        let provider = providerOverride ?? config.provider
        let model = modelOverride ?? config.model
        switch provider {
        case .google:
            streamGoogle(messages: messages, model: model, temperature: config.temperature, maxOutputTokens: config.maxOutputTokens, onFirstToken: onFirstToken, onDelta: onDelta, onComplete: onComplete, onError: onError)
        case .openai:
            onError(NSError(domain: "LLMClient", code: -2, userInfo: [NSLocalizedDescriptionKey: "OpenAI provider not implemented yet"]))
        case .proxy:
            streamProxy(messages: messages, overrideURL: proxyURLOverride, onFirstToken: onFirstToken, onDelta: onDelta, onComplete: onComplete, onError: onError)
        case .local:
            streamLocal(messages: messages, overrideURL: localURLOverride, onFirstToken: onFirstToken, onDelta: onDelta, onComplete: onComplete, onError: onError)
        }
    }

    // MARK: - Key loading
    // MARK: - Proxy implementation (normalized SSE)
    private func streamProxy(
        messages: [(role: String, text: String)],
        overrideURL: URL? = nil,
        onFirstToken: @escaping (LLMetrics) -> Void,
        onDelta: @escaping (String, LLMetrics) -> Void,
        onComplete: @escaping (String, LLMetrics) -> Void,
        onError: @escaping (Error) -> Void
    ) {
        let info = Bundle.main.infoDictionary ?? [:]
        let url: URL? = overrideURL ?? (info["AI_PROXY_URL"] as? String).flatMap(URL.init(string:))
        guard let url = url else {
            onError(NSError(domain: "LLMClient", code: -10, userInfo: [NSLocalizedDescriptionKey: "Missing AI_PROXY_URL (and no override)"]))
            return
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        struct Body: Encodable { let messages: [Message]; struct Message: Encodable { let role: String; let content: String } }
        let body = Body(messages: messages.map { .init(role: $0.role, content: $0.text) })
        do { req.httpBody = try JSONEncoder().encode(body) } catch { onError(error); return }

        let start = CFAbsoluteTimeGetCurrent()
        var firstTokenTime: TimeInterval?
        var fullText = ""
        var metrics = LLMetrics(ttft: nil, totalTokens: 0, duration: nil)

        struct ProxyDelta: Decodable { let delta: String?; let done: Bool? }

        Task {
            do {
                let (bytes, response) = try await URLSession.shared.bytes(for: req)
                guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                    throw NSError(domain: "LLMClient", code: (response as? HTTPURLResponse)?.statusCode ?? -11, userInfo: [NSLocalizedDescriptionKey: "HTTP error from proxy"])
                }
                var iterator = bytes.lines.makeAsyncIterator()
                while let line = try await iterator.next() {
                    guard line.hasPrefix("data:") else { continue }
                    let payload = line.dropFirst(5).trimmingCharacters(in: .whitespaces)
                    guard !payload.isEmpty, let data = payload.data(using: .utf8) else { continue }
                    if let evt = try? JSONDecoder().decode(ProxyDelta.self, from: data) {
                        if evt.done == true { break }
                        if let delta = evt.delta, !delta.isEmpty {
                            if firstTokenTime == nil {
                                firstTokenTime = CFAbsoluteTimeGetCurrent() - start
                                metrics.ttft = firstTokenTime
                                DispatchQueue.main.async { onFirstToken(metrics) }
                            }
                            fullText.append(delta)
                            metrics.totalTokens = fullText.split(whereSeparator: { $0.isWhitespace || $0.isNewline }).count
                            if firstTokenTime != nil { metrics.duration = CFAbsoluteTimeGetCurrent() - start }
                            let current = fullText
                            DispatchQueue.main.async { onDelta(current, metrics) }
                        }
                    }
                }
                metrics.duration = CFAbsoluteTimeGetCurrent() - start
                let final = fullText
                DispatchQueue.main.async { onComplete(final, metrics) }
            } catch {
                DispatchQueue.main.async { onError(error) }
            }
        }
    }

    private func streamLocal(
        messages: [(role: String, text: String)],
        overrideURL: URL? = nil,
        onFirstToken: @escaping (LLMetrics) -> Void,
        onDelta: @escaping (String, LLMetrics) -> Void,
        onComplete: @escaping (String, LLMetrics) -> Void,
        onError: @escaping (Error) -> Void
    ) {
        let info = Bundle.main.infoDictionary ?? [:]
        let url: URL? = overrideURL ?? (info["AI_LOCAL_URL"] as? String).flatMap(URL.init(string:))
        guard let url = url else {
            onError(NSError(domain: "LLMClient", code: -20, userInfo: [NSLocalizedDescriptionKey: "Missing AI_LOCAL_URL (and no override)"]))
            return
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        struct Body: Encodable { let messages: [Message]; struct Message: Encodable { let role: String; let content: String } }
        let body = Body(messages: messages.map { .init(role: $0.role, content: $0.text) })
        do { req.httpBody = try JSONEncoder().encode(body) } catch { onError(error); return }

        let start = CFAbsoluteTimeGetCurrent()
        var firstTokenTime: TimeInterval?
        var fullText = ""
        var metrics = LLMetrics(ttft: nil, totalTokens: 0, duration: nil)

        struct ProxyDelta: Decodable { let delta: String?; let done: Bool? }

        Task {
            do {
                let (bytes, response) = try await URLSession.shared.bytes(for: req)
                guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                    throw NSError(domain: "LLMClient", code: (response as? HTTPURLResponse)?.statusCode ?? -21, userInfo: [NSLocalizedDescriptionKey: "HTTP error from local server"])
                }
                var iterator = bytes.lines.makeAsyncIterator()
                while let line = try await iterator.next() {
                    guard line.hasPrefix("data:") else { continue }
                    let payload = line.dropFirst(5).trimmingCharacters(in: .whitespaces)
                    guard !payload.isEmpty, let data = payload.data(using: .utf8) else { continue }
                    if let evt = try? JSONDecoder().decode(ProxyDelta.self, from: data) {
                        if evt.done == true { break }
                        if let delta = evt.delta, !delta.isEmpty {
                            if firstTokenTime == nil {
                                firstTokenTime = CFAbsoluteTimeGetCurrent() - start
                                metrics.ttft = firstTokenTime
                                DispatchQueue.main.async { onFirstToken(metrics) }
                            }
                            fullText.append(delta)
                            metrics.totalTokens = fullText.split(whereSeparator: { $0.isWhitespace || $0.isNewline }).count
                            if firstTokenTime != nil { metrics.duration = CFAbsoluteTimeGetCurrent() - start }
                            let current = fullText
                            DispatchQueue.main.async { onDelta(current, metrics) }
                        }
                    }
                }
                metrics.duration = CFAbsoluteTimeGetCurrent() - start
                let final = fullText
                DispatchQueue.main.async { onComplete(final, metrics) }
            } catch {
                DispatchQueue.main.async { onError(error) }
            }
        }
    }
    private func apiKey(for provider: LLMProvider) -> String? {
        let info = Bundle.main.infoDictionary
        // Generic key first, then provider-specific fallbacks
        let generic = info?["AI_API_KEY"] as? String
        if let generic, !generic.isEmpty { return generic }
        switch provider {
        case .google:
            return info?["GOOGLE_API_KEY"] as? String
        case .openai:
            return info?["OPENAI_API_KEY"] as? String
        case .proxy:
            return nil
        case .local:
            return nil
        }
    }

    // MARK: - Google (Gemini) implementation
    private struct GenerateContentRequest: Encodable {
        let contents: [Content]
        let generationConfig: GenerationConfig?
        let safetySettings: [SafetySetting]?

        struct Content: Encodable { let role: String; let parts: [Part] }
        struct Part: Encodable { let text: String }
        struct GenerationConfig: Encodable { let temperature: Double?; let maxOutputTokens: Int? }
        struct SafetySetting: Encodable { let category: String; let threshold: String }
    }

    private struct StreamChunk: Decodable {
        let candidates: [Candidate]?
        struct Candidate: Decodable { let content: Content }
        struct Content: Decodable { let parts: [Part] }
        struct Part: Decodable { let text: String? }
    }

    private func streamGoogle(
        messages: [(role: String, text: String)],
        model: String,
        temperature: Double,
        maxOutputTokens: Int,
        onFirstToken: @escaping (LLMetrics) -> Void,
        onDelta: @escaping (String, LLMetrics) -> Void,
        onComplete: @escaping (String, LLMetrics) -> Void,
        onError: @escaping (Error) -> Void
    ) {
        guard let key = apiKey(for: .google), !key.isEmpty else {
            onError(NSError(domain: "LLMClient", code: -1, userInfo: [NSLocalizedDescriptionKey: "Missing AI_API_KEY in Info.plist (or GOOGLE_API_KEY) "]))
            return
        }
        guard var url = URL(string: "https://generativelanguage.googleapis.com/v1beta/models") else {
            onError(NSError(domain: "LLMClient", code: -3, userInfo: [NSLocalizedDescriptionKey: "Bad URL"]))
            return
        }
        url.append(path: "\(model):streamGenerateContent")
        var comps = URLComponents(url: url, resolvingAgainstBaseURL: false)
        comps?.queryItems = [
            URLQueryItem(name: "key", value: key),
            URLQueryItem(name: "alt", value: "sse")
        ]
        guard let finalURL = comps?.url else {
            onError(NSError(domain: "LLMClient", code: -4, userInfo: [NSLocalizedDescriptionKey: "Bad URL components"]))
            return
        }

        var req = URLRequest(url: finalURL)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("application/json", forHTTPHeaderField: "Accept")

        let payload = GenerateContentRequest(
            contents: messages.map { .init(role: $0.role, parts: [.init(text: $0.text)]) },
            generationConfig: .init(temperature: temperature, maxOutputTokens: maxOutputTokens),
            safetySettings: nil
        )

        do { req.httpBody = try JSONEncoder().encode(payload) } catch { onError(error); return }

        let start = CFAbsoluteTimeGetCurrent()
        var firstTokenTime: TimeInterval?
        var fullText = ""
        var metrics = LLMetrics(ttft: nil, totalTokens: 0, duration: nil)

        Task {
            do {
                let (bytes, response) = try await URLSession.shared.bytes(for: req)
                guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                    throw NSError(domain: "LLMClient", code: (response as? HTTPURLResponse)?.statusCode ?? -5, userInfo: [NSLocalizedDescriptionKey: "HTTP error"])
                }

                var iterator = bytes.lines.makeAsyncIterator()
                while let line = try await iterator.next() {
                    guard line.hasPrefix("data:") else { continue }
                    let payload = line.dropFirst(5).trimmingCharacters(in: .whitespaces)
                    guard !payload.isEmpty, let data = payload.data(using: .utf8) else { continue }
                    if let chunk = try? JSONDecoder().decode(StreamChunk.self, from: data),
                       let delta = chunk.candidates?.first?.content.parts.compactMap({ $0.text }).joined(), !delta.isEmpty {
                        if firstTokenTime == nil {
                            firstTokenTime = CFAbsoluteTimeGetCurrent() - start
                            metrics.ttft = firstTokenTime
                            DispatchQueue.main.async { onFirstToken(metrics) }
                        }
                        fullText.append(delta)
                        metrics.totalTokens = fullText.split(whereSeparator: { $0.isWhitespace || $0.isNewline }).count
                        if firstTokenTime != nil {
                            metrics.duration = CFAbsoluteTimeGetCurrent() - start
                        }
                        let current = fullText
                        DispatchQueue.main.async { onDelta(current, metrics) }
                    }
                }

                metrics.duration = CFAbsoluteTimeGetCurrent() - start
                let final = fullText
                DispatchQueue.main.async { onComplete(final, metrics) }
            } catch {
                DispatchQueue.main.async { onError(error) }
            }
        }
    }
}
