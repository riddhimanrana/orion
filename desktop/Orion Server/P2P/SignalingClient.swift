
//
//  SignalingClient.swift
//  Orion Server
//
//  Created by Gemini on 8/15/25.
//

import Foundation
import WebRTC

// MARK: - Delegate & Status Enum
protocol SignalingClientDelegate: AnyObject {
    func signalingClientDidConnect(_ client: SignalingClient)
    func signalingClientDidDisconnect(_ client: SignalingClient)
    func signalingClient(_ client: SignalingClient, didReceiveRemoteSdp sdp: RTCSessionDescription)
    func signalingClient(_ client: SignalingClient, didReceiveCandidate candidate: RTCIceCandidate)
    func signalingClient(_ client: SignalingClient, didReceiveProcessingMode mode: String)
    func signalingClient(_ client: SignalingClient, didEncounterError error: Error)
}

enum ConnectionStatus: String, CustomStringConvertible {
    case disconnected
    case connecting
    case connected

    var description: String {
        self.rawValue.capitalized
    }
}

// MARK: - Codable Message Structs
private struct SignalingMessage: Codable {
    let t: String // Type: "offer", "answer", "ice"
    let pairId: String
    let sdp: String?
    let ice: IceCandidatePayload?
}

private struct IceCandidatePayload: Codable {
    let candidate: String
    let sdpMLineIndex: Int32
    let sdpMid: String?
}

private struct ProcessingModeMessage: Codable {
    let t: String // "mode"
    let pairId: String
    let mode: String // "server" or "hybrid"
    
    enum CodingKeys: String, CodingKey {
        case t, mode
        case pairId = "pairId"
    }
}

// MARK: - Signaling Client
@MainActor
class SignalingClient: NSObject, URLSessionWebSocketDelegate, ObservableObject {
    @Published var connectionState: ConnectionStatus = .disconnected
    @Published private(set) var packetsSent: Int = 0
    @Published private(set) var packetsReceived: Int = 0
    @Published private(set) var packetBytesSent: Int = 0
    @Published private(set) var packetBytesReceived: Int = 0
    @Published private(set) var lastPacketTypeSent: String?
    @Published private(set) var lastPacketTypeReceived: String?
    @Published private(set) var lastSignalHealth: SignalHealthResponse?
    @Published private(set) var lastSignalDiagnostics: SignalDiagnosticsResponse?
    weak var delegate: SignalingClientDelegate?

    private var webSocket: URLSessionWebSocketTask?
    private let serverURL = URL(string: "wss://signal.orionlive.ai")!
    private let apiService: APIService
    private let deviceManager: DeviceManager
    private var pairId: String?
    private var currentToken: String?
    private var tokenExpiryDate: Date?
    private var isManualDisconnect = false
    private var reconnectAttempt = 0
    private var reconnectTask: Task<Void, Never>?
    private var heartbeatTask: Task<Void, Never>?
    private var tokenRefreshTask: Task<Void, Never>?
    private var diagnosticsTask: Task<Void, Never>?
    private let heartbeatIntervalNs: UInt64 = 25_000_000_000 // 25s
    private let maxReconnectDelaySeconds: UInt64 = 30
    private let tokenRefreshLeadTime: TimeInterval = 60
    private lazy var urlSession: URLSession = {
        // Use a dedicated URLSession so delegate callbacks fire properly
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 15
        config.timeoutIntervalForResource = 30
        return URLSession(configuration: config, delegate: self, delegateQueue: nil)
    }()

    init(apiService: APIService, deviceManager: DeviceManager) {
        self.apiService = apiService
        self.deviceManager = deviceManager
        super.init()
    }

    // Internal accessors for WebRTC setup
    func webrtcDeviceId() -> String? { deviceManager.deviceId }
    func webrtcAPI() -> APIService { apiService }

    func connect() {
        guard connectionState == .disconnected else {
            print("SignalingClient: Connection aborted. Already connected or deviceId is nil.")
            return
        }
        isManualDisconnect = false
        reconnectTask?.cancel()
        print("SignalingClient: Connecting...")
        self.connectionState = .connecting

        connectInternal(forceTokenRefresh: false)
    }

    private func connectInternal(forceTokenRefresh: Bool) {
        guard let deviceId = deviceManager.deviceId else {
            print("SignalingClient: Connection aborted. deviceId is nil.")
            self.connectionState = .disconnected
            return
        }

        Task {
            do {
                let token = try await getValidToken(deviceId: deviceId, forceRefresh: forceTokenRefresh)
                print("SignalingClient: Got token (len=\(token.count)). Decoding pairId…")
                self.pairId = try decodePairId(from: token)
                print("SignalingClient: pairId=\(self.pairId ?? "nil")")
                
                // Build URL safely with query items to avoid invalid URL crashes
                var comps = URLComponents(url: serverURL, resolvingAgainstBaseURL: false)
                comps?.queryItems = [URLQueryItem(name: "token", value: token)]
                guard let wsURL = comps?.url else {
                    throw NSError(domain: "SignalingClient", code: -1, userInfo: [NSLocalizedDescriptionKey: "Failed to construct signaling URL"])
                }

                let urlRequest = URLRequest(url: wsURL)

                webSocket = urlSession.webSocketTask(with: urlRequest)
                print("SignalingClient: Opening WebSocket to \(wsURL.absoluteString)…")
                webSocket?.resume()
                print("SignalingClient: WebSocket task resumed.")
                listenForMessages()
            } catch {
                print("SignalingClient: connect() error: \(error)")
                handleError(error)
            }
        }
    }

