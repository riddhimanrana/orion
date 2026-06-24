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

3.  Create a `.env` file in this directory and add the required environment variables. You will need the JWT secret from your website's configuration and your Supabase project URL and secret key.
    ```
    P2P_SIGNAL_JWT_SECRET=your-super-secret-key
    NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
    SUPABASE_SECRET_KEY=your-supabase-secret-key
    ```

### Running Locally

```bash
bun run dev
```

## Connection diagnostics

Run a full auth + connectivity diagnostic against deployed services:

```bash
npm run verify:connections
```

The diagnostics script validates:

- `GET /health`
- auth guards on `GET /v1/ice`, `GET /v1/diag`, `GET /v1/account-usage`
- authenticated checks (when `SIGNAL_BEARER_TOKEN` is provided)

Optional environment variables:

- `SIGNAL_BASE_URL` (default: `https://signal.orionlive.ai`)
- `ORION_API_BASE_URL` (default: `https://orionlive.ai`)
- `SIGNAL_BEARER_TOKEN` (enables authenticated `/v1/ice` + `/v1/diag` + `/v1/account-usage` checks)
- `RENDER_API_KEY` + `RENDER_SERVICE_ID` (enables Render API status check)

## Render deploy + status

Deploy the signal service with Render CLI and wait for completion:

```bash
npm run render:deploy
```

Show workspace/service/deploy status plus signal API usage snapshot:

```bash
npm run render:status
```

Optional environment variables:

- `RENDER_SERVICE_ID` (preferred)
- `RENDER_SERVICE_NAME` (default: `Orion Signal Server`)
- `RENDER_WAIT_FOR_COMPLETION` (`true` by default)
- `RENDER_DEPLOY_CLEAR_CACHE` (`false` by default)

## Account usage + cost estimate endpoint

Authenticated endpoint:

- `GET /v1/account-usage`

This returns per-user signaling usage counters and estimated cost from process-lifetime counters.

Pricing env vars (optional):

- `BILLING_RELAY_GB_USD` (default `0.12`)
- `BILLING_ICE_REQUEST_USD` (default `0.002`)
- `BILLING_CONNECTION_MIN_USD` (default `0.0005`)

The server will start on `ws://localhost:3001` by default.
