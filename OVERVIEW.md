
# 1) Goals & constraints (what we’re optimizing for)

* **Transport**: P2P by default; TURN relay only when NATs force it. End-to-end encryption mandatory. ([MDN Web Docs][1], [WebRTC][2], [WebRTC for the Curious][3])
* **Data types**:

  * **Text/control**: ≤2000 chars, sub-100 ms one-way (partial reliability, unordered). ([MDN Web Docs][4])
  * **Images**: you’ll emit a \~600×400 keyframe every 3–4 s on a **video track** (H.264) using hardware encoding on iOS/macOS. ([MDN Web Docs][5], [WebKit][6], [Apple Developer][7])

---

# 2) High-level architecture

**Control plane (signaling)**

* Single endpoint: `wss://orionlive.ai/api/signal` using WebSockets. It only shuttles **SDP offers/answers** and **ICE candidates**; no media or data goes through it. ([MDN Web Docs][8], [Ant Media][9])

**Media/data plane (P2P)**

* **RTCPeerConnection** with STUN (public discovery) and TURN (relay fallback).
* **Video track**: your “keyframe-as-video” frames.
* **RTCDataChannel**: text/control, configured for **unordered** + **partial reliability**.
* All WebRTC flows are secured by **DTLS/SRTP** by design. ([MDN Web Docs][1], [WebRTC for the Curious][3], [IETF Datatracker][10])

---

# 3) Hosting the signaling API

* **Runtime**: Any fast WS server (Node/Go/Rust). Keep it **stateless** and horizontally scalable; store device/pair state in Supabase (you already have this).
* **DNS/Certs**: `orionlive.ai` apex → CDN/edge/ALB → your WS service.
* **Protocol**: JSON messages with minimal schema:

  ```json
  { "t":"offer","pairId":"...","sdp":"..." }
  { "t":"answer","pairId":"...","sdp":"..." }
  { "t":"ice","pairId":"...","candidate":"...", "mid":"..." }
  { "t":"bye","pairId":"..." }
  ```
* **Why WebSocket?** It’s the simplest low-latency, bidirectional channel and is the canonical path in the MDN sample flows for WebRTC signaling. ([MDN Web Docs][8])

**Auth for signaling**

* Issue **short-lived JWTs** (≤5 min) per device/pair with claims: `sub=deviceId`, `pairId`, `exp`, `kid`.
* WS connects with `Authorization: Bearer <token>`.
* Server checks device ↔ pair in Supabase, then lets peers exchange SDP/ICE.
* You don’t need mTLS on signaling; the actual media/data is end-to-end under DTLS/SRTP. ([IETF Datatracker][10])

---

# 4) NAT traversal (ICE/STUN/TURN)

* **STUN**: Add at least 2 geographically close STUN servers.
* **TURN**: Run **coturn** yourself (on UDP+TCP, ports 3478 + TLS 5349) or use a managed service (Twilio NTS).

  * Managed **Twilio NTS** pricing (Aug 2025): **\$0.40/GB** for US/EU, **\$0.60/GB** APAC, **\$0.80/GB** AU/BR. ([Twilio][11], [WebRTC.ventures][12])
  * If self-hosting coturn, follow hardened config (long-term creds, TLS, no loopback peers, proper firewall). ([GitHub][13], [metered.ca][14])
* **Trickle ICE**: Enable it for faster setup; start checks as candidates appear. ([WebRTC][2], [IETF Datatracker][15], [webrtcHacks][16])

---

# 5) Media pipeline — “keyframe as video”

You’ll send stills as periodic keyframes over a **video track** so WebRTC gives you congestion control, pacing, FEC/NACK, and hardware decode for free.

**Codec**

* Prefer **H.264 Constrained Baseline/Main**, universally supported (and HW-accelerated on iOS/macOS). Safari supports H.264 and VP8 in WebRTC (H.264 is default). ([MDN Web Docs][5], [WebKit][6])

**On iPhone (sender)**

* Use **VideoToolbox** `VTCompressionSession` with low-delay settings:

  * Real-time mode, no frame reordering (B-frames off), short keyframe interval (since every frame can be an IDR in your scheme), target bitrate tuned to hit <100 KB for \~600×400.
  * Force IDR on each emission or set interval so every frame is an IDR (your “keyframe-only” stream).
  * APIs: `VTCompressionSession`, compression properties, and “complete frames” control. ([Apple Developer][7])

