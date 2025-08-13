//
//  AuthManager.swift
//  Orion
//
//  Created by Riddhiman Rana on 7/22/25.
//  Authentication manager for Orion Live, handling user sessions and OAuth.
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
            do {
                let currentSession = try await supabase.auth.session
                DispatchQueue.main.async {
                    self.session = currentSession
                }
            } catch {
                Logger.shared.log("Error fetching initial session: \(error.localizedDescription)", level: .error, category: .general)
            }
        }
    }

    private func setupAuthListener() {
        // Listen for auth state changes
        Task {
            authChangeListener = await supabase.auth.onAuthStateChange { [weak self] event, session in
                DispatchQueue.main.async {
                    self?.session = session
                }
            }
        }
    }

        // MARK: - OAuth Sign In
        func signInWithProvider(_ provider: Provider) async {
            isLoading = true
            defer { isLoading = false }

            do {
                try await supabase.auth.signInWithOAuth(
                provider: provider,
                redirectTo: URL(string: "orionauth://auth/mobile-auth-callback")!
            )
        } catch {
            Logger.shared.log("Error signing in with \(provider.rawValue): \(error.localizedDescription)", level: .error, category: .general)
        }
        }

        // MARK: - Web Sign In/Up
        func openWebSignIn() {
            guard var urlComponents = URLComponents(string: "https://orionlive.ai/login") else { return }
            urlComponents.queryItems = [URLQueryItem(name: "redirectTo", value: "orionauth://auth/mobile-auth-callback")]
            guard let url = urlComponents.url else { return }
            startWebAuthenticationSession(url: url)
        }

        func openWebSignUp() {
            guard var urlComponents = URLComponents(string: "https://orionlive.ai/signup") else { return }
            urlComponents.queryItems = [URLQueryItem(name: "redirectTo", value: "orionauth://auth/mobile-auth-callback")]
            guard let url = urlComponents.url else { return }
            startWebAuthenticationSession(url: url)
        }

        private func startWebAuthenticationSession(url: URL) {
            Logger.shared.log("Starting web auth session with URL: \(url.absoluteString)", level: .info, category: .general)

            webAuthSession = ASWebAuthenticationSession(url: url, callbackURLScheme: "orionauth") { [weak self] callbackURL, error in
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
                DispatchQueue.main.async {
                    self.webAuthSession = nil
                }
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
                    return
                }

                do {
                    try await supabase.auth.setSession(accessToken: accessToken, refreshToken: refreshToken)
                    Logger.shared.log("Session successfully set from URL fragment.", level: .info, category: .general)
                } catch {
                    Logger.shared.log("Error setting session from URL fragment: \(error.localizedDescription)", level: .error, category: .general)
                }
                return
            }

            // Check for query parameters (backup method)
            guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
                  let queryItems = components.queryItems else {
                Logger.shared.log("Error: No query items found in URL", level: .error, category: .general)
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
                }
            } else {
                Logger.shared.log("Error: No tokens found in query parameters. Available params: \(params)", level: .error, category: .general)
            }
        }

        // MARK: - Sign Out
        func signOut() async {
            isLoading = true
            defer { isLoading = false }
            do {
                try await supabase.auth.signOut()
            } catch {
                Logger.shared.log("Error signing out: \(error.localizedDescription)", level: .error, category: .general)
            }
        }
    }

extension AuthManager: ASWebAuthenticationPresentationContextProviding {
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        return ASPresentationAnchor()
    }
}