    private func getValidToken(deviceId: String, forceRefresh: Bool) async throws -> String {
        if !forceRefresh,
           let token = currentToken,
           let expiry = tokenExpiryDate,
           expiry.timeIntervalSinceNow > tokenRefreshLeadTime {
            return token
        }

        print("SignalingClient: Fetching WebRTC token…")
        let token = try await apiService.fetchWebRTCToken(deviceId: deviceId)
        currentToken = token
        tokenExpiryDate = extractExpiryDate(from: token)
        scheduleTokenRefreshIfNeeded()
        return token
    }

    func disconnect() {
        print("SignalingClient: Disconnecting.")
        isManualDisconnect = true
        reconnectTask?.cancel()
        reconnectTask = nil
        stopHeartbeat()
        tokenRefreshTask?.cancel()
        tokenRefreshTask = nil
        diagnosticsTask?.cancel()
        diagnosticsTask = nil
        webSocket?.cancel(with: .normalClosure, reason: nil)
        webSocket = nil
        self.connectionState = .disconnected
    }

    private func scheduleReconnect() {
        guard !isManualDisconnect else { return }
        guard reconnectTask == nil else { return }

        reconnectTask = Task { [weak self] in
            guard let self else { return }
            let exp = min(reconnectAttempt, 5)
            let delay = min(UInt64(pow(2.0, Double(exp))), maxReconnectDelaySeconds)
            try? await Task.sleep(nanoseconds: delay * 1_000_000_000)
            guard !Task.isCancelled else { return }

            reconnectAttempt += 1
            reconnectTask = nil
            connectionState = .disconnected
            connectInternal(forceTokenRefresh: true)
        }
    }

    private func startHeartbeat() {
        stopHeartbeat()
        heartbeatTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: heartbeatIntervalNs)
                guard !Task.isCancelled else { return }
                guard connectionState == .connected else { return }

