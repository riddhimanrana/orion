# Orion Live

Real-time scene understanding with temporal vision context combining on-device **fastVLM-0.5b** and **YOLOv11n** with **gemma3:1.5b** reasoning to track, remember, and analyze visual events as they unfold.

## System Overview

1. **iOS App**:
   - Runs **YOLOv11n** for real-time object detection
   - Runs **fastVLM-0.5b** for on-device image description (vision-language model)
   - Streams object detections and image descriptions to the server via WebSocket
   - Displays enhanced scene understanding and receives contextual responses

2. **Mac Server**:
   - Runs on Apple Silicon (M1/M2/M3)
   - Receives detections and descriptions from iOS device
   - Uses **gemma3:1.5b** for language and contextual analysis
   - Maintains **temporal context** for richer, history-aware responses
   - Sends back contextual scene analysis and answers

## Requirements

- Apple Silicon Mac (M1/M2/M3/M4)
- macOS 12.0 or later
- Python 3.10+
- iOS 15.0+ device
- Local network connection(since we use websocket for communication)

## Quick Start

1. Clone the repository:

```bash
git clone https://github.com/riddhimanrana/orion
cd orion
```

*This is broken for now, it will be eventually fixed*

1. Install and setup server:

```bash
cd server
chmod +x orion.sh
./orion.sh --install
```

1. Start the server:

```bash
./orion.sh --start
```

## iOS App Setup

1. Open the iOS project in Xcode:

```bash
cd ios/Orion
open Orion.xcodeproj
```

1. Update server address in `Constants.swift`
1. Build and run on your device

## System Architecture

### iOS Components

- Real-time camera feed
- **YOLOv11n** object detection (on-device)
- **fastVLM-0.5b** image description (on-device)
- WebSocket communication (sends both detections and VLM descriptions)
- Detection and context visualization

### Server Components

- Receives detections and VLM descriptions from iOS
- **Gemma** model for language/contextual analysis
- **Temporal context memory** for scene history and continuity
- WebSocket server for communication

## Model Information

- **On-device (iOS):**
  - **YOLOv11n** for object detection
  - **fastVLM-0.5b** for image/scene description

- **Server (Mac):**
  - **Gemma** for language and contextual analysis
  - Temporal context module for scene memory

## Performance Notes

- All vision-language inference (fastVLM-0.5b) runs on-device for privacy and speed
- Only lightweight data (detections + descriptions) sent to server
- Server maintains context and provides fast, relevant responses using Gemma
- Low-latency WebSocket communication

## Customization

### Environment Variables

```bash
# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true
LOG_LEVEL=INFO
```

### Model Weights

- iOS models (YOLOv11n, fastVLM-0.5b) are bundled or downloaded on first launch
- Server models (Gemma) are downloaded automatically during setup
- Custom models can be placed in `server/weights/`

## Development

- iOS app code in `mobile/Orion/`
- Server code in `server/`
- Models in `server/weights/`

## License

MIT License - See LICENSE file for details.

## Support

- Works exclusively on Apple Silicon Macs
- Requires MLX for model inference on server
- All vision-language inference is on-device for privacy
- Local network deployment only
