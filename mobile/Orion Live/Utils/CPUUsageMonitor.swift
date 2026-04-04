//
//  CPUUsageMonitor.swift
//  Orion Live
//
//  Created by Copilot on 9/14/25.
//  Lightweight CPU usage sampler for app/system for Debug UI.
//

import Foundation
import Combine

final class CPUUsageMonitor: ObservableObject {
    @Published var systemCPUPercent: Double = 0 // 0-100 overall
    
    private var timer: Timer?
    private let interval: TimeInterval = 1.0
    
    func start() {
        stop()
        timer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { [weak self] _ in
            self?.sample()
        }
        if let timer { RunLoop.main.add(timer, forMode: .common) }
    }
    
    func stop() {
        timer?.invalidate()
        timer = nil
    }
    
    private var prevUser: Double = 0
    private var prevSystem: Double = 0
    private var prevIdle: Double = 0
    private var prevNice: Double = 0

    private func sample() {
        var count = mach_msg_type_number_t(MemoryLayout<host_cpu_load_info_data_t>.stride / MemoryLayout<integer_t>.stride)
        var info = host_cpu_load_info_data_t()
        let kr = withUnsafeMutablePointer(to: &info) { infoPtr in
            infoPtr.withMemoryRebound(to: integer_t.self, capacity: Int(count)) { intPtr in
                host_statistics(mach_host_self(), host_flavor_t(HOST_CPU_LOAD_INFO), intPtr, &count)
            }
        }
        guard kr == KERN_SUCCESS else { return }
        let user = Double(info.cpu_ticks.0)
        let system = Double(info.cpu_ticks.1)
        let idle = Double(info.cpu_ticks.2)
        let nice = Double(info.cpu_ticks.3)

        let dUser = user - prevUser
        let dSystem = system - prevSystem
        let dIdle = idle - prevIdle
        let dNice = nice - prevNice
        let total = dUser + dSystem + dIdle + dNice
        if total > 0 {
            let busy = dUser + dSystem + dNice
            systemCPUPercent = min(max(busy / total * 100.0, 0), 100)
        }
        prevUser = user; prevSystem = system; prevIdle = idle; prevNice = nice
    }
}

// MARK: - Sampling helpers
import Darwin

// No extra helpers needed; we compute deltas inside sample()
