//
//  NetworkDetection.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Data structure for sending detection results to the server in Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//
import Foundation

// Detection structure for sending to server
struct NetworkDetection: Codable {
    let label: String
    let confidence: Float
    let bbox: [Float]
    let trackId: Int?
    var contextualLabel: String? // e.g., "person (center)"
    
    enum CodingKeys: String, CodingKey {
        case label
        case confidence
        case bbox
        case trackId = "track_id"
        case contextualLabel = "contextual_label"
    }
}
