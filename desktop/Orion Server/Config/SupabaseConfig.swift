//
//  SupabaseConfig.swift
//  Orion Server
//
//  Created by Riddhiman Rana on 8/9/25.
//  Supabase configuration - backup approach if Info.plist doesn't work
//

import Foundation

struct SupabaseConfig {
    // If Info.plist approach doesn't work, you can temporarily use these constants:
    static let url = "https://svltefplctinykebecyv.supabase.co"
    static let publishableKey = "sb_publishable_xbZg9iawNirb6uCt5mw6ZA_FI9dttqk"

    // Method to get config from Info.plist with fallback
    static func getSupabaseURL() -> String {
        if let url = Bundle.main.infoDictionary?["SUPABASE_URL"] as? String,
           !url.isEmpty && !url.contains("YOUR_") {
            return url
        }
        return SupabaseConfig.url
    }

    static func getSupabasePublishableKey() -> String {
        if let key = Bundle.main.infoDictionary?["SUPABASE_PUBLISHABLE_KEY"] as? String,
           !key.isEmpty && !key.contains("YOUR_") {
            return key
        }
        if let key = Bundle.main.infoDictionary?["SUPABASE_ANON_KEY"] as? String,
           !key.isEmpty && !key.contains("YOUR_") {
            return key
        }
        return SupabaseConfig.publishableKey
    }
}
