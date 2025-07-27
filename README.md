# Orion

(This is a foundational prototype product; I am actively developing it and currently in Phase 2 – see [Development Timeline](https://orionlive.ai/research#timeline))

**Orion** is the architecture behind **Orion Live**, a real-time visual intelligence platform designed around a hybrid edge-server architecture with a privacy-first approach. It is designed to be an intelligent, interactive, and deployable visual perception agent that can truly "remember" and "understand" the world as it unfolds with a focus on being open-source, real-time, and privacy-first.

**Check it out at [orionlive.ai](https://orionlive.ai)**

## Demo

![Orion Demo](./demo/mobiledemo.gif)

*This is a demo of the iOS app running a prototype foundational version of Orion Live on an iPhone 12 w/4GB RAM and an A14 Bionic chip. Processing times, TTFT, and latency are still being optimized and are targeted to be under 1-2 seconds. Nothing is sent to the cloud in this demo, and all processing is done on-device.*

## What makes Orion different than Gemini Live/OpenAI Sora?

The problem with tools like Gemini Live and OpenAI Sora(Note: As of 7/26/25, OpenAI Sora still lacks the ability to process real-time visual queries) is that they are often slow, require steady cloud processing, and are solely focused on short, user-based interactions. Like imagine you are a blind person who really needs assistance from a tool like this, and imagine that every aspect of your life and every moment and interaction is sent to some Google server hundreds of miles away and you have no clue with who's accessing that data and what they're doing with it. With Orion, I aim to change that by providing a system architecture that can run on an entirely local architecture, split processing on edge devices, and provide real-time responses to user queries while maintaining a high quality of output, privacy, and security in various types of environments, maintaining context and memory of the world as it unfolds.

## Architecture Overview

- **iOS App**  
  Runs YOLOv11n for object detection and FastVLM for on-device image captioning. Streams structured payloads over API Packets to the server.

- **Mac/Cloud Server**  
  Python FastAPI + API server backend for queue management, LLM reasoning (Gemma-3B via MLX or Vertex AI), and vision-language processing. Supports local macOS deployment and cloud hosting on Google Vertex AI(this will be released soon in an upcoming prototype release)

- **Web Dashboard**  
  Next.js + Tailwind CSS responsive interface for billing, authentication, usage metrics, and API interaction, with real-time monitoring of detections and system performance.

## Getting Started

Each component lives in its own folder with its own README and startup instructions:

- **mobile/** – iOS app (see mobile/README.md)  
- **server/** – Python FastAPI backend (see server/README.md)  
- **website/** – Next.js dashboard (see website/README.md)  
- **desktop/** – macOS app (see desktop/README.md)

## Research & Deep Dive

For full research details, system design, and related research, visit [orionlive.ai/research](https://orionlive.ai/research).
I will be publishing a formal research paper next year upon completion of development.

## Current Work

- Developing a **macOS desktop app** in SwiftUI.  
- Developing the **server backend** on Google Vertex AI for managed inference.  
- Working on the **cloud API** for scalable, multi-tenant deployments.

See the [Development Timeline](https://orionlive.ai/research#timeline) for more details on current and future work.

## Real-world Applications

Orion Live can be used in various applications such as blind disability assistance systems, deployable visual perception agents in systems like drones, robots, and other autonomous systems, and also act as a general-purpose live visual intelligence agent similar to the likes of Gemini Live and OpenAI Sora but with a focus on being open-source, real-time, and privacy-first and at a higher quality of output more tailored to specific use cases. See [Real-World Applications](https://orionlive.ai/research#applications) for more details.

## License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.
