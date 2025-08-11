//
//  ContentView.swift
//  Orion Server
//
//  Created by Riddhiman Rana on 7/16/25.
//

import SwiftUI

struct ContentView: View {
    @Environment(\.colorScheme) var colorScheme
    
    var body: some View {
        VStack(spacing: 40) {
            Spacer()
            
            // Main title and tagline
            VStack(spacing: 16) {
                Text("Orion Server")
                    .font(.system(size: 48, weight: .bold, design: .default))
                    .foregroundColor(colorScheme == .dark ? .white : .black)
                
                Text("Real-time visual intelligence\nat speed.")
                    .font(.system(size: 18, weight: .medium))
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .lineSpacing(4)
            }
            
            Spacer()
            
            // Auth buttons
            VStack(spacing: 16) {
                // Continue with Google
                Button(action: {
                    // TODO: Implement Google auth
                }) {
                    HStack(spacing: 12) {
                        Image("google-icon") // You'll need to add this to Assets
                            .resizable()
                            .frame(width: 20, height: 20)
                        Text("Continue with Google")
                            .font(.system(size: 16, weight: .medium))
                            .foregroundColor(.black)
                    }
                    .frame(width: 280, height: 50)
                    .background(Color.white)
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color.gray.opacity(0.3), lineWidth: 1)
                    )
                    .cornerRadius(12)
                }
                .buttonStyle(PlainButtonStyle())
                .onHover { isHovered in
                    // Add hover effect if needed
                }
                
                // Continue with GitHub
                Button(action: {
                    // TODO: Implement GitHub auth
                }) {
                    HStack(spacing: 12) {
                        Image(colorScheme == .dark ? "github-icon-dark" : "github-icon-light") // You'll need to add these to Assets
                            .resizable()
                            .frame(width: 20, height: 20)
                        Text("Continue with GitHub")
                            .font(.system(size: 16, weight: .medium))
                            .foregroundColor(colorScheme == .dark ? .white : .black)
                    }
                    .frame(width: 280, height: 50)
                    .background(Color(NSColor.systemGray).opacity(0.2))
                    .cornerRadius(12)
                }
                .buttonStyle(PlainButtonStyle())
                
                // Sign Up
                Button(action: {
                    // TODO: Implement sign up
                }) {
                    Text("Sign Up")
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(colorScheme == .dark ? .white : .black)
                        .frame(width: 280, height: 50)
                        .background(Color(NSColor.systemGray).opacity(0.2))
                        .cornerRadius(12)
                }
                .buttonStyle(PlainButtonStyle())
                
                // Log In
                Button(action: {
                    // TODO: Implement log in
                }) {
                    Text("Log In")
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(colorScheme == .dark ? .white : .black)
                        .frame(width: 280, height: 50)
                        .background(Color(NSColor.systemGray).opacity(0.3))
                        .cornerRadius(12)
                }
                .buttonStyle(PlainButtonStyle())
            }
            
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(colorScheme == .dark ? Color(red: 0.129, green: 0.129, blue: 0.129) : Color.white)
    }
}

#Preview {
    ContentView()
}
