//
//  CompatibilityCheckView.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Device compatibility check and summary view for Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//

import SwiftUI

struct CompatibilityCheckView: View {
    @EnvironmentObject var compatibilityManager: SystemCompatibilityManager
    @Environment(\.dismiss) var dismiss
    @State private var showDetails = false

    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                Spacer()

                Image(systemName: compatibilityManager.isCompatible ? "checkmark.circle.fill" : "xmark.circle.fill")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 100, height: 100)
                    .foregroundColor(compatibilityManager.isCompatible ? .green : .red)
                    .animation(.easeInOut, value: compatibilityManager.isCompatible)

                Text(compatibilityManager.isCompatible ? "Device Compatible!" : "Device Not Fully Compatible")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)

                Text(compatibilityManager.isCompatible ?
                     "Your device meets the recommended specifications for Orion Live." :
                     "Your device does not meet all recommended specifications. Performance may vary."
                )
                .font(.body)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)

                Spacer()

                VStack(alignment: .leading, spacing: 10) {
                    Text("Device Details")
                        .font(.headline)

                    InfoRow(icon: "iphone", label: "Model", value: compatibilityManager.deviceModel)
                    InfoRow(icon: "gear", label: "iOS Version", value: compatibilityManager.iosVersion)
                    InfoRow(icon: "cpu", label: "Processor", value: compatibilityManager.chipType)
                    InfoRow(icon: "memorychip", label: "RAM", value: "\(compatibilityManager.ramGB) GB")
                }
                .padding()
                .background(Color(UIColor.secondarySystemBackground))
                .cornerRadius(12)
                .padding(.horizontal)

                Button(action: { showDetails.toggle() }) {
                    Label(showDetails ? "Hide Compatibility Details" : "Show Compatibility Details", systemImage: showDetails ? "chevron.up" : "chevron.down")
                }
                .font(.callout)
                .foregroundColor(.accentColor)
                .padding(.top, 10)

                if showDetails {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Compatibility Checks")
                            .font(.headline)

                        ForEach(compatibilityManager.compatibilityDetails) { check in
                            HStack {
                                Image(systemName: check.status ? "checkmark.circle.fill" : "xmark.circle.fill")
                                    .foregroundColor(check.status ? .green : .red)
                                Text(check.name)
                                Spacer()
                                Text(check.details)
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                    .padding()
                    .background(Color(UIColor.secondarySystemBackground))
                    .cornerRadius(12)
                    .padding(.horizontal)
                    .transition(.opacity)
                }

                Spacer()

                Button("Continue") {
                    dismiss()
                }
                .buttonStyle(InvertedPrimaryButtonStyle())
                .padding(.horizontal)
                .padding(.bottom, 20)
            }
            .navigationTitle("System Compatibility")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

struct CompatibilityCheckView_Previews: PreviewProvider {
    static var previews: some View {
        CompatibilityCheckView()
            .environmentObject(SystemCompatibilityManager())
    }
}
