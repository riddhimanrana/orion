
//
//  SignalingClient.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 8/14/25.
//  Manages the WebSocket connection to the signaling server for WebRTC.
//

import Foundation
import Combine

// MARK: - Delegate Protocol
protocol SignalingClientDelegate: AnyObject {
    func signalingClient(_ client: SignalingClient, didReceiveRemoteSdp sdp: String, type: String)
    func signalingClient(_ client: SignalingClient, didReceiveCandidate candidate: String, sdpMLineIndex: Int32, sdpMid: String?)
    func signalingClient(_ client: SignalingClient, didReceiveProcessingMode mode: String)
    func signalingClientDidConnect(_ client: SignalingClient)
    func signalingClientDidDisconnect(_ client: SignalingClient)
    func signalingClient(_ client: SignalingClient, didEncounterError error: Error)
}

@MainActor
class SignalingClient: NSObject, ObservableObject {

    // MARK: - Published Properties
    @Published var connectionState: ConnectionStatus = .disconnected

    // MARK: - Private Properties
    private var webSocket: URLSessionWebSocketTask?
    private let serverURL = URL(string: "wss://signal.orionlive.ai")!
    private var pairId: String? // Store the pairId for message validation
    private var currentToken: String?
    private var tokenExpiryDate: Date?
    private var isManualDisconnect = false
    private var reconnectAttempt = 0
    private var reconnectTask: Task<Void, Never>?
    private var heartbeatTask: Task<Void, Never>?
    private var tokenRefreshTask: Task<Void, Never>?

    private let heartbeatIntervalNs: UInt64 = 25_000_000_000 // 25s
    private let maxReconnectDelaySeconds: UInt64 = 30
    private let tokenRefreshLeadTime: TimeInterval = 60

    // MARK: - Dependencies
    private let apiService: APIService
    private let deviceManager: DeviceManager

    // MARK: - Delegate
    weak var delegate: SignalingClientDelegate?

    init(apiService: APIService, deviceManager: DeviceManager) {
        self.apiService = apiService
        self.deviceManager = deviceManager
        super.init()
    }

    // Internal accessors for WebRTC setup
    func webrtcDeviceId() -> String? { deviceManager.deviceId }
    func webrtcAPI() -> APIService { apiService }

    func connect() async {
        isManualDisconnect = false
        reconnectTask?.cancel()
        await connectInternal(forceTokenRefresh: false)
    }

    func disconnect() {
        isManualDisconnect = true
        reconnectTask?.cancel()
        reconnectTask = nil
        stopHeartbeat()
        tokenRefreshTask?.cancel()
        tokenRefreshTask = nil
        webSocket?.cancel(with: .normalClosure, reason: nil)
        webSocket = nil
        connectionState = .disconnected
    }

    private func connectInternal(forceTokenRefresh: Bool) async {
        guard connectionState == .disconnected else { return }

        self.connectionState = .connecting

        do {
            guard let deviceId = deviceManager.deviceId else {
                throw WSError.connectionFailed
            }

            let token = try await getValidToken(deviceId: deviceId, forceRefresh: forceTokenRefresh)
            self.currentToken = token
            self.pairId = try decodePairId(from: token)

            var urlRequest = URLRequest(url: serverURL.appending(queryItems: [URLQueryItem(name: "token", value: token)]))
            urlRequest.timeoutInterval = 10

            webSocket = URLSession.shared.webSocketTask(with: urlRequest)
            webSocket?.delegate = self
            webSocket?.resume()
            listenForMessages()
        } catch {
            await handleError(error)
        }
    }

