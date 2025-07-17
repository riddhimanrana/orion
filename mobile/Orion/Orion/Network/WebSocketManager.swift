import Foundation
import Network
import Combine


// WebSocket connection status
enum ConnectionStatus {
    case disconnected
    case connecting
    case connected
    
    var description: String {
        switch self {
        case .disconnected: return "Disconnected"
        case .connecting: return "Connecting"
        case .connected: return "Connected"
        }
    }
}

// WebSocket manager errors
enum WSError: Error, Equatable {
    case connectionFailed
    case sendFailed
    case invalidData
    case serverError(String)
    case invalidURL // Added for invalid URL construction
}

// Configuration message for sending to server
struct ConfigurationMessage: ClientToServerMessage {
    let type: String = "configuration"
    let processingMode: String
    
    enum CodingKeys: String, CodingKey {
        case type
        case processingMode = "processing_mode"
    }
}

// Base protocol for messages sent from client to server
protocol ClientToServerMessage: Encodable {
    var type: String { get }
}

// Base protocol for messages received from server by client
protocol ServerToClientMessage: Decodable {
    var type: String { get }
}

// Handler for server responses (frame analysis)
struct ServerResponse: ServerToClientMessage {
    let type: String
    let frameId: String
    let analysis: SceneAnalysis
    let timestamp: TimeInterval
    let error: String?
    
    enum CodingKeys: String, CodingKey {
        case type
        case frameId = "frame_id"
        case analysis
        case timestamp
        case error
    }
}



// Frame data message for sending to server
struct FrameDataMessage: ClientToServerMessage {
    let type: String = "frame_data"
    let frameId: String
    let timestamp: TimeInterval
    let imageData: String? // Base64 encoded image data
    let detections: [NetworkDetection]? // Optional for full server processing mode
    let deviceId: String?
    let vlmDescription: String? // Optional for full server processing mode
    let vlmConfidence: Float? // Optional for full server processing mode
    
    enum CodingKeys: String, CodingKey {
        case type
        case frameId = "frame_id"
        case timestamp
        case imageData = "image_data"
        case detections
        case deviceId = "device_id"
        case vlmDescription = "vlm_description"
        case vlmConfidence = "vlm_confidence"
    }
}

// User prompt message for sending to server
struct UserPromptMessage: ClientToServerMessage {
    let type: String = "user_prompt"
    let promptId: String
    let question: String
    let timestamp: TimeInterval
    let deviceId: String?
    
    enum CodingKeys: String, CodingKey {
        case type
        case promptId = "prompt_id"
        case question
        case timestamp
        case deviceId = "device_id"
    }
}

// Response to a user prompt from server
struct PromptResponse: ServerToClientMessage {
    let type: String
    let responseId: String
    let question: String
    let answer: String
    let timestamp: TimeInterval
    let error: String?
    
    enum CodingKeys: String, CodingKey {
        case type
        case responseId = "response_id"
        case question
        case answer
        case timestamp
        case error
    }
}

// Enum to help parse incoming messages based on their 'type' field
enum ServerMessageType: String, Codable {
    case connectionAck = "connection_ack"
    case liveUpdate = "live_update" // This is what ServerResponse will be
    case userPromptResponse = "user_prompt_response"
    case frameProcessed = "frame_processed"
    case error = "error"
    // Add other types as needed
}

class WebSocketManager: ObservableObject {
    // Published properties for UI updates
    @Published private(set) var status = ConnectionStatus.disconnected
    @Published private(set) var lastRoundTripTime: TimeInterval? = nil
    @Published private(set) var serverQueueSize: Int = 0 // New published property for queue size
    let lastRoundTripTimePublisher = PassthroughSubject<TimeInterval?, Never>()
    let networkLogPublisher = PassthroughSubject<NetworkLogEntry, Never>()

    // WebSocket task and session
    private var wsTask: URLSessionWebSocketTask?
    private let session = URLSession(configuration: .default)
    
    // Server configuration
    private var currentHost: String
    private var currentPort: Int
    private var processingMode: String
    
    // Computed server URL
    private var serverURL: URL? {
        let urlString = "ws://\(currentHost):\(currentPort)/ios"
        return URL(string: urlString)
    }
    
    // Dependencies
    private weak var cameraManager: CameraManager?

