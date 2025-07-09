//
//  SceneAnalysisTabView.swift
//  Orion
//
//  Created by Riddhiman Rana on 6/16/25.
//

import SwiftUI

struct SceneAnalysisTabView: View {
    @EnvironmentObject var wsManager: WebSocketManager
    @EnvironmentObject var appState: AppStateManager
    
    let latestAnalysis: SceneAnalysis?
    let analysisTimestamp: TimeInterval
    
    @State private var analysisHistory: [AnalysisHistoryItem] = []
    @State private var showingSettings = false
    
    private var formattedTimestamp: String {
        let date = Date(timeIntervalSince1970: analysisTimestamp)
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"
        return formatter.string(from: date)
    }
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    // Current Scene Analysis
                    if let analysis = latestAnalysis {
                        currentAnalysisView(analysis)
                            .onAppear {
                                addToHistory(analysis)
                            }
                    } else {
                        waitingForAnalysisView
                    }
                    
                    // Scene Context and Insights
                    if let analysis = latestAnalysis {
                        sceneInsightsView(analysis)
                    }
                    
                    // Enhanced Detections Grid
                    if let analysis = latestAnalysis, !analysis.enhancedDetections.isEmpty {
                        enhancedDetectionsView(analysis.enhancedDetections)
                    }
                    
                    // Recent Analysis History
                    if !analysisHistory.isEmpty {
                        recentAnalysisHistoryView
                    }
                }
                .padding()
            }
            .navigationTitle("Scene Analysis")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        showingSettings = true
                    } label: {
                        Image(systemName: "slider.horizontal.3")
                    }
                }
            }
        }
        .navigationViewStyle(StackNavigationViewStyle())
        .sheet(isPresented: $showingSettings) {
            FastVLMSettingsView()
                .environmentObject(wsManager)
        }
    }
    
    // MARK: - Current Analysis View
    @ViewBuilder
    private func currentAnalysisView(_ analysis: SceneAnalysis) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Current Scene")
                        .font(.title2.weight(.semibold))
                        .foregroundColor(.primary)
                    
                    Text("Last updated: \(formattedTimestamp)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                ConfidenceIndicator(confidence: analysis.confidence)
            }
            
            // Scene Description
            Text(analysis.sceneDescription)
                .font(.body)
                .foregroundColor(.primary)
                .multilineTextAlignment(.leading)
                .padding()
                .background(Color(.secondarySystemBackground))
                .cornerRadius(12)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
    }
    
    // MARK: - Waiting View
    private var waitingForAnalysisView: some View {
        VStack(spacing: 16) {
            Image(systemName: "brain.head.profile")
                .font(.system(size: 60))
                .foregroundColor(.secondary)
            
            Text("Waiting for Scene Analysis")
                .font(.title2.weight(.medium))
                .foregroundColor(.primary)
            
            Text("Fast-VLM is processing the camera feed to understand the current scene")
                .font(.body)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            // Connection status indicator
            HStack {
                Circle()
                    .fill(connectionStatusColor)
                    .frame(width: 8, height: 8)
                
                Text("Server: \(connectionStatusText)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding(40)
        .background(Color(.secondarySystemBackground))
        .cornerRadius(16)
    }
    
    // MARK: - Scene Insights View
    @ViewBuilder
    private func sceneInsightsView(_ analysis: SceneAnalysis) -> some View {
        if !analysis.contextualInsights.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Text("Contextual Insights")
                    .font(.headline.weight(.semibold))
                    .foregroundColor(.primary)
                
                LazyVStack(spacing: 8) {
                    ForEach(Array(analysis.contextualInsights.enumerated()), id: \.offset) { index, insight in
                        InsightCard(insight: insight, index: index)
                    }
                }
            }
            .padding()
            .background(Color(.systemBackground))
            .cornerRadius(16)
            .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
        }
    }
    
    // MARK: - Enhanced Detections View
    @ViewBuilder
    private func enhancedDetectionsView(_ detections: [EnhancedDetection]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Enhanced Object Analysis")
                .font(.headline.weight(.semibold))
                .foregroundColor(.primary)
            
            LazyVGrid(columns: [
                GridItem(.flexible()),
                GridItem(.flexible())
            ], spacing: 12) {
                ForEach(detections, id: \.trackId) { detection in
                    EnhancedDetectionCard(detection: detection)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
    }
    
    // MARK: - Recent Analysis History
    private var recentAnalysisHistoryView: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Recent Analysis")
                .font(.headline.weight(.semibold))
                .foregroundColor(.primary)
            
            LazyVStack(spacing: 8) {
                ForEach(analysisHistory.suffix(5).reversed(), id: \.id) { item in
                    HistoryAnalysisCard(item: item)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
    }
    
    // MARK: - Helper Properties
    private var connectionStatusColor: Color {
        switch wsManager.status {
        case .connected: return .green
        case .connecting: return .yellow
        case .disconnected: return .red
        }
    }
    
    private var connectionStatusText: String {
        switch wsManager.status {
        case .connected: return "Connected"
        case .connecting: return "Connecting..."
        case .disconnected: return "Disconnected"
        }
    }
    
    // MARK: - Helper Methods
    private func addToHistory(_ analysis: SceneAnalysis) {
        let item = AnalysisHistoryItem(
            analysis: analysis,
            timestamp: analysisTimestamp
        )
        
        // Add to history and keep only last 10 items
        analysisHistory.append(item)
        if analysisHistory.count > 10 {
            analysisHistory.removeFirst()
        }
    }
}

// MARK: - Supporting Views

struct ConfidenceIndicator: View {
    let confidence: Float
    
    private var color: Color {
        switch confidence {
        case 0.8...: return .green
        case 0.5..<0.8: return .yellow
        default: return .red
        }
    }
    
    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            
            Text("\(Int(confidence * 100))%")
                .font(.caption.weight(.semibold))
                .foregroundColor(color)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(color.opacity(0.1))
        .cornerRadius(12)
    }
}

struct InsightCard: View {
    let insight: String
    let index: Int
    
    private var iconName: String {
        switch index % 4 {
        case 0: return "lightbulb.fill"
        case 1: return "eye.fill"
        case 2: return "location.fill"
        default: return "star.fill"
        }
    }
    
    private var iconColor: Color {
        switch index % 4 {
        case 0: return .yellow
        case 1: return .blue
        case 2: return .green
        default: return .orange
        }
    }
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: iconName)
                .foregroundColor(iconColor)
                .frame(width: 20)
            
            Text(insight)
                .font(.subheadline)
                .foregroundColor(.primary)
                .multilineTextAlignment(.leading)
            
            Spacer()
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(10)
    }
}