    private func getValidToken(deviceId: String, forceRefresh: Bool) async throws -> String {
        if !forceRefresh,
           let token = currentToken,
           let expiry = tokenExpiryDate,
           expiry.timeIntervalSinceNow > tokenRefreshLeadTime {
            return token
        }

        let token = try await apiService.fetchWebRTCToken(deviceId: deviceId)
        self.tokenExpiryDate = extractExpiryDate(from: token)
        scheduleTokenRefreshIfNeeded()
        return token
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
            await connectInternal(forceTokenRefresh: true)
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
                currentToken = try await apiService.fetchWebRTCToken(deviceId: deviceId)
                tokenExpiryDate = extractExpiryDate(from: currentToken ?? "")
                scheduleTokenRefreshIfNeeded()
            } catch {
                // If refresh fails, reconnect path will fetch a fresh token.
            }
        }
    }

    // MARK: - Message Sending
    func sendSdp(sdp: String, type: String) {
        let message = SignalingMessage(t: type, pairId: self.pairId ?? "", sdp: sdp, ice: nil)
        sendMessage(message)
    }

    func sendCandidate(candidate: String, sdpMLineIndex: Int32, sdpMid: String?) {
        let icePayload = IceCandidatePayload(candidate: candidate, sdpMLineIndex: sdpMLineIndex, sdpMid: sdpMid)
        let message = SignalingMessage(t: "ice", pairId: self.pairId ?? "", sdp: nil, ice: icePayload)
        sendMessage(message)
    }

    func sendBye() {
        let message = SignalingMessage(t: "bye", pairId: self.pairId ?? "", sdp: nil, ice: nil)
        sendMessage(message)
    }
    
    func sendProcessingMode(_ mode: String) {
        let message = ProcessingModeMessage(t: "mode", pairId: self.pairId ?? "", mode: mode)
        sendMessage(message)
    }

    private func sendMessage<T: Encodable>(_ message: T) {
        guard connectionState == .connected else { return }
        do {
            let data = try JSONEncoder().encode(message)
            webSocket?.send(.data(data)) { [weak self] error in
                if let error = error {
                    Task { [weak self] in
                        await self?.handleError(error)
                    }
                }
            }
        } catch {
            Task { await handleError(error) }
        }
    }

    // MARK: - Message Handling
    private func listenForMessages() {
        webSocket?.receive { [weak self] result in
            Task {
                switch result {
                case .failure(let error):
                    await self?.handleError(error)
                case .success(let message):
                    await self?.handleMessage(message)
                    await self?.listenForMessages()
                }
            }
        }
    }

    private func handleMessage(_ message: URLSessionWebSocketTask.Message) async {
        guard let data = message.data else { return }

        // First try to decode as a standard SignalingMessage
        if let decodedMessage = try? JSONDecoder().decode(SignalingMessage.self, from: data) {
            guard decodedMessage.pairId == self.pairId else { return }

            switch decodedMessage.t {
            case "offer", "answer":
                if let sdp = decodedMessage.sdp {
                    delegate?.signalingClient(self, didReceiveRemoteSdp: sdp, type: decodedMessage.t)
                }
            case "ice":
                if let ice = decodedMessage.ice {
                    delegate?.signalingClient(self, didReceiveCandidate: ice.candidate, sdpMLineIndex: ice.sdpMLineIndex, sdpMid: ice.sdpMid)
                }
            default:
                break
            }
        }
        // Try to decode as a ProcessingModeMessage
        else if let modeMessage = try? JSONDecoder().decode(ProcessingModeMessage.self, from: data) {
            guard modeMessage.pairId == self.pairId else { return }
            
            if modeMessage.t == "mode" {
                delegate?.signalingClient(self, didReceiveProcessingMode: modeMessage.mode)
            }
        }
    }

    private func handleError(_ error: Error) async {
        print("SignalingClient Error: \(error.localizedDescription)")
        self.connectionState = .disconnected
        stopHeartbeat()
        webSocket = nil
        self.delegate?.signalingClient(self, didEncounterError: error)
        scheduleReconnect()
    }

    private func decodePairId(from jwt: String) throws -> String {
        let components = jwt.split(separator: ".")
        guard components.count == 3 else { throw WSError.invalidData }
        let payloadData = Data(base64Encoded: String(components[1]).padding(toLength: ((components[1].count+3)/4)*4, withPad: "=", startingAt: 0)) ?? Data()

        if let json = try JSONSerialization.jsonObject(with: payloadData, options: []) as? [String: Any],
           let pairId = json["pairId"] as? String {
            return pairId
        }
        throw WSError.invalidData
    }

    private func extractExpiryDate(from jwt: String) -> Date? {
        let components = jwt.split(separator: ".")
        guard components.count == 3 else { return nil }
        let payloadBase64 = String(components[1]).padding(toLength: ((components[1].count+3)/4)*4, withPad: "=", startingAt: 0)
        guard let payloadData = Data(base64Encoded: payloadBase64),
              let payload = try? JSONSerialization.jsonObject(with: payloadData) as? [String: Any],
              let exp = payload["exp"] as? Double else {
            return nil
        }
        return Date(timeIntervalSince1970: exp)
    }
}

// MARK: - URLSessionWebSocketDelegate
extension SignalingClient: URLSessionWebSocketDelegate {
    nonisolated func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        Task { @MainActor in
            self.connectionState = .connected
            self.reconnectAttempt = 0
            self.delegate?.signalingClientDidConnect(self)
            // Send current processing mode to paired device
            self.sendProcessingMode(SettingsManager.shared.processingMode)
            self.startHeartbeat()
        }
    }

    nonisolated func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        Task { @MainActor in
            self.connectionState = .disconnected
            self.stopHeartbeat()
            self.webSocket = nil
            self.delegate?.signalingClientDidDisconnect(self)
            self.scheduleReconnect()
        }
    }
}

// MARK: - Helper Extensions & Structs
fileprivate extension URLSessionWebSocketTask.Message {
    var data: Data? {
        switch self {
        case .data(let data): return data
        case .string(let string): return string.data(using: .utf8)
        @unknown default: return nil
        }
    }
}

// MARK: - Codable Message Structs
struct SignalingMessage: Codable {
    let t: String // Type: "offer", "answer", "ice"
    let pairId: String
    let sdp: String?
    let ice: IceCandidatePayload?

    enum CodingKeys: String, CodingKey {
        case t, sdp, ice
        case pairId = "pairId"
    }
}

struct IceCandidatePayload: Codable {
    let candidate: String
    let sdpMLineIndex: Int32
    let sdpMid: String?
}

struct ProcessingModeMessage: Codable {
    let t: String // "mode"
    let pairId: String
    let mode: String // "server" or "hybrid"
    
    enum CodingKeys: String, CodingKey {
        case t, mode
        case pairId = "pairId"
    }
}