**Receiver (Mac)**

* Attach the remote track to your renderer (or decode yourself with VideoToolbox if you’re not using WebRTC’s renderer). VT decoding is hardware-accelerated. ([Apple Developer][7])

**Why this works well**

* WebRTC’s media stack (SRTP, jitter buffers, loss recovery, congestion control) is purpose-built for low-latency visuals; you avoid reinventing custom UDP logic. ([MDN Web Docs][1])

---

# 6) Text/control path — RTCDataChannel

* Create one channel for **control** and another for **telemetry** (optional).
* Options for your 2000-char messages:

  * `ordered: false` (don’t head-of-line block), and **either** `maxPacketLifeTime: 100` ms **or** `maxRetransmits: 0`. (You can’t set both.) ([MDN Web Docs][17])
* Messages are secured via DTLS (part of WebRTC). ([MDN Web Docs][4])
* Use a compact payload format (**CBOR** or **protobuf**) to keep frames tiny and alloc-light. (General best practice; MDN covers channel usage.) ([MDN Web Docs][4])

---

# 7) Performance targets & tunables

**Latency**

* Text/control: sub-100 ms achievable with unordered/partial reliability and P2P paths. (SCTP over DTLS over UDP with partial reliability is the design point.) ([IETF Datatracker][18])

**Bitrate & size (video keyframes)**

* For 600×400 every \~3–4 s, start around **80–120 kbps** target and measure. H.264 will often yield **<100 KB** per keyframe at that size with reasonable QP. Adjust VT bitrate and profile to hit your size ceiling. (Apple docs show VT low-latency controls; exact numbers depend on scene complexity.) ([Apple Developer][19])

**QoS / DSCP**

* If your clients are on managed networks (enterprise/Wi-Fi with QoS), you can leverage the **WebRTC Priority/DSCP** control surface. Browsers may mark packets per **RFC 8837** (when allowed by OS/policy). Don’t rely on it on the open internet, but it helps on LANs. ([W3C][20], [IETF Datatracker][21])

---

# 8) Security model (end-to-end)

* **Signaling**: WSS + JWT auth (short-lived, pair-bound).
* **Media/Data**: DTLS-SRTP for media, DTLS-SCTP for data channels; keys negotiated per-session. Browser/stack enforces encryption; it’s mandatory in WebRTC. ([IETF Datatracker][10], [WebRTC Security][22])
* **Identity binding**: Verify the **certificate fingerprints** carried in SDP match the peer you expect (your signaling can cross-check). (Covered by WebRTC security architecture.) ([IETF Datatracker][10])
* **TURN creds**: Use **time-limited TURN REST** credentials (short TTL) so leaked creds are useless; coturn supports this mode. ([GitHub][13])

---

# 9) Detailed implementation steps

## A) Signaling service

1. **WebSocket server** (`/api/signal`): accept connections with **JWT**; map each connection to `{accountId, deviceId, pairId}`.
2. **Rooms** keyed by `pairId`. Broadcast `offer`, `answer`, and `ice` only to the other peer in the room.
3. **Rate limiting**: per IP + per account to avoid abuse (signals are tiny, but WS can be DoS’d).
4. **Observability**: log call setup times, ICE state transitions, failures (no candidates / relay required). MDN has end-to-end examples you can mirror. ([MDN Web Docs][8])

## B) iPhone app (sender of keyframes + datachannel)

1. Create `RTCPeerConnection` with ICE servers (\[STUN, TURN]). ([MDN Web Docs][1])
2. **VideoTrack pipeline**:

   * Capture from your camera manager or render a buffer you already have.
   * Encode via **VideoToolbox** (`VTCompressionSessionCreate`), **realtime**, **no B-frames**, force **IDR** per emission, set bitrate to fit <100 KB @ 600×400.
   * Wrap into a `CMSampleBuffer` → feed to WebRTC video source/track (for native you’d use WebRTC SDK’s capturer; for custom native apps you adapt the sample buffers). ([Apple Developer][7])
