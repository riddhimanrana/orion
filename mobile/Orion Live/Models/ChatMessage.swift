//
//  ChatMessage.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 8/18/25.
//  Models for chat message handling in Orion Live.
//

import Foundation

struct ChatMessage: Identifiable, Hashable {
    let id: UUID
    let content: String
    let isFromUser: Bool
    let timestamp: Date

    init(id: UUID = UUID(), content: String, isFromUser: Bool, timestamp: Date = Date()) {
        self.id = id
        self.content = content
        self.isFromUser = isFromUser
        self.timestamp = timestamp
    }
}

// Extension for mock responses
extension ChatMessage {
    static let orionGreeting = "Hello, I am Orion, a helpful assistant ready to help you scan your surroundings."
    
    static func createOrionResponse() -> ChatMessage {
        return ChatMessage(content: orionGreeting, isFromUser: false)
    }
}