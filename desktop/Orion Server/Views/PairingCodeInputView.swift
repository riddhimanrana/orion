
import SwiftUI

struct PairingCodeInputView: View {
    @EnvironmentObject var deviceManager: DeviceManager
    @Environment(\.dismiss) var dismiss

    @State private var code: String = ""
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var successMessage: String?

    var body: some View {
        VStack(spacing: 20) {
            Text("Enter Pairing Code")
                .font(.title2)
                .fontWeight(.bold)

            Text("Enter the 6-digit code displayed on your iOS device.")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)

            OTPInputView(code: $code)
                .onChange(of: code) {
                    // Clear messages on input change
                    errorMessage = nil
                    successMessage = nil
                }

            if let msg = errorMessage {
                Text(msg)
                    .foregroundColor(.red)
            } else if let msg = successMessage {
                Text(msg)
                    .foregroundColor(.green)
            }

            HStack {
                Button("Cancel") {
                    dismiss()
                }
                .buttonStyle(.bordered)

                Button("Pair") {
                    Task {
                        await pairDevice()
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(code.count != 6 || isLoading)
            }
        }
        .padding(40)
        .frame(width: 400, height: 300)
        .onDisappear {
            // Refresh paired devices list when this view is dismissed
            Task {
                await deviceManager.fetchPairedDevices()
            }
        }
    }

    private func pairDevice() async {
        isLoading = true
        errorMessage = nil
        successMessage = nil

        do {
            let pairedDevice = try await deviceManager.consumePairingCode(code: code)
            successMessage = "Successfully paired with \(pairedDevice.mobileDevice.name)!"
            // Dismiss after a short delay on success
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                dismiss()
            }
        } catch {
            errorMessage = "Pairing failed: \(error.localizedDescription)"
        }
        isLoading = false
    }
}
