# TURN Server Setup Guide (WebRTC)

This guide helps you stand up a TURN server so your iOS ↔ macOS peers can connect even behind strict NATs. It covers:

- When/why you need TURN
- Managed vs self‑host options
- Self‑hosting CoTURN on a small VPS (Ubuntu)
- DNS, firewall, and TLS
- Short‑lived (ephemeral) credentials
- Wiring into this app (Info.plist keys)
- Validation and troubleshooting

---

## Do I really need TURN?

- STUN only works if at least one peer can accept inbound connections after NAT discovery. Symmetric NATs or locked-down networks will fail.
- TURN relays media/data through a public server. It’s the fallback when direct P2P fails.
- Costs: TURN traffic is bandwidth-heavy for video; budget accordingly. For our data channel and occasional video, a small VPS can be okay to start.

---

## Option A: Managed TURN (fastest to production)

Pick a provider and grab ICE URLs + credentials:

- Twilio Network Traversal Service (NTS)
- Xirsys
- Metered.ca
- Vonage (Nexmo)

They provide `urls` (stun/turn), `username`, `credential` and often an API for short‑lived creds. Paste those into your config or fetch dynamically from your backend.

Pros: No ops, HA included. Cons: Monthly + bandwidth costs.

---

## Option B: Self‑host TURN with CoTURN (recommended OSS)

CoTURN is the de-facto standard. Below is a minimal Ubuntu setup.

### 1) Provision a small VPS

- 1 vCPU / 1–2 GB RAM is fine to start (DigitalOcean, Linode, Hetzner, AWS Lightsail, etc.)
- OS: Ubuntu 22.04 LTS is recommended. Ubuntu 24.04 LTS is also a solid choice. Ubuntu 25.04 is usable but is a non‑LTS release — it may have newer packages but shorter support; prefer LTS for production unless you need a specific kernel/package only in 25.04.

# CPU & disk choices (brief)
- CPU cores:
  - 1 vCPU: fine for small-scale testing, data‑channel usage, or very light relay load.
  - 2 vCPU: recommended minimum for small production workloads (some concurrent sessions).
  - 4+ vCPU: choose this for heavier relay/video workloads or many concurrent peers.
  - Look for higher single‑thread clock and newer CPU microarchitectures for better crypto/TLS and media processing performance.
- CPU type:
  - Premium Intel (or other "premium"/dedicated CPU types) can give better single‑thread throughput and consistent performance; beneficial when you expect CPU/crypto/TLS to be a bottleneck.
  - Regular (shared) CPUs are cost‑effective for light usage but can suffer noisy‑neighbor variability.
- Disk:
  - NVMe SSD (Premium) is faster for logs and system I/O. TURN is primarily network‑bound, so NVMe is not critical for basic relay use, but NVMe improves responsiveness and is recommended if budget allows.
- Ubuntu 25.04 note:
  - 25.04 is usable but non‑LTS; you'll get newer packages but shorter support windows. For production, prefer an LTS release unless you require a feature only available in 25.04.

### 2) Install CoTURN

```bash
sudo apt-get update
sudo apt-get install -y coturn
```

CoTURN installs a `turnserver` daemon and `/etc/turnserver.conf`.

### 3) DNS (Cloudflare registrar)

- Create a DNS A record: `turn.orionlive.ai` → your VPS public IP
- IMPORTANT: Set Cloudflare proxy to “DNS only” (gray cloud). TURN must handle UDP/TCP directly.

### 4) Firewall

Open these ports inbound to the VPS (both UDP and TCP where noted):

- 3478 (UDP/TCP) – TURN
- 5349 (TCP) – TURN over TLS (optional but recommended)
- Relay port range – default is wide (49152–65535). Restrict it to a manageable range:
  - Example: 49160–49250 UDP/TCP

On Ubuntu UFW:

```bash
sudo ufw allow 3478/udp
sudo ufw allow 3478/tcp
sudo ufw allow 5349/tcp
sudo ufw allow 49160:49250/udp
sudo ufw allow 49160:49250/tcp
sudo ufw enable
sudo ufw status verbose
```

