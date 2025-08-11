//
//  AuthManager.swift
//  Orion Server
//
//  Created by Riddhiman Rana on 8/9/25.
//  Authentication manager for Orion Server, handling user sessions and OAuth.
//

import Foundation
import Supabase
import Combine
import SwiftUI
import AuthenticationServices

@MainActor
class AuthManager: NSObject, ObservableObject {
    @Published var session: Session?
    @Published var isLoading = false

    private var cancellables = Set<AnyCancellable>()
    private var authChangeListener: AuthStateChangeListenerRegistration?
    private var webAuthSession: ASWebAuthenticationSession?

    var supabase: SupabaseClient!

    override init() {
        super.init()
        
        // Debug: Print all available Info.plist keys
        if let infoPlist = Bundle.main.infoDictionary {
            print("Available Info.plist keys: \(infoPlist.keys)")
        } else {
            print("No Info.plist found in main bundle")
        }
        
        // Try multiple approaches to read the Info.plist
        var supabaseURLString: String?
        var supabaseAnonKey: String?
        
        // Approach 1: Direct from Bundle
        if let infoDictionary = Bundle.main.infoDictionary {
            supabaseURLString = infoDictionary["SUPABASE_URL"] as? String
            supabaseAnonKey = infoDictionary["SUPABASE_ANON_KEY"] as? String
            print("Approach 1 - Bundle.main.infoDictionary:")
            print("  SUPABASE_URL: \(supabaseURLString ?? "NOT FOUND")")
            print("  SUPABASE_ANON_KEY: \(supabaseAnonKey ?? "NOT FOUND")")
        }
        
        // Approach 2: Direct from plist file path
        if supabaseURLString == nil || supabaseAnonKey == nil {
            if let plistPath = Bundle.main.path(forResource: "Info", ofType: "plist"),
               let plistData = NSDictionary(contentsOfFile: plistPath) {
                supabaseURLString = plistData["SUPABASE_URL"] as? String
                supabaseAnonKey = plistData["SUPABASE_ANON_KEY"] as? String
                print("Approach 2 - Direct plist file:")
                print("  SUPABASE_URL: \(supabaseURLString ?? "NOT FOUND")")
                print("  SUPABASE_ANON_KEY: \(supabaseAnonKey ?? "NOT FOUND")")
            }
        }
        
        // Approach 3: Read from embedded plist
        if supabaseURLString == nil || supabaseAnonKey == nil {
            if let url = Bundle.main.url(forResource: "Info", withExtension: "plist"),
               let data = try? Data(contentsOf: url),
               let plist = try? PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any] {
                supabaseURLString = plist["SUPABASE_URL"] as? String
                supabaseAnonKey = plist["SUPABASE_ANON_KEY"] as? String
                print("Approach 3 - PropertyListSerialization:")
                print("  SUPABASE_URL: \(supabaseURLString ?? "NOT FOUND")")
                print("  SUPABASE_ANON_KEY: \(supabaseAnonKey ?? "NOT FOUND")")
            }
        }
        
        // Validate we got the values
        guard let finalURLString = supabaseURLString,
              !finalURLString.isEmpty,
              !finalURLString.contains("YOUR_") else {
            fatalError("SUPABASE_URL not found in Info.plist. Make sure the Info.plist file is properly included in your app bundle.")
        }
        
        guard let finalAnonKey = supabaseAnonKey,
              !finalAnonKey.isEmpty,
              !finalAnonKey.contains("YOUR_") else {
            fatalError("SUPABASE_ANON_KEY not found in Info.plist. Make sure the Info.plist file is properly included in your app bundle.")
        }
        
        guard let supabaseURL = URL(string: finalURLString) else {
            fatalError("Invalid SUPABASE_URL format: \(finalURLString)")
        }
        
        print("✅ Successfully loaded Supabase credentials from Info.plist:")
        print("- URL: \(finalURLString)")
        print("- Key: \(String(finalAnonKey.prefix(20)))...")
        
        self.supabase = SupabaseClient(supabaseURL: supabaseURL, supabaseKey: finalAnonKey)

        setupAuthListener()

