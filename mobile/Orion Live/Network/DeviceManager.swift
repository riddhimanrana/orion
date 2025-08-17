
import Foundation
import Combine
import Supabase
import UIKit // For UIDevice

@MainActor
class DeviceManager: ObservableObject {
    @Published var deviceId: String? {
        didSet {
            if let deviceId {
                UserDefaults.standard.set(deviceId, forKey: "orion_device_id")
            } else {
                UserDefaults.standard.removeObject(forKey: "orion_device_id")
            }
        }
    }
    @Published var pairedDevices: [DevicePair] = []
    @Published var activePairedDevice: PairedDevice?

    private let supabase: SupabaseClient
    private var apiBaseURL: URL {
        // In a real app, this should be configurable.
        return URL(string: "https://orionlive.ai/api")!
    }

    init(supabase: SupabaseClient) {
        self.supabase = supabase
        self.deviceId = UserDefaults.standard.string(forKey: "orion_device_id")
    }

    deinit {
        // Clean up if necessary
    }

    // MARK: - Device Registration
    func registerDeviceIfNeeded(type: String) async {
        if deviceId != nil {
            print("Device already registered with ID: \(deviceId!)")
            // Optionally, you could update the `last_seen` timestamp here.
            return
        }

        do {
            let name = UIDevice.current.name
            let newDeviceId = try await registerDevice(type: type, name: name)
            self.deviceId = newDeviceId.uuidString
            print("Device registered successfully with ID: \(newDeviceId.uuidString)")
        } catch {
            print("Error registering device: \(error.localizedDescription)")
        }
    }

    private func registerDevice(type: String, name: String) async throws -> UUID {
        let session = try await getAuthSession()
        guard !session.accessToken.isEmpty else {
            print("DEBUG: Access token is empty for registerDevice, cannot make authenticated request.")
            throw URLError(.userAuthenticationRequired)
        }
        let url = apiBaseURL.appendingPathComponent("devices/register")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")

        let body = ["type": type, "name": name]
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }

        let decodedResponse = try JSONDecoder().decode(DeviceRegistrationResponse.self, from: data)
        return decodedResponse.deviceId
    }

    // MARK: - Pairing Flow
    func createPairingCode() async throws -> PairingCodeResponse {
        guard let deviceId = self.deviceId else { throw URLError(.badURL) }
        let session = try await getAuthSession()
        guard !session.accessToken.isEmpty else {
            print("DEBUG: Access token is empty for createPairingCode, cannot make authenticated request.")
            throw URLError(.userAuthenticationRequired)
        }

        let url = apiBaseURL.appendingPathComponent("pairings/create")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")

        let body = ["device_id": deviceId]
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }

        return try JSONDecoder().decode(PairingCodeResponse.self, from: data)
    }





    func consumePairingCode(code: String) async throws -> DevicePair {
        guard let deviceId = self.deviceId else { throw URLError(.badURL) }
        let session = try await getAuthSession()
        guard !session.accessToken.isEmpty else {
            print("DEBUG: Access token is empty for consumePairingCode, cannot make authenticated request.")
            throw URLError(.userAuthenticationRequired)
        }

        let url = apiBaseURL.appendingPathComponent("pairings/consume")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")

        let body = ["code": code, "device_id": deviceId]
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }

        let newPair = try createJSONDecoder().decode(DevicePair.self, from: data)
        await fetchPairedDevices()
        return newPair
    }

    // MARK: - Data Fetching & Management
    func fetchPairedDevices() async {
        do {
            let session = try await getAuthSession()
            guard !session.accessToken.isEmpty else {
                print("DEBUG: Access token is empty for fetchPairedDevices, cannot make authenticated request.")
                throw URLError(.userAuthenticationRequired)
            }
            let url = apiBaseURL.appendingPathComponent("pairs")
            var request = URLRequest(url: url)
            request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")

            let (data, _) = try await URLSession.shared.data(for: request)
            let pairs = try createJSONDecoder().decode([DevicePair].self, from: data)
            self.pairedDevices = pairs
            self.activePairedDevice = pairs.first(where: { $0.status == "active" })?.serverDevice
        } catch {
            print("Error fetching paired devices: \(error.localizedDescription)")
        }
    }

    func revokePair(pairId: UUID) async {
        do {
            let session = try await getAuthSession()
            guard !session.accessToken.isEmpty else {
                print("DEBUG: Access token is empty for revokePair, cannot make authenticated request.")
                throw URLError(.userAuthenticationRequired)
            }
            let url = apiBaseURL.appendingPathComponent("pairs/\(pairId.uuidString)/revoke")
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")

            let (_, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
                throw URLError(.badServerResponse)
            }
            await fetchPairedDevices() // Refresh list
        } catch {
            print("Error revoking pair: \(error.localizedDescription)")
        }
    }



    // MARK: - Helpers
    private func getAuthSession() async throws -> Session {
        let session = try await supabase.auth.session
        return session
    }

    private func createJSONDecoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let dateString = try container.decode(String.self)

            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

            if let date = formatter.date(from: dateString) {
                return date
            }
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Invalid date: \(dateString)")
        }
        return decoder
    }
}
