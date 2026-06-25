import Foundation
import SwiftUI
import Combine

struct DashboardDetection: Codable, Identifiable {
    var id: String { "\(label)_\(track_id ?? 0)_\(bbox[0])_\(bbox[1])" }
    let label: String
    let confidence: Double
    let bbox: [Double]
    let track_id: Int?
}

class DashboardSocket: ObservableObject {
    static let shared = DashboardSocket()
    
    @Published var isConnected = false
    @Published var currentFrame: NSImage? = nil
    @Published var detections: [DashboardDetection] = []
    @Published var sceneDescription = "Waiting for live feed..."
    @Published var queueSize = 0
    @Published var processingMode = "full"
    @Published var frameId = "-"
    @Published var modelHealth: [String: Bool] = [:]
    @Published var latestReasoningPayload = "No reasoning payload yet."
    @Published var packetEventCount = 0
    
    private var webSocketTask: URLSessionWebSocketTask?
    private let session = URLSession(configuration: .default)
    
    private init() {}
    
    func connect() {
        guard !isConnected else { return }
        
        let url = URL(string: "ws://127.0.0.1:8000/ws/dashboard")!
        webSocketTask = session.webSocketTask(with: url)
        webSocketTask?.resume()
        
        isConnected = true
        receiveMessage()
    }
    
    func disconnect() {
        webSocketTask?.cancel(with: .normalClosure, reason: nil)
        webSocketTask = nil
        isConnected = false
    }
    
    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            guard let self = self else { return }
            
            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    self.parseMessage(text)
                case .data(let data):
                    if let text = String(data: data, encoding: .utf8) {
                        self.parseMessage(text)
                    }
                @unknown default:
                    break
                }
                self.receiveMessage()
                
            case .failure:
                DispatchQueue.main.async {
                    self.isConnected = false
                }
                DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                    self.connect()
                }
            }
        }
    }
    
    private func parseMessage(_ text: String) {
        guard let data = text.data(using: .utf8) else { return }
        
        do {
            if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
               let event = json["type"] as? String {
                
                if event == "response_sent_to_ios" {
                    if let frameId = json["frame_id"] {
                        DispatchQueue.main.async {
                            self.frameId = "\(frameId)"
                        }
                    }

                    // Extract image data
                    if let base64Image = json["image_data"] as? String,
                       let imageData = Data(base64Encoded: base64Image),
                       let nsImage = NSImage(data: imageData) {
                        DispatchQueue.main.async {
                            self.currentFrame = nsImage
                        }
                    }
                    
                    // Extract scene description
                    if let desc = json["scene_description"] as? String {
                        DispatchQueue.main.async {
                            self.sceneDescription = desc
                        }
                    }
                    
                    // Extract server status
                    if let serverStatus = json["server_status"] as? [String: Any] {
                        if let qSize = serverStatus["queue_size"] as? Int {
                            DispatchQueue.main.async {
                                self.queueSize = qSize
                            }
                        }
                        if let mode = serverStatus["processing_mode"] as? String {
                            DispatchQueue.main.async {
                                self.processingMode = mode
                            }
                        }
                        if let health = serverStatus["model_health"] as? [String: Bool] {
                            DispatchQueue.main.async {
                                self.modelHealth = health
                            }
                        }
                    }

                    if let reasoning = json["llm_reasoning"] {
                        let formatted = Self.prettyPrinted(reasoning) ?? "\(reasoning)"
                        DispatchQueue.main.async {
                            self.latestReasoningPayload = formatted
                        }
                    }

                    if let events = json["packet_events"] as? [Any] {
                        DispatchQueue.main.async {
                            self.packetEventCount = events.count
                        }
                    }
                    
                    // Extract detections
                    if let detectionsArray = json["detections"] as? [[String: Any]] {
                        var parsedDetections: [DashboardDetection] = []
                        for det in detectionsArray {
                            if let label = det["label"] as? String,
                               let confidence = det["confidence"] as? Double,
                               let bbox = det["bbox"] as? [Double] {
                                let trackId = det["track_id"] as? Int
                                parsedDetections.append(DashboardDetection(
                                    label: label,
                                    confidence: confidence,
                                    bbox: bbox,
                                    track_id: trackId
                                ))
                            }
                        }
                        DispatchQueue.main.async {
                            self.detections = parsedDetections
                        }
                    }
                }
            }
        } catch {
            // Skip parsing errors silently
        }
    }

    private static func prettyPrinted(_ object: Any) -> String? {
        guard JSONSerialization.isValidJSONObject(object),
              let data = try? JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys]) else {
            return nil
        }
        return String(data: data, encoding: .utf8)
    }
}
