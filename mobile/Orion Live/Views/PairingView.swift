import SwiftUI

struct PairingView: View {
    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var authManager: AuthManager
    @StateObject private var viewModel: PairingViewModel
    
    init(authManager: AuthManager) {
        _viewModel = StateObject(wrappedValue: PairingViewModel(authManager: authManager))
    }
    
    var body: some View {
        NavigationView {
            ZStack {
                Color(UIColor.systemBackground).edgesIgnoringSafeArea(.all)
                
                VStack(spacing: 30) {
                    VStack(spacing: 12) {
                        Image(systemName: "link.circle.fill")
                            .font(.system(size: 72))
                            .foregroundColor(.blue)
                            .padding(.top, 45)
                        
                        Text("Pair with macOS Server")
                            .font(.title)
                            .fontWeight(.bold)
                        
                        Text("Enter the 6-digit pairing code shown on your Mac's Orion dashboard to link this device.")
                            .font(.body)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 30)
                    }
                    
                    VStack(spacing: 20) {
                        // 6-digit textfield
                        TextField("000000", text: $viewModel.code)
                            .font(.system(size: 36, weight: .bold, design: .monospaced))
                            .multilineTextAlignment(.center)
                            .keyboardType(.numberPad)
                            .onChange(of: viewModel.code) { _, newValue in
                                if newValue.count > 6 {
                                    viewModel.code = String(newValue.prefix(6))
                                }
                            }
                            .padding()
                            .background(Color(UIColor.secondarySystemBackground))
                            .cornerRadius(16)
                            .padding(.horizontal, 40)
                        
                        if let error = viewModel.errorMessage {
                            Text(error)
                                .foregroundColor(.red)
                                .font(.callout)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal)
                        }
                        
                        if let status = viewModel.pairingStatus {
                            Text(status)
                                .foregroundColor(.blue)
                                .font(.callout)
                        }
                    }
                    
                    Spacer()
                    
                    Button(action: {
                        Task {
                            await viewModel.pairDevice()
                            if viewModel.isPaired {
                                DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                                    dismiss()
                                }
                            }
                        }
                    }) {
                        if viewModel.isLoading {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        } else {
                            Text("Confirm Pairing")
                                .fontWeight(.semibold)
                        }
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(viewModel.code.count != 6 || viewModel.isLoading)
                    .padding(.horizontal, 30)
                    .padding(.bottom, 30)
                }
            }
            .navigationBarItems(leading: Button("Cancel") {
                dismiss()
            })
            .navigationTitle("Device Pairing")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding()
            .background(Color.blue)
            .cornerRadius(12)
            .opacity(configuration.isPressed ? 0.8 : 1.0)
            .scaleEffect(configuration.isPressed ? 0.98 : 1.0)
    }
}
