//
//  SecureStore.swift
//  Orion Live
//
//  Created by Copilot on 9/19/25.
//  Simple Keychain wrapper for securely storing small secrets like API keys.
//

import Foundation
import Security

enum SecureStoreError: Error, LocalizedError {
    case unexpectedStatus(OSStatus)
    case stringEncoding

    var errorDescription: String? {
        switch self {
        case .unexpectedStatus(let status):
            return "Keychain error (status: \(status))"
        case .stringEncoding:
            return "Failed to encode/decode string for Keychain"
        }
    }
}

struct SecureStore {
    let service: String

    init(service: String = "ai.orion.live") {
        self.service = service
    }

    func set(_ value: String, forKey key: String, accessGroup: String? = nil) throws {
        guard let data = value.data(using: .utf8) else { throw SecureStoreError.stringEncoding }

        // Delete any existing item first
        try? delete(forKey: key, accessGroup: accessGroup)

        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecValueData as String: data
        ]
        if let group = accessGroup { query[kSecAttrAccessGroup as String] = group }

        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else { throw SecureStoreError.unexpectedStatus(status) }
    }

    func get(_ key: String, accessGroup: String? = nil) throws -> String? {
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        if let group = accessGroup { query[kSecAttrAccessGroup as String] = group }

        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess else { throw SecureStoreError.unexpectedStatus(status) }

        guard let data = item as? Data, let string = String(data: data, encoding: .utf8) else {
            throw SecureStoreError.stringEncoding
        }
        return string
    }

    func delete(forKey key: String, accessGroup: String? = nil) throws {
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key
        ]
        if let group = accessGroup { query[kSecAttrAccessGroup as String] = group }
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else { throw SecureStoreError.unexpectedStatus(status) }
    }
}
