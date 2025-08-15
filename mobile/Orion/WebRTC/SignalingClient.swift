
//
//  SignalingClient.swift
//  Orion
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
    
    func connect() async {
        guard connectionState == .disconnected else { return }
        
        self.connectionState = .connecting
        
        do {
            guard let deviceId = deviceManager.deviceId else {
                throw WSError.connectionFailed
            }
            
            let token = try await apiService.fetchWebRTCToken(deviceId: deviceId)
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
    
    func disconnect() {
        webSocket?.cancel(with: .normalClosure, reason: nil)
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
    
    private func sendMessage<T: Encodable>(_ message: T) {
        guard connectionState == .connected else { return }
        do {
            let data = try JSONEncoder().encode(message)
            webSocket?.send(.data(data)) { [weak self] error in
                if let error = error {
                    Task { await self?.handleError(error) }
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
                    self?.listenForMessages()
                }
            }
        }
    }
    
    private func handleMessage(_ message: URLSessionWebSocketTask.Message) async {
        guard let data = message.data else { return }
        
        do {
            let decodedMessage = try JSONDecoder().decode(SignalingMessage.self, from: data)
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
        } catch {
            await handleError(error)
        }
    }
    
    private func handleError(_ error: Error) async {
        print("SignalingClient Error: \(error.localizedDescription)")
        self.connectionState = .disconnected
        self.delegate?.signalingClient(self, didEncounterError: error)
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
}

// MARK: - URLSessionWebSocketDelegate
extension SignalingClient: URLSessionWebSocketDelegate {
    nonisolated func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        Task { @MainActor in
            self.connectionState = .connected
            self.delegate?.signalingClientDidConnect(self)
        }
    }
    
    nonisolated func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        Task { @MainActor in
            self.connectionState = .disconnected
            self.delegate?.signalingClientDidDisconnect(self)
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
