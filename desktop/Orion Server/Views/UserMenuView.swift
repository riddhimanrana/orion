//
//  UserMenuView.swift
//  Orion Server
//
//  Created by Riddhiman Rana on 8/9/25.
//  User dropdown menu component.
//

import SwiftUI

struct UserMenuView: View {
    @ObservedObject var userViewModel: UserProfileViewModel
    @Binding var showingSettings: Bool
    let authManager: AuthManager
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // User Info Header
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 12) {
                    // Avatar
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
                    .frame(width: 40, height: 40)
                    .clipShape(Circle())
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text(userViewModel.fullName)
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(.primary)
                        
                        Text(userViewModel.email)
                            .font(.system(size: 12))
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                    }
                    
                    Spacer()
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
            }
            
            Divider()
            
            // Menu Items
            VStack(alignment: .leading, spacing: 0) {
                MenuItemButton(
                    icon: "gearshape.fill",
                    title: "Settings",
                    shortcut: "⌘,",
                    action: {
                        dismiss()
                        showingSettings = true
                    }
                )
                
                MenuItemButton(
                    icon: "arrow.right.square.fill",
                    title: "Sign Out",
                    shortcut: nil,
                    isDestructive: true,
                    action: {
                        dismiss()
                        Task {
                            await authManager.signOut()
                        }
                    }
                )
            }
        }
        .frame(width: 220)
        .background(Color(.windowBackgroundColor))
        .cornerRadius(8)
        .shadow(color: .black.opacity(0.15), radius: 8, x: 0, y: 4)
    }
}

struct MenuItemButton: View {
    let icon: String
    let title: String
    let shortcut: String?
    var isDestructive: Bool = false
    let action: () -> Void
    
    @State private var isHovered = false
    
    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: icon)
                    .font(.system(size: 13))
                    .foregroundColor(isDestructive ? .red : .primary)
                    .frame(width: 16)
                
                Text(title)
                    .font(.system(size: 13))
                    .foregroundColor(isDestructive ? .red : .primary)
                
                Spacer()
                
                if let shortcut = shortcut {
                    Text(shortcut)
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(
                Rectangle()
                    .fill(isHovered ? Color(.controlAccentColor).opacity(0.1) : Color.clear)
            )
        }
        .buttonStyle(PlainButtonStyle())
        .onHover { hovering in
            isHovered = hovering
        }
    }
}

#Preview {
    UserMenuView(
        userViewModel: UserProfileViewModel(),
        showingSettings: Binding.constant(false),
        authManager: AuthManager()
    )
}
