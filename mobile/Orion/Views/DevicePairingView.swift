
import SwiftUI
import Combine

struct DevicePairingView: View {
    @EnvironmentObject var deviceManager: DeviceManager
    @Environment(\.dismiss) var dismiss

    @State private var pairingCode: String?
    @State private var errorMessage: String?
    @State private var isLoading = true
    @State private var timeRemaining = 300
    @State private var codeTimer: Timer? = nil
    @State private var pollingTimer: Timer? = nil

    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                if isLoading {
                    ProgressView("Generating Code...")
                } else if let code = pairingCode {
                    Spacer()
                    
                    Image(systemName: "desktopcomputer")
                        .font(.system(size: 60))
                        .foregroundColor(.secondary)
                    
                    Text("Enter this code on your Mac:")
                        .font(.title2)
                    
                    Text(code)
                        .font(.system(size: 60, weight: .bold, design: .monospaced))
                        .tracking(10)
                        .padding()
                        .background(Color(.secondarySystemBackground))
                        .cornerRadius(12)

                    if timeRemaining > 0 {
                        Text("This code will expire in \(timeString(time: timeRemaining)).")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    } else {
                        Text("Code expired.")
                            .font(.subheadline)
                            .foregroundColor(.red)
                        Button("Generate New Code") {
                            Task {
                                await createNewCode()
                            }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                    Spacer()
                    
                } else if let error = errorMessage {
                    Text("Error: \(error)")
                        .foregroundColor(.red)
                    Button("Try Again") {
                        Task {
                            await createNewCode()
                        }
                    }
                }
            }
            .padding()
            .navigationTitle("Link Device")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
            .onAppear(perform: start)
            .onDisappear(perform: stop)
        }
    }

    private func start() {
        Task {
            await createNewCode()
        }
    }

    private func stop() {
        codeTimer?.invalidate()
        codeTimer = nil
        pollingTimer?.invalidate()
        pollingTimer = nil
    }

    private func startCodeTimer() {
        stop()
        codeTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in
            if timeRemaining > 0 {
                timeRemaining -= 1
            } else {
                stop()
                self.pairingCode = nil
                self.errorMessage = "Code expired. Please generate a new one."
            }
        }
    }

    private func startPollingTimer() {
        pollingTimer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { _ in
            Task {
                let initialPairCount = deviceManager.pairedDevices.count
                await deviceManager.fetchPairedDevices()
                if deviceManager.pairedDevices.count > initialPairCount {
                    // A new device was successfully paired
                    stop()
                    dismiss()
                }
            }
        }
    }
    
    private func createNewCode() async {
        isLoading = true
        errorMessage = nil
        do {
            let response = try await deviceManager.createPairingCode()
            self.pairingCode = response.code
            self.timeRemaining = 300
            startCodeTimer()
            startPollingTimer()
        } catch {
            self.errorMessage = error.localizedDescription
        }
        isLoading = false
    }
    
    private func timeString(time: Int) -> String {
        let minutes = time / 60
        let seconds = time % 60
        return String(format: "%02i:%02i", minutes, seconds)
    }
}
