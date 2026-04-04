//
//  P2PMessage.swift
//  Orion Live
//
//  Defines a versioned, provider-agnostic message contract for WebRTC data channels
//  and other P2P transports. Includes a simple JSON codec.
//

import Foundation

public let P2P_MESSAGE_VERSION: Int = 1

public enum P2PMessageType: String, Codable {
    case ping
    case pong
    case request
    case chunk
    case done
    case error
}

public struct LLMUsage: Codable, Equatable {
    public var promptTokens: Int?
    public var completionTokens: Int?
    public var totalTokens: Int? { (promptTokens ?? 0) + (completionTokens ?? 0) }
    public init(promptTokens: Int? = nil, completionTokens: Int? = nil) {
        self.promptTokens = promptTokens
        self.completionTokens = completionTokens
    }
}

public struct PingPayload: Codable, Equatable {
    public var clientTs: Int64
    public var nonce: String?
    public init(clientTs: Int64 = Date().toMillis(), nonce: String? = nil) {
        self.clientTs = clientTs
        self.nonce = nonce
    }
}

public struct PongPayload: Codable, Equatable {
    public var clientTs: Int64
    public var serverTs: Int64
    public init(clientTs: Int64, serverTs: Int64 = Date().toMillis()) {
        self.clientTs = clientTs
        self.serverTs = serverTs
    }
}

public struct RequestPayload: Codable, Equatable {
    public var route: String
    public var model: String?
    public var input: String
    public var params: [String: JSONValue]?
    public init(route: String, model: String? = nil, input: String, params: [String: JSONValue]? = nil) {
        self.route = route
        self.model = model
        self.input = input
        self.params = params
    }
}

public struct ChunkPayload: Codable, Equatable {
    public var index: Int
    public var text: String
    public var tokens: Int?
    public init(index: Int, text: String, tokens: Int? = nil) {
        self.index = index
        self.text = text
        self.tokens = tokens
    }
}

public struct DonePayload: Codable, Equatable {
    public var finishReason: String?
    public var usage: LLMUsage?
    public init(finishReason: String? = nil, usage: LLMUsage? = nil) {
        self.finishReason = finishReason
        self.usage = usage
    }
}

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

public struct P2PMessage: Codable, Equatable {
    public var v: Int
    public var type: P2PMessageType
    public var id: String
    public var ts: Int64
    public var correlationId: String?
    public var size: Int?
    public var data: Payload

    public init(type: P2PMessageType, id: String = UUID().uuidString, ts: Int64 = Date().toMillis(), correlationId: String? = nil, size: Int? = nil, data: Payload) {
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
        case .ping: self.data = .ping(try container.decode(PingPayload.self, forKey: .data))
        case .pong: self.data = .pong(try container.decode(PongPayload.self, forKey: .data))
        case .request: self.data = .request(try container.decode(RequestPayload.self, forKey: .data))
        case .chunk: self.data = .chunk(try container.decode(ChunkPayload.self, forKey: .data))
        case .done: self.data = .done(try container.decode(DonePayload.self, forKey: .data))
        case .error: self.data = .error(try container.decode(ErrorPayload.self, forKey: .data))
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
        case .ping(let p): try container.encode(p, forKey: .data)
        case .pong(let p): try container.encode(p, forKey: .data)
        case .request(let p): try container.encode(p, forKey: .data)
        case .chunk(let p): try container.encode(p, forKey: .data)
        case .done(let p): try container.encode(p, forKey: .data)
        case .error(let p): try container.encode(p, forKey: .data)
        }
    }
}

public enum P2PMessageCodec {
    private static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.outputFormatting = [.withoutEscapingSlashes]
        return e
    }()
    private static let decoder = JSONDecoder()

    public static func encode(_ message: P2PMessage) throws -> Data {
        var msg = message
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

public enum JSONValue: Codable, Equatable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() { self = .null }
        else if let b = try? container.decode(Bool.self) { self = .bool(b) }
        else if let n = try? container.decode(Double.self) { self = .number(n) }
        else if let s = try? container.decode(String.self) { self = .string(s) }
        else if let arr = try? container.decode([JSONValue].self) { self = .array(arr) }
        else if let obj = try? container.decode([String: JSONValue].self) { self = .object(obj) }
        else { throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported JSON value") }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .null: try container.encodeNil()
        case .bool(let b): try container.encode(b)
        case .number(let n): try container.encode(n)
        case .string(let s): try container.encode(s)
        case .array(let arr): try container.encode(arr)
        case .object(let obj): try container.encode(obj)
        }
    }
}

public extension Date { func toMillis() -> Int64 { Int64((timeIntervalSince1970 * 1000.0).rounded()) } }
public extension Data { var utf8String: String { String(data: self, encoding: .utf8) ?? "" } }
