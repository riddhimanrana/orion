# P2P Test Plan & Fallback

This guide walks you through validating the WebRTC P2P connection between iOS and macOS using your TURN server, and how to confirm whether the session is relayed (TURN) or direct (STUN).

## 1) Wire your TURN server

Add your TURN endpoints and credentials to both apps.

iOS `Orion Live/Info.plist`:

- TURN_URLS:
  - turn:turn.orionlive.ai:3478?transport=udp
  - turn:turn.orionlive.ai:3478?transport=tcp
  - turns:turn.orionlive.ai:5349?transport=tcp
- TURN_USERNAME: your-turn-username
- TURN_PASSWORD: your-turn-password

macOS `Orion Server/Info.plist`:

- Same keys and values as above.

Notes:

- Include both UDP and TCP, plus TLS (5349) for restrictive networks. WebRTC will pick the best viable candidate.
- For production, prefer short‑lived (ephemeral) TURN credentials minted server-side. Static creds work for initial validation.

## 2) Bring up peers

On macOS (Orion Server):

- Sign in and open the main dashboard. Ensure Signaling shows “connected”.

On iOS (Orion Live):

- Navigate to Debug → P2P Connection.
- Tap Connect.

Expected:

- WebRTC Status goes to connected/completed.
- DataChannel shows open.

## 3) Verify TURN vs STUN in the UI

In iOS Debug → P2P Connection:

- ICE Mode row: shows “TURN (relay)” when your session is using your TURN server; otherwise “STUN/Direct”.
- ICE Types row: shows Local/Remote candidate types (host, srflx, prflx, relay) and transport (udp/tcp).

On macOS Sidebar (Orion Server):

- ICE Mode and ICE Types mirror the same info.

Tip: On typical home Wi‑Fi you may see STUN/Direct (host/srflx). On restricted or cross‑NAT networks you should see TURN (relay).

## 4) Ping sanity check

- Tap Ping in iOS Debug. RTT should update (in ms). Expect higher RTT when relayed via TURN.

## 5) Troubleshooting

If ICE Mode never shows TURN (relay):

- Confirm ports are reachable from both devices:
  - 3478/udp, 3478/tcp, 5349/tcp on turn.orionlive.ai
- Check your TLS cert is valid and SNI matches (for turns://).
- Verify firewall allows outbound and inbound on the above ports.
- Inspect TURN logs (coturn) for allocations and relayed candidate generation.
- Try temporarily disabling UDP on one client’s network (e.g., captive portal/enterprise Wi‑Fi) to force TCP/TLS.

If connection fails (WebRTC failed/disconnected):

- Ensure signaling is connected on both ends.
- Re‑check TURN_USERNAME/PASSWORD; wrong creds will prevent relay candidates.
- Use only turns:5349 if UDP is blocked by the network.

Optional force‑relay test (dev only):

- In `WebRTCManager.setupPeerConnection`, set `configuration.iceTransportPolicy = .relay` to force TURN. Rebuild both apps, connect, and confirm ICE Mode shows TURN, then revert.

## 6) Fallback (future)

If P2P cannot be established even with TURN, a server relay fallback can be added:

- WebSocket relay on the signaling server to forward data channel payloads.
- The app would switch to relay mode after a timeout (e.g., 8–12s) without ICE connection.

This repo currently prefers WebRTC+TURN; fallback relay is a future enhancement.
