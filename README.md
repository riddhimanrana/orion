# Orion

(This is a foundational prototype product; I am actively developing it and currently in Phase 2 – see [Development Timeline](https://orionlive.ai/research#timeline).)

Orion is the architecture behind Orion Live, a real-time visual intelligence platform designed around a hybrid edge-server architecture with a privacy-first approach. It combines on-device vision models, a Python FastAPI cloud-based backend, a Mac server desktop app, and a responsive web dashboard to deliver low-latency object detection, semantic understanding, and temporal reasoning.

## Demo

![Orion Demo](./demo/iosdemo.gif)

## Architecture Overview

- **iOS App**  
  Runs YOLOv11n for object detection and FastVLM for on-device image captioning. Streams structured payloads over WebSockets to the server.

- **Mac/Cloud Server**  
  Python FastAPI + WebSockets backend for queue management, LLM reasoning (Gemma-3B via MLX or Vertex AI), and vision-language processing. Supports local macOS deployment and cloud hosting on Google Vertex AI(this will be released soon in an upcoming prototype release)

- **Web Dashboard**  
  Next.js + Tailwind CSS interface for billing, authentication, usage metrics, and API interaction, with real-time monitoring of detections and system performance.

## Getting Started

Each component lives in its own folder with its own README and startup instructions:

- **mobile/** – iOS app (see mobile/Orion/README.md)  
- **server/** – Python FastAPI backend (see server/README.md)  
- **website/** – Next.js dashboard (see website/README.md)  
- **desktop/** – macOS app (see desktop/README.md)

## Research & Deep Dive

For full research details, system design, and technical architecture, visit [https://orionlive.ai/research](https://orionlive.ai/research).
A formal research paper will be published next year upon completion of development.

## Current Work

- Developing a **macOS desktop app** in SwiftUI.  
- Developing the **server backend** on Google Vertex AI for managed inference.  
- Working on the **cloud API** for scalable, multi-tenant deployments.
- Developing the **server backend** on Google Vertex AI for managed inference.  
- Working on the **cloud API** for scalable, multi-tenant deployments.

## Real-world Applications

Orion Live can be used in various applications such as blind disability assistance systems, deployable visual perception agents in systems like drones, robots, and other autonomous systems, and also act as a general-purpose live visual intelligence agent similar to the likes of Gemini Live and OpenAI Sora but with a focus on being open-source, real-time, and privacy-first.


## License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.
