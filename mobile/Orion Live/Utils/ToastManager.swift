//
//  ToastManager.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Global toast notification system for user feedback in Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//

import SwiftUI
import Combine

@MainActor
class ToastManager: ObservableObject {
    @Published var toastMessage: String = ""
    @Published var toastType: ToastType = .info
    @Published var showToast: Bool = false
    
    static let shared = ToastManager()
    
    private init() {}
    
    func showToast(message: String, type: ToastType = .error, duration: TimeInterval = 3.0) {
        toastMessage = message
        toastType = type
        showToast = true
        
        // Auto-hide after duration
        DispatchQueue.main.asyncAfter(deadline: .now() + duration) {
            self.hideToast()
        }
    }
    
    func showNetworkError(_ message: String = "No internet connection", duration: TimeInterval = 5.0) {
        showToast(message: message, type: .error, duration: duration)
    }
    
    func showAuthError(_ message: String = "Authentication failed: Please check your connection and try again") {
        showToast(message: message, type: .error)
    }
    
    func hideToast() {
        showToast = false
    }
}

enum ToastType {
    case success
    case error
    case warning
    case info
    
    var color: Color {
        switch self {
        case .success:
            return .green
        case .error:
            return .red
        case .warning:
            return .orange
        case .info:
            return .blue
        }
    }
    
    var icon: String {
        switch self {
        case .success:
            return "checkmark.circle.fill"
        case .error:
            return "exclamationmark.triangle.fill"
        case .warning:
            return "exclamationmark.triangle"
        case .info:
            return "info.circle.fill"
        }
    }
}

struct ToastView: View {
    let message: String
    let type: ToastType
    let onDismiss: () -> Void
    
    var body: some View {
        HStack {
            Image(systemName: type.icon)
                .foregroundColor(.white)
            
            Text(message)
                .foregroundColor(.white)
                .font(.system(size: 14, weight: .medium))
                .multilineTextAlignment(.leading)
            
            Spacer()
            
            Button(action: onDismiss) {
                Image(systemName: "xmark")
                    .foregroundColor(.white)
                    .font(.system(size: 12, weight: .bold))
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(type.color)
        .cornerRadius(8)
        .shadow(radius: 4)
        .padding(.horizontal, 16)
    }
}

struct ToastModifier: ViewModifier {
    @ObservedObject var toastManager = ToastManager.shared
    
    func body(content: Content) -> some View {
        ZStack(alignment: .top) {
            content
            
            if toastManager.showToast {
                VStack {
                    ToastView(
                        message: toastManager.toastMessage,
                        type: toastManager.toastType,
                        onDismiss: toastManager.hideToast
                    )
                    .transition(.move(edge: .top).combined(with: .opacity))
                    .animation(.spring(response: 0.6, dampingFraction: 0.8), value: toastManager.showToast)
                    
                    Spacer()
                }
                .zIndex(1000)
            }
        }
    }
}

extension View {
    func withToast() -> some View {
        self.modifier(ToastModifier())
    }
}
