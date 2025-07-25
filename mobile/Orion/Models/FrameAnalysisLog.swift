//
//  FrameAnalysisLog.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Log entry for all analysis performed on a single camera frame in Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//
import Foundation
import UIKit

/// A comprehensive log entry for all analysis performed on a single camera frame.
struct FrameAnalysisLog: Identifiable, Hashable, Codable {
    let id = UUID()
    let frameId: String
    let timestamp: Date
    
    // YOLO Data
    let yoloDetections: [Detection]
    let yoloProcessingTime: TimeInterval
    
    // VLM Data
    let vlmPrompt: String
    let vlmResult: FastVLMModel.VLMResult?
    
    // System Metrics (placeholders, require dedicated system monitoring)
    let cpuUsage: Double // Range 0.0 - 1.0
    let gpuUsage: Double // Range 0.0 - 1.0
    let aneUsage: Double // Range 0.0 - 1.0 for Apple Neural Engine
    let batteryLevel: Float // Range 0.0 - 1.0
    
    var formattedTimestamp: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .medium
        formatter.dateStyle = .short
        return formatter.string(from: timestamp)
    }
    
    /// Provides a placeholder object for SwiftUI previews and testing.
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
