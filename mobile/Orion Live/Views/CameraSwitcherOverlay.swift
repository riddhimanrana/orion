

//
//  CameraSwitcherOverlay.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 6/26/25.
//  SwiftUI overlay for switching between available cameras in Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//

import SwiftUI

struct CameraSwitcherOverlay: View {
    @EnvironmentObject var cameraManager: CameraManager
    @Binding var showingCameraSwitcher: Bool
    
    // Use the namespace from the parent view
    var animation: Namespace.ID
    
    var body: some View {
        // Filter out the currently selected option so it doesn't appear in the list
        let availableOptions = cameraManager.availableCameraOptions.filter { $0.id != cameraManager.currentCameraOption?.id }
        
        VStack(spacing: 12) {
            ForEach(availableOptions) { option in
                Button(action: {
                    // Switch camera and hide the switcher
                    withAnimation(.interpolatingSpring(stiffness: 300, damping: 20)) {
                        cameraManager.switchCamera(to: option)
                        showingCameraSwitcher = false
                    }
                }) {
                    if option.isFrontCamera {
                        Image(systemName: "arrow.triangle.2.circlepath.camera.fill")
                            .font(.system(size: 18))
                            .frame(width: 44, height: 44)
                            // Match the geometry to the icon in the main button
                            .matchedGeometryEffect(id: "front_camera_icon", in: animation)
                    } else {
                        Text(option.displayName)
                            .font(.system(size: 14, weight: .bold))
                            .frame(width: 44, height: 44)
                            // Match the geometry to the text in the main button
                            .matchedGeometryEffect(id: option.id, in: animation)
                    }
                }
                .foregroundColor(.white)
                .background(Color.black.opacity(0.5))
                .clipShape(Circle())
                .transition(.asymmetric(insertion: .opacity.animation(.easeIn.delay(0.1)), removal: .opacity.animation(.easeOut)))
            }
        }
    }
}