        // Fetch current session on launch to get latest user metadata
        Task {
            do {
                let currentSession = try await supabase.auth.session
                DispatchQueue.main.async {
                    self.session = currentSession
                    print("Found existing session for user: \(currentSession.user.email ?? "unknown")")
                }
            } catch {
                print("No existing session found: \(error.localizedDescription)")
            }
        }
    }

    private func setupAuthListener() {
        // Listen for auth state changes
        Task {
            authChangeListener = await supabase.auth.onAuthStateChange { [weak self] event, session in
                DispatchQueue.main.async {
                    self?.session = session
                    if let session = session {
                        print("Auth state changed - User logged in: \(session.user.email ?? "unknown")")
                    } else {
                        print("Auth state changed - User logged out")
                    }
                }
            }
        }
    }

    // MARK: - OAuth Sign In
    func signInWithProvider(_ provider: Provider) async {
        isLoading = true
        defer { isLoading = false }

        print("Starting OAuth sign in with \(provider.rawValue)")

        do {
            try await supabase.auth.signInWithOAuth(
                provider: provider,
                redirectTo: URL(string: "orionauth://auth/mobile-auth-callback")!
            )
            print("OAuth sign in initiated successfully")
        } catch {
            print("Error signing in with \(provider.rawValue): \(error.localizedDescription)")
        }
    }

    // MARK: - Web Sign In/Up
    func openWebSignIn() {
        guard var urlComponents = URLComponents(string: "https://orionlive.ai/login") else { 
            print("Failed to create URL components for login")
            return 
        }
        urlComponents.queryItems = [URLQueryItem(name: "redirectTo", value: "orionauth://auth/mobile-auth-callback")]
        guard let url = urlComponents.url else { 
            print("Failed to create login URL")
            return 
        }
        print("Opening web sign in URL: \(url.absoluteString)")
        startWebAuthenticationSession(url: url)
    }

    func openWebSignUp() {
        guard var urlComponents = URLComponents(string: "https://orionlive.ai/signup") else { 
            print("Failed to create URL components for signup")
            return 
        }
        urlComponents.queryItems = [URLQueryItem(name: "redirectTo", value: "orionauth://auth/mobile-auth-callback")]
        guard let url = urlComponents.url else { 
            print("Failed to create signup URL")
            return 
        }
        print("Opening web sign up URL: \(url.absoluteString)")
        startWebAuthenticationSession(url: url)
    }

    private func startWebAuthenticationSession(url: URL) {
        print("Starting web authentication session with URL: \(url.absoluteString)")

        webAuthSession = ASWebAuthenticationSession(url: url, callbackURLScheme: "orionauth") { [weak self] callbackURL, error in
            guard let self = self else { return }

            if let error = error {
                // Check if the error is user cancellation (this is expected behavior)
                if let authError = error as? ASWebAuthenticationSessionError,
                   authError.code == .canceledLogin {
                    print("Web authentication session was cancelled by user")
                } else {
                    print("Web authentication session failed: \(error.localizedDescription)")
                }
                return
            }

            guard let callbackURL = callbackURL else {
                print("Web authentication session completed but no callback URL received")
                return
            }

            print("Web auth session completed with callback URL: \(callbackURL.absoluteString)")

            Task {
                await self.handleSessionCallback(from: callbackURL)
            }
        }

        // This ensures the web view is presented modally and can be dismissed properly
        webAuthSession?.presentationContextProvider = self
        webAuthSession?.prefersEphemeralWebBrowserSession = false // Allow cookies for better UX

        if !webAuthSession!.start() {
            print("Failed to start web authentication session")
            webAuthSession = nil
        }
    }

    // MARK: - Session Management
    func handleSessionCallback(from url: URL) async {
        isLoading = true
        defer {
            isLoading = false
            // Clean up the web auth session after handling the callback
            DispatchQueue.main.async {
                self.webAuthSession = nil
            }
        }

        print("Handling session callback from URL: \(url.absoluteString)")

        // Check if we have URL fragment (hash) for tokens
        if let fragment = url.fragment, !fragment.isEmpty {
            print("Found URL fragment: \(fragment)")

            let params = fragment
                .split(separator: "&")
                .map { $0.split(separator: "=", maxSplits: 1) }
                .reduce(into: [String: String]()) { dict, pair in
                    if pair.count == 2 {
                        let key = String(pair[0])
                        let value = String(pair[1]).removingPercentEncoding ?? String(pair[1])
                        dict[key] = value
                    }
                }

            guard let accessToken = params["access_token"],
                  let refreshToken = params["refresh_token"] else {
                print("Error: Tokens not found in URL fragment. Available params: \(params)")
                return
            }

            do {
                try await supabase.auth.setSession(accessToken: accessToken, refreshToken: refreshToken)
                print("Session successfully set from URL fragment.")
            } catch {
                print("Error setting session from URL fragment: \(error.localizedDescription)")
            }
            return
        }

        // Check for query parameters (backup method)
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let queryItems = components.queryItems else {
            print("Error: No query items found in URL")
            return
        }

        let params = queryItems.reduce(into: [String: String]()) { dict, item in
            dict[item.name] = item.value
        }

        if let accessToken = params["access_token"],
           let refreshToken = params["refresh_token"] {
            do {
                try await supabase.auth.setSession(accessToken: accessToken, refreshToken: refreshToken)
                print("Session successfully set from query parameters.")
            } catch {
                print("Error setting session from query parameters: \(error.localizedDescription)")
            }
        } else {
            print("Error: No tokens found in query parameters. Available params: \(params)")
        }
    }

    // MARK: - Sign Out
    func signOut() async {
        isLoading = true
        defer { isLoading = false }
        
        print("Signing out user")
        do {
            try await supabase.auth.signOut()
            print("Successfully signed out")
        } catch {
            print("Error signing out: \(error.localizedDescription)")
        }
    }
}

extension AuthManager: ASWebAuthenticationPresentationContextProviding {
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        return NSApplication.shared.keyWindow ?? ASPresentationAnchor()
    }
}
