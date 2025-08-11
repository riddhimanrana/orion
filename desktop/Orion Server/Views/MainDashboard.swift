//
//  MainDashboard.swift
//  Orion Server
//
//  Created by Riddhiman Rana on 8/9/25.
//  Main dashboard view for authenticated users.
//

import SwiftUI
import Supabase

@MainActor
class UserProfileViewModel: ObservableObject {
    @Published var fullName: String = "Loading..."
    @Published var email: String = "-"
    @Published var memberSince: String = "-"
    @Published var subscriptionTier: String = "Free"
    @Published var profilePictureURL: URL? = nil
    @Published var isLoading = true

    func fetchUserDetails(for user: User) async {
        self.email = user.email ?? "No email provided"
        let joinDate = user.createdAt
        self.memberSince = joinDate.formatted(date: .abbreviated, time: .omitted)

        // Extract full name from user metadata
        if let fullNameJSON = user.userMetadata["full_name"], case .string(let fullName) = fullNameJSON {
            self.fullName = fullName
        } else {
            self.fullName = user.email?.components(separatedBy: "@").first?.capitalized ?? "User"
        }

        // Extract subscription tier
        if let tierJSON = user.userMetadata["subscription_tier"], case .string(let tier) = tierJSON {
            self.subscriptionTier = tier.capitalized
        }

        await fetchProfilePictureURL(for: user)
        self.isLoading = false
    }

    private func fetchProfilePictureURL(for user: User) async {
        var finalProfilePictureURL: URL? = nil

        // Check profile_picture_source preference
        if let preferredSourceJSON = user.userMetadata["profile_picture_source"],
           case .string(let preferredSource) = preferredSourceJSON {
            
            if preferredSource == "monogram" {
                finalProfilePictureURL = nil // Use monogram
            } else {
                // Try to get avatar from specific identity (Google/GitHub)
                if let identities = user.identities {
                    if let identity = identities.first(where: { $0.provider == preferredSource }),
                       let avatarURLString = identity.identityData?["avatar_url"] as? String {
                        finalProfilePictureURL = URL(string: avatarURLString)
                    }
                }
            }
        }

        // Fallback to user_metadata.avatar_url
        if finalProfilePictureURL == nil {
            if let avatarURLJSON = user.userMetadata["avatar_url"],
               case .string(let avatarURLString) = avatarURLJSON {
                finalProfilePictureURL = URL(string: avatarURLString)
            }
        }

        self.profilePictureURL = finalProfilePictureURL
    }
    
    func getInitials(from fullName: String) -> String {
        let components = fullName.split(separator: " ")
        let firstNameInitial = components.first?.first.map(String.init) ?? ""
        let lastNameInitial = components.count > 1 ? components.last?.first.map(String.init) ?? "" : ""
        return "\(firstNameInitial)\(lastNameInitial)"
    }
}

struct MainDashboard: View {
    @Environment(\.colorScheme) var colorScheme
    @EnvironmentObject var authManager: AuthManager
    @StateObject private var userViewModel = UserProfileViewModel()
    @State private var showingSettings = false
    
    var body: some View {
        ZStack {
            // Background
            Color(.windowBackgroundColor)
                .ignoresSafeArea()
            
            VStack(spacing: 40) {
                // Top spacing for traffic lights
                Spacer()
                    .frame(height: 60)
                
                Spacer()
                
                // Welcome Section
                VStack(spacing: 24) {
                    Group {
                        if let profileURL = userViewModel.profilePictureURL {
                            AsyncImage(url: profileURL) { image in
                                image.resizable()
                                    .aspectRatio(contentMode: .fill)
                            } placeholder: {
                                MonogramAvatar(initials: userViewModel.getInitials(from: userViewModel.fullName))
                            }
                        } else {
                            MonogramAvatar(initials: userViewModel.getInitials(from: userViewModel.fullName))
                        }
                    }
                    .frame(width: 100, height: 100)
                    .clipShape(Circle())
                    .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
                    
                    VStack(spacing: 8) {
                        Text("Welcome back, \(userViewModel.fullName.components(separatedBy: " ").first ?? "User")")
                            .font(.system(size: 28, weight: .semibold))
                            .foregroundColor(.primary)
                        
                        Text("Orion Server is running and ready")
                            .font(.system(size: 18))
                            .foregroundColor(.secondary)
                    }
                    
                    // Simple status indicator
                    HStack(spacing: 8) {
                        Circle()
                            .fill(Color.green)
                            .frame(width: 8, height: 8)
                        
                        Text("Connected")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(.secondary)
                    }
                    .padding(.top, 8)
                }
                
                Spacer()
                Spacer()
            }
        }
        .task {
            if let user = authManager.session?.user {
                await userViewModel.fetchUserDetails(for: user)
            }
        }
    }
}

struct MonogramAvatar: View {
    let initials: String
    
    var body: some View {
        ZStack {
            Circle()
                .fill(
                    LinearGradient(
                        colors: [Color.blue, Color.purple],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
            
            Text(initials)
                .font(.system(size: 14, weight: .semibold))
                .foregroundColor(.white)
        }
    }
}

#Preview {
    MainDashboard()
        .environmentObject(AuthManager())
}
