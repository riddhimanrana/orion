# Orion Website

This is the web front-end for the Orion architecture which handles authentication, showcase research findings, dashboard pages, and billing setups. It is very fast, entirely mobile-responsive, and has a modern design built with Next.js and Tailwind CSS.

## Features

- Research dashboard with technical deep dives and related works  
- Vector database query examples and validation metrics  
- User authentication (sign up, login, email change, confirmation)  
- Account management (profile, email updates)  
- Responsive UI built with Tailwind CSS and Lucide icons  

## Technologies

- [Next.js](https://nextjs.org/) — React framework for handling SSR, routing, and API routes  
- [shadcn/ui](https://ui.shadcn.com/) — Tailwind Component library for Orion's web interface
- [Aceternity UI](https://ui.aceternity.com/) — Used for certain components in the Orion UI (like the 'speed' text in the landing page)
- [Supabase](https://supabase.com/) — Backend database service for handling user auth, storage, and billing data
- [Vercel](https://vercel.com/) — Deployment/hosting platform for the website
- [Cloudflare](https://cloudflare.com/) — Domain CDN and DNS management

## Getting Started

### Installation

1. Clone the repo  

   ```bash
   git clone https://github.com/riddhimanrana/orion
   cd orion/orion-website
   ```

2. Install dependencies  

   ```bash
   bun install
   ```

3. Create a `.env.local` file based on `.env.example` and add your Supabase credentials.  

### Running Locally

```bash
bun run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Local E2E diagnostics (pairing + signaling)

This repo includes a script that exercises the full pairing + signaling path:

- Creates a Supabase test user
- Registers iOS + mac devices via the website API
- Creates + consumes a pairing code (writes `device_pairs`)
- Mints signaling JWTs via `POST /api/auth/webrtc-token`
- Connects two WebSockets to the signaling server and verifies a relayed message

Prereqs:

- Website dev server running (any port is fine)
- Local signaling server running (defaults to `ws://localhost:3001`)

Run:

```bash
node scripts/e2e-pairing-signal.mjs
```

Optional env overrides:

- `ORION_API_BASE_URL` (e.g. `http://localhost:3005`)
- `NEXT_PUBLIC_P2P_SIGNAL_URL` (e.g. `ws://localhost:3001`)
- `E2E_EMAIL` / `E2E_PASSWORD` (if you want to reuse an existing user)

## Contributing

This is a solo project and I'm currently not accepting contributions, however the code is still publicly available for transparency.

## License

This project is open source under the MIT License.
