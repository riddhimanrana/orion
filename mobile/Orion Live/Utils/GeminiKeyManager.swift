//
//  GeminiKeyManager.swift
//  Orion Live
//
//  Created by Copilot on 9/19/25.
//  Convenience wrapper around SecureStore for Gemini API key.
//

import Foundation
import Combine

final class GeminiKeyManager: ObservableObject {
    static let shared = GeminiKeyManager()

    private let secure = SecureStore()
    private let keyName = "gemini_api_key"

    @Published private(set) var hasKey: Bool = false

    private init() {
        hasKey = (try? secure.get(keyName))?.isEmpty == false
    }

    func saveKey(_ key: String) throws {
        let trimmed = key.trimmingCharacters(in: .whitespacesAndNewlines)
        try secure.set(trimmed, forKey: keyName)
        DispatchQueue.main.async { self.hasKey = !trimmed.isEmpty }
    }

    func readKey() -> String? {
        return try? secure.get(keyName)
    }

    func deleteKey() {
        try? secure.delete(forKey: keyName)
        DispatchQueue.main.async { self.hasKey = false }
    }
}
