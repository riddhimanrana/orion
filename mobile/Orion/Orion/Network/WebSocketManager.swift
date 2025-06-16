import Foundation
import Network
import Combine

/// WebSocket connection status
enum ConnectionStatus {
    case disconnected
    case connecting
    case connected
}

/// WebSocket manager errors
enum WSError: Error {
    case connectionFailed
    case sendFailed
    case invalidData
    case serverError(String)
    case invalidURL // Added for invalid URL construction
}

/// Handler for server responses
struct ServerResponse: Codable {
    let frameId: String
    let analysis: SceneAnalysis
    let timestamp: TimeInterval
    let error: String?
    
    enum CodingKeys: String, CodingKey {
        case frameId = "frame_id"
        case analysis
        case timestamp
        case error
    }
}

/// Scene analysis from server
struct SceneAnalysis: Codable {
    let sceneDescription: String
    let contextualInsights: [String]
    let enhancedDetections: [EnhancedDetection]
    let confidence: Float
    
    enum CodingKeys: String, CodingKey {
        case sceneDescription = "scene_description"
        case contextualInsights = "contextual_insights"
        case enhancedDetections = "enhanced_detections"
        case confidence
    }
}

/// Enhanced detection from server
struct EnhancedDetection: Codable {
    let label: String
    let confidence: Float
    let bbox: [Float]
    let trackId: Int?
    let category: String
    let isMoving: Bool
    
    enum CodingKeys: String, CodingKey {
        case label
        case confidence
        case bbox
        case trackId = "track_id"
        case category
        case isMoving = "is_moving"
    }
}

class WebSocketManager: ObservableObject {
    /// Current connection status
    @Published private(set) var status = ConnectionStatus.disconnected
    
    /// WebSocket task
    private var wsTask: URLSessionWebSocketTask?
    private let session = URLSession(configuration: .default)
    
    /// Server host and port - now dynamic
    private var currentHost: String
    private var currentPort: Int

    /// Computed server URL
    private var serverURL: URL? {
        let urlString = "ws://\(currentHost):\(currentPort)/ios"
        return URL(string: urlString)
    }
    
    /// Completion handlers
    var onAnalysis: ((SceneAnalysis) -> Void)?
    var onError: ((WSError) -> Void)?
    
    /// Debug logging
    static var enableLogging = false
    
    /// Network path monitor
    private var networkMonitor: NWPathMonitor? // Added to make network monitoring optional to start

    init() {
        // Get server host and port from UserDefaults or ServerConfig defaults
        self.currentHost = UserDefaults.standard.string(forKey: UserDefaultsKeys.serverHost) ?? ServerConfig.host
        self.currentPort = UserDefaults.standard.object(forKey: UserDefaultsKeys.serverPort) as? Int ?? ServerConfig.port
        
        log("WebSocketManager initialized. Server: ws://\(currentHost):\(currentPort)/ios")
        startNetworkMonitoring()
    }
    
    /// Connect to server
    func connect() {
        guard status == .disconnected else {
            log("Connect called but status is not disconnected: \(status)")
            return
        }
        
        guard let urlToConnect = serverURL else {
            log("Cannot connect: Server URL is invalid (currentHost: \(currentHost), currentPort: \(currentPort))")
            onError?(.invalidURL)
            // Optionally set status to disconnected if it was trying to connect
            DispatchQueue.main.async {
                self.status = .disconnected
            }
            return
        }
        
        DispatchQueue.main.async {
            self.status = .connecting
        }
        wsTask = session.webSocketTask(with: urlToConnect)
        wsTask?.resume()
        
        receiveMessage()
        
        log("Connecting to server: \(urlToConnect)")
    }
    
    /// Disconnect from server
    func disconnect() {
        wsTask?.cancel(with: .normalClosure, reason: nil)
        wsTask = nil
        // Ensure status is updated only if it's not already disconnected
        // to avoid redundant UI updates or logic triggers.
        if status != .disconnected {
            DispatchQueue.main.async {
                self.status = .disconnected
            }
            log("Disconnected from server")
        }
    }

    /// Update server URL and reconnect
    func updateServerURL(host: String, port: Int) {
        log("Updating server URL to ws://\(host):\(port)/ios")

        UserDefaults.standard.set(host, forKey: UserDefaultsKeys.serverHost)
        UserDefaults.standard.set(port, forKey: UserDefaultsKeys.serverPort)

        self.currentHost = host
        self.currentPort = port

        // Disconnect if currently connected or connecting
        if status != .disconnected {
            disconnect()
        }
        // Attempt to connect with the new URL
        // connect() itself checks if status is .disconnected before proceeding
        connect()
    }
    
    /// Send frame data to server
    func sendFrame(_ frame: DetectionFrame) {
        guard status == .connected else {
            // Do not log an error here if simply not connected, onError callback handles it.
            // log("Cannot send frame, not connected. Status: \(status)")
            onError?(.connectionFailed)
            return
        }
        
        do {
            let data = try JSONEncoder().encode(frame)
            guard let jsonString = String(data: data, encoding: .utf8) else {
                log("Send error: Could not convert frame data to UTF8 string.")
                onError?(.invalidData)
                return
            }
            let message = URLSessionWebSocketTask.Message.string(jsonString)
            
            wsTask?.send(message) { [weak self] error in
                if let error = error {
                    self?.log("Send error: \(error.localizedDescription)")
                    self?.onError?(.sendFailed)
                }
            }
        } catch {
            log("Encode error: \(error.localizedDescription)")
            onError?(.invalidData)
        }
    }
    