    // Callbacks
    var onFrameProcessed: (() -> Void)?
    var onAnalysis: ((SceneAnalysis) -> Void)?
    var onPromptResponse: ((PromptResponse) -> Void)?
    var onError: ((WSError) -> Void)?
    
    // Debugging
    static var enableLogging = false
    private var frameSendTimestamps: [String: TimeInterval] = [:]
    
    // Network monitoring
    private var networkMonitor: NWPathMonitor?
    
    init() {
        self.currentHost = UserDefaults.standard.string(forKey: UserDefaultsKeys.serverHost) ?? ServerConfig.host
        self.currentPort = UserDefaults.standard.object(forKey: UserDefaultsKeys.serverPort) as? Int ?? ServerConfig.port
        self.processingMode = UserDefaults.standard.string(forKey: UserDefaultsKeys.processingMode) ?? "split"
        
        log("WebSocketManager initialized. Server: ws://\(currentHost):\(currentPort)/ios")
        startNetworkMonitoring()
    }
    
    func setCameraManager(_ manager: CameraManager) {
        self.cameraManager = manager
    }

    func connect() {
        guard status == .disconnected else {
            log("Connect called but status is not disconnected: \(status)")
            return
        }
        
        guard let urlToConnect = serverURL else {
            log("Cannot connect: Server URL is invalid")
            onError?(.invalidURL)
            DispatchQueue.main.async { self.status = .disconnected }
            return
        }
        
        DispatchQueue.main.async { self.status = .connecting }
        wsTask = session.webSocketTask(with: urlToConnect)
        wsTask?.resume()
        
        receiveMessage()
        log("Connecting to server: \(urlToConnect)")
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            self.sendConfiguration(mode: self.processingMode)
        }
    }
    
    func disconnect() {
        wsTask?.cancel(with: .normalClosure, reason: nil)
        wsTask = nil
        if status != .disconnected {
            DispatchQueue.main.async {
                self.status = .disconnected
                self.lastRoundTripTime = nil
            }
            log("Disconnected from server")
        }
    }
    
    func updateServerURL(host: String, port: Int) {
        log("Updating server URL to ws://\(host):\(port)/ios")
        UserDefaults.standard.set(host, forKey: UserDefaultsKeys.serverHost)
        UserDefaults.standard.set(port, forKey: UserDefaultsKeys.serverPort)
        self.currentHost = host
        self.currentPort = port
        if status != .disconnected { disconnect() }
        connect()
    }
    
    func sendConfiguration(mode: String) {
        self.processingMode = mode
        let configMessage = ConfigurationMessage(processingMode: mode)
        sendMessage(configMessage)
    }
    
    func sendFrame(_ frame: FrameDataMessage) {
        if SettingsManager.shared.processingMode == "full" {
            frameSendTimestamps[frame.frameId] = Date().timeIntervalSince1970
        }
        sendMessage(frame)
    }
    
    func sendPrompt(_ prompt: UserPromptMessage) {
        sendMessage(prompt)
    }
    
    private func sendMessage<T: ClientToServerMessage>(_ message: T) {
        guard status == .connected else {
            onError?(.connectionFailed)
            return
        }
        
        do {
            let data = try JSONEncoder().encode(message)
            log("Sending message of type \(message.type) with size \(data.count) bytes.")
            guard let jsonString = String(data: data, encoding: .utf8) else {
                log("Send error: Could not convert data to UTF8 string.")
                onError?(.invalidData)
                return
            }
            let wsMessage = URLSessionWebSocketTask.Message.string(jsonString)
            
            wsTask?.send(wsMessage) { [weak self] error in
                if let error = error {
                    self?.log("Send error for message type \(message.type): \(error.localizedDescription)")
                    self?.onError?(.sendFailed)
                }
            }
        } catch {
            log("Encode error for message type \(message.type): \(error.localizedDescription)")
            onError?(.invalidData)
        }
    }
    
    private func receiveMessage() {
        wsTask?.receive { [weak self] result in
            guard let self = self else { return }
            
            switch result {
            case .success(let message):
                switch message {
                case .string(let text): self.handleMessage(text)
                case .data(let data): self.handleMessage(String(data: data, encoding: .utf8) ?? "")
                @unknown default: self.log("Received unknown message type.")
                }
                if self.wsTask?.state == .running { self.receiveMessage() }
                
            case .failure(let error):
                let nsError = error as NSError
                let closeCode = (error as? WSError) == .connectionFailed ? nil : nsError.code
                let reason = (error as? WSError) == .connectionFailed ? nil : nsError.localizedFailureReason
                self.log("Receive error: \(error.localizedDescription), domain: \(nsError.domain), code: \(closeCode ?? 0), reason: \(reason ?? "N/A")")
                if self.status != .disconnected {
                    DispatchQueue.main.async { self.status = .disconnected }
                    self.onError?(.connectionFailed)
                    DispatchQueue.main.asyncAfter(deadline: .now() + SettingsManager.shared.reconnectDelay) {
                        if self.status == .disconnected { self.connect() }
                    }
                }
            }
        }
    }
    
    private func handleMessage(_ text: String) {
        guard let data = text.data(using: .utf8) else {
            log("Failed to convert message text to data.")
            onError?(.invalidData)
            return
        }
        
        do {
            let json = try JSONSerialization.jsonObject(with: data, options: []) as? [String: Any]
            guard let messageTypeString = json?["type"] as? String, let messageType = ServerMessageType(rawValue: messageTypeString) else {
                log("Received message with unknown or missing type: \(text)")
                onError?(.invalidData)
                return
            }
            
            DispatchQueue.main.async {
                if self.status != .connected { self.status = .connected }
            }
            
            switch messageType {
            case .connectionAck: log("Received connection_ack from server.")
            case .liveUpdate:
                if let dataDict = json?["data"] as? [String: Any], let serverStatus = dataDict["server_status"] as? [String: Any], let queueSize = serverStatus["queue_size"] as? Int {
                    DispatchQueue.main.async { self.serverQueueSize = queueSize }
                }
                handleDecodable(ServerResponse.self, from: data)
            case .frameProcessed:
                if let frameId = json?["frame_id"] as? String {
                    if let startTime = frameSendTimestamps.removeValue(forKey: frameId) {
                        let rtt = Date().timeIntervalSince1970 - startTime
                        DispatchQueue.main.async {
                            self.lastRoundTripTime = rtt
                            self.lastRoundTripTimePublisher.send(rtt)
                        }
                    }
                }
                DispatchQueue.main.async { self.onFrameProcessed?() }
                // Notify CameraManager to allow next frame in full mode
                if SettingsManager.shared.processingMode == "full" {
                    DispatchQueue.main.async {
                        self.cameraManager?.serverDidAcknowledgeFrame()
                    }
                }
            case .userPromptResponse: handleDecodable(PromptResponse.self, from: data)
            case .error: handleServerError(json)
            }
        } catch {
            log("Failed to parse incoming message JSON: \(error.localizedDescription)")
            onError?(.invalidData)
        }
    }
    
    private func handleDecodable<T: Decodable>(_ type: T.Type, from data: Data) {
        do {
            let decodedObject = try JSONDecoder().decode(T.self, from: data)
            DispatchQueue.main.async {
                if let response = decodedObject as? ServerResponse { self.onAnalysis?(response.analysis) }
                else if let response = decodedObject as? PromptResponse { self.onPromptResponse?(response) }
            }
        } catch {
            log("Failed to decode \(String(describing: T.self)): \(error.localizedDescription)")
            onError?(.invalidData)
        }
    }
    
    private func handleServerError(_ json: [String: Any]?) {
        let errorMessage = json?["message"] as? String ?? "Unknown server error"
        log("Server sent an error message: \(errorMessage)")
        onError?(.serverError(errorMessage))
    }
    
    private func startNetworkMonitoring() {
        guard networkMonitor == nil else { return }
        let monitor = NWPathMonitor()
        monitor.pathUpdateHandler = { [weak self] path in
            guard let self = self else { return }
            if path.status == .satisfied {
                if self.status == .disconnected { self.connect() }
            } else {
                if self.status != .disconnected { self.disconnect() }
            }
        }
        self.networkMonitor = monitor
        monitor.start(queue: DispatchQueue.global(qos: .background))
    }
    
    private func log(_ message: String) {
        if Self.enableLogging { Logger.shared.network("WebSocketManager: \(message)") }
    }
    
    deinit {
        log("WebSocketManager deinitialized.")
        networkMonitor?.cancel()
        disconnect()
    }
}
