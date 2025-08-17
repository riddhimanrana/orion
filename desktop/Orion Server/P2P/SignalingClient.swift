
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

// MARK: - Signaling Client
@MainActor
class SignalingClient: NSObject, URLSessionWebSocketDelegate, ObservableObject {
    @Published var connectionState: ConnectionStatus = .disconnected
    weak var delegate: SignalingClientDelegate?
    
    private var webSocket: URLSessionWebSocketTask?
    private let serverURL = URL(string: "wss://signal.orionlive.ai")!
    private let apiService: APIService
    private let deviceManager: DeviceManager
    private var pairId: String?

    init(apiService: APIService, deviceManager: DeviceManager) {
        self.apiService = apiService
        self.deviceManager = deviceManager
        super.init()
    }

    func connect() {
        guard connectionState == .disconnected, let deviceId = deviceManager.deviceId else {
            print("SignalingClient: Connection aborted. Already connected or deviceId is nil.")
            return
        }
        print("SignalingClient: Connecting...")
        self.connectionState = .connecting
        
        Task {
            do {
                let token = try await apiService.fetchWebRTCToken(deviceId: deviceId)
                self.pairId = try decodePairId(from: token)
                
                let urlRequest = URLRequest(url: URL(string: "\(serverURL.absoluteString)?token=\(token)")!)
                
                webSocket = URLSession.shared.webSocketTask(with: urlRequest)
                webSocket?.delegate = self
                webSocket?.resume()
                listenForMessages()
            } catch {
                handleError(error)
            }
        }
    }

    func disconnect() {
        print("SignalingClient: Disconnecting.")
        webSocket?.cancel(with: .normalClosure, reason: nil)
        webSocket = nil
        self.connectionState = .disconnected
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
        
        do {
            let decodedMessage = try JSONDecoder().decode(SignalingMessage.self, from: data)
            guard decodedMessage.pairId == self.pairId else { return }
            
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
        } catch {
            handleError(error)
        }
    }
    
    private func handleError(_ error: Error) {
        print("SignalingClient Error: \(error.localizedDescription)")
        self.connectionState = .disconnected
        delegate?.signalingClient(self, didEncounterError: error)
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
    
    // MARK: - URLSessionWebSocketDelegate
    nonisolated func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        Task { @MainActor in
            print("SignalingClient: WebSocket connected.")
            self.connectionState = .connected
            self.delegate?.signalingClientDidConnect(self)
        }
    }
    
    nonisolated func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        Task { @MainActor in
            print("SignalingClient: WebSocket disconnected.")
            self.connectionState = .disconnected
            self.delegate?.signalingClientDidDisconnect(self)
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
