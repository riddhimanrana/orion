//
//  LoginView.swift
//  Orion Server
//
//  Created by Riddhiman Rana on 8/9/25.
//  Login and authentication view for Orion Server.
//

import SwiftUI

struct LoginView: View {
    @Environment(\.colorScheme) var colorScheme
    @EnvironmentObject var authManager: AuthManager

    var body: some View {
        ZStack {
            // Background
            Color(red: 0.129, green: 0.129, blue: 0.129) // #212121
                .ignoresSafeArea()
            
            VStack(spacing: 60) {
                Spacer()
                
                // Orion Live branding
                VStack(spacing: 16) {
                    Text("Orion Live")
                        .font(.system(size: 48, weight: .bold))
                        .foregroundColor(.white)
                    
                    Text("Real-time visual intelligence\nat speed.")
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(.white.opacity(0.7))
                        .multilineTextAlignment(.center)
                        .lineSpacing(4)
                        .fixedSize(horizontal: false, vertical: true)
                }
                
                // Auth buttons container with fixed height
                VStack(spacing: 12) {
                    // Continue with Google
                    Button(action: {
                        Task { await authManager.signInWithProvider(.google) }
                    }) {
                        HStack(spacing: 12) {
                            Image("google-icon")
                                .resizable()
                                .frame(width: 18, height: 18)
                            Text("Continue with Google")
                                .font(.system(size: 15, weight: .medium))
                                .foregroundColor(.black)
                        }
                        .frame(height: 44)
                        .frame(maxWidth: .infinity)
                        .background(Color.white)
                        .cornerRadius(8)
                    }
                    .buttonStyle(PlainButtonStyle())
                    .disabled(authManager.isLoading)
                    
                    // Continue with GitHub
                    Button(action: {
                        Task { await authManager.signInWithProvider(.github) }
                    }) {
                        HStack(spacing: 12) {
                            Image("github-icon-light")
                                .resizable()
                                .frame(width: 18, height: 18)
                            Text("Continue with GitHub")
                                .font(.system(size: 15, weight: .medium))
                                .foregroundColor(.white)
                        }
                        .frame(height: 44)
                        .frame(maxWidth: .infinity)
                        .background(Color.white.opacity(0.15))
                        .cornerRadius(8)
                    }
                    .buttonStyle(PlainButtonStyle())
                    .disabled(authManager.isLoading)
                    
                    // Sign Up
                    Button(action: {
                        authManager.openWebSignUp()
                    }) {
                        Text("Sign Up")
                            .font(.system(size: 15, weight: .medium))
                            .foregroundColor(.white)
                            .frame(height: 44)
                            .frame(maxWidth: .infinity)
                            .background(Color.white.opacity(0.15))
                            .cornerRadius(8)
                    }
                    .buttonStyle(PlainButtonStyle())
                    .disabled(authManager.isLoading)
                    
                    // Log In
                    Button(action: {
                        authManager.openWebSignIn()
                    }) {
                        Text("Log In")
                            .font(.system(size: 15, weight: .medium))
                            .foregroundColor(.white)
                            .frame(height: 44)
                            .frame(maxWidth: .infinity)
                            .background(Color.white.opacity(0.2))
                            .cornerRadius(8)
                    }
                    .buttonStyle(PlainButtonStyle())
                    .disabled(authManager.isLoading)
                }
                .frame(width: 300)
                .padding(.horizontal, 30)
                
                Spacer()
            }
            
            // Loading indicator overlay (doesn't affect layout)
            if authManager.isLoading {
                VStack {
                    Spacer()
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        .scaleEffect(1.2)
                        .padding(.bottom, 40)
                }
            }
        }
    }
}

#Preview {
    LoginView()
        .environmentObject(AuthManager())
}
