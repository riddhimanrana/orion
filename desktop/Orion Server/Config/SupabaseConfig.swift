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
    static let anonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN2bHRlZnBsY3RpbnlrZWJlY3l2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjE2Njg5NzIsImV4cCI6MjAzNzI0NDk3Mn0.sb_publishable_xbZg9iawNirb6uCt5mw6ZA_FI9dttqk"
    
    // Method to get config from Info.plist with fallback
    static func getSupabaseURL() -> String {
        if let url = Bundle.main.infoDictionary?["SUPABASE_URL"] as? String,
           !url.isEmpty && !url.contains("YOUR_") {
            return url
        }
        return SupabaseConfig.url
    }
    
    static func getSupabaseAnonKey() -> String {
        if let key = Bundle.main.infoDictionary?["SUPABASE_ANON_KEY"] as? String,
           !key.isEmpty && !key.contains("YOUR_") {
            return key
        }
        return SupabaseConfig.anonKey
    }
}
