# Orion Live Vision Understanding

Real-time scene understanding system using YOLOv11n on iOS and MLX-powered vision-language models on Apple Silicon Macs.

## System Overview

1. **iOS App**:
   - Runs YOLOv11n for real-time object detection
   - Streams detections and frame data to server
   - Displays enhanced scene understanding

2. **Mac Server**:
   - Runs on Apple Silicon (M1/M2/M3)
   - Uses MLX for efficient model inference
   - Combines iOS detections with enhanced vision understanding
   - Provides contextual scene analysis

## Requirements

- Apple Silicon Mac (M1/M2/M3)
- macOS 12.0 or later
- Python 3.13+
- iOS 15.0+ device
- Local network connection

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/riddhimanrana/orion-live
cd orion-live
```

2. Install and setup server:
```bash
cd server
chmod +x orion.sh
./orion.sh --install
```

3. Start the server:
```bash
./orion.sh --start
```

## iOS App Setup

1. Open the iOS project in Xcode:
```bash
cd ios/Orion
open Orion.xcodeproj
```

2. Update server address in `Constants.swift`
3. Build and run on your device

## System Architecture

### iOS Components
- Real-time camera feed
- YOLOv11n object detection
- WebSocket communication
- Detection visualization

### Server Components
- MLX vision-language model for scene understanding
- Gemma 3B for language processing
- Context memory system
- WebSocket server

## Model Information

The server uses:
- Apple MLX for efficient inference
- Vision-Language model for scene understanding
- Gemma 3B for contextual analysis
- Scene memory for temporal context

## Performance Notes

- YOLOv11n runs in real-time on iOS devices
- MLX enables efficient inference on Apple Silicon
- Low-latency WebSocket communication
- Contextual understanding with 1-second history

## Customization

### Environment Variables
```bash
# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true
LOG_LEVEL=INFO

# MLX Models
VLM_MODEL_PATH=weights/vlm/model.mlx
GEMMA_MODEL_PATH=weights/gemma/model.mlx
```

### Model Weights
- Models are downloaded automatically during setup
- Custom models can be placed in `server/weights/`

## Development

- iOS app code in `ios/Orion/`
- Server code in `server/`
- Models in `server/weights/`

## License

MIT License - See LICENSE file for details.

## Support

- Works exclusively on Apple Silicon Macs
- Requires MLX for model inference
- Local network deployment only
