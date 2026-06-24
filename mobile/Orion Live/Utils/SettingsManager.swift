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

    // Connection Mode ("direct" or "webrtc")
    @Published var connectionMode: String {
        didSet { UserDefaults.standard.set(connectionMode, forKey: "connectionMode") }
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

    // Chat
    @Published var showChatStats: Bool {
        didSet { UserDefaults.standard.set(showChatStats, forKey: "showChatStats") }
    }

    // LLM Routing
    // Values: "google", "openai", "proxy", "local"
    @Published var llmProvider: String {
        didSet { UserDefaults.standard.set(llmProvider, forKey: "llmProvider") }
    }
    // Model identifier string passed to providers (e.g., "gemini-2.5-flash-lite", "gpt-4o-mini", "gemma-3b")
    @Published var llmModel: String {
        didSet { UserDefaults.standard.set(llmModel, forKey: "llmModel") }
    }
    // URL for your hosted proxy/gateway (e.g., https://ai.orionlive.ai/v1/chat)
    @Published var llmProxyURL: String {
        didSet { UserDefaults.standard.set(llmProxyURL, forKey: "llmProxyURL") }
    }
    // URL for local Orion Server chat endpoint (e.g., http://orion-server.local:8787/v1/chat)
    @Published var llmLocalURL: String {
        didSet { UserDefaults.standard.set(llmLocalURL, forKey: "llmLocalURL") }
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
        self.processingMode = "server"
        UserDefaults.standard.set("server", forKey: UserDefaultsKeys.processingMode)
        self.connectionMode = UserDefaults.standard.string(forKey: "connectionMode") ?? "direct" // Default to direct

        // Camera & Detection
        self.showDetectionBoxes = UserDefaults.standard.bool(forKey: "showDetectionBoxes")
        self.showDetectionLabels = UserDefaults.standard.bool(forKey: UserDefaultsKeys.showLabels)

        // Chat
        self.showChatStats = UserDefaults.standard.bool(forKey: "showChatStats")

        // LLM Routing defaults from Info.plist where possible
        let info = Bundle.main.infoDictionary ?? [:]
        let providerDefault = (info["AI_PROVIDER"] as? String)?.lowercased() ?? "proxy"
        let providerValue = UserDefaults.standard.string(forKey: "llmProvider") ?? providerDefault
        let modelDefault = (info["AI_MODEL"] as? String) ?? (providerValue == "google" ? "gemini-2.5-flash-lite" : "gpt-4.1-mini")
        let modelValue = UserDefaults.standard.string(forKey: "llmModel") ?? modelDefault
        let proxyDefault = (info["AI_PROXY_URL"] as? String) ?? "https://ai.orionlive.ai/v1/chat"
        let proxyValue = UserDefaults.standard.string(forKey: "llmProxyURL") ?? proxyDefault
        let localDefault = (info["AI_LOCAL_URL"] as? String) ?? "http://orion-server.local:8787/v1/chat"
        let localValue = UserDefaults.standard.string(forKey: "llmLocalURL") ?? localDefault

        self.llmProvider = providerValue
        self.llmModel = modelValue
        self.llmProxyURL = proxyValue
        self.llmLocalURL = localValue

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
