//
//  ProcessingModePill.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Processing mode status pill for Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//

import SwiftUI

struct ProcessingModePill: View {
    @ObservedObject var settingsManager = SettingsManager.shared
    
    @Environment(\.colorScheme) var colorScheme
    
    var body: some View {
        StatusPill(
            title: "Mode",
            status: processingModeDisplayText,
            statusColor: processingModeColor,
            isAnimated: false
        )
    }
    
    private var processingModeDisplayText: String {
        switch settingsManager.processingMode.lowercased() {
        case "hybrid":
            return "Hybrid"
        case "server":
            return "Server"
        // case "local": not yet implemented
        //     return "Local" 
        default:
            return "Unknown"
        }
    }
    
    private var processingModeColor: Color {
        switch settingsManager.processingMode.lowercased() {
        case "hybrid":
            return .blue // Hybrid mode - balanced approach
        case "server":
            return .purple // Server mode - cloud processing
        // case "local": not yet implemented
        //     return .orange // Local mode - device processing
        default:
            return .gray
        }
    }
}

// MARK: - Preview
struct ProcessingModePill_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 20) {
            ProcessingModePill()
        }
        .padding()
        .preferredColorScheme(.dark)
    }
}