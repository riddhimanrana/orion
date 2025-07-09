//
//  SceneUnderstandingView.swift
//  Orion
//
//  Created by Riddhiman Rana on 6/12/25.
//


import SwiftUI

struct SceneUnderstandingView: View {
    let analysis: SceneAnalysis
    let timestamp: TimeInterval
    
    private var formattedTime: String {
        let date = Date(timeIntervalSince1970: timestamp)
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss.SSS"
        return formatter.string(from: date)
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Scene description
            VStack(alignment: .leading, spacing: 4) {
                Text("Scene Description")
                    .font(.headline)
                    .foregroundColor(.primary)
                
                Text(analysis.sceneDescription)
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.leading)
            }
            .padding(.horizontal)
            
            // Insights
            if !analysis.contextualInsights.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Insights")
                        .font(.headline)
                        .foregroundColor(.primary)
                    
                    ForEach(analysis.contextualInsights, id: \.self) { insight in
                        HStack(spacing: 8) {
                            Image(systemName: "lightbulb")
                                .foregroundColor(.yellow)
                            Text(insight)
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                .padding(.horizontal)
            }
            
            // Enhanced detections
            if !analysis.enhancedDetections.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Enhanced Detections")
                        .font(.headline)
                        .foregroundColor(.primary)
                    
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 12) {
                            ForEach(analysis.enhancedDetections, id: \.trackId) { detection in
                                DetectionCard(detection: detection)
                            }
                        }
                        .padding(.horizontal)
                    }
                }
                .padding(.horizontal)
            }
            
            // Confidence and timestamp
            HStack {
                ConfidenceView(value: analysis.confidence)
                Spacer()
                Text(formattedTime)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal)
        }
        .padding(.vertical)
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 4)
    }
}

struct DetectionCard: View {
    let detection: EnhancedDetection
    
    private var motionIndicator: String {
        detection.isMoving ? "figure.walk" : "figure.stand"
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(detection.label.capitalized)
                    .font(.headline)
                Spacer()
                Image(systemName: motionIndicator)
                    .foregroundColor(.blue)
            }
            
            Text(detection.category.capitalized)
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            ConfidenceView(value: detection.confidence)
        }
        .padding(12)
        .background(Color(.secondarySystemBackground))
        .cornerRadius(8)
        .frame(width: 160)
    }
}

struct ConfidenceView: View {
    let value: Float
    
    private var color: Color {
        switch value {
        case 0.8...: return .green
        case 0.5..<0.8: return .yellow
        default: return .red
        }
    }
    
    var body: some View {
        HStack(spacing: 4) {
            Text("Confidence:")
                .font(.caption)
                .foregroundColor(.secondary)
            Text("\(Int(value * 100))%")
                .font(.caption.bold())
                .foregroundColor(color)
        }
    }
}

#Preview {
    // Sample data for preview
    SceneUnderstandingView(
        analysis: SceneAnalysis(
            sceneDescription: "A person walking through a room with furniture",
            contextualInsights: [
                "Person appears to be heading towards the door",
                "Room is well-lit with natural light"
            ],
            enhancedDetections: [
                EnhancedDetection(
                    label: "person",
                    confidence: 0.95,
                    bbox: [0.1, 0.1, 0.5, 0.8],
                    trackId: 1,
                    category: "human",
                    isMoving: true
                ),
                EnhancedDetection(
                    label: "chair",
                    confidence: 0.88,
                    bbox: [0.6, 0.4, 0.8, 0.9],
                    trackId: 2,
                    category: "furniture",
                    isMoving: false
                )
            ],
            confidence: 0.92
        ),
        timestamp: Date().timeIntervalSince1970
    )
    .padding()
}