struct EnhancedDetectionCard: View {
    let detection: EnhancedDetection
    
    private var categoryColor: Color {
        switch detection.category.lowercased() {
        case "human": return .blue
        case "vehicle": return .green
        case "animal": return .orange
        case "furniture": return .brown
        case "electronics": return .purple
        default: return .gray
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(detection.label.capitalized)
                    .font(.subheadline.weight(.semibold))
                    .foregroundColor(.primary)
                
                Spacer()
                
                if detection.isMoving {
                    Image(systemName: "figure.walk")
                        .foregroundColor(.blue)
                        .font(.caption)
                }
            }
            
            HStack {
                Text(detection.category.capitalized)
                    .font(.caption)
                    .foregroundColor(categoryColor)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(categoryColor.opacity(0.1))
                    .cornerRadius(6)
                
                Spacer()
                
                Text("\(Int(detection.confidence * 100))%")
                    .font(.caption.weight(.medium))
                    .foregroundColor(.secondary)
            }
        }
        .padding(12)
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }
}

struct HistoryAnalysisCard: View {
    let item: AnalysisHistoryItem
    
    private var formattedTime: String {
        let date = Date(timeIntervalSince1970: item.timestamp)
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"
        return formatter.string(from: date)
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(formattedTime)
                    .font(.caption.weight(.medium))
                    .foregroundColor(.secondary)
                
                Spacer()
                
                ConfidenceIndicator(confidence: item.analysis.confidence)
            }
            
            Text(item.analysis.sceneDescription)
                .font(.caption)
                .foregroundColor(.primary)
                .lineLimit(2)
                .multilineTextAlignment(.leading)
        }
        .padding(12)
        .background(Color(.secondarySystemBackground))
        .cornerRadius(10)
    }
}

// MARK: - Data Models

struct AnalysisHistoryItem: Identifiable {
    let id = UUID()
    let analysis: SceneAnalysis
    let timestamp: TimeInterval
}

// MARK: - Settings View Placeholder

struct FastVLMSettingsView: View {
    @EnvironmentObject var wsManager: WebSocketManager
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationView {
            Form {
                Section("Fast-VLM Configuration") {
                    Text("Fast-VLM model integration settings will be available here when the model is integrated.")
                        .foregroundColor(.secondary)
                }
                
                Section("Analysis Settings") {
                    Toggle("Enable Contextual Insights", isOn: .constant(true))
                    Toggle("Track Object Movement", isOn: .constant(true))
                    Toggle("Enhanced Descriptions", isOn: .constant(true))
                }
            }
            .navigationTitle("Scene Analysis Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

// MARK: - Preview

struct SceneAnalysisTabView_Previews: PreviewProvider {
    static var previews: some View {
        let sampleAnalysis = SceneAnalysis(
            sceneDescription: "A person is standing in a modern living room with natural lighting. There are several pieces of furniture visible including a couch and a coffee table. The person appears to be looking towards a window.",
            contextualInsights: [
                "Natural lighting suggests daytime",
                "Person appears relaxed in comfortable environment",
                "Modern furniture indicates contemporary living space",
                "Open layout suggests spacious room design"
            ],
            enhancedDetections: [
                EnhancedDetection(
                    label: "person",
                    confidence: 0.95,
                    bbox: [0.1, 0.1, 0.5, 0.8],
                    trackId: 1,
                    category: "human",
                    isMoving: false
                ),
                EnhancedDetection(
                    label: "couch",
                    confidence: 0.88,
                    bbox: [0.6, 0.4, 0.9, 0.9],
                    trackId: 2,
                    category: "furniture",
                    isMoving: false
                )
            ],
            confidence: 0.92
        )
        
        return SceneAnalysisTabView(
            latestAnalysis: sampleAnalysis,
            analysisTimestamp: Date().timeIntervalSince1970
        )
        .environmentObject(WebSocketManager())
        .environmentObject(AppStateManager())
    }
}
