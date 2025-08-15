# Orion Signaling Server

This server is a critical component of the Orion architecture, responsible for facilitating peer-to-peer (P2P) WebRTC connections between the Orion iOS and macOS applications. It is a lightweight, standalone WebSocket server.

## Features

- **WebSocket Communication:** Uses WebSockets for real-time, low-latency message relaying.
- **Secure Authentication:** Connections are authenticated using short-lived JSON Web Tokens (JWTs).
- **Room Management:** Creates temporary "rooms" based on a `pairId` to ensure signals are only relayed between correctly paired devices.
- **Simple Message Relaying:** Relays WebRTC `offer`, `answer`, and `ice-candidate` messages between peers without inspecting the content.

## Technologies

- [Bun](https://bun.sh/) — JavaScript runtime & toolkit
- [TypeScript](https://www.typescriptlang.org/) — Statically typed language
- [ws](https://github.com/websockets/ws) — High-performance WebSocket library for Node.js
- [jsonwebtoken](https://github.com/auth0/node-jsonwebtoken) — For handling JWTs

## Getting Started

### Installation

1.  Navigate to the `signal` directory:
    ```bash
    cd signal
    ```

2.  Install dependencies:
    ```bash
    bun install
    ```

3.  Create a `.env` file in this directory and add the required environment variables. You will need the JWT secret from your website's configuration and your Supabase project URL and service role key.
    ```
    P2P_SIGNAL_JWT_SECRET=your-super-secret-key
    NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
    SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
    ```

### Running Locally

```bash
bun run dev
```

The server will start on `ws://localhost:3001` by default.
