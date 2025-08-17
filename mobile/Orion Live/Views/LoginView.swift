//
//  LoginView.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Login and authentication view for Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//

import SwiftUI
internal import Auth

struct LoginView: View {
    @Environment(\.colorScheme) var colorScheme
    @EnvironmentObject var authManager: AuthManager

    var body: some View {
        ZStack {
            Color(UIColor.systemBackground).edgesIgnoringSafeArea(.all)

            VStack(spacing: 20) {
                Spacer()

                VStack(spacing: 8) {
                    Text("Orion Live")
                        .font(.system(size: 48, weight: .bold))
                        .foregroundColor(.primary)
                    Text("Real-time visual intelligence at speed.")
                        .font(.system(size: 18, weight: .regular))
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 40)
                }

                Spacer()

                // Auth Buttons
                VStack(spacing: 10) {
                    Button(action: { Task { await authManager.signInWithProvider(.google) } }) {
                        HStack {
                            Image("google_logo") // Make sure to add this asset
                                .resizable()
                                .scaledToFit()
                                .frame(width: 24, height: 24)
                            Text("Continue with Google")
                        }
                    }
                    .buttonStyle(InvertedPrimaryButtonStyle())

                    Button(action: { Task { await authManager.signInWithProvider(.github) } }) {
                        HStack {
                            Image(colorScheme == .dark ? "github_logo_dark" : "github_logo_light") // Make sure to add these assets
                                .resizable()
                                .scaledToFit()
                                .frame(width: 24, height: 24)
                            Text("Continue with GitHub")
                        }
                    }
                    .buttonStyle(SecondaryButtonStyle())

                    Button("Sign Up") { authManager.openWebSignUp() }
                        .buttonStyle(SecondaryButtonStyle())

                    Button("Log In") { authManager.openWebSignIn() }
                        .buttonStyle(OutlineButtonStyle())
                }
            }
            .padding()
        }
    }
}

struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundColor(.primary)
            .frame(maxWidth: .infinity)
            .padding()
            .background(Color(UIColor.secondarySystemBackground))
            .cornerRadius(12)
            .opacity(configuration.isPressed ? 0.8 : 1.0)
            .scaleEffect(configuration.isPressed ? 0.97 : 1.0)
    }
}

struct InvertedPrimaryButtonStyle: ButtonStyle {
    @Environment(\.colorScheme) var colorScheme

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundColor(colorScheme == .dark ? .black : .white)
            .frame(maxWidth: .infinity)
            .padding()
            .background(colorScheme == .dark ? Color.white : Color.black)
            .cornerRadius(12)
            .opacity(configuration.isPressed ? 0.8 : 1.0)
            .scaleEffect(configuration.isPressed ? 0.97 : 1.0)
    }
}

struct LoginView_Previews: PreviewProvider {
    static var previews: some View {
        LoginView()
            .environmentObject(AuthManager())
    }
}

struct OutlineButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundColor(.primary)
            .frame(maxWidth: .infinity)
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color(UIColor.tertiarySystemBackground))  // background fill below stroke
            )
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color(UIColor.secondarySystemBackground), lineWidth: 2)
            )
            .opacity(configuration.isPressed ? 0.6 : 1.0)
            .scaleEffect(configuration.isPressed ? 0.97 : 1.0)
    }
}
