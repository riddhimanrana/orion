#!/usr/bin/env node

/**
 * End-to-end pairing + signaling sanity check (local dev)
 *
 * What it does:
 * - Creates (or signs into) a Supabase test user
 * - Registers iOS + mac devices via the Orion website API
 * - Creates + consumes a pairing code (creates device_pairs row)
 * - Mints signaling JWTs via /api/auth/webrtc-token
 * - Validates signal auth endpoints (/v1/diag, /v1/account-usage)
 * - Opens two WebSocket connections and verifies message relay
 * - Calls /api/usage/summary to confirm usage telemetry is readable
 *
 * Usage:
 *   node scripts/e2e-pairing-signal.mjs
 *
 * Optional env vars:
 *   ORION_API_BASE_URL=http://localhost:3005
 *   NEXT_PUBLIC_P2P_SIGNAL_URL=ws://localhost:3001
 *   E2E_EMAIL=you@example.com
 *   E2E_PASSWORD=your-password
 */

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import WebSocket from "ws";
import { createClient } from "@supabase/supabase-js";

function stripTrailingSlash(url) {
  return url.endsWith("/") ? url.slice(0, -1) : url;
}

function loadDotEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return;
  const content = fs.readFileSync(filePath, "utf8");
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;

    const normalized = line.startsWith("export ") ? line.slice("export ".length) : line;
    const eq = normalized.indexOf("=");
    if (eq <= 0) continue;

    const key = normalized.slice(0, eq).trim();
    let value = normalized.slice(eq + 1).trim();

    if (!key) continue;
    if (process.env[key] !== undefined) continue;

    // Strip surrounding quotes.
    if (
      (value.startsWith("\"") && value.endsWith("\"")) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }

    process.env[key] = value;
  }
}

function requireEnv(name) {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required env var: ${name}`);
  return value;
}

function toSignalHttpBaseUrl(wsBaseUrl) {
  return stripTrailingSlash(
    wsBaseUrl
      .replace(/^ws:\/\//i, "http://")
      .replace(/^wss:\/\//i, "https://"),
  );
}

async function jsonFetch(url, options = {}) {
  const res = await fetch(url, options);
  const text = await res.text();
  let body;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  return { res, body };
}

async function apiJson(orionBaseUrl, apiPath, { method = "GET", token, json } = {}) {
  const url = `${orionBaseUrl}${apiPath.startsWith("/") ? "" : "/"}${apiPath}`;

  const headers = {
    Accept: "application/json",
  };
  if (json !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  return jsonFetch(url, {
    method,
    headers,
    body: json !== undefined ? JSON.stringify(json) : undefined,
  });
}

function withTimeout(promise, ms, label) {
  let timeout;
  const t = new Promise((_, reject) => {
    timeout = setTimeout(() => reject(new Error(`Timeout after ${ms}ms: ${label}`)), ms);
  });
  return Promise.race([promise, t]).finally(() => clearTimeout(timeout));
}

function waitForWsOpen(ws) {
  return new Promise((resolve, reject) => {
    const onOpen = () => {
      cleanup();
      resolve();
    };
    const onError = (err) => {
      cleanup();
      reject(err);
    };
    const cleanup = () => {
      ws.off("open", onOpen);
      ws.off("error", onError);
    };

    ws.on("open", onOpen);
    ws.on("error", onError);
  });
}

function waitForWsMessage(ws) {
  return new Promise((resolve, reject) => {
    const onMessage = (data) => {
      cleanup();
      resolve(data);
    };
    const onClose = () => {
      cleanup();
      reject(new Error("WebSocket closed before message was received"));
    };
    const onError = (err) => {
      cleanup();
      reject(err);
    };
    const cleanup = () => {
      ws.off("message", onMessage);
      ws.off("close", onClose);
      ws.off("error", onError);
    };

    ws.on("message", onMessage);
    ws.on("close", onClose);
    ws.on("error", onError);
  });
}

async function resolveOrionBaseUrl() {
  const explicit = process.env.ORION_API_BASE_URL;
  if (explicit) return stripTrailingSlash(explicit);

  const candidates = [
    process.env.NEXT_PUBLIC_SITE_URL,
    "http://localhost:3005",
    "http://localhost:3000",
  ]
    .filter(Boolean)
    .map((u) => stripTrailingSlash(u));

  const seen = new Set();
  for (const base of candidates) {
    if (!base || seen.has(base)) continue;
    seen.add(base);
    try {
      const { res } = await withTimeout(
        apiJson(base, "/api/system-status"),
        3_000,
        `ping ${base}`,
      );

      if (res.status === 200) return base;
    } catch {
      // Ignore and try next candidate.
    }
  }

  throw new Error(
    `Could not reach Orion API on any candidate base URL. ` +
      `Start the Next dev server or set ORION_API_BASE_URL (e.g. http://localhost:3005).`,
  );
}

