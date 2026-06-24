import SwiftUI

struct ContentView: View {
    @StateObject private var processManager = ProcessManager.shared
    @StateObject private var socket = DashboardSocket.shared
    @StateObject private var restClient = SupabaseRESTClient.shared
    
    @State private var selectedTab: String? = "onboarding"
    @State private var mockUserId = "4b67fd31-628d-4f15-8461-127e997a3eb0" // Mock User UUID for local dev pairing
    
    var body: some View {
        NavigationView {
            // Sidebar Navigation
            List {
                NavigationLink(destination: onboardingView, tag: "onboarding", selection: $selectedTab) {
                    Label("Pairing & Onboarding", systemImage: "link")
                }
                
                NavigationLink(destination: dashboardView, tag: "dashboard", selection: $selectedTab) {
                    Label("Live Dashboard", systemImage: "macwindow.play.background.and.video.fill")
                }
                
                NavigationLink(destination: reasoningView, tag: "reasoning", selection: $selectedTab) {
                    Label("Gemma-4 Reasoning", systemImage: "brain.head.profile")
                }
                
                NavigationLink(destination: logsView, tag: "logs", selection: $selectedTab) {
                    Label("Server Logs", systemImage: "terminal.fill")
                }
            }
            .listStyle(SidebarListStyle())
            .frame(minWidth: 220)
            
            // Default view
            onboardingView
        }
        .frame(minWidth: 1000, minHeight: 650)
        .preferredColorScheme(.dark)
        .onAppear {
            socket.connect()
            // Poll pairing status periodically
            Timer.scheduledTimer(withTimeInterval: 3.0, repeats: true) { _ in
                Task {
                    await restClient.checkPairingStatus()
                }
            }
        }
    }
    
    // MARK: - Onboarding & Pairing View
    private var onboardingView: some View {
        VStack(spacing: 30) {
            Text("Orion Server Onboarding")
                .font(.system(size: 32, weight: .bold))
                .padding(.top, 40)
            
            Text("Real-time Visual Intelligence with privacy-first Apple Silicon acceleration.")
                .foregroundColor(.secondary)
                .font(.title3)
            
            HStack(spacing: 40) {
                // Server Process Controller
                VStack(alignment: .leading, spacing: 20) {
                    Text("Server Process Controller")
                        .font(.headline)
                    
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Text("Process Status:")
                            Spacer()
                            Text(processManager.isRunning ? "RUNNING" : "STOPPED")
                                .fontWeight(.bold)
                                .foregroundColor(processManager.isRunning ? .green : .red)
                        }
                        
                        HStack {
                            Text("CPU Usage:")
                            Spacer()
                            Text(String(format: "%.1f %%", processManager.cpuUsage))
                                .foregroundColor(.secondary)
                        }
                        
                        HStack {
                            Text("Memory Usage:")
                            Spacer()
                            Text(String(format: "%.1f MB", processManager.memoryUsage))
                                .foregroundColor(.secondary)
                        }
                        
                        HStack {
                            Text("Local Network IP:")
                            Spacer()
                            Text(getLocalIPAddress())
                                .foregroundColor(.blue)
                        }
                    }
                    .padding()
                    .background(Color(NSColor.controlBackgroundColor))
                    .cornerRadius(12)
                    
                    Button(action: {
                        if processManager.isRunning {
                            processManager.stop()
                        } else {
                            processManager.start()
                        }
                    }) {
                        Text(processManager.isRunning ? "Stop Server Subprocess" : "Start Server Subprocess")
                            .fontWeight(.semibold)
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(processManager.isRunning ? Color.red : Color.blue)
                            .cornerRadius(10)
                    }
                    .buttonStyle(PlainButtonStyle())
                }
                .frame(width: 320)
                
                // Device Pairing Dashboard
                VStack(alignment: .leading, spacing: 20) {
                    Text("Device Pairing & Remote Signal")
                        .font(.headline)
                    
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Text("Pairing Status:")
                            Spacer()
                            Text(restClient.isPaired ? "PAIRED" : "UNPAIRED")
                                .fontWeight(.bold)
                                .foregroundColor(restClient.isPaired ? .green : .yellow)
                        }
                        
                        if restClient.isPaired {
                            HStack {
                                Text("Paired Device:")
                                Spacer()
                                Text(restClient.pairedDeviceId ?? "Unknown ID")
                                    .font(.system(.body, design: .monospaced))
                                    .foregroundColor(.secondary)
                            }
                        } else {
                            VStack(alignment: .center, spacing: 10) {
                                Text("6-Digit Pairing Code")
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                                
                                if restClient.isLoading {
                                    ProgressView()
                                        .frame(height: 50)
                                } else if let code = restClient.pairingCode {
                                    Text(code)
                                        .font(.system(size: 42, weight: .bold, design: .monospaced))
                                        .foregroundColor(.accentColor)
                                        .tracking(10)
                                        .padding(.vertical, 8)
                                        .frame(maxWidth: .infinity)
                                        .background(Color.black.opacity(0.3))
                                        .cornerRadius(8)
                                } else {
                                    Text("------")
                                        .font(.system(size: 42, weight: .bold, design: .monospaced))
                                        .foregroundColor(.secondary)
                                        .padding(.vertical, 8)
                                }
                            }
                            .frame(maxWidth: .infinity)
                        }
                    }
                    .padding()
                    .background(Color(NSColor.controlBackgroundColor))
                    .cornerRadius(12)
                    