### 5) Configure CoTURN

Edit `/etc/turnserver.conf`:

```ini
# Basic networking
listening-port=3478
#tls-listening-port=5349
listening-ip=YOUR_VPS_PUBLIC_IP
# If you have a dedicated relay IP (often same as listening-ip):
#relay-ip=YOUR_VPS_PUBLIC_IP

# Restrict relay ports for easier firewalling
min-port=49160
max-port=49250

# Realm for auth (use a subdomain you control)
realm=orionlive.ai

# Auth mechanism: choose ONE of the two below

# (A) Long-term credentials (static username/password)
lt-cred-mech
# Suggested static username pattern for quick local/testing use:
# format: turn-<project>-<env>-<id>
# example:
user=turn-orion-static:REPLACE_WITH_STRONG_PASSWORD

# Or (production): HMAC short-lived credentials (recommended for production)
#static-auth-secret=YOUR_RANDOM_32B_SECRET
#use-auth-secret
#realm=orionlive.ai

# Security & hardening
fingerprint
stale-nonce
total-quota=100
bps-capacity=0
no-loopback-peers
no-multicast-peers

# TLS (optional but recommended for 5349)
#cert=/etc/letsencrypt/live/turn.orionlive.ai/fullchain.pem
#pkey=/etc/letsencrypt/live/turn.orionlive.ai/privkey.pem
#cipher-list="ECDHE+AESGCM:!aNULL"  
```

Then enable and start:

```bash
sudo systemctl enable coturn
sudo systemctl restart coturn
sudo systemctl status coturn --no-pager
```

If you want TURN over TLS (5349): use Let’s Encrypt with DNS or HTTP challenge:

```bash
# Install certbot
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot

# Obtain certificate for turn.orionlive.ai
sudo certbot certonly --standalone -d turn.orionlive.ai --preferred-challenges http

# Update turnserver.conf with cert/pkey paths, uncomment tls-listening-port
sudo systemctl restart coturn
```

### 6) Credentials mode — production (recommended)

For production, use HMAC short‑lived credentials (TURN REST/HMAC mode). This avoids long‑lived static passwords embedded in apps and makes rotation simple. Configure CoTURN with a shared secret and enable auth‑secret mode; clients obtain time‑limited credentials from your backend just before connecting.

Add these lines to /etc/turnserver.conf (example):

```ini
# Enable short‑lived HMAC credentials (recommended for production)
use-auth-secret
static-auth-secret=REPLACE_WITH_A_STRONG_RANDOM_SECRET_32+_BYTES
realm=orionlive.ai

# Disable long-term static users in production
#lt-cred-mech
#user=turn-orion-static:REPLACE_WITH_STRONG_PASSWORD
```

Important notes:
- Keep static-auth-secret off your public repos and rotate it periodically.
- Username format: typically the expiry timestamp (or expiry + identifier); coturn validates HMAC(username, secret).
- Choose TTL (expiry) small enough to limit exposure (e.g., 1 hour or less).

Node (production) example — mint short‑lived TURN credentials and expose a secure endpoint:

```typescript
// filepath: /Users/riddhiman.rana/Desktop/Coding/orion-mobile/Orion Live/Docs/TURN_SETUP.md
// Example Node + Express endpoint to mint TURN REST credentials (HMAC SHA1, base64)

import express from 'express';
import crypto from 'crypto';

const app = express();
app.use(express.json());

const TURN_SECRET = process.env.TURN_STATIC_SECRET as string; // 32+ bytes, keep secret
const TTL_SECONDS = 60 * 60; // 1 hour (adjust as needed)
const TURN_HOST = 'turn.orionlive.ai';
const TURN_PORT = 3478;

function mintTurnCredentials(ttlSeconds = TTL_SECONDS) {
  const expiry = Math.floor(Date.now() / 1000) + ttlSeconds;
  // username is expiry (coturn default expectation), you can include other info if desired
  const username = String(expiry);

  // coturn expects HMAC-SHA1 and base64-encoded result
  const hmac = crypto.createHmac('sha1', TURN_SECRET).update(username).digest('base64');
  const password = hmac;

  return {
    username,
    credential: password,
    ttl: ttlSeconds,
    urls: [
      `turn:${TURN_HOST}:${TURN_PORT}?transport=udp`,
      `turn:${TURN_HOST}:${TURN_PORT}?transport=tcp`,
      // if you enable TLS (5349) add 'turns:turn.orionlive.ai:5349?transport=tcp'
      `stun:${TURN_HOST}:${TURN_PORT}`
    ]
  };
}

// secure endpoint: require your app's auth before returning credentials
app.get('/api/turn-credentials', (req, res) => {
  // ... authenticate the request (session, JWT, etc.) ...
  const creds = mintTurnCredentials(3600);
  res.json(creds);
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`TURN credential minting service listening on ${PORT}`);
});
```