3. Create **RTCDataChannel**: `{ ordered: false, maxPacketLifeTime: 100 }` for control. ([MDN Web Docs][23])
4. **Trickle ICE**: send candidates as they arrive. ([WebRTC][2])

## C) Mac app (receiver + responder)

1. Same ICE server config; set a **DataChannel** handler for low-latency control.
2. Render incoming video track in your UI (or decode with VideoToolbox if you need custom processing). ([Apple Developer][7])
3. On the datachannel, acknowledge command reception when needed (small acks keep your app-level state tight).

## D) TURN/STUN

* **Managed** (fastest to ship): add Twilio NTS `iceServers` entries; you only pay if the media relays via TURN. Pricing as above. ([Twilio][24])
* **Self-hosted coturn** (cost control, sovereignty):

  * Hardened config (TLS on 5349, DTLS 443/UDP fallback, long-term creds), disable loopback peers, rotate secrets. ([GitHub][13])
  * Recent guides provide exact cmdlines and terraform-friendly steps. ([metered.ca][14], [WebRTC.ventures][25])

---

# 10) Client-side tuning cheat-sheet

* **DataChannel**:

  * control: `{ordered:false, maxPacketLifeTime:100}` or `{ordered:false, maxRetransmits:0}`. (Pick **one** of lifetime vs retransmits; both isn’t allowed.) ([MDN Web Docs][26])
* **H.264 encoder (VideoToolbox)**:

  * Real-time: enable low-delay mode; disable frame reordering; small VBV buffer; keyframe on each push. (WWDC + VideoToolbox docs cover low-latency presets and properties.) ([Apple Developer][19])
* **Codec choice**: H.264 is safest across Safari/iOS/macOS; VP8 is supported in Safari WebRTC too, but H.264 gets hardware accel everywhere in your stack. ([WebKit][6])
* **ICE**: enable Trickle; surface `iceConnectionState` in logs/telemetry to see when you hit TURN (`relay` candidates). ([MDN Web Docs][27])

---

# 11) Observability & health

* Poll **`RTCPeerConnection.getStats()`** every few seconds; track:

  * `candidate-pair` selected (is it `relay`?) → cost & latency signals
  * RTT, jitter, retransmits, datachannel RTT/throughput
  * bytes sent/received (media vs data)
* Emit to your metrics backend; alert if **TURN usage spikes** (can indicate ISP/NAT changes).

(While I didn’t cite a specific stats API page, this is standard WebRTC ops practice aligned with MDN/WebRTC.org patterns above.)

---

# 12) Cost model: what you actually pay for

* **Signaling**: negligible — tiny JSON over WebSockets.
* **TURN relay**: you pay **only** when peers can’t connect P2P (e.g., symmetric NATs).

  * With Twilio NTS: **\$0.40/GB** (US/EU), **\$0.60/GB** (APAC), **\$0.80/GB** (AU/BR). Budget assuming **10–20%** of sessions hit TURN; tune after observing. ([Twilio][11])
* **Bandwidth**: your *keyframe-as-video* approach is very light. At one 600×400 IDR every 3 s (\~80–100 KB), that’s \~**33 KB/s** average (\~0.26 Mbps). Over TURN that’s \~0.12 GB/hour → **\~\$0.05/h** per TURN-relayed session (US/EU). (Order-of-magnitude estimate; validate with your real encodes.)

---

# 13) Hardening checklist

* WSS only; HSTS at apex.
* JWTs ≤5 min; rotate signing keys; bind claims to `{accountId, deviceId, pairId}`.
* **TURN REST** short-TTL creds; don’t embed static TURN passwords in apps. ([GitHub][13])
* Rate-limit signaling connects/messages; drop oversized payloads.
* Pin allowed **SDP fingerprints** to a device record if you want extra scrutiny (optional; WebRTC already verifies fingerprints inside DTLS/SRTP). ([IETF Datatracker][10])

---

# 14) Rollout plan (minimal risk)

