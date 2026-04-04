//
//  AuthManager.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Authentication manager for Orion Live, handling user sessions and OAuth.
//

import Foundation
import Supabase
import Combine
import SwiftUI
@preconcurrency import AuthenticationServices

@MainActor
class AuthManager: NSObject, ObservableObject {
    @Published var session: Session?
    @Published var isLoading = false
    @Published var isInitializing = true // Add this to track initial session check
    @Published var isOffline = false // Track offline state

    private var cancellables = Set<AnyCancellable>()
    private var authChangeListener: AuthStateChangeListenerRegistration?
    private var webAuthSession: ASWebAuthenticationSession?
    private var refreshTimer: Timer?

    var supabase: SupabaseClient!

    // MARK: - Cleanup handlers
    var onSignOut: (() -> Void)?

    override init() {
        super.init()
        guard let supabaseURLString = Bundle.main.infoDictionary?["SUPABASE_URL"] as? String else {
            fatalError("SUPABASE_URL not found in Info.plist. Please add your Supabase project URL.")
        }
        guard let supabaseAnonKey = Bundle.main.infoDictionary?["SUPABASE_ANON_KEY"] as? String else {
            fatalError("SUPABASE_ANON_KEY not found in Info.plist. Please add your Supabase anon key.")
        }
        guard supabaseURLString != "[your_supabase_url]" else {
            fatalError("Please replace the placeholder SUPABASE_URL in Info.plist with your actual Supabase project URL")
        }
        guard supabaseAnonKey != "[your_supabase_anon_key]" else {
            fatalError("Please replace the placeholder SUPABASE_ANON_KEY in Info.plist with your actual Supabase anon key")
        }
        guard let supabaseURL = URL(string: supabaseURLString) else {
            fatalError("Invalid SUPABASE_URL in Info.plist: \(supabaseURLString)")
        }

        self.supabase = SupabaseClient(supabaseURL: supabaseURL, supabaseKey: supabaseAnonKey)

        setupAuthListener()

        // Fetch current session on launch to get latest user metadata
        Task {
            await fetchInitialSession()
        }
    }

    private func setupAuthListener() {
        // Listen for auth state changes
        Task {
            authChangeListener = await supabase.auth.onAuthStateChange { [weak self] event, session in
                Task { @MainActor in
                    guard let self = self else { return }
                    self.session = session
                    // Use auth event to drive timer rather than nil checks
                    switch event {
                    case .signedIn, .tokenRefreshed, .userUpdated:
                        self.startTokenRefreshTimer()
                    case .signedOut, .userDeleted:
                        self.stopTokenRefreshTimer()
                    default:
                        break
                    }
                }
            }
        }
    }
    
    // MARK: - Network-Resilient Session Management
    private func fetchInitialSession() async {
        do {
            let fetchedSession = try await supabase.auth.session
            await MainActor.run {
                self.session = fetchedSession
                self.isOffline = false
                self.isInitializing = false
                
                // We successfully fetched a session, start the refresh timer
                self.startTokenRefreshTimer()
            }
        } catch {
            Logger.shared.log("Error fetching initial session: \(error.localizedDescription)", level: .error, category: .general)
            
            // Check if this is a network error
            if isNetworkError(error) {
                await MainActor.run {
                    self.isOffline = true
                    self.isInitializing = false
                    // Don't show toast during initialization - app should still open
                }
            } else {
                await MainActor.run {
                    self.isInitializing = false
                    ToastManager.shared.showAuthError("Authentication initialization failed: \(error.localizedDescription)")
                }
            }
        }
    }
    
    // MARK: - Token Refresh Management
    private func startTokenRefreshTimer() {
        stopTokenRefreshTimer() // Clean up any existing timer

        // Refresh token every 20 hours (before the typical 24-hour expiry)
        let interval: TimeInterval = 20 * 60 * 60

        refreshTimer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { [weak self] _ in
            Task {
                await self?.refreshSessionIfNeeded()
            }
        }
    }
    
    private func stopTokenRefreshTimer() {
        refreshTimer?.invalidate()
        refreshTimer = nil
    }
    