Return the JSON from a secure endpoint (authenticated + rate‑limited) and have clients fetch it right before creating an RTCPeerConnection.

---

## Wire it into this app

We already added Info.plist hooks so you can configure TURN without code changes.


- iOS Info.plist keys (same for macOS target):
  - `TURN_URL` → e.g. `turn:turn.orionlive.ai:3478?transport=udp`
  - `TURN_USERNAME` → `webrtcuser` (or minted username)
  - `TURN_PASSWORD` → `strongpassword` (or minted HMAC password)

You can include both UDP and TCP variants by returning multiple URLs from your backend and setting multiple `RTCIceServer` entries. The code currently reads a single `TURN_URL`; to support multiple, we can extend the config to a comma‑separated list or fetch at runtime from your API (recommended for ephemeral creds).

Where this is used:

- iOS: `WebRTCManager.buildIceServersFromInfoPlist()`
- macOS: `P2P/WebRTCManager.buildIceServersFromInfoPlist()`

If you adopt short‑lived creds, update the app to fetch ICE servers from your backend right before connecting instead of Info.plist.

- Production workflow (recommended): do NOT store TURN username/password in Info.plist. Instead:
  1. At connect time, call your backend `/api/turn-credentials` endpoint (authenticated).
  2. Parse the response (username, credential, urls) and build RTCIceServer entries dynamically.
  3. Create the RTCPeerConnection using the freshly-minted, short‑lived ICE servers.

- Quick testing only: you can keep these keys in Info.plist:
  - TURN_URL
  - TURN_USERNAME
  - TURN_PASSWORD
  But treat them as temporary and remove before release.

Where this is used:

- iOS: `WebRTCManager.buildIceServersFromInfoPlist()` — keep it for a fallback/testing path, but add a runtime fetch path that requests `/api/turn-credentials` in production.
- macOS: `P2P/WebRTCManager.buildIceServersFromInfoPlist()` — same advice.

Example client flow (pseudocode):
- If in production: fetch /api/turn-credentials → build RTCIceServers → connect.
- Else for quick local testing: read Info.plist values.

---

## Validate your TURN

- Basic service check (on the server):

  ```bash
  sudo ss -lntup | grep -E "(3478|5349)"
  ```

- External ICE tests:
  - Use WebRTC samples (Trickle ICE): [https://webrtc.github.io/samples/src/content/peerconnection/trickle-ice/](https://webrtc.github.io/samples/src/content/peerconnection/trickle-ice/)
  - Enter your STUN/TURN URLs and credentials
  - Verify that relay candidates (typ relay) appear

If you see only `host` or `srflx` (server-reflexive) and no `relay`, TURN may be unreachable or blocked.

### Common pitfalls

- Cloudflare proxy enabled for your TURN DNS → disable proxy (must be DNS-only)
- Firewall not allowing UDP 3478 or relay port range
- NAT hairpinning issues → ensure `listening-ip`/`relay-ip` are correct
- TLS paths wrong or cert mismatch on 5349
- Using `lt-cred-mech` on server but trying HMAC creds on client (or vice versa)

---

## Costs & scaling

- A small VPS can relay a few streams/data channels, but relay bandwidth grows quickly with video.
- Place TURN close to your users (regionally) to minimize latency.
- Monitor bandwidth and CPU; consider autoscaling and multiple regions for production.


---

## Quick summary

1) Start with managed TURN if speed > cost.
2) For self-host: Deploy CoTURN, open firewall, set realm, either static or HMAC creds.
3) Point DNS `turn.orionlive.ai` to your server (DNS-only).
4) Wire creds into the app (Info.plist for static; backend endpoint for ephemeral).
5) Validate with Trickle ICE and in-app Ping.

