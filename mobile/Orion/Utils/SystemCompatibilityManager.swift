//
//  SystemCompatibilityManager.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//  Manages device compatibility checks and requirements for Orion Live.
//  Copyright (C) 2025 Riddhiman Rana. All Rights Reserved.
//
import Foundation
import SwiftUI
import Combine
import UIKit // For UIDevice
import os.log // For Logger

@MainActor
class SystemCompatibilityManager: ObservableObject {
    @Published var deviceModel: String = "Unknown Device"
    @Published var iosVersion: String = "Unknown iOS"
    @Published var chipType: String = "Unknown Chip"
    @Published var ramGB: Int = 0
    @Published var isCompatible: Bool = false
    @Published var compatibilityDetails: [CompatibilityCheckResult] = []

    // Compatibility Requirements
    private let requirediOSVersionMajor = 18
    private let requiredChipMinAValue = 14 // A14 Bionic or newer
    private let requiredRAMGB = 4

    init() {
        Task {
            await performSystemChecks()
        }
    }

    func performSystemChecks() async {
        // Reset for fresh check
        compatibilityDetails = []

        // 1. Get Device Model and Chip Type
        let (model, chip) = getDeviceModelAndChip()
        self.deviceModel = model
        self.chipType = chip

        // 2. Get iOS Version
        let osVersion = ProcessInfo.processInfo.operatingSystemVersion
        self.iosVersion = "\(osVersion.majorVersion).\(osVersion.minorVersion)\(osVersion.patchVersion > 0 ? ".\(osVersion.patchVersion)" : "")"

        // 3. Get RAM
        self.ramGB = Int(ProcessInfo.processInfo.physicalMemory / (1024 * 1024 * 1024))

        // 4. Evaluate Compatibility
        evaluateCompatibility()
    }

    private func getDeviceModelAndChip() -> (model: String, chip: String) {
        var systemInfo = utsname()
        uname(&systemInfo)
        let machineMirror = Mirror(reflecting: systemInfo.machine)
        let identifier = machineMirror.children.reduce("") { identifier, element in
            guard let value = element.value as? Int8, value != 0 else { return identifier }
            return identifier + String(UnicodeScalar(UInt8(value)))
        }

        // Mapping from identifier to marketing name and chip type
        // This list needs to be updated as new devices are released
        // Only including A14+ and M-series chips as per requirement
        let deviceMap: [String: (model: String, chip: String)] = [
            // A14 Bionic
            "iPhone13,2": ("iPhone 12", "A14 Bionic"),
            "iPhone13,3": ("iPhone 12 Pro", "A14 Bionic"),
            "iPhone13,4": ("iPhone 12 Pro Max", "A14 Bionic"),
            "iPhone13,1": ("iPhone 12 mini", "A14 Bionic"),
            "iPad13,1": ("iPad Air (4th Gen)", "A14 Bionic"),
            "iPad13,2": ("iPad Air (4th Gen)", "A14 Bionic"),
            "iPad13,16": ("iPad (10th Gen)", "A14 Bionic"),
            "iPad13,17": ("iPad (10th Gen)", "A14 Bionic"),

            // A15 Bionic
            "iPhone14,2": ("iPhone 13 Pro", "A15 Bionic"),
            "iPhone14,3": ("iPhone 13 Pro Max", "A15 Bionic"),
            "iPhone14,4": ("iPhone 13 mini", "A15 Bionic"),
            "iPhone14,5": ("iPhone 13", "A15 Bionic"),
            "iPhone14,6": ("iPhone SE (3rd Gen)", "A15 Bionic"),
            "iPhone14,7": ("iPhone 14", "A15 Bionic"),
            "iPhone14,8": ("iPhone 14 Plus", "A15 Bionic"),
            "iPad14,1": ("iPad mini (6th Gen)", "A15 Bionic"),
            "iPad14,2": ("iPad mini (6th Gen)", "A15 Bionic"),

            // A16 Bionic
            "iPhone15,2": ("iPhone 15 Pro", "A16 Bionic"),
            "iPhone15,3": ("iPhone 15 Pro Max", "A16 Bionic"),
            "iPhone15,4": ("iPhone 15", "A16 Bionic"),
            "iPhone15,5": ("iPhone 15 Plus", "A16 Bionic"),

            // A17 Pro (Hypothetical for future, assuming A17 is A17 Pro)
            "iPhone16,1": ("iPhone 16 Pro", "A17 Pro"), // Placeholder
            "iPhone16,2": ("iPhone 16 Pro Max", "A17 Pro"), // Placeholder

            // M1 Series
            "iPad8,11": ("iPad Pro (3rd Gen)", "M1"), // 11-inch
            "iPad8,12": ("iPad Pro (3rd Gen)", "M1"), // 11-inch
            "iPad8,9": ("iPad Pro (5th Gen)", "M1"), // 12.9-inch
            "iPad8,10": ("iPad Pro (5th Gen)", "M1"), // 12.9-inch
            "iPad13,4": ("iPad Pro (5th Gen)", "M1"), // 11-inch
            "iPad13,5": ("iPad Pro (5th Gen)", "M1"), // 11-inch
            "iPad13,6": ("iPad Pro (5th Gen)", "M1"), // 11-inch
            "iPad13,7": ("iPad Pro (5th Gen)", "M1"), // 11-inch
            "iPad13,8": ("iPad Pro (5th Gen)", "M1"), // 12.9-inch
            "iPad13,9": ("iPad Pro (5th Gen)", "M1"), // 12.9-inch
            "iPad13,10": ("iPad Pro (5th Gen)", "M1"), // 12.9-inch
            "iPad13,11": ("iPad Pro (5th Gen)", "M1"), // 12.9-inch
            "iPad14,3": ("iPad Air (5th Gen)", "M1"),
            "iPad14,4": ("iPad Air (5th Gen)", "M1"),

            // M2 Series
            "iPad14,8": ("iPad Pro (6th Gen)", "M2"), // 11-inch
            "iPad14,9": ("iPad Pro (6th Gen)", "M2"), // 11-inch
            "iPad14,10": ("iPad Pro (6th Gen)", "M2"), // 12.9-inch
            "iPad14,11": ("iPad Pro (6th Gen)", "M2"), // 12.9-inch
            "iPad14,12": ("iPad Air (6th Gen)", "M2"), // Placeholder
            "iPad14,13": ("iPad Air (6th Gen)", "M2"), // Placeholder

            // M3 Series (Hypothetical for future iPads)
            "iPad15,1": ("iPad Pro (7th Gen)", "M3"), // Placeholder
            "iPad15,2": ("iPad Pro (7th Gen)", "M3"), // Placeholder
        ]

        let (model, chip) = deviceMap[identifier] ?? ("Unknown Device", "Unknown Chip")
        Logger.shared.log("Detected Device: \(model) (\(identifier)), Chip: \(chip)", level: .info, category: .general)
        return (model, chip)
    }