                    Button(action: {
                        Task {
                            await restClient.fetchPairingCode(userId: mockUserId)
                        }
                    }) {
                        Text("Generate New Code")
                            .fontWeight(.semibold)
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.blue)
                            .cornerRadius(10)
                    }
                    .buttonStyle(PlainButtonStyle())
                    .disabled(processManager.isRunning == false)
                    
                    if !processManager.isRunning {
                        Text("Start the Python server process above to generate a pairing code.")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                .frame(width: 320)
            }
            .padding()
            
            Spacer()
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    // MARK: - Live Dashboard View
    private var dashboardView: some View {
        VStack(spacing: 15) {
            HStack {
                Text("Live Vision Feed")
                    .font(.title2)
                    .fontWeight(.bold)
                Spacer()
                HStack {
                    Circle()
                        .fill(socket.isConnected ? Color.green : Color.red)
                        .frame(width: 10, height: 10)
                    Text(socket.isConnected ? "WebSocket Connected" : "WebSocket Disconnected")
                        .foregroundColor(.secondary)
                }
            }
            .padding(.horizontal)
            
            HStack(spacing: 20) {
                // Video & Boxes Canvas
                ZStack {
                    if let img = socket.currentFrame {
                        GeometryReader { geo in
                            ZStack(alignment: .topLeading) {
                                Image(nsImage: img)
                                    .resizable()
                                    .scaledToFit()
                                    .frame(width: geo.size.width, height: geo.size.height)
                                
                                // Bounding Boxes Overlays
                                ForEach(socket.detections) { det in
                                    let imgW = img.size.width
                                    let imgH = img.size.height
                                    let scaleX = geo.size.width / imgW
                                    let scaleY = geo.size.height / imgH
                                    
                                    let x = det.bbox[0] * scaleX
                                    let y = det.bbox[1] * scaleY
                                    let w = (det.bbox[2] - det.bbox[0]) * scaleX
                                    let h = (det.bbox[3] - det.bbox[1]) * scaleY
                                    
                                    ZStack(alignment: .topLeading) {
                                        Rectangle()
                                            .stroke(det.track_id != nil ? Color.blue : Color.green, lineWidth: 2)
                                            .frame(width: max(0, w), height: max(0, h))
                                            .offset(x: x, y: y)
                                        
                                        Text("\(det.label) \(det.track_id != nil ? "ReID: \(det.track_id!)" : "")")
                                            .font(.caption2)
                                            .foregroundColor(.white)
                                            .padding(3)
                                            .background(det.track_id != nil ? Color.blue : Color.green)
                                            .cornerRadius(3)
                                            .offset(x: x, y: y - 16)
                                    }
                                }
                            }
                        }
                    } else {
                        VStack(spacing: 12) {
                            Image(systemName: "video.slash")
                                .font(.system(size: 48))
                                .foregroundColor(.secondary)
                            Text("Waiting for live frame stream...")
                                .foregroundColor(.secondary)
                        }
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                    }
                }
                .background(Color.black)
                .cornerRadius(12)
                
                // Sidebar Feed Details
                VStack(alignment: .leading, spacing: 20) {
                    Text("Scene Insights")
                        .font(.headline)
                    
                    ScrollView {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("FastVLM Caption:")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                            Text(socket.sceneDescription)
                                .font(.body)
                                .padding()
                                .background(Color.black.opacity(0.3))
                                .cornerRadius(8)
                            
                            Text("Detected Objects:")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                            
                            VStack(alignment: .leading, spacing: 6) {
                                ForEach(socket.detections) { det in
                                    HStack {
                                        Text("• \(det.label)")
                                        if let id = det.track_id {
                                            Text("(Track: \(id))")
                                                .foregroundColor(.blue)
                                                .fontWeight(.bold)
                                        }
                                        Spacer()
                                        Text(String(format: "%.1f %%", det.confidence * 100))
                                            .foregroundColor(.secondary)
                                    }
                                }
                            }
                        }
                    }
                }
                .frame(width: 300)
                .padding()
                .background(Color(NSColor.controlBackgroundColor))
                .cornerRadius(12)
            }
            .padding(.horizontal)
            .padding(.bottom)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    // MARK: - Gemma-4 Reasoning Chat View
    private var reasoningView: some View {
        VStack {
            Text("Gemma-4 Conversational Reasoning")
                .font(.title2)
                .fontWeight(.bold)
                .padding()
            
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    HStack(alignment: .top) {
                        Text("Gemma-4:")
                            .fontWeight(.bold)
                            .foregroundColor(.blue)
                        Text("I am connected to the visual context graph. Ask me anything about what I've seen in the feed.")
                    }
                    .padding()
                    .background(Color.blue.opacity(0.1))
                    .cornerRadius(8)
                }
                .padding()
            }
            
            HStack {
                TextField("Ask Gemma a question about the scene...", text: .constant(""))
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .padding()
                Button("Send") {
                    // Send prompt to server
                }
                .padding(.trailing)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    // MARK: - Server Subprocess Terminal Logs
    private var logsView: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Subprocess Terminal Logs (Uvicorn stdout/stderr)")
                .font(.title2)
                .fontWeight(.bold)
                .padding([.top, .horizontal])
            
            ScrollView {
                Text(processManager.logs.isEmpty ? "No log output received yet." : processManager.logs)
                    .font(.system(.body, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
            }
            .background(Color.black)
            .foregroundColor(.green)
            .cornerRadius(12)
            .padding([.bottom, .horizontal])
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    // MARK: - Network IP Helper
    private func getLocalIPAddress() -> String {
        var address: String?
        var ifaddr: UnsafeMutablePointer<ifaddrs>?
        if getifaddrs(&ifaddr) == 0 {
            var ptr = ifaddr
            while ptr != nil {
                defer { ptr = ptr?.pointee.ifa_next }
                guard let interface = ptr?.pointee else { continue }
                let addrFamily = interface.ifa_addr.pointee.sa_family
                if addrFamily == UInt8(AF_INET) {
                    let name = String(cString: interface.ifa_name)
                    if name == "en0" || name == "en1" {
                        var hostname = [CChar](repeating: 0, count: Int(NI_MAXHOST))
                        getnameinfo(interface.ifa_addr, socklen_t(interface.ifa_addr.pointee.sa_len),
                                    &hostname, socklen_t(hostname.count),
                                    nil, socklen_t(0), NI_NUMERICHOST)
                        address = String(cString: hostname)
                    }
                }
            }
            freeifaddrs(ifaddr)
        }
        return address ?? "127.0.0.1"
    }
}