    private func refreshSessionIfNeeded() async {
        do {
            let refreshedSession = try await supabase.auth.refreshSession()
            await MainActor.run {
                self.session = refreshedSession
                self.isOffline = false
            }
            Logger.shared.log("Session refreshed successfully", level: .info, category: .general)
        } catch {
            Logger.shared.log("Failed to refresh session: \(error.localizedDescription)", level: .error, category: .general)
            
            if isNetworkError(error) {
                await MainActor.run {
                    self.isOffline = true
                    ToastManager.shared.showNetworkError("Connection lost. Some features may be unavailable.")
                }
            } else {
                // If refresh fails due to invalid token, user needs to re-authenticate
                await MainActor.run {
                    ToastManager.shared.showAuthError("Session expired. Please sign in again.")
                }
                await signOut()
            }
        }
    }
    
    // MARK: - Network Error Detection
    private func isNetworkError(_ error: Error) -> Bool {
        let errorString = error.localizedDescription.lowercased()
        return errorString.contains("network") ||
               errorString.contains("internet") ||
               errorString.contains("offline") ||
               errorString.contains("connection") ||
               errorString.contains("timeout") ||
               errorString.contains("unreachable") ||
               (error as NSError).domain.contains("NSURLError")
    }

        // MARK: - OAuth Sign In
        func signInWithProvider(_ provider: Provider) async {
            isLoading = true
            defer { isLoading = false }

            do {
                try await supabase.auth.signInWithOAuth(
                provider: provider,
                redirectTo: URL(string: "orion://auth/native-auth-callback")!
            )
        } catch {
            Logger.shared.log("Error signing in with \(provider.rawValue): \(error.localizedDescription)", level: .error, category: .general)
            
            if isNetworkError(error) {
                ToastManager.shared.showNetworkError("Cannot connect to authentication service. Please check your internet connection.")
            } else {
                ToastManager.shared.showAuthError("Sign in failed: \(error.localizedDescription)")
            }
        }
        }

        // MARK: - Web Sign In/Up
        func openWebSignIn() {
            guard var urlComponents = URLComponents(string: "https://orionlive.ai/login") else { 
                ToastManager.shared.showAuthError("Invalid authentication URL")
                return 
            }
            urlComponents.queryItems = [URLQueryItem(name: "redirectTo", value: "orion://auth/native-auth-callback")]
            guard let url = urlComponents.url else { 
                ToastManager.shared.showAuthError("Invalid authentication URL")
                return 
            }
            startWebAuthenticationSession(url: url)
        }

        func openWebSignUp() {
            guard var urlComponents = URLComponents(string: "https://orionlive.ai/signup") else { 
                ToastManager.shared.showAuthError("Invalid authentication URL")
                return 
            }
            urlComponents.queryItems = [URLQueryItem(name: "redirectTo", value: "orion://auth/native-auth-callback")]
            guard let url = urlComponents.url else { 
                ToastManager.shared.showAuthError("Invalid authentication URL")
                return 
            }
            startWebAuthenticationSession(url: url)
        }

        private func startWebAuthenticationSession(url: URL) {
            Logger.shared.log("Starting web auth session with URL: \(url.absoluteString)", level: .info, category: .general)

            webAuthSession = ASWebAuthenticationSession(url: url, callbackURLScheme: "orion") { [weak self] callbackURL, error in
                guard let self = self else { return }

                if let error = error {
                    // Check if the error is user cancellation (this is expected behavior)
                    if let authError = error as? ASWebAuthenticationSessionError,
                       authError.code == .canceledLogin {
                        Logger.shared.log("Web authentication session was cancelled by user", level: .info, category: .general)
                    } else {
                        Logger.shared.log("Web authentication session failed: \(error.localizedDescription)", level: .error, category: .general)
                    }
                    return
                }

                guard let callbackURL = callbackURL else {
                    Logger.shared.log("Web authentication session completed but no callback URL received", level: .error, category: .general)
                    return
                }

                Logger.shared.log("Web auth session completed with callback URL: \(callbackURL.absoluteString)", level: .info, category: .general)

                Task {
                    await self.handleSessionCallback(from: callbackURL)
                }
            }

            // This ensures the web view is presented modally and can be dismissed properly
            webAuthSession?.presentationContextProvider = self
            webAuthSession?.prefersEphemeralWebBrowserSession = false // Allow cookies for better UX

            if !webAuthSession!.start() {
                Logger.shared.log("Failed to start web authentication session", level: .error, category: .general)
                webAuthSession = nil
            }
        }