    /// Receive messages from server
    private func receiveMessage() {
        wsTask?.receive { [weak self] result in
            guard let self = self else { return }
            
            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    self.handleMessage(text)
                case .data(let data):
                    self.handleMessage(String(data: data, encoding: .utf8) ?? "")
                @unknown default:
                    self.log("Received unknown message type.")
                    break
                }
                // Continue receiving messages only if the task is still valid
                if self.wsTask?.state == .running || self.wsTask?.state == .suspended {
                     self.receiveMessage()
                }
                
            case .failure(let error):
                // Avoid logging "Socket is not connected" if it's a normal closure or graceful disconnect.
                // The error might be `POSIXErrorCode: Software caused connection abort` or similar on disconnect.
                let nsError = error as NSError
                if !(nsError.domain == NSPOSIXErrorDomain && nsError.code == Int(ECONNABORTED)) &&
                   !(nsError.domain == NSPOSIXErrorDomain && nsError.code == Int(EPIPE)) && // Broken pipe
                    !(nsError.domain == kNWErrorDomainPOSIX as String && nsError.code == Int(ECONNABORTED)) { // For NWError
                    self.log("Receive error: \(error.localizedDescription) (Domain: \(nsError.domain), Code: \(nsError.code))")
                }

                // Only change status and attempt reconnect if not intentionally disconnected
                if self.status != .disconnected {
                    DispatchQueue.main.async {
                        self.status = .disconnected
                    }
                    self.onError?(.connectionFailed)
                
                    // Simple reconnect delay, ensure this doesn't loop too aggressively
                    // if server is genuinely down. Consider exponential backoff for production.
                    DispatchQueue.main.asyncAfter(deadline: .now() + ServerConfig.reconnectDelay) {
                        if self.status == .disconnected { // Check again before reconnecting
                            self.log("Attempting to reconnect after receive error.")
                            self.connect()
                        }
                    }
                }
            }
        }
    }
    
    /// Handle received message
    private func handleMessage(_ text: String) {
        guard let data = text.data(using: .utf8) else {
            log("Failed to convert message text to data.")
            onError?(.invalidData)
            return
        }

        var messageHandled = false
        do {
            if let json = try JSONSerialization.jsonObject(with: data, options: []) as? [String: Any],
               let messageType = json["type"] as? String {

                if messageType == "connection_ack" {
                    log("Received connection_ack from server. Client ID: \(json["client_id"] as? String ?? "N/A")")
                    DispatchQueue.main.async {
                        if self.status != .connected {
                            self.status = .connected
                            self.log("Status updated to Connected by ACK.")
                        }
                    }
                    messageHandled = true
                }
            }
        } catch {
            log("Initial JSON type check failed or not a simple typed message. Will attempt ServerResponse decoding. Error: \(error.localizedDescription). Received: \(text)")
        }

        if messageHandled {
            return
        }

        do {
            let response = try JSONDecoder().decode(ServerResponse.self, from: data)
            // log("Successfully decoded ServerResponse for frame_id: \(response.frameId)") // Can be too verbose

            if let error = response.error {
                log("ServerResponse contained an error: \(error)")
                onError?(.serverError(error))
                return
            }

            DispatchQueue.main.async {
                if self.status != .connected {
                    self.status = .connected
                    // log("Status updated to Connected by valid ServerResponse.") // Can be verbose
                }
                self.onAnalysis?(response.analysis)
            }
            
        } catch {
            log("Failed to decode as ServerResponse: \(error.localizedDescription). Received text: \(text)")
            onError?(.invalidData)
        }
    }
    
    /// Monitor network path
    private func startNetworkMonitoring() {
        // Avoid re-initializing if already monitoring
        guard networkMonitor == nil else { return }

        let monitor = NWPathMonitor()
        monitor.pathUpdateHandler = { [weak self] path in
            guard let self = self else { return }
            if path.status == .satisfied {
                self.log("Network path is satisfied.")
                if self.status == .disconnected {
                    DispatchQueue.main.async { // Ensure connect is called on main thread if it modifies UI related @Published vars
                        self.log("Network reconnected, attempting to connect WebSocket.")
                        self.connect()
                    }
                }
            } else {
                self.log("Network path is not satisfied.")
                if self.status == .connected || self.status == .connecting {
                    DispatchQueue.main.async { // Ensure disconnect is called on main thread
                        self.log("Network lost, disconnecting WebSocket.")
                        self.disconnect()
                        self.onError?(.connectionFailed) // Notify that connection is lost due to network
                    }
                }
            }
        }
        self.networkMonitor = monitor // Store the monitor
        monitor.start(queue: DispatchQueue.global(qos: .background))
    }
    
    /// Log debug messages
    private func log(_ message: String) {
        if Self.enableLogging {
            // Using Logger.shared.network for consistency if you have it
            // Or fallback to print for simplicity if Logger isn't set up for this context
            Logger.shared.network("WebSocketManager: \(message)")
            // print("WebSocketManager: \(message)")
        }
    }
    
    deinit {
        log("WebSocketManager deinitialized.")
        networkMonitor?.cancel() // Cancel the network monitor
        networkMonitor = nil
        disconnect()
    }
}