If you want, I can add a tiny backend endpoint in your signaling or API to mint short‑lived TURN creds and update the app to fetch them before connecting.

---

### DigitalOcean (Droplet) — step-by-step (practical)

This section gives a concrete sequence to self-host CoTURN on DigitalOcean.

1) Create the Droplet
- Use Ubuntu 22.04 LTS (or 24.04 when available).
- Size: 1 vCPU, 2GB RAM is a good starting point.
- Region: pick the region closest to your users.
- Authentication: upload your SSH public key.
- Enable IPv4 (you can add a Floating IP later for failover).

You can create via UI or doctl. Example doctl command:

```bash
# Example: replace KEY_FINGERPRINT and SSH_KEY_ID as appropriate
doctl compute droplet create turn-orion \
  --region nyc3 \
  --image ubuntu-22-04-x64 \
  --size s-1vcpu-2gb \
  --ssh-keys <SSH_KEY_ID> \
  --wait
```

### Droplet naming & hostnames (recommendation)
Pick a short, descriptive hostname that encodes purpose, size and region so you and your team can quickly identify instances. Example patterns:

- Single droplet: turn-orion-sfo2-01
- With size in name: turn-orion-1vcpu-2gb-sfo2-01
- If you expect multiple regions: turn-orion-sfo2-01, turn-orion-nyc3-01

If you deploy several identical droplets, use a numeric suffix for easy automation and DNS/floating-IP assignment.

Doctl example — create multiple droplets with a predictable naming pattern:
```bash
# create 3 droplets named turn-orion-sfo2-01 .. -03
doctl compute droplet create turn-orion-sfo2 --image ubuntu-22-04-x64 --size s-1vcpu-2gb --region sfo2 --ssh-keys <SSH_KEY_ID> --count 3 --wait \
  --format ID,Name,PublicIPv4 --no-header
# if you prefer explicit names, create in a loop:
for i in 1 2 3; do
  doctl compute droplet create turn-orion-sfo2-0$i \
    --region sfo2 --image ubuntu-22-04-x64 --size s-1vcpu-2gb --ssh-keys <SSH_KEY_ID> --wait
done
```

Recommended default hostname for your example: turn-orion-sfo2-01 (more descriptive than the default ubuntu-s-1vcpu-2gb-sfo2-01).

2) DNS
- Create an A record: turn.orionlive.ai → Droplet Public IP.
- If your domain is behind Cloudflare, set the record to DNS-only (gray cloud). TURN must not be proxied.

3) Basic droplet hardening & prerequisites (on the droplet)
```bash
# login as root or your sudo user
sudo apt-get update
sudo apt-get upgrade -y

# create a non-root user (if not using droplet SSH user)
adduser deploy
usermod -aG sudo deploy

# Optional: install fail2ban
sudo apt-get install -y fail2ban
```

4) Install CoTURN
```bash
sudo apt-get install -y coturn
# prevent coturn from running until configured
sudo systemctl stop coturn || true
```

5) Firewall (UFW) — allow TURN ports and relay range
- Choose a restricted relay range to simplify firewall rules, e.g. 49160–49250.

```bash
sudo ufw allow OpenSSH
sudo ufw allow 3478/udp
sudo ufw allow 3478/tcp
sudo ufw allow 5349/tcp
sudo ufw allow 49160:49250/udp
sudo ufw allow 49160:49250/tcp
sudo ufw enable
sudo ufw status verbose
```

You can also use DigitalOcean Cloud Firewalls (network-level) to open the same ports to the droplet(s).

6) Configure /etc/turnserver.conf
- Edit the config and set listening-ip to your droplet public IP (or 0.0.0.0 if you prefer).
- Restrict relay ports to the chosen range.
- Pick realm matching your domain (orionlive.ai).
- Choose auth: lt-cred-mech for quick start, or static-auth-secret + use-auth-secret for HMAC short-lived creds.