async function main() {
  // Load local env if running from repo root.
  loadDotEnvFile(path.join(process.cwd(), ".env"));
  loadDotEnvFile(path.join(process.cwd(), ".env.local"));

  const orionBaseUrl = await resolveOrionBaseUrl();

  const signalWsBaseUrl = stripTrailingSlash(
    process.env.NEXT_PUBLIC_P2P_SIGNAL_URL || "ws://localhost:3001",
  );
  const signalHttpBaseUrl = toSignalHttpBaseUrl(signalWsBaseUrl);

  const supabaseUrl = requireEnv("NEXT_PUBLIC_SUPABASE_URL");
  const supabaseAnonKey = requireEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY");
  const supabaseServiceRoleKey = requireEnv("SUPABASE_SERVICE_ROLE_KEY");

  const email =
    process.env.E2E_EMAIL || `orion-e2e+${Date.now()}@example.com`;
  const password =
    process.env.E2E_PASSWORD ||
    `${crypto.randomBytes(18).toString("hex")}Aa1!`;

  console.log("E2E: pairing + signaling");
  console.log(`- Orion API base: ${orionBaseUrl}`);
  console.log(`- Signal WS base: ${signalWsBaseUrl}`);
  console.log(`- Signal HTTP base: ${signalHttpBaseUrl}`);
  console.log(`- Test user email: ${email}`);

  const supabaseAdmin = createClient(supabaseUrl, supabaseServiceRoleKey, {
    auth: { persistSession: false },
  });
  const supabase = createClient(supabaseUrl, supabaseAnonKey, {
    auth: { persistSession: false },
  });

  // Sign in (or create user then sign in).
  let session;
  {
    const attempt = await supabase.auth.signInWithPassword({ email, password });
    session = attempt.data?.session;

    if (!session) {
      const created = await supabaseAdmin.auth.admin.createUser({
        email,
        password,
        email_confirm: true,
      });

      if (created.error) {
        throw new Error(`Failed to create e2e user: ${created.error.message}`);
      }

      const signedIn = await supabase.auth.signInWithPassword({ email, password });
      session = signedIn.data?.session;
      if (signedIn.error || !session) {
        throw new Error(`Failed to sign in e2e user: ${signedIn.error?.message || "no session"}`);
      }
    }
  }

  const accessToken = session.access_token;
  console.log("- Supabase session acquired (access token omitted)");

  // Register devices.
  const iosDeviceId = await (async () => {
    const { res, body } = await apiJson(orionBaseUrl, "/api/devices/register", {
      method: "POST",
      token: accessToken,
      json: { type: "ios", name: `iOS E2E ${new Date().toISOString()}` },
    });
    if (res.status !== 200 || !body?.device_id) {
      throw new Error(`Device register (ios) failed: status=${res.status} body=${JSON.stringify(body)}`);
    }
    return body.device_id;
  })();

  const macDeviceId = await (async () => {
    const { res, body } = await apiJson(orionBaseUrl, "/api/devices/register", {
      method: "POST",
      token: accessToken,
      json: { type: "mac", name: `Mac E2E ${new Date().toISOString()}` },
    });
    if (res.status !== 200 || !body?.device_id) {
      throw new Error(`Device register (mac) failed: status=${res.status} body=${JSON.stringify(body)}`);
    }
    return body.device_id;
  })();

  console.log(`- Devices registered: ios=${iosDeviceId}, mac=${macDeviceId}`);

  // Create a pairing code from iOS, consume on mac.
  const pairingCode = await (async () => {
    const { res, body } = await apiJson(orionBaseUrl, "/api/pairings/create", {
      method: "POST",
      token: accessToken,
      json: { device_id: iosDeviceId },
    });
    if (res.status !== 200 || !body?.code) {
      throw new Error(`Pairings create failed: status=${res.status} body=${JSON.stringify(body)}`);
    }
    return body.code;
  })();

  const pair = await (async () => {
    const { res, body } = await apiJson(orionBaseUrl, "/api/pairings/consume", {
      method: "POST",
      token: accessToken,
      json: { code: pairingCode, device_id: macDeviceId },
    });
    if (res.status !== 200 || !body?.id) {
      throw new Error(`Pairings consume failed: status=${res.status} body=${JSON.stringify(body)}`);
    }
    return body;
  })();

  const pairId = pair.id;
  console.log(`- Pair active: pairId=${pairId}`);

  // Mint signaling tokens.
  const iosSignalToken = await (async () => {
    const { res, body } = await apiJson(orionBaseUrl, "/api/auth/webrtc-token", {
      method: "POST",
      token: accessToken,
      json: { deviceId: iosDeviceId },
    });
    if (res.status !== 200 || !body?.token) {
      throw new Error(`WebRTC token (ios) failed: status=${res.status} body=${JSON.stringify(body)}`);
    }
    return body.token;
  })();

  const macSignalToken = await (async () => {
    const { res, body } = await apiJson(orionBaseUrl, "/api/auth/webrtc-token", {
      method: "POST",
      token: accessToken,
      json: { deviceId: macDeviceId },
    });
    if (res.status !== 200 || !body?.token) {
      throw new Error(`WebRTC token (mac) failed: status=${res.status} body=${JSON.stringify(body)}`);
    }
    return body.token;
  })();

  console.log("- Signaling JWTs minted (tokens omitted)");

  // Validate signal authenticated endpoints.
  {
    const headers = { Authorization: `Bearer ${iosSignalToken}`, Accept: "application/json" };
    const diag = await jsonFetch(`${signalHttpBaseUrl}/v1/diag`, { headers });
    const usage = await jsonFetch(`${signalHttpBaseUrl}/v1/account-usage`, { headers });

    if (diag.res.status !== 200) {
      throw new Error(`Signal /v1/diag failed: status=${diag.res.status} body=${JSON.stringify(diag.body)}`);
    }
    if (usage.res.status !== 200) {
      throw new Error(`Signal /v1/account-usage failed: status=${usage.res.status} body=${JSON.stringify(usage.body)}`);
    }

    console.log(`- Signal auth OK: diag.connectedClients=${diag.body?.room?.connectedClients ?? "?"}`);
  }

  // WebSocket relay check.
  let wsIos;
  let wsMac;
  try {
    const iosUrl = new URL(signalWsBaseUrl);
    iosUrl.searchParams.set("token", iosSignalToken);

    const macUrl = new URL(signalWsBaseUrl);
    macUrl.searchParams.set("token", macSignalToken);

    wsIos = new WebSocket(iosUrl.toString());
    wsMac = new WebSocket(macUrl.toString());

    await withTimeout(Promise.all([waitForWsOpen(wsIos), waitForWsOpen(wsMac)]), 10_000, "WebSocket open");
    console.log("- WebSockets connected (2 clients)");

    // Wait for a message on mac while sending from ios.
    const messagePromise = withTimeout(waitForWsMessage(wsMac), 10_000, "relay message");

    const msg = {
      t: "mode",
      pairId,
      fromDeviceId: iosDeviceId,
      mode: "e2e_test",
      ts: Date.now(),
    };
    wsIos.send(JSON.stringify(msg));

    const receivedRaw = await messagePromise;
    const receivedText = Buffer.isBuffer(receivedRaw) ? receivedRaw.toString("utf8") : receivedRaw.toString();

    let received;
    try {
      received = JSON.parse(receivedText);
    } catch {
      received = null;
    }

    if (!received || received.t !== "mode" || received.pairId !== pairId) {
      throw new Error(`Unexpected relayed payload: ${receivedText}`);
    }

    console.log("- Relay OK: received mode message on mac");
  } finally {
    try {
      wsIos?.close();
    } catch {}
    try {
      wsMac?.close();
    } catch {}
  }

  // Re-check account usage now that we've relayed a packet.
  {
    const headers = { Authorization: `Bearer ${iosSignalToken}`, Accept: "application/json" };
    const usage = await jsonFetch(`${signalHttpBaseUrl}/v1/account-usage`, { headers });
    if (usage.res.status !== 200) {
      throw new Error(`Signal /v1/account-usage (post-relay) failed: status=${usage.res.status}`);
    }

    const packetsRelayed = usage.body?.usage?.packetsRelayed;
    const bytesRelayed = usage.body?.usage?.bytesRelayed;
    console.log(`- Signal usage updated: packetsRelayed=${packetsRelayed ?? "?"}, bytesRelayed=${bytesRelayed ?? "?"}`);
  }

  // Confirm website usage summary is readable for the user.
  {
    const { res, body } = await apiJson(orionBaseUrl, "/api/usage/summary?days=7", {
      method: "GET",
      token: accessToken,
    });

    if (res.status !== 200) {
      throw new Error(`Usage summary failed: status=${res.status} body=${JSON.stringify(body)}`);
    }

    console.log(
      `- Usage summary OK: today=${body?.usage?.requestsToday ?? "?"}, month=${body?.usage?.requestsThisMonth ?? "?"}, dailyPoints=${Array.isArray(body?.daily) ? body.daily.length : "?"}`,
    );
  }

  console.log("Done.");
}

main().catch((err) => {
  console.error(`E2E failed: ${err.message}`);
  process.exit(1);
});
