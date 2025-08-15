Phase 1: Signaling Server & Web API

  This is the central nervous system of the P2P connection. Its only job is to help the two peers find and talk to each other. It never touches the actual media or data.

   1. Technology Choice:
       * You've suggested Node.js, Go, or Rust. Given the existing website is a Next.js app, the most straightforward path is to build the signaling server as a Next.js API route with WebSocket support. We can use a library like ws or socket.io within a custom server setup for Next.js, or explore Vercel's Edge Functions which are increasingly
         supporting WebSockets. For simplicity and scalability, I'll plan to use a serverless function approach.
       * Endpoint: wss://orionlive.ai/api/signal is a perfect choice.

   2. Signaling Logic:
       * Connection & Authentication: When a client (iOS or Mac app) connects, it will present a short-lived JWT as you specified. The server will validate this JWT. The claims (sub=deviceId, pairId) are crucial. The server will look up the pairId in the Supabase device_pairs table to ensure the device is part of an active pair.
       * Room Management: I'll implement a simple in-memory "room" concept on the signaling server, keyed by pairId. When two devices with the same pairId are connected, they form a room.
       * Message Relaying: The server's logic will be simple:
           * If it receives a message (offer, answer, ice) from one peer in a room, it immediately forwards it to the other peer in that same room.
           * It will validate the message schema ({ "t": "...", "pairId": "...", ... }) to prevent malformed data.
           * It will enforce that a peer can only send signals for the pairId specified in its JWT, preventing cross-talk.

   3. JWT Generation:
       * I'll need to create a new, secure API endpoint, perhaps /api/auth/webrtc-token, on the website.
       * When a logged-in client (iOS/Mac) calls this endpoint, the server will generate a JWT with a 5-minute expiry, containing the deviceId and pairId claims. This ensures that only authenticated and paired devices can even attempt to signal.

  ---


  Phase 2: iOS App Implementation (Sender)

  The iPhone will be the primary sender of the "keyframe-as-video" stream and control data.

   1. WebRTC Framework: I will use Google's official WebRTC.framework for iOS. It's the standard and provides all the necessary APIs. I'll add this as a Swift Package dependency.

   2. Connection Flow:
       * On app start (for an authenticated, paired user), the app will fetch a signaling JWT from our new /api/auth/webrtc-token endpoint.
       * It will then connect to wss://orionlive.ai/api/signal.
       * It will create an RTCPeerConnection instance, configured with the STUN/TURN server details.
       * It will create an RTCDataChannel for control messages, configured as { ordered: false, maxPacketLifeTime: 100 }.
       * It will create a video track for the H.264 keyframes.

   3. "Keyframe-as-Video" Pipeline: This is a clever approach.
       * I'll use AVCaptureSession to get raw frames from the camera.
       * Instead of streaming them directly, every 3-4 seconds I will take a single CMSampleBuffer.
       * This buffer will be passed to a VTCompressionSession (VideoToolbox). I will configure this session for low-latency H.264 encoding, specifically by:
           * Setting kVTCompressionPropertyKey_RealTime to true.
           * Disabling frame reordering (kVTCompressionPropertyKey_AllowFrameReordering to false).
           * Forcing each frame to be a keyframe (IDR) by setting kVTEncodeFrameOptionKey_ForceKeyFrame to true on every frame.
       * The resulting compressed CMSampleBuffer will be fed into the WebRTC video track's source.

   4. Signaling Implementation:
       * The app will implement handlers for RTCPeerConnectionDelegate methods.
       * didGenerate candidate: When an ICE candidate is generated, it will be wrapped in our JSON format and sent over the WebSocket.
       * When the app is ready to connect, it will call createOffer, and send the resulting SDP to the signaling server.
       * When it receives an answer or ice message from the signaling server, it will call setRemoteDescription or add(iceCandidate:) respectively.

  ---

  Phase 3: macOS App Implementation (Receiver)

  The Mac app will primarily receive and display the data.

   1. WebRTC Framework: Similar to iOS, I'll use the official WebRTC.framework for macOS.

   2. Connection Flow: The flow is symmetrical to the iOS app. It will also fetch a JWT, connect to the signaling server, and create its RTCPeerConnection.

   3. Handling Incoming Data:
       * Video Track: The didAdd stream delegate method will be triggered. I will extract the remote video track and link it to a MTKView or a native NSView that can render the video frames. Since it's a standard H.264 stream, the OS's hardware decoder will handle it automatically.
       * Data Channel: The didOpen dataChannel delegate will fire. I will set a handler for the dataChannel.didReceiveMessage(with:) event. When a message (e.g., text/control data) arrives, this handler will process it.

   4. Responding (Control Path): The Mac app will also be able to send messages back to the iPhone over its own RTCDataChannel, allowing for bidirectional control.

  ---

  Phase 4: Integration, Testing & Hardening

  This phase is about making the system robust and observable.

   1. STUN/TURN Setup:
       * Initial: I'll start with public STUN servers (stun:stun.l.google.com:19302) and Twilio's Network Traversal Service for TURN. This is the fastest way to get it working across difficult networks. The cost is minimal during development.
       * Long-term: If TURN usage is high, I'll plan a migration to a self-hosted coturn server on a cheap cloud instance for cost control. I will use the time-limited REST API for credentials as you've wisely specified.

   2. Testing & Validation:
       * Latency: I'll add simple ping/pong messages over the data channel and measure the round-trip time (RTT) using Date().timeIntervalSince1970. This will be logged to validate the sub-100ms goal.
       * Image Quality: I'll visually inspect the received keyframes on the Mac app and log the compressed frame size to ensure it stays within the ~100KB target.
       * Connection Success Rate: I will use the iceConnectionState property and getStats() API to monitor connections. I'll log whether the final connection is host, srflx (STUN), or relay (TURN). This is the most critical metric for understanding real-world performance.

   3. Observability:
       * I will build a simple "Stats" view in both the iOS and macOS apps.
       * This view will use a timer to call RTCPeerConnection.getStats() every few seconds.
       * It will display key metrics like:
           * Connection Type (P2P or Relayed)
           * Round-Trip Time (RTT)
           * Bytes Sent/Received on both video and data channels.
           * Video frame rate (even if it's just 1 frame every 3-4s).