Example snippet to place in /etc/turnserver.conf (merge with the existing file; uncomment/adjust as needed):

```ini
# Basic networking
listening-port=3478
#tls-listening-port=5349
listening-ip=YOUR_DROPLET_PUBLIC_IP
#relay-ip=YOUR_DROPLET_PUBLIC_IP

# Restrict relay ports
min-port=49160
max-port=49250

realm=orionlive.ai

# Quick start: static user
lt-cred-mech
# Suggested static username pattern for quick local/testing use:
# format: turn-<project>-<env>-<id>
# example:
user=turn-orion-static:REPLACE_WITH_STRONG_PASSWORD

# Or (production): HMAC short-lived credentials (recommended for production)
#static-auth-secret=YOUR_RANDOM_32B_SECRET
#use-auth-secret
#realm=orionlive.ai

fingerprint
stale-nonce
total-quota=100
no-loopback-peers
no-multicast-peers

# TLS paths (when using certs)
#cert=/etc/letsencrypt/live/turn.orionlive.ai/fullchain.pem
#pkey=/etc/letsencrypt/live/turn.orionlive.ai/privkey.pem
```

7) Obtain TLS certificate (recommended for port 5349)
Option A — standalone certbot (stop coturn temporarily if it listens on 80/443):
```bash
sudo apt-get install -y snapd
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot

# If coturn is using no HTTP ports, you can use --standalone:
sudo systemctl stop coturn
sudo certbot certonly --standalone -d turn.orionlive.ai --preferred-challenges http
sudo systemctl start coturn
```

Option B — install nginx and use webroot or nginx plugin (preferred if you already host other sites):
```bash
sudo apt-get install -y nginx
# configure a simple server block for turn.orionlive.ai to serve the challenge
sudo certbot --nginx -d turn.orionlive.ai
# ensure /etc/letsencrypt paths are set in turnserver.conf and enable tls-listening-port=5349
```

After obtaining certs, uncomment and set cert/pkey lines in /etc/turnserver.conf and enable:
```ini
tls-listening-port=5349
cert=/etc/letsencrypt/live/turn.orionlive.ai/fullchain.pem
pkey=/etc/letsencrypt/live/turn.orionlive.ai/privkey.pem
```

8) Enable and start coturn
```bash
sudo systemctl enable coturn
sudo systemctl restart coturn
sudo systemctl status coturn --no-pager
```

9) Test and validate
- Check listening sockets:
```bash
sudo ss -lntup | grep -E "(3478|5349)"
```
- Use Trickle ICE (https://webrtc.github.io/samples/src/content/peerconnection/trickle-ice/) with your TURN URLs and credentials. Look for relay candidates.
- If you do not see relay candidates, re-check DNS, UFW/DO firewall, and listening-ip/relay-ip values.

10) Production notes
- Use HMAC short-lived credentials for security: set static-auth-secret in turnserver.conf and implement a minting endpoint in your backend that returns username (expiry) and credential (HMAC SHA1) as shown in the Node snippet earlier.
- Monitor bandwidth and CPU on the droplet. Consider multiple regions or a managed service for heavy loads.
- If you want high availability: deploy multiple TURN servers with a shared credential secret and a load balancer or DNS-based failover.

### Naming & production recommendation (added)
- Prefer descriptive static usernames (e.g., turn-orion-static, turn-orion-prod-01) if you must use lt-cred-mech for quick testing.
- For production, use HMAC short‑lived credentials (static-auth-secret + use-auth-secret in coturn) and mint credentials from your backend right before clients connect. This avoids long‑lived secrets in configs and makes rotation simple.
- If by "rpediction" you meant "production", the HMAC short‑lived approach is the recommended best practice. If you meant something else, please clarify.

Okay so now I have a TURN server up and running on DigitalOcean with CoTURN, secured with TLS, and ready to provide short-lived credentials via a backend endpoint. The app can fetch these credentials at runtime to connect reliably even behind strict NATs.
