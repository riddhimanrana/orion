//
//  P2PMessage.swift
//  Orion Live
//
//  Defines a versioned, provider-agnostic message contract for WebRTC data channels
//  and other P2P transports. Includes a simple JSON codec.
//

import Foundation

/// Version of the P2P message envelope/schema. Increment on breaking changes.
public let P2P_MESSAGE_VERSION: Int = 1

/// Discriminator for message kinds carried over the P2P data channel.
public enum P2PMessageType: String, Codable {
    case ping
    case pong
    case request      // Generic request (e.g., LLM generate)
    case chunk        // Streamed partial response chunk
    case done         // Stream completion with usage/summary
    case error        // Error response for a prior request or transport error
}

/// Common usage metrics for streaming LLM completions.
public struct LLMUsage: Codable, Equatable {
    public var promptTokens: Int?
    public var completionTokens: Int?
    public var totalTokens: Int? {
        if let p = promptTokens, let c = completionTokens { return p + c }
        return nil
    }

    public init(promptTokens: Int? = nil, completionTokens: Int? = nil) {
        self.promptTokens = promptTokens
        self.completionTokens = completionTokens
    }
}

/// Ping payload. RTT is measured by correlating Ping.id with Pong.correlationId.
public struct PingPayload: Codable, Equatable {
    /// Client-sent timestamp (ms since epoch) for RTT calculations.
    public var clientTs: Int64
    /// Optional arbitrary marker to help spot duplicates
    public var nonce: String?

    public init(clientTs: Int64 = Date().toMillis(), nonce: String? = nil) {
        self.clientTs = clientTs
        self.nonce = nonce
    }
}

/// Pong payload. Echoes back the client's timestamp and includes server timestamp.
public struct PongPayload: Codable, Equatable {
    public var clientTs: Int64
    public var serverTs: Int64

    public init(clientTs: Int64, serverTs: Int64 = Date().toMillis()) {
        self.clientTs = clientTs
        self.serverTs = serverTs
    }
}

/// Generic request payload for streaming operations (e.g., LLM generation).
/// Keep this minimal and extensible; vendor-specific details should go in `params`.
public struct RequestPayload: Codable, Equatable {
    /// Logical route for the request (e.g., "llm.generate")
    public var route: String
    /// Optional model identifier (e.g., "gpt-4o-mini", "gemini-1.5-flash")
    public var model: String?
    /// Input text or serialized instruction. For chats, use your own schema in `params`.
    public var input: String
    /// Free-form parameters for provider-specific or feature-specific knobs.
    public var params: [String: JSONValue]?

    public init(route: String, model: String? = nil, input: String, params: [String: JSONValue]? = nil) {
        self.route = route
        self.model = model
        self.input = input
        self.params = params
    }
}

/// Streamed partial response chunk.
public struct ChunkPayload: Codable, Equatable {
    /// 0-based index of the chunk for ordering.
    public var index: Int
    /// Text content of the chunk (could be a delta token string).
    public var text: String
    /// Optional token count in this chunk.
    public var tokens: Int?

    public init(index: Int, text: String, tokens: Int? = nil) {
        self.index = index
        self.text = text
        self.tokens = tokens
    }
}

/// Completion summary for a streamed operation.
public struct DonePayload: Codable, Equatable {
    public var finishReason: String?
    public var usage: LLMUsage?

    public init(finishReason: String? = nil, usage: LLMUsage? = nil) {
        self.finishReason = finishReason
        self.usage = usage
    }
}

/// Error payload for a failed request.
public struct ErrorPayload: Codable, Equatable {
    public var code: String
    public var message: String
    public var retryable: Bool?

    public init(code: String, message: String, retryable: Bool? = nil) {
        self.code = code
        self.message = message
        self.retryable = retryable
    }
}

/// A versioned message envelope with type discriminator and typed payloads.
/// JSON shape (example for ping):
/// {
///   "v": 1,
///   "type": "ping",
///   "id": "2b7d4b7a-...",
///   "ts": 1737312345678,
///   "correlationId": null,
///   "size": 0,
///   "data": { "clientTs": 1737312345678, "nonce": "abc" }
/// }
public struct P2PMessage: Codable, Equatable {
    public var v: Int
    public var type: P2PMessageType
    /// Unique message id (UUID string recommended)
    public var id: String
    /// Message timestamp in milliseconds since epoch.
    public var ts: Int64
    /// For replies, correlates back to the triggering message id (e.g., pong -> ping).
    public var correlationId: String?
    /// Optional size hint for the payload (bytes). Useful for flow control.
    public var size: Int?
    /// Strongly typed payload determined by `type`.
    public var data: Payload

