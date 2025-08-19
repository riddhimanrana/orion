//
//  LoadingView.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 8/16/25.
//  Loading screen for app initialization.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//

import SwiftUI

struct LoadingView: View {
    @State private var animationAmount = 1.0
    
    var body: some View {
        ZStack {
            Color(UIColor.systemBackground).edgesIgnoringSafeArea(.all)
            
            VStack(spacing: 20) {
                Image("AppLogo")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 100, height: 100)
                    .scaleEffect(animationAmount)
                    .animation(
                        .easeInOut(duration: 1.0)
                        .repeatForever(autoreverses: true),
                        value: animationAmount
                    )
                
                Text("Orion Live")
                    .font(.system(size: 32, weight: .bold))
                    .foregroundColor(.primary)
                
                ProgressView()
                    .scaleEffect(1.2)
                    .tint(.blue)
            }
        }
        .onAppear {
            animationAmount = 1.1
        }
    }
}

struct LoadingView_Previews: PreviewProvider {
    static var previews: some View {
        LoadingView()
    }
}