//
//  FrameAnalysisLog.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//

import Foundation
import UIKit

struct FrameAnalysisLog: Identifiable, Hashable, Codable {
    var id = UUID()
    let frameId: String
    let timestamp: Date

    let yoloDetections: [Detection]
    let yoloProcessingTime: TimeInterval

    let vlmPrompt: String
    let vlmResult: FastVLMModel.VLMResult?

    let cpuUsage: Double
    let gpuUsage: Double
    let aneUsage: Double
    let batteryLevel: Float

    enum CodingKeys: String, CodingKey {
        case frameId, timestamp, yoloDetections, yoloProcessingTime, vlmPrompt, vlmResult, cpuUsage, gpuUsage, aneUsage, batteryLevel
    }

    var formattedTimestamp: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .medium
        formatter.dateStyle = .short
        return formatter.string(from: timestamp)
    }

    static func placeholder() -> FrameAnalysisLog {
        return FrameAnalysisLog(
            frameId: UUID().uuidString,
            timestamp: Date(),
            yoloDetections: [
                Detection(label: "person", confidence: 0.91, bbox: [0.1, 0.1, 0.3, 0.5], trackId: 1, contextualLabel: "person (left)"),
                Detection(label: "laptop", confidence: 0.88, bbox: [0.4, 0.4, 0.6, 0.6], trackId: 2, contextualLabel: "laptop (center)")
            ],
            yoloProcessingTime: 16.7,
            vlmPrompt: "The following objects were detected...",
            vlmResult: FastVLMModel.VLMResult(description: "A person is sitting at a desk with a laptop. They appear to be working.", timeToFirstToken: 0.18, totalGenerationTime: 1.32, tokensGenerated: 22),
            cpuUsage: 0.65,
            gpuUsage: 0.88,
            aneUsage: 0.95,
            batteryLevel: UIDevice.current.batteryLevel
        )
    }
}