                webSocket?.sendPing { [weak self] error in
                    if error != nil {
                        Task { @MainActor in
                            self?.webSocket?.cancel(with: .goingAway, reason: "heartbeat failed".data(using: .utf8))
                        }
                    }
                }
            }
        }
    }

    private func stopHeartbeat() {
        heartbeatTask?.cancel()
        heartbeatTask = nil
    }

    private func scheduleTokenRefreshIfNeeded() {
        tokenRefreshTask?.cancel()
        guard let expiry = tokenExpiryDate else { return }

        let refreshDelay = max(expiry.timeIntervalSinceNow - tokenRefreshLeadTime, 1)
        tokenRefreshTask = Task { [weak self] in
            guard let self else { return }
            try? await Task.sleep(nanoseconds: UInt64(refreshDelay * 1_000_000_000))
            guard !Task.isCancelled else { return }
            guard let deviceId = deviceManager.deviceId else { return }

            do {
                let refreshed = try await apiService.fetchWebRTCToken(deviceId: deviceId)
                currentToken = refreshed
                tokenExpiryDate = extractExpiryDate(from: refreshed)
                scheduleTokenRefreshIfNeeded()
            } catch {
                print("SignalingClient: Token refresh failed: \(error.localizedDescription)")
            }
        }
    }

    func sendSdp(_ sdp: RTCSessionDescription) {
        let sdpType = RTCSessionDescription.string(for: sdp.type)
        let message = SignalingMessage(t: sdpType, pairId: self.pairId ?? "", sdp: sdp.sdp, ice: nil)
        sendMessage(message)
    }

    func sendCandidate(_ candidate: RTCIceCandidate) {
        let icePayload = IceCandidatePayload(candidate: candidate.sdp, sdpMLineIndex: candidate.sdpMLineIndex, sdpMid: candidate.sdpMid)
        let message = SignalingMessage(t: "ice", pairId: self.pairId ?? "", sdp: nil, ice: icePayload)
        sendMessage(message)
    }

    private func sendMessage<T: Encodable>(_ message: T) {
        guard connectionState == .connected else { return }
        do {
            let data = try JSONEncoder().encode(message)
            packetsSent += 1
            packetBytesSent += data.count
            lastPacketTypeSent = packetType(from: data)
            webSocket?.send(.data(data)) { [weak self] error in
                if let error = error {
                    Task { @MainActor in
                        self?.handleError(error)
                    }
                }
            }
        } catch {
            Task { @MainActor in
                handleError(error)
            }
        }
    }

    private func listenForMessages() {
        webSocket?.receive { [weak self] result in
            Task { @MainActor in
                guard let self = self else { return }

                switch result {
                case .success(let message):
                    self.handleMessage(message)
                    self.listenForMessages()
                case .failure(let error):
                    self.handleError(error)
                }
            }
        }
    }

    private func handleMessage(_ message: URLSessionWebSocketTask.Message) {
        guard let data = message.data else { return }
        packetsReceived += 1
        packetBytesReceived += data.count

        // First try to decode as a standard SignalingMessage
        if let decodedMessage = try? JSONDecoder().decode(SignalingMessage.self, from: data) {
            guard decodedMessage.pairId == self.pairId else { return }
            lastPacketTypeReceived = decodedMessage.t

            switch decodedMessage.t {
            case "offer", "answer":
                guard let sdpString = decodedMessage.sdp else { return }
                let sdpType = RTCSessionDescription.type(for: decodedMessage.t)
                let sdp = RTCSessionDescription(type: sdpType, sdp: sdpString)
                self.delegate?.signalingClient(self, didReceiveRemoteSdp: sdp)

            case "ice":
                guard let ice = decodedMessage.ice else { return }
                let candidate = RTCIceCandidate(sdp: ice.candidate, sdpMLineIndex: ice.sdpMLineIndex, sdpMid: ice.sdpMid)
                self.delegate?.signalingClient(self, didReceiveCandidate: candidate)

            default:
                break
            }
        }
        // Try to decode as a ProcessingModeMessage
        else if let modeMessage = try? JSONDecoder().decode(ProcessingModeMessage.self, from: data) {
            guard modeMessage.pairId == self.pairId else { return }
            lastPacketTypeReceived = modeMessage.t
            
            if modeMessage.t == "mode" {
                self.delegate?.signalingClient(self, didReceiveProcessingMode: modeMessage.mode)
            }
        }
    }

    private func handleError(_ error: Error) {
        print("SignalingClient Error: \(error.localizedDescription)")
        self.connectionState = .disconnected
        stopHeartbeat()
        webSocket = nil
        delegate?.signalingClient(self, didEncounterError: error)
        scheduleReconnect()
    }

    private func decodePairId(from jwt: String) throws -> String {
        let components = jwt.split(separator: ".")
        guard components.count == 3 else { throw NSError(domain: "JWTError", code: 1, userInfo: [NSLocalizedDescriptionKey: "Invalid token structure"]) }

        var base64String = String(components[1])
        base64String = base64String.padding(toLength: ((base64String.count+3)/4)*4, withPad: "=", startingAt: 0)

        guard let payloadData = Data(base64Encoded: base64String) else {
            throw NSError(domain: "JWTError", code: 2, userInfo: [NSLocalizedDescriptionKey: "Invalid base64 in token payload"])
        }

        if let json = try? JSONSerialization.jsonObject(with: payloadData, options: []) as? [String: Any],
           let pairId = json["pairId"] as? String {
            return pairId
        }
        throw NSError(domain: "JWTError", code: 3, userInfo: [NSLocalizedDescriptionKey: "pairId not found in token"])
    }

    private func extractExpiryDate(from jwt: String) -> Date? {
        let components = jwt.split(separator: ".")
        guard components.count == 3 else { return nil }

        var base64String = String(components[1])
        base64String = base64String.padding(toLength: ((base64String.count+3)/4)*4, withPad: "=", startingAt: 0)
        guard let payloadData = Data(base64Encoded: base64String),
              let payload = (try? JSONSerialization.jsonObject(with: payloadData)) as? [String: Any],
              let exp = payload["exp"] as? Double else {
            return nil
        }
        return Date(timeIntervalSince1970: exp)
    }

    private func packetType(from data: Data) -> String? {
        guard let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return nil
        }
        return object["t"] as? String
    }

    private func runSignalDiagnostics(token: String) {
        diagnosticsTask?.cancel()
        diagnosticsTask = Task { [weak self] in
            guard let self else { return }
            do {
                async let healthTask = apiService.fetchSignalHealth()
                async let diagTask = apiService.fetchSignalDiagnostics(token: token)
                let (health, diagnostics) = try await (healthTask, diagTask)
                guard !Task.isCancelled else { return }
                self.lastSignalHealth = health
                self.lastSignalDiagnostics = diagnostics
            } catch {
                print("Signaling diagnostics check failed: \(error.localizedDescription)")
            }
        }
    }

    // MARK: - URLSessionWebSocketDelegate
    nonisolated func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        Task { @MainActor in
            print("SignalingClient: WebSocket connected.")
            self.connectionState = .connected
            self.reconnectAttempt = 0
            self.delegate?.signalingClientDidConnect(self)
            self.startHeartbeat()
            if let token = self.currentToken {
                self.runSignalDiagnostics(token: token)
            }
        }
    }

    nonisolated func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        Task { @MainActor in
            print("SignalingClient: WebSocket disconnected.")
            self.connectionState = .disconnected
            self.stopHeartbeat()
            self.webSocket = nil
            self.delegate?.signalingClientDidDisconnect(self)
            self.scheduleReconnect()
        }
    }
}

fileprivate extension URLSessionWebSocketTask.Message {
    var data: Data? {
        switch self {
        case .data(let data): return data
        case .string(let string): return string.data(using: .utf8)
        @unknown default: return nil
        }
    }
}
