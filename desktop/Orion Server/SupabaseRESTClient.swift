import Foundation

class SupabaseRESTClient: ObservableObject {
    static let shared = SupabaseRESTClient()
    
    @Published var pairingCode: String? = nil
    @Published var isPaired = false
    @Published var pairedDeviceId: String? = nil
    @Published var pairedUserId: String? = nil
    @Published var errorMessage: String? = nil
    @Published var isLoading = false
    
    private init() {}
    
    func fetchPairingCode(userId: String) async {
        DispatchQueue.main.async {
            self.isLoading = true
            self.errorMessage = nil
        }
        
        let urlString = "http://127.0.0.1:8000/pairing/code?user_id=\(userId)"
        guard let url = URL(string: urlString) else {
            DispatchQueue.main.async {
                self.errorMessage = "Invalid URL"
                self.isLoading = false
            }
            return
        }
        
        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
                DispatchQueue.main.async {
                    self.errorMessage = "Failed to fetch code (is Python server running?)"
                    self.isLoading = false
                }
                return
            }
            
            if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
               let code = json["code"] as? String {
                DispatchQueue.main.async {
                    self.pairingCode = code
                    self.isLoading = false
                }
            }
        } catch {
            DispatchQueue.main.async {
                self.errorMessage = error.localizedDescription
                self.isLoading = false
            }
        }
    }
    
    func checkPairingStatus() async {
        let urlString = "http://127.0.0.1:8000/pairing/status"
        guard let url = URL(string: urlString) else { return }
        
        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else { return }
            
            if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
               let status = json["status"] as? String {
                DispatchQueue.main.async {
                    if status == "paired" {
                        self.isPaired = true
                        self.pairedDeviceId = json["mobile_device_id"] as? String
                        self.pairedUserId = json["user_id"] as? String
                    } else {
                        self.isPaired = false
                        self.pairedDeviceId = nil
                        self.pairedUserId = nil
                    }
                }
            }
        } catch {
            // Fail silently
        }
    }
}