    public init(type: P2PMessageType,
                id: String = UUID().uuidString,
                ts: Int64 = Date().toMillis(),
                correlationId: String? = nil,
                size: Int? = nil,
                data: Payload) {
        self.v = P2P_MESSAGE_VERSION
        self.type = type
        self.id = id
        self.ts = ts
        self.correlationId = correlationId
        self.size = size
        self.data = data
    }

    public enum Payload: Equatable {
        case ping(PingPayload)
        case pong(PongPayload)
        case request(RequestPayload)
        case chunk(ChunkPayload)
        case done(DonePayload)
        case error(ErrorPayload)
    }

    private enum CodingKeys: String, CodingKey { case v, type, id, ts, correlationId, size, data }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.v = try container.decode(Int.self, forKey: .v)
        self.type = try container.decode(P2PMessageType.self, forKey: .type)
        self.id = try container.decode(String.self, forKey: .id)
        self.ts = try container.decode(Int64.self, forKey: .ts)
        self.correlationId = try container.decodeIfPresent(String.self, forKey: .correlationId)
        self.size = try container.decodeIfPresent(Int.self, forKey: .size)

        switch type {
        case .ping:
            let p = try container.decode(PingPayload.self, forKey: .data)
            self.data = .ping(p)
        case .pong:
            let p = try container.decode(PongPayload.self, forKey: .data)
            self.data = .pong(p)
        case .request:
            let p = try container.decode(RequestPayload.self, forKey: .data)
            self.data = .request(p)
        case .chunk:
            let p = try container.decode(ChunkPayload.self, forKey: .data)
            self.data = .chunk(p)
        case .done:
            let p = try container.decode(DonePayload.self, forKey: .data)
            self.data = .done(p)
        case .error:
            let p = try container.decode(ErrorPayload.self, forKey: .data)
            self.data = .error(p)
        }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(v, forKey: .v)
        try container.encode(type, forKey: .type)
        try container.encode(id, forKey: .id)
        try container.encode(ts, forKey: .ts)
        try container.encodeIfPresent(correlationId, forKey: .correlationId)
        try container.encodeIfPresent(size, forKey: .size)
        switch data {
        case .ping(let p):
            try container.encode(p, forKey: .data)
        case .pong(let p):
            try container.encode(p, forKey: .data)
        case .request(let p):
            try container.encode(p, forKey: .data)
        case .chunk(let p):
            try container.encode(p, forKey: .data)
        case .done(let p):
            try container.encode(p, forKey: .data)
        case .error(let p):
            try container.encode(p, forKey: .data)
        }
    }
}

// MARK: - Simple JSON Codec

public enum P2PMessageCodec {
    private static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.outputFormatting = [.withoutEscapingSlashes]
        return e
    }()
    private static let decoder = JSONDecoder()

    public static func encode(_ message: P2PMessage) throws -> Data {
        var msg = message
        // If size hint isn't provided, auto-fill for text payloads to help flow control.
        if msg.size == nil {
            if case let .chunk(p) = msg.data { msg.size = p.text.lengthOfBytes(using: .utf8) }
            if case let .request(p) = msg.data { msg.size = p.input.lengthOfBytes(using: .utf8) }
        }
        return try encoder.encode(msg)
    }

    public static func decode(_ data: Data) throws -> P2PMessage {
        return try decoder.decode(P2PMessage.self, from: data)
    }
}

// MARK: - Lightweight JSON value to support free-form params

public enum JSONValue: Codable, Equatable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let b = try? container.decode(Bool.self) {
            self = .bool(b)
        } else if let n = try? container.decode(Double.self) {
            self = .number(n)
        } else if let s = try? container.decode(String.self) {
            self = .string(s)
        } else if let arr = try? container.decode([JSONValue].self) {
            self = .array(arr)
        } else if let obj = try? container.decode([String: JSONValue].self) {
            self = .object(obj)
        } else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported JSON value")
        }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .null:
            try container.encodeNil()
        case .bool(let b):
            try container.encode(b)
        case .number(let n):
            try container.encode(n)
        case .string(let s):
            try container.encode(s)
        case .array(let arr):
            try container.encode(arr)
        case .object(let obj):
            try container.encode(obj)
        }
    }
}

// MARK: - Utilities

public extension Date {
    func toMillis() -> Int64 {
        return Int64((timeIntervalSince1970 * 1000.0).rounded())
    }
}

public extension Data {
    /// Best-effort transform of UTF-8 data to string for debug logs.
    var utf8String: String { String(data: self, encoding: .utf8) ?? "" }
}