1. **Phase 0**: Spin up `wss://orionlive.ai/api/signal` (stateless) and add **STUN only**; verify P2P works on friendly networks. ([MDN Web Docs][8])
2. **Phase 1**: Add **Twilio NTS** TURN creds to `iceServers`; test hostile NATs (hotel Wi-Fi, CGNAT). ([Twilio][24])
3. **Phase 2**: Integrate **VideoToolbox** low-latency H.264 and push periodic IDR frames; tune bitrate to stay under 100 KB/frame. ([Apple Developer][19])
4. **Phase 3**: Add **RTCDataChannel** with partial reliability; confirm <100 ms delivery in logs. ([MDN Web Docs][23])
5. **Phase 4**: Instrument **getStats**; dashboard TURN %, RTT, keyframe sizes, DC RTT.
6. **Phase 5**: (Optional) Stand up **coturn** in your cloud for cost control / sovereignty, after you have baseline stats. ([metered.ca][14])

---

# 15) Copy-pasteable configs & snippets (what to actually set)

**ICE servers (example)**

```ts
const pc = new RTCPeerConnection({
  iceServers: [
    { urls: ["stun:stun.l.google.com:19302"] },      // plus your own STUN(s)
    { urls: ["turn:global.turn.twilio.com:3478?transport=udp","turns:global.turn.twilio.com:5349?transport=tcp"],
      username: "twilio-user", credential: "twilio-cred" } // or your coturn REST creds
  ]
});
```

(Use your provider’s latest hostnames/creds; Twilio docs linked.) ([Twilio][24])

**DataChannel (control)**

```ts
const dc = pc.createDataChannel("ctl", { ordered: false, maxPacketLifeTime: 100 });
```

(Prohibit setting both lifetime and retransmits.) ([MDN Web Docs][26])

**Trickle ICE**
Send `ice` messages as `pc.onicecandidate` fires; don’t wait for gathering to complete. ([WebRTC][2])

**VideoToolbox (iOS/macOS) knobs to look up**

* Enable realtime: low-latency config (WWDC “Explore low-latency video encoding with VideoToolbox”).
* Disable B-frames (no reordering).
* Set target bitrate \~80–120 kbps to start.
* Force IDR per emission or set max keyframe interval to 1.
  (See VideoToolbox doc sets + WWDC.) ([Apple Developer][19])

---

# 16) Future niceties (optional)

* **DSCP/priority control** where networks honor it (enterprises/Wi-Fi QoS). ([W3C][20], [IETF Datatracker][21])
* **VP8 fallback** (WebRTC-only in Safari) if you want more flexibility on non-Apple peers. H.264 default stays correct for you. ([WebKit][6], [MDN Web Docs][28])
* **libdatachannel** (C++ native) if you ever want a headless/embedded implementation without full browser stacks. ([GitHub][29])

---

## The TL;DR build recipe

* **Signal** with a tiny **WSS** server; **Trickle ICE**; short-lived **JWT**. ([MDN Web Docs][8], [WebRTC][2])
* **Connect** using **STUN first**, **TURN fallback** (managed first, then self-host if/when needed). ([MDN Web Docs][1], [Twilio][11])
* **Send images** as **H.264 keyframes** on a video track via **VideoToolbox** low-latency settings. ([Apple Developer][19])
* **Send text** on **RTCDataChannel** with `{ordered:false, maxPacketLifeTime:100}` for sub-100 ms. ([MDN Web Docs][23])
* **Measure** with `getStats()` and log TURN %, RTT, and frame sizes.
* **Harden** creds & configs; watch costs only when sessions hit TURN. ([GitHub][13])

If you want, I can draft the exact Node/Go WS signaling handler (auth, rooms, message validation) and the Swift (iOS) VideoToolbox configuration code with the low-latency/IDR settings next.

