//
//  UserProfileViewModel.swift
//  Orion Server
//
//  Created by Riddhiman Rana on 8/15/25.
//

import Foundation
import SwiftUI
import Supabase

@MainActor
class UserProfileViewModel: ObservableObject {
    @Published var email: String = ""
    @Published var fullName: String = ""
    @Published var subscriptionTier: String = "Free Plan"
    @Published var memberSince: String = ""
    @Published var profilePictureURL: URL? = nil
    
    func fetchUserDetails(for user: User) async {
        self.email = user.email ?? ""
        
        // Extract full name from user metadata or use email as fallback
        let metaData = user.userMetadata
        if let fullNameValue = metaData["full_name"],
           case let .string(fullName) = fullNameValue {
            self.fullName = fullName
        } else if let firstNameValue = metaData["first_name"],
                  let lastNameValue = metaData["last_name"],
                  case let .string(firstName) = firstNameValue,
                  case let .string(lastName) = lastNameValue {
            self.fullName = "\(firstName) \(lastName)"
        } else {
            self.fullName = user.email ?? "Unknown User"
        }
        
        // Extract profile picture URL from metadata
        if let avatarUrlValue = metaData["avatar_url"],
           case let .string(avatarUrlString) = avatarUrlValue {
            self.profilePictureURL = URL(string: avatarUrlString)
        }
        
        // Set member since date from user creation
        let formatter = DateFormatter()
        formatter.dateFormat = "MMMM yyyy"
        self.memberSince = formatter.string(from: user.createdAt)
        
        // TODO: Fetch subscription tier from your backend/Supabase
        // For now, defaulting to Free Plan
        self.subscriptionTier = "Free Plan"
    }
    
    func getInitials(from name: String) -> String {
        let components = name.components(separatedBy: " ")
        let initials = components.compactMap { $0.first }.map { String($0) }
        return String(initials.prefix(2).joined())
    }
}