        // MARK: - Session Management
        func handleSessionCallback(from url: URL) async {
            isLoading = true
            defer {
                isLoading = false
                // Clean up the web auth session after handling the callback
                self.webAuthSession = nil
            }

            Logger.shared.log("Handling session callback from URL: \(url.absoluteString)", level: .info, category: .general)

            // Check if we have URL fragment (hash) for tokens
            if let fragment = url.fragment, !fragment.isEmpty {
                Logger.shared.log("Found URL fragment: \(fragment)", level: .info, category: .general)

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
                    Logger.shared.log("Error: Tokens not found in URL fragment. Available params: \(params)", level: .error, category: .general)
                    ToastManager.shared.showAuthError("Authentication tokens not found in callback")
                    return
                }

                do {
                    try await supabase.auth.setSession(accessToken: accessToken, refreshToken: refreshToken)
                    Logger.shared.log("Session successfully set from URL fragment.", level: .info, category: .general)
                } catch {
                    Logger.shared.log("Error setting session from URL fragment: \(error.localizedDescription)", level: .error, category: .general)
                    if isNetworkError(error) {
                        ToastManager.shared.showNetworkError("Failed to complete authentication due to network issues")
                    } else {
                        ToastManager.shared.showAuthError("Failed to set authentication session: \(error.localizedDescription)")
                    }
                }
                return
            }

            // Check for query parameters (backup method)
            guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
                  let queryItems = components.queryItems else {
                Logger.shared.log("Error: No query items found in URL", level: .error, category: .general)
                ToastManager.shared.showAuthError("Invalid authentication callback URL")
                return
            }

            let params = queryItems.reduce(into: [String: String]()) { dict, item in
                dict[item.name] = item.value
            }

            if let accessToken = params["access_token"],
               let refreshToken = params["refresh_token"] {
                do {
                    try await supabase.auth.setSession(accessToken: accessToken, refreshToken: refreshToken)
                    Logger.shared.log("Session successfully set from query parameters.", level: .info, category: .general)
                } catch {
                    Logger.shared.log("Error setting session from query parameters: \(error.localizedDescription)", level: .error, category: .general)
                    if isNetworkError(error) {
                        ToastManager.shared.showNetworkError("Failed to complete authentication due to network issues")
                    } else {
                        ToastManager.shared.showAuthError("Failed to set authentication session: \(error.localizedDescription)")
                    }
                }
            } else {
                Logger.shared.log("Error: No tokens found in query parameters. Available params: \(params)", level: .error, category: .general)
                ToastManager.shared.showAuthError("Authentication tokens not found in callback URL")
            }
        }

        // MARK: - Sign Out
        func signOut() async {
            isLoading = true
            
            // Stop the refresh timer
            stopTokenRefreshTimer()
            
            // Call cleanup handlers before signing out
            onSignOut?()
            
            do {
                try await supabase.auth.signOut()
            } catch {
                Logger.shared.log("Error signing out: \(error.localizedDescription)", level: .error, category: .general)
                // Even if sign out fails on server, clear local session
                await MainActor.run {
                    self.session = nil
                }
            }
            
            // Ensure UI updates happen after cleanup
            await MainActor.run {
                isLoading = false
            }
        }
    
    deinit {
        // Clean up auth listener, web session, and timer
        authChangeListener?.remove()
        webAuthSession?.cancel()
        refreshTimer?.invalidate()
        refreshTimer = nil
        cancellables.removeAll()
    }
}

extension AuthManager: ASWebAuthenticationPresentationContextProviding {
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        return ASPresentationAnchor()
    }
}
