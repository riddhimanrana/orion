<div align="center">

# Orion Server macOS Desktop Application

The macOS desktop application that serves as the server component for the Orion Live ecosystem, enabling real-time peer-to-peer WebRTC connections for visual intelligence streaming.

[![Swift](https://img.shields.io/badge/Swift-5.8+-orange.svg)](https://swift.org)
[![Platform](https://img.shields.io/badge/platform-macOS%2013.0+-blue.svg)](https://developer.apple.com/macos/)
[![Xcode](https://img.shields.io/badge/Xcode-16+-blue.svg)](https://developer.apple.com/xcode/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Dependencies](#dependencies)
- [Development](#development)
- [Contributing](#contributing)

## Overview

This is the native macOS application built with SwiftUI that acts as a WebRTC server for the Orion Live platform. It allows for real-time, low-latency video streaming and bi-directional data communication between macOS and iOS devices using peer-to-peer connections.

The application features:

- **OAuth Authentication** via Google and GitHub
- **Device Management** with automatic registration and pairing
- **WebRTC Connectivity** with STUN/TURN support for NAT traversal
- **Real-time Video Streaming** from connected iOS devices
- **Data Channel Communication** for control messages and metadata
- **Menu Bar Integration** for quick access and status monitoring
- **Connection Health Monitoring** with ICE status and RTT metrics

## Features

### Authentication & User Management

- **OAuth 2.0 Integration**: Sign in with Google or GitHub
- **Supabase Backend**: Secure session management and user profiles
- **Deep Link Handling**: Seamless OAuth callback flow
- **Auto-reconnect**: Persistent session across app launches

### Device Management

- **Automatic Device Registration**: Registers Mac as a server device
- **Device Pairing**: Pair with iOS devices using secure pairing codes
- **Multi-device Support**: Manage connections to multiple iOS devices
- **Device Discovery**: Real-time device status updates

### WebRTC P2P Communication

- **Ephemeral ICE Credentials**: Enhanced security with time-limited TURN credentials
- **ICE Connection Modes**: Automatic fallback between STUN (direct) and TURN (relay)
- **Connection Health Metrics**:
  - ICE connection state monitoring
  - Candidate type tracking (local/remote)
  - Transport protocol detection (UDP/TCP)
  - RTT (Round Trip Time) measurements
- **Signaling via Supabase**: Real-time signaling channel for SDP exchange

### Video & Data Streaming

- **Real-time Video Rendering**: Live video feed from iOS camera
- **Bi-directional Data Channel**: JSON-based message protocol
- **Versioned Message Protocol**: Extensible P2P message format
  - Ping/Pong for latency measurement
  - Request/Response patterns
  - Chunked streaming support
  - Error handling
- **LLM Integration Ready**: Infrastructure for streaming AI responses

### User Interface

- **Native SwiftUI Design**: Modern, responsive macOS interface
- **Split View Layout**: Video preview with status sidebar
- **Menu Bar Integration**: Quick access and system tray presence
- **Real-time Status Updates**: Live connection metrics and logs
- **Dark/Light Mode**: Adaptive color scheme support

## Architecture

### Core Components

```
Orion_ServerApp (Main)
├── AuthManager
│   ├── Supabase Client
│   └── OAuth Flow (ASWebAuthenticationSession)
│
├── DeviceManager
│   ├── Device Registration
│   └── Pairing Management
│
├── P2PManagers
│   ├── APIService (Backend communication)
│   ├── SignalingClient (WebRTC signaling)
│   └── WebRTCManager (RTCPeerConnection)
│
└── MenuBarManager
    └── System Tray Integration
```

### WebRTC Flow

1. **Authentication**: User signs in via OAuth
2. **Device Registration**: Mac registers as server device
3. **Pairing**: iOS app initiates pairing with code
4. **Signaling**: Exchange SDP offer/answer via Supabase
5. **ICE Negotiation**: Establish peer connection with STUN/TURN
6. **Media/Data**: Stream video and exchange messages

### Message Protocol

The application uses a versioned JSON message protocol (`P2PMessage`) for data channel communication:

```swift
{
  "v": 1,                    // Protocol version
  "id": "uuid",              // Message ID
  "t": "request",            // Type: ping, pong, request, chunk, done, error
  "correlationId": "uuid",   // For request/response matching
  "payload": { ... }         // Type-specific payload
}
```

## Requirements

- **macOS**: 13.0 (Ventura) or later
- **Xcode**: 16.0 or later
- **Swift**: 5.8 or later
- **Apple ID**: For code signing and development
- **Supabase Project**: For authentication and signaling

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/riddhimanrana/orion-desktop.git
cd orion-desktop/Orion\ Server
```

### 2. Open in Xcode

```bash
open Orion\ Server.xcodeproj
```

### 3. Install Dependencies

Dependencies are managed via Swift Package Manager and will be resolved automatically:

- **Supabase Swift SDK** (v2.31.2)
- **WebRTC** (v139.0.0)
- Supporting packages (automatically resolved)

### 4. Configure Signing

1. Select the project in Xcode
2. Go to **Signing & Capabilities**
3. Select your development team
4. Xcode will automatically manage provisioning profiles

## Configuration

### Supabase Setup

1. Create a new project at [supabase.com](https://supabase.com)
2. Note your **Project URL** and **Anon Key**
3. Set up OAuth providers (Google, GitHub) in Supabase Auth settings

### Info.plist Configuration

Add your Supabase credentials to `Orion Server/Info.plist`:

```xml
<key>SUPABASE_URL</key>
<string>https://your-project.supabase.co</string>
<key>SUPABASE_PUBLISHABLE_KEY</key>
<string>your-publishable-key-here</string>
```

### OAuth Redirect URLs

Add the following redirect URL to your OAuth providers:

```
orion://auth/callback
```

### Entitlements

The app requires the following entitlements (already configured):

- **Network Client**: For WebRTC connections
- **Outgoing Network Connections**: For Supabase API
- **App Sandbox**: macOS security requirement

## Usage

### First Launch

1. Launch the app from Xcode (`⌘+R`)
2. Sign in with Google or GitHub
3. The app will register your Mac as a server device

### Pairing with iOS Device

1. Open the Orion Live iOS app
2. Go to Settings → Server Mode
3. Enter the pairing code displayed on the Mac
4. Confirm pairing on both devices

### Viewing Video Stream

1. Once paired, the iOS app will establish a WebRTC connection
2. Video feed will appear in the main window
3. Monitor connection health in the sidebar:
   - **Signaling Status**: WebSocket connection state
   - **WebRTC Status**: Peer connection state
   - **ICE Mode**: Connection type (STUN/TURN)
   - **Data Channel**: Control message channel state
   - **Ping RTT**: Round-trip latency

### Menu Bar Integration

- Click the Orion icon in the menu bar for quick access
- View connection status at a glance
- Quick actions: Open Dashboard, Settings, Quit

## Project Structure

```
Orion Server/
├── Orion_ServerApp.swift          # App entry point, dependency injection
├── ContentView.swift              # Legacy view (not currently used)
│
├── Auth/
│   └── AuthManager.swift          # OAuth & session management
│
├── Config/
│   └── SupabaseConfig.swift       # Supabase client configuration
│
├── Managers/
│   ├── DeviceManager.swift        # Device registration & pairing
│   └── MenuBarManager.swift       # Menu bar integration
│
├── Models/
│   ├── DeviceModels.swift         # Device & pairing data models
│   └── UserProfileViewModel.swift # User profile state
│
├── P2P/
│   ├── APIService.swift           # Backend API client
│   ├── SignalingClient.swift     # WebRTC signaling (via Supabase)
│   └── WebRTCManager.swift        # RTCPeerConnection wrapper
│
├── Views/
│   ├── LoginView.swift            # OAuth login screen
│   ├── MainDashboard.swift        # Main video + sidebar UI
│   ├── UserMenuView.swift         # User profile menu
│   ├── SettingsWindow.swift       # App settings
│   ├── OTPInputView.swift         # OTP entry component
│   └── PairingCodeInputView.swift # Pairing code entry
│
└── Models/ (Top-level)
    └── P2PMessage.swift           # Shared message protocol
```

## Dependencies

All dependencies are managed via **Swift Package Manager**:

| Package | Version | Purpose |
|---------|---------|---------|
| [Supabase Swift](https://github.com/supabase/supabase-swift) | 2.31.2 | Authentication, database, real-time |
| [WebRTC](https://github.com/stasel/WebRTC) | 139.0.0 | Peer-to-peer video/data streaming |
| Apple Swift Crypto | 3.14.0 | Cryptographic operations |
| Swift HTTP Types | 1.4.0 | HTTP primitives |
| Swift Clocks | 1.0.6 | Time-based utilities |
| Swift Concurrency Extras | 1.3.1 | Concurrency helpers |

Dependencies are automatically resolved on first build.

## Development

### Building

```bash
# Build for development
xcodebuild -project "Orion Server.xcodeproj" -scheme "Orion Server" -configuration Debug

# Build for release
xcodebuild -project "Orion Server.xcodeproj" -scheme "Orion Server" -configuration Release
```

### Running Tests

```bash
xcodebuild test -project "Orion Server.xcodeproj" -scheme "Orion Server" -destination 'platform=macOS'
```

### Debugging WebRTC

Enable verbose logging in `WebRTCManager.swift`:

```swift
RTCSetMinDebugLogLevel(.verbose)
```

View logs in Xcode console for:

- ICE candidate gathering
- SDP negotiation
- Connection state changes
- Data channel messages

### Code Style

- **SwiftUI**: Declarative UI components
- **Async/await**: Modern concurrency (Swift 5.5+)
- **Combine**: Reactive state management
- **MVVM**: Model-View-ViewModel architecture
- **ObservableObject**: State propagation via `@Published`

### Development Setup

1. Ensure you have the latest Xcode installed
2. Install SwiftLint (optional but recommended):

   ```bash
   brew install swiftlint
   ```

3. Follow the Installation steps above
4. Make your changes and test thoroughly

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built and designed by Riddhiman Rana**

[Website](https://orionlive.ai) • [Research](https://orionlive.ai/research) • [GitHub](https://github.com/riddhimanrana/orion)

</div>