[1]: https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API/Protocols?utm_source=chatgpt.com "Introduction to WebRTC protocols - Web APIs | MDN"
[2]: https://webrtc.org/getting-started/peer-connections?utm_source=chatgpt.com "Getting started with peer connections - WebRTC"
[3]: https://webrtcforthecurious.com/docs/04-securing/?utm_source=chatgpt.com "Securing | WebRTC for the Curious"
[4]: https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API/Using_data_channels?utm_source=chatgpt.com "Using WebRTC data channels - Web APIs | MDN"
[5]: https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Formats/WebRTC_codecs?utm_source=chatgpt.com "Codecs used by WebRTC - Media - MDN Web Docs - Mozilla"
[6]: https://webkit.org/blog/8672/on-the-road-to-webrtc-1-0-including-vp8/?utm_source=chatgpt.com "On the Road to WebRTC 1.0, Including VP8 | WebKit"
[7]: https://developer.apple.com/documentation/videotoolbox?utm_source=chatgpt.com "Video Toolbox | Apple Developer Documentation"
[8]: https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API/Signaling_and_video_calling?utm_source=chatgpt.com "Signaling and video calling - WebRTC API - MDN Web Docs"
[9]: https://antmedia.io/webrtc-signaling-servers-everything-you-need-to-know/?utm_source=chatgpt.com "WebRTC Signaling Server: How it Works?"
[10]: https://datatracker.ietf.org/doc/html/rfc8827?utm_source=chatgpt.com "RFC 8827 - WebRTC Security Architecture - IETF Datatracker"
[11]: https://www.twilio.com/en-us/stun-turn/pricing?utm_source=chatgpt.com "Pricing - Network Traversal Service - Twilio"
[12]: https://webrtc.ventures/2024/11/selecting-and-deploying-managed-stun-turn-servers/?utm_source=chatgpt.com "Selecting and Deploying Managed STUN/TURN Servers"
[13]: https://github.com/coturn/coturn/wiki/turnserver?utm_source=chatgpt.com "turnserver · coturn/coturn Wiki - GitHub"
[14]: https://www.metered.ca/blog/coturn/?utm_source=chatgpt.com "How to setup and configure TURN server using coTURN?"
[15]: https://datatracker.ietf.org/doc/rfc8838/?utm_source=chatgpt.com "RFC 8838 - Trickle ICE: Incremental Provisioning of Candidates for ..."
[16]: https://webrtchacks.com/trickle-ice/?utm_source=chatgpt.com "ICE always tastes better when it trickles! (Emil Ivov) - webrtcHacks"
[17]: https://developer.mozilla.org/en-US/docs/Web/API/RTCDataChannel/ordered?utm_source=chatgpt.com "RTCDataChannel: ordered property - Web APIs - MDN Web Docs"
[18]: https://datatracker.ietf.org/doc/html/rfc8831?utm_source=chatgpt.com "RFC 8831 - WebRTC Data Channels - IETF Datatracker"
[19]: https://developer.apple.com/videos/play/wwdc2021/10158/?utm_source=chatgpt.com "Explore low-latency video encoding with VideoToolbox - WWDC21"
[20]: https://www.w3.org/TR/webrtc-priority/?utm_source=chatgpt.com "WebRTC Priority Control API - W3C"
[21]: https://datatracker.ietf.org/doc/html/rfc8837?utm_source=chatgpt.com "RFC 8837 - Differentiated Services Code Point (DSCP) Packet ..."
[22]: https://webrtc-security.github.io/?utm_source=chatgpt.com "A Study of WebRTC Security"
[23]: https://developer.mozilla.org/en-US/docs/Web/API/RTCDataChannel/maxPacketLifeTime?utm_source=chatgpt.com "RTCDataChannel: maxPacketLifeTime property - Web APIs | MDN"
[24]: https://www.twilio.com/docs/stun-turn?utm_source=chatgpt.com "Network Traversal Service - Twilio"
[25]: https://webrtc.ventures/2025/01/how-to-set-up-self-hosted-stun-turn-servers-for-webrtc-applications/?utm_source=chatgpt.com "How to Set Up Self-Hosted STUN/TURN Servers for WebRTC ..."
[26]: https://developer.mozilla.org/en-US/docs/Web/API/RTCPeerConnection/createDataChannel?utm_source=chatgpt.com "RTCPeerConnection: createDataChannel() method - Web APIs | MDN"
[27]: https://developer.mozilla.org/en-US/docs/Web/API/RTCPeerConnection/iceConnectionState?utm_source=chatgpt.com "RTCPeerConnection: iceConnectionState property - Web APIs | MDN"
[28]: https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Formats/Video_codecs?utm_source=chatgpt.com "Web video codec guide - Media - MDN Web Docs"
[29]: https://github.com/paullouisageneau/libdatachannel?utm_source=chatgpt.com "paullouisageneau/libdatachannel: C/C++ WebRTC network library ..."
