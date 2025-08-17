//
//  SettingsManager.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Manages app settings, preferences, and debug options for Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//

import Foundation
import Combine

class SettingsManager: ObservableObject {
    static let shared = SettingsManager()

    // Server Configuration
    @Published var serverHost: String {
        didSet { UserDefaults.standard.set(serverHost, forKey: UserDefaultsKeys.serverHost) }
    }
    @Published var serverPort: Int {
        didSet { UserDefaults.standard.set(serverPort, forKey: UserDefaultsKeys.serverPort) }
    }
    @Published var reconnectDelay: Double {
        didSet { UserDefaults.standard.set(reconnectDelay, forKey: "reconnectDelay") }
    }

    // Processing Mode
    @Published var processingMode: String {
        didSet { UserDefaults.standard.set(processingMode, forKey: UserDefaultsKeys.processingMode) }
    }

    // Camera & Detection
    @Published var showDetectionBoxes: Bool {
        didSet {
            UserDefaults.standard.set(showDetectionBoxes, forKey: "showDetectionBoxes")
            if !showDetectionBoxes {
                showDetectionLabels = false
            }
        }
    }
    @Published var showDetectionLabels: Bool {
        didSet { UserDefaults.standard.set(showDetectionLabels, forKey: UserDefaultsKeys.showLabels) }
    }

    // Debug Options
    @Published var enableNetworkLogging: Bool {
        didSet {
            DebugConfig.enableNetworkLogs = enableNetworkLogging
            UserDefaults.standard.set(enableNetworkLogging, forKey: "enableNetworkLogging")
        }
    }
    @Published var enableProcessingLogs: Bool {
        didSet {
            DebugConfig.enableProcessingLogs = enableProcessingLogs
            UserDefaults.standard.set(enableProcessingLogs, forKey: "enableProcessingLogs")
        }
    }
    @Published var enablePerformanceMetrics: Bool {
        didSet {
            DebugConfig.enablePerformanceMetrics = enablePerformanceMetrics
            UserDefaults.standard.set(enablePerformanceMetrics, forKey: "enablePerformanceMetrics")
        }
    }
    @Published var enableWebsocketDebug: Bool {
        didSet {
            WebSocketManager.enableLogging = enableWebsocketDebug
            UserDefaults.standard.set(enableWebsocketDebug, forKey: "enableWebsocketDebug")
        }
    }

    private init() {
        // Server Configuration
        self.serverHost = UserDefaults.standard.string(forKey: UserDefaultsKeys.serverHost) ?? ServerConfig.host
        self.serverPort = UserDefaults.standard.object(forKey: UserDefaultsKeys.serverPort) as? Int ?? ServerConfig.port
        self.reconnectDelay = UserDefaults.standard.double(forKey: "reconnectDelay")
        self.processingMode = UserDefaults.standard.string(forKey: UserDefaultsKeys.processingMode) ?? "split" // Default to split

        // Camera & Detection
        self.showDetectionBoxes = UserDefaults.standard.bool(forKey: "showDetectionBoxes")
        self.showDetectionLabels = UserDefaults.standard.bool(forKey: UserDefaultsKeys.showLabels)

        // Debug Options
        self.enableNetworkLogging = UserDefaults.standard.bool(forKey: "enableNetworkLogging")
        self.enableProcessingLogs = UserDefaults.standard.bool(forKey: "enableProcessingLogs")
        self.enablePerformanceMetrics = UserDefaults.standard.bool(forKey: "enablePerformanceMetrics")
        self.enableWebsocketDebug = UserDefaults.standard.bool(forKey: "enableWebsocketDebug")

        // Set initial values
        DebugConfig.enableNetworkLogs = enableNetworkLogging
        DebugConfig.enableProcessingLogs = enableProcessingLogs
        DebugConfig.enablePerformanceMetrics = enablePerformanceMetrics
        WebSocketManager.enableLogging = enableWebsocketDebug
    }
}
