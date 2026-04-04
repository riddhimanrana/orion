//
//  NetworkMonitor.swift
//  Orion Live
//
//  Created by Copilot on 9/16/25.
//  Monitors network connectivity status using NWPathMonitor per Apple guidelines.
//

import Foundation
import Network
import Combine
import SwiftUI

@MainActor
final class NetworkMonitor: ObservableObject {
    @Published private(set) var isConnected: Bool = true
    @Published private(set) var interfaceType: NWInterface.InterfaceType? = nil

    private var monitor: NWPathMonitor?
    private let queue = DispatchQueue(label: "ai.orionlive.network.monitor")

    init() {
        start()
    }

    func start() {
        // Avoid starting twice
        if monitor != nil { return }
        let monitor = NWPathMonitor()
        self.monitor = monitor
        monitor.pathUpdateHandler = { [weak self] path in
            guard let self = self else { return }
            Task { @MainActor in
                self.isConnected = path.status == .satisfied
                self.interfaceType = path.availableInterfaces.first(where: { path.usesInterfaceType($0.type) })?.type
            }
        }
        monitor.start(queue: queue)
    }

    func stop() {
        monitor?.cancel()
        monitor = nil
    }

    deinit {
        monitor?.cancel()
        monitor = nil
    }
}
