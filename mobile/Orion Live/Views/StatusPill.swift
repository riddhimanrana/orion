//
//  StatusPill.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Reusable status pill component with liquid glass design for Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//

import SwiftUI

struct StatusPill: View {
    let title: String
    let status: String
    let statusColor: Color
    let isAnimated: Bool
    
    @Environment(\.colorScheme) var colorScheme
    @State private var isAnimating = false
    
    init(title: String, status: String, statusColor: Color, isAnimated: Bool = false) {
        self.title = title
        self.status = status
        self.statusColor = statusColor
        self.isAnimated = isAnimated
    }
    
    var body: some View {
        HStack(spacing: 8) {
            // Status indicator circle
            Circle()
                .fill(statusColor)
                .frame(width: 10, height: 10)
                .shadow(color: statusColor.opacity(0.35), radius: 6, x: 0, y: 0)
                .scaleEffect(isAnimated && isAnimating ? 1.25 : 1.0)
                .animation(
                    isAnimated ? 
                    Animation.easeInOut(duration: 1.1).repeatForever(autoreverses: true) : 
                    .none, 
                    value: isAnimating
                )
            
            // Status text
            VStack(alignment: .leading, spacing: 1) {
                Text(title)
                    .font(.caption2)
                    .fontWeight(.semibold)
                    .foregroundStyle(.secondary)
                
                Text(status)
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundStyle(.primary)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(.ultraThinMaterial)
                .overlay(
                    // Gradient border for liquid glass edge
                    RoundedRectangle(cornerRadius: 20, style: .continuous)
                        .stroke(
                            LinearGradient(
                                colors: [Color.white.opacity(0.35), statusColor.opacity(0.35)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            ),
                            lineWidth: 1
                        )
                        .blendMode(.overlay)
                )
                .shadow(color: Color.black.opacity(colorScheme == .dark ? 0.25 : 0.08), radius: 8, x: 0, y: 4)
        )
        .overlay(
            // Subtle inner shadow to give depth
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(Color.black.opacity(colorScheme == .dark ? 0.15 : 0.05), lineWidth: 0.5)
                .blendMode(.multiply)
        )
        .overlay(
            // Soft glow ring tied to status color
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(statusColor.opacity(0.15), lineWidth: 3)
                .blur(radius: 6)
                .opacity(isAnimated ? (isAnimating ? 1 : 0.7) : 0.6)
        )
        .onAppear {
            if isAnimated {
                isAnimating = true
            }
        }
    }
}

// MARK: - Preview
struct StatusPill_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 20) {
            StatusPill(
                title: "Server",
                status: "Connected",
                statusColor: .green
            )
            
            StatusPill(
                title: "Mode",
                status: "Mac Server",
                statusColor: .green
            )
            
            StatusPill(
                title: "Server",
                status: "Connecting",
                statusColor: .yellow,
                isAnimated: true
            )
            
            StatusPill(
                title: "Server",
                status: "Disconnected",
                statusColor: .red
            )
        }
        .padding()
        .preferredColorScheme(.dark)
    }
}