    private func evaluateCompatibility() {
        var allChecksPassed = true

        // iOS Version Check
        let osVersionComponents = iosVersion.split(separator: ".").compactMap { Int($0) }
        let isiOSCompatible = osVersionComponents.first ?? 0 >= requirediOSVersionMajor
        compatibilityDetails.append(CompatibilityCheckResult(
            name: "iOS Version",
            status: isiOSCompatible,
            details: "Requires iOS \(requirediOSVersionMajor)+. Detected: iOS \(iosVersion)"
        ))
        if !isiOSCompatible { allChecksPassed = false }

        // Chip Type Check
        var isChipCompatible = false
        if chipType.hasPrefix("A") {
            let chipNumberString = String(chipType.filter(\.isNumber))
            if let chipNumber = Int(chipNumberString) {
                isChipCompatible = chipNumber >= requiredChipMinAValue
            }
        } else if chipType.hasPrefix("M") {
            // All M-series chips are considered compatible for now
            isChipCompatible = true
        }
        compatibilityDetails.append(CompatibilityCheckResult(
            name: "Processor",
            status: isChipCompatible,
            details: "Requires iPhone 12 (A14 Bionic) or newer. Detected: \(chipType)"
        ))
        if !isChipCompatible { allChecksPassed = false }

        // RAM Check
        let isRAMCompatible = Double(ramGB) >= 3 // Roughly 4GB RAM
        compatibilityDetails.append(CompatibilityCheckResult(
            name: "RAM",
            status: isRAMCompatible,
            details: "Requires roughly 4GB RAM+. Detected: \(ramGB)GB"
        ))
        if !isRAMCompatible { allChecksPassed = false }

        self.isCompatible = allChecksPassed
        Logger.shared.log("System Compatibility: \(isCompatible ? "Compatible" : "Not Compatible")", level: .info, category: .general)
    }
}

struct CompatibilityCheckResult: Identifiable {
    let id = UUID()
    let name: String
    let status: Bool // true for compatible, false for not
    let details: String
}