import Foundation
import Combine

class ProcessManager: ObservableObject {
    static let shared = ProcessManager()
    
    @Published var isRunning = false
    @Published var logs = ""
    @Published var cpuUsage: Double = 0.0
    @Published var memoryUsage: Double = 0.0
    
    private var process: Process?
    private var outputPipe: Pipe?
    private var errorPipe: Pipe?
    private var timer: Timer?
    
    private init() {}
    
    private func findProjectRoot() -> URL? {
        let sourceFilePath = #file
        let fileURL = URL(fileURLWithPath: sourceFilePath)
        let projectRoot = fileURL
            .deletingLastPathComponent() // desktop/Orion Server/
            .deletingLastPathComponent() // desktop/
            .deletingLastPathComponent() // project root/
        
        let packageJsonPath = projectRoot.appendingPathComponent("package.json").path
        if FileManager.default.fileExists(atPath: packageJsonPath) {
            return projectRoot
        }
        return nil
    }
    
    func start() {
        guard !isRunning else { return }
        
        guard let projectRoot = findProjectRoot() else {
            appendLog("[Error] Could not locate project root directory.\n")
            return
        }
        
        let pythonPath = projectRoot.appendingPathComponent("research/.venv/bin/python").path
        let serverPath = projectRoot.appendingPathComponent("server").path
        
        guard FileManager.default.fileExists(atPath: pythonPath) else {
            appendLog("[Error] Python virtual environment not found at: \(pythonPath)\n")
            return
        }
        
        appendLog("[Info] Starting Python uvicorn server process...\n")
        appendLog("[Info] Python path: \(pythonPath)\n")
        appendLog("[Info] Server path: \(serverPath)\n")
        
        let process = Process()
        self.process = process
        process.executableURL = URL(fileURLWithPath: pythonPath)
        process.currentDirectoryURL = URL(fileURLWithPath: serverPath)
        process.arguments = ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"]
        
        // Setup pipes
        let outputPipe = Pipe()
        let errorPipe = Pipe()
        self.outputPipe = outputPipe
        self.errorPipe = errorPipe
        process.standardOutput = outputPipe
        process.standardError = errorPipe
        
        let outHandle = outputPipe.fileHandleForReading
        let errHandle = errorPipe.fileHandleForReading
        
        outHandle.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if let str = String(data: data, encoding: .utf8), !str.isEmpty {
                DispatchQueue.main.async {
                    self?.appendLog(str)
                }
            }
        }
        
        errHandle.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if let str = String(data: data, encoding: .utf8), !str.isEmpty {
                DispatchQueue.main.async {
                    self?.appendLog(str)
                }
            }
        }
        
        process.terminationHandler = { [weak self] proc in
            DispatchQueue.main.async {
                self?.isRunning = false
                self?.appendLog("[Info] Subprocess exited with status: \(proc.terminationStatus)\n")
                self?.stopMonitoring()
            }
        }
        
        do {
            try process.run()
            self.isRunning = true
            appendLog("[Info] Subprocess is running (PID: \(process.processIdentifier))\n")
            startMonitoring(pid: process.processIdentifier)
        } catch {
            appendLog("[Error] Failed to launch subprocess: \(error.localizedDescription)\n")
            self.isRunning = false
        }
    }
    
    func stop() {
        guard isRunning, let process = process else { return }
        appendLog("[Info] Stopping Python uvicorn server process...\n")
        process.terminate()
        
        outputPipe?.fileHandleForReading.readabilityHandler = nil
        errorPipe?.fileHandleForReading.readabilityHandler = nil
        
        self.process = nil
        self.outputPipe = nil
        self.errorPipe = nil
        self.isRunning = false
        stopMonitoring()
    }
    
    private func appendLog(_ text: String) {
        self.logs += text
        if self.logs.count > 100_000 {
            self.logs = String(self.logs.suffix(50_000))
        }
    }
    
    private func startMonitoring(pid: Int32) {
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.updateResourceUsage(pid: pid)
        }
    }
    
    private func stopMonitoring() {
        timer?.invalidate()
        timer = nil
        cpuUsage = 0.0
        memoryUsage = 0.0
    }
    
    private func updateResourceUsage(pid: Int32) {
        let psProcess = Process()
        psProcess.executableURL = URL(fileURLWithPath: "/bin/ps")
        psProcess.arguments = ["-p", "\(pid)", "-o", "%cpu,rss"]
        
        let pipe = Pipe()
        psProcess.standardOutput = pipe
        
        do {
            try psProcess.run()
            psProcess.waitUntilExit()
            
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            if let output = String(data: data, encoding: .utf8) {
                let lines = output.split(separator: "\n")
                if lines.count >= 2 {
                    let statsLine = lines[1].trimmingCharacters(in: .whitespacesAndNewlines)
                    let components = statsLine.split(separator: " ", omittingEmptySubsequences: true)
                    if components.count >= 2 {
                        if let cpuVal = Double(components[0]), let rssVal = Double(components[1]) {
                            DispatchQueue.main.async {
                                self.cpuUsage = cpuVal
                                self.memoryUsage = rssVal / 1024.0
                            }
                        }
                    }
                }
            }
        } catch {
            // Fail silently
        }
    }
    
    deinit {
        stop()
    }
}
