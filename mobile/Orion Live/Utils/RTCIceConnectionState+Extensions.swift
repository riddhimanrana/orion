//
//  RTCIceConnectionState+Extensions.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 8/16/25.
//  Extensions for WebRTC types to provide user-friendly descriptions.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//

import Foundation
import WebRTC

// MARK: - RTCIceConnectionState Extension
extension RTCIceConnectionState {
    var displayDescription: String {
        switch self {
        case .new:
            return "New"
        case .checking:
            return "Checking"
        case .connected:
            return "Connected"
        case .completed:
            return "Completed"
        case .failed:
            return "Failed"
        case .disconnected:
            return "Disconnected"
        case .closed:
            return "Closed"
        case .count:
            return "Count"
        @unknown default:
            return "Unknown"
        }
    }
}
