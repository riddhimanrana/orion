//
//  AccountView.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  User account/profile view and view model for Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//
import SwiftUI
import Supabase
import Combine

@MainActor
class AccountViewModel: ObservableObject {
    @Published var fullName: String = "Loading..."
    @Published var email: String = "-"
    @Published var memberSince: String = "-"
    @Published var subscriptionTier: String = "Free"
    @Published var profilePictureURL: URL? = nil
    @Published var isLoading = true

    func fetchAccountDetails(for user: User) async {
        self.email = user.email ?? "No email provided"
        let joinDate = user.createdAt
        self.memberSince = joinDate.formatted(date: .abbreviated, time: .omitted)

        if let fullNameJSON = user.userMetadata["full_name"], case .string(let fullName) = fullNameJSON {
            self.fullName = fullName
        }

        if let tierJSON = user.userMetadata["subscription_tier"], case .string(let tier) = tierJSON {
            self.subscriptionTier = tier.capitalized
        }

        await fetchProfilePictureURL(for: user)
        self.isLoading = false
    }

    private func fetchProfilePictureURL(for user: User) async {
        var finalProfilePictureURL: URL? = nil

        // 1. Check profile_picture_source preference
        if let preferredSourceJSON = user.userMetadata["profile_picture_source"],
           case .string(let preferredSource) = preferredSourceJSON {

            Logger.shared.log("Preferred profile picture source: \(preferredSource)", level: .debug, category: .general)

            if preferredSource == "monogram" {
                finalProfilePictureURL = nil // Explicitly prefer monogram
            } else {
                // Try to get avatar from specific identity
                if let identities = user.identities {
                    if let identity = identities.first(where: { $0.provider == preferredSource }),
                       let avatarURLString = identity.identityData?["avatar_url"] as? String {
                        finalProfilePictureURL = URL(string: avatarURLString)
                        Logger.shared.log("Found avatar from \(preferredSource) identity: \(avatarURLString)", level: .debug, category: .general)
                    } else {
                        Logger.shared.log("No avatar found for \(preferredSource) identity.", level: .debug, category: .general)
                    }
                } else {
                    Logger.shared.log("No identities found for user.", level: .debug, category: .general)
                }
            }
        } else {
            Logger.shared.log("No profile_picture_source preference found in metadata.", level: .debug, category: .general)
        }

        // 2. Fallback to user_metadata.avatar_url if no specific identity URL was found or preferredSource was not set/invalid
        if finalProfilePictureURL == nil {
            if let avatarURLJSON = user.userMetadata["avatar_url"],
               case .string(let avatarURLString) = avatarURLJSON {
                finalProfilePictureURL = URL(string: avatarURLString)
                Logger.shared.log("Falling back to user_metadata.avatar_url: \(avatarURLString)", level: .debug, category: .general)
            } else {
                Logger.shared.log("No avatar_url found in user_metadata. Falling back to monogram.", level: .debug, category: .general)
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

struct AccountView: View {
    @EnvironmentObject var authManager: AuthManager
    @StateObject private var viewModel = AccountViewModel()
    @State private var showingSignOutAlert = false

    var body: some View {
        NavigationView {
            VStack {
                if viewModel.isLoading {
                    ProgressView()
                        .onAppear {
                            if let user = authManager.session?.user {
                                Task {
                                    await viewModel.fetchAccountDetails(for: user)
                                }
                            }
                        }
                } else {
                    ScrollView {
                        VStack(spacing: 20) {
                            // Profile Header
                            VStack {
                                AsyncImage(url: viewModel.profilePictureURL) { image in
                                    image.resizable()
                                        .aspectRatio(contentMode: .fill)
                                } placeholder: {
                                    ZStack {
                                        Circle()
                                            .fill(Color.blue.gradient)
                                        Text(viewModel.getInitials(from: viewModel.fullName))
                                            .font(.system(size: 40, weight: .bold))
                                            .foregroundColor(.white)
                                    }
                                }
                                .frame(width: 100, height: 100)
                                .clipShape(Circle())
                                .shadow(radius: 5)

                                Text(viewModel.fullName)
                                    .font(.title).bold()
                                    .padding(.top, 8)

                                Text(viewModel.email)
                                    .font(.body)
                                    .foregroundColor(.secondary)
                            }
                            .padding(.vertical, 20)

                            // Account Details Section
                            VStack(alignment: .leading, spacing: 15) {
                                Text("Account Details")
                                    .font(.headline)
                                    .padding(.horizontal)

                                InfoRow(icon: "crown.fill", label: "Plan", value: viewModel.subscriptionTier, isPro: viewModel.subscriptionTier == "Pro")
                                InfoRow(icon: "calendar", label: "Member Since", value: viewModel.memberSince)
                            }
                            .padding()
                            .background(Color(UIColor.secondarySystemBackground))
                            .cornerRadius(12)

                            // Actions Section
                            VStack(alignment: .leading, spacing: 15) {
                                Text("Actions")
                                    .font(.headline)
                                    .padding(.horizontal)

                                Button(action: {
                                    if let url = URL(string: "https://orionlive.ai/account") {
                                        UIApplication.shared.open(url)
                                    }
                                }) {
                                    Label("Manage Subscription", systemImage: "creditcard.fill")
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .contentShape(Rectangle())
                                }
                                .buttonStyle(PlainButtonStyle()) // Use PlainButtonStyle to remove default button styling
                                .foregroundColor(.primary)

                                Divider()

                                Button(action: { showingSignOutAlert = true }) {
                                    Label("Sign Out", systemImage: "arrow.right.square.fill")
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .contentShape(Rectangle())
                                }
                                .buttonStyle(PlainButtonStyle()) // Use PlainButtonStyle to remove default button styling
                                .foregroundColor(.red)
                            }
                            .padding()
                            .background(Color(UIColor.secondarySystemBackground))
                            .cornerRadius(12)
                        }
                        .padding()
                    }
                }
            }
            .navigationTitle("My Account")
            .navigationBarTitleDisplayMode(.inline)
            .alert("Log out of Orion Live as \(viewModel.email)?", isPresented: $showingSignOutAlert) {
                Button("Cancel", role: .cancel) { }
                Button("Log Out", role: .destructive) {
                    Task {
                        await authManager.signOut()
                    }
                }
            }
        }
    }
}

struct InfoRow: View {
    let icon: String
    let label: String
    let value: String
    var isPro: Bool = false

    var body: some View {
        HStack {
            Image(systemName: icon)
                .font(.headline)
                .frame(width: 30)
                .foregroundColor(isPro ? .yellow : .accentColor)

            Text(label)
                .font(.body)

            Spacer()

            if isPro {
                Text(value)
                    .font(.headline).bold()
                    .foregroundColor(.yellow)
            } else {
                Text(value)
                    .font(.body)
                    .foregroundColor(.secondary)
            }
        }
    }
}

struct AccountView_Previews: PreviewProvider {
    static var previews: some View {
        AccountView()
            .environmentObject(AuthManager())
    }
}
