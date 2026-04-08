// @ts-nocheck
import { WebSocketServer, WebSocket } from "ws";
import http from "http";
import jwt from "jsonwebtoken";
import { createClient } from "@supabase/supabase-js";
import crypto from "node:crypto";
import type { IncomingMessage } from "http";

// --- Config from env ---
const JWT_SECRET = process.env.P2P_SIGNAL_JWT_SECRET;
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const PORT = process.env.P2P_SIGNAL_PORT
  ? parseInt(process.env.P2P_SIGNAL_PORT, 10)
  : 3001;
const TURN_REALM = process.env.TURN_REALM || "orionlive.ai";
const TURN_REST_SECRET = process.env.TURN_REST_SECRET || "";
const TURN_URLS = (process.env.TURN_URLS || "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);
const TURN_TTL = process.env.TURN_TTL
  ? parseInt(process.env.TURN_TTL, 10)
  : 600; // seconds
const ICE_RATE_WINDOW_SEC = process.env.ICE_RATE_WINDOW_SEC
  ? parseInt(process.env.ICE_RATE_WINDOW_SEC, 10)
  : 600;
const ICE_RATE_MAX = process.env.ICE_RATE_MAX
  ? parseInt(process.env.ICE_RATE_MAX, 10)
  : 20;
const BILLING_RELAY_GB_USD = process.env.BILLING_RELAY_GB_USD
  ? parseFloat(process.env.BILLING_RELAY_GB_USD)
  : 0.12;
const BILLING_ICE_REQUEST_USD = process.env.BILLING_ICE_REQUEST_USD
  ? parseFloat(process.env.BILLING_ICE_REQUEST_USD)
  : 0.002;
const BILLING_CONNECTION_MIN_USD = process.env.BILLING_CONNECTION_MIN_USD
  ? parseFloat(process.env.BILLING_CONNECTION_MIN_USD)
  : 0.0005;

if (!JWT_SECRET || !SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
  throw new Error("Missing required environment variables");
}

// --- Supabase admin client ---
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

// --- Types ---
type SignalMessage = {
  t: "offer" | "answer" | "ice" | "bye" | "mode";
  pairId: string;
  fromDeviceId: string;
  toDeviceId?: string;
  sdp?: any;
  ice?: any;
  mode?: string;
  ts?: number;
};

type PacketType = SignalMessage["t"];

type PairPacketStats = {
  relayedByType: Record<PacketType, number>;
  bytesRelayed: number;
  lastRelayAt: number | null;
};

type UserUsageStats = {
  packetsRelayed: number;
  relayedByType: Record<PacketType, number>;
  bytesRelayed: number;
  iceIssued: number;
  connectionsStarted: number;
  connectionMs: number;
  lastSeenAt: number | null;
};

interface ClientMeta {
  userId: string;
  pairId: string;
  deviceId: string;
  connectedAtMs: number;
}

// --- In-memory state ---
const rooms = new Map<string, WebSocket[]>();
const serverStartedAtMs = Date.now();
const packetStatsByPair = new Map<string, PairPacketStats>();
const usageByUser = new Map<string, UserUsageStats>();
const iceRateState = new Map<string, { windowStart: number; count: number }>();

function ensurePairStats(pairId: string): PairPacketStats {
  let stats = packetStatsByPair.get(pairId);
  if (!stats) {
    stats = {
      relayedByType: {
        offer: 0,
        answer: 0,
        ice: 0,
        bye: 0,
        mode: 0,
      },
      bytesRelayed: 0,
      lastRelayAt: null,
    };
    packetStatsByPair.set(pairId, stats);
  }
  return stats;
}

function totalConnectedClients(): number {
  let total = 0;
  for (const clients of rooms.values()) total += clients.length;
  return total;
}

function aggregatePacketStats() {
  const totals: Record<PacketType, number> = {
    offer: 0,
    answer: 0,
    ice: 0,
    bye: 0,
    mode: 0,
  };
  let bytesRelayed = 0;
  let pairCount = 0;

  for (const stats of packetStatsByPair.values()) {
    pairCount += 1;
    bytesRelayed += stats.bytesRelayed;
    totals.offer += stats.relayedByType.offer;
    totals.answer += stats.relayedByType.answer;
    totals.ice += stats.relayedByType.ice;
    totals.bye += stats.relayedByType.bye;
    totals.mode += stats.relayedByType.mode;
  }

  return { totals, bytesRelayed, pairCount };
}

function ensureUserUsage(userId: string): UserUsageStats {
  let usage = usageByUser.get(userId);
  if (!usage) {
    usage = {
      packetsRelayed: 0,
      relayedByType: {
        offer: 0,
        answer: 0,
        ice: 0,
        bye: 0,
        mode: 0,
      },
      bytesRelayed: 0,
      iceIssued: 0,
      connectionsStarted: 0,
      connectionMs: 0,
      lastSeenAt: null,
    };
    usageByUser.set(userId, usage);
  }
  return usage;
}

function buildCostEstimate(usage: UserUsageStats) {
  const relayGb = usage.bytesRelayed / 1024 ** 3;
  const relayCostUsd = relayGb * BILLING_RELAY_GB_USD;
  const iceCostUsd = usage.iceIssued * BILLING_ICE_REQUEST_USD;
  const connectionMinutes = usage.connectionMs / 60_000;
  const connectionCostUsd = connectionMinutes * BILLING_CONNECTION_MIN_USD;
  const totalUsd = relayCostUsd + iceCostUsd + connectionCostUsd;

  return {
    relayGb,
    connectionMinutes,
    relayCostUsd,
    iceCostUsd,
    connectionCostUsd,
    totalUsd,
    rates: {
      relayGbUsd: BILLING_RELAY_GB_USD,
      iceRequestUsd: BILLING_ICE_REQUEST_USD,
      connectionMinuteUsd: BILLING_CONNECTION_MIN_USD,
    },
    note: "Estimated signaling cost from process-lifetime usage counters.",
  };
}

function wsMeta(ws: WebSocket): ClientMeta | undefined {
  return (ws as any)._meta as ClientMeta | undefined;
}

function setWsMeta(ws: WebSocket, meta: ClientMeta) {
  (ws as any)._meta = meta;
}

function makeTurnCredentials(user: string, ttlSec: number) {
  const unix = Math.floor(Date.now() / 1000) + ttlSec;
  const username = `${unix}:${user}`;
  const hmac = crypto.createHmac("sha1", TURN_REST_SECRET);
  hmac.update(username);
  const credential = hmac.digest("base64");
  return { username, credential };
}

function checkIceRate(userId: string) {
  const now = Math.floor(Date.now() / 1000);
  const rec = iceRateState.get(userId);
  if (!rec || now - rec.windowStart >= ICE_RATE_WINDOW_SEC) {
    const next = { windowStart: now, count: 1 };
    iceRateState.set(userId, next);
    return {
      allowed: true,
      count: next.count,
      remaining: Math.max(0, ICE_RATE_MAX - next.count),
      resetIn: ICE_RATE_WINDOW_SEC,
    };
  }
  rec.count += 1;
  const allowed = rec.count <= ICE_RATE_MAX;
  const resetIn = Math.max(0, ICE_RATE_WINDOW_SEC - (now - rec.windowStart));
  return {
    allowed,
    count: rec.count,
    remaining: Math.max(0, ICE_RATE_MAX - rec.count),
    resetIn,
  };
}

// --- HTTP server for health + authenticated ICE + diagnostics ---
const server = http.createServer(async (req, res) => {
  const url = req.url || "";
  const parsed = new URL(url, `http://${req.headers.host || "localhost"}`);
  const path = parsed.pathname;

  if (path === "/health") {
    const aggregate = aggregatePacketStats();
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(
      JSON.stringify({
        status: "ok",
        uptimeSec: Math.floor((Date.now() - serverStartedAtMs) / 1000),
        roomsActive: rooms.size,
        clientsConnected: totalConnectedClients(),
        trackedPairs: aggregate.pairCount,
        packetsRelayedByType: aggregate.totals,
        bytesRelayed: aggregate.bytesRelayed,
      }),
    );
    return;
  }

  if (path === "/v1/diag") {
    try {
      const authHeader = req.headers["authorization"] || "";
      let token: string | undefined;
      if (authHeader.toLowerCase().startsWith("bearer ")) {
        token = authHeader.slice(7).trim();
      } else if (parsed.searchParams.get("token")) {
        token = parsed.searchParams.get("token") || undefined;
      }

      if (!token) {
        res.writeHead(401, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Missing token" }));
        return;
      }

      const payload = jwt.verify(token, JWT_SECRET!);
      if (typeof payload === "string") throw new Error("Invalid token payload");

      const { pairId, deviceId, userId } = payload as {
        pairId: string;
        deviceId: string;
        userId: string;
      };

      if (!pairId || !deviceId || !userId) {
        res.writeHead(401, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Invalid token claims" }));
        return;
      }

      const { data: pair, error } = await supabase
        .from("device_pairs")
        .select("*")
        .eq("id", pairId)
        .single();

      if (error || !pair) {
        res.writeHead(403, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Invalid pair" }));
        return;
      }

      if (pair.user_id !== userId) {
        res.writeHead(403, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Unauthorized pair" }));
        return;
      }

      const room = rooms.get(pairId) ?? [];
      const pairStats = ensurePairStats(pairId);
      const aggregate = aggregatePacketStats();

      const hasDeviceA = Boolean(pair.mobile_device_id ?? pair.device_a_id);
      const hasDeviceB = Boolean(pair.server_device_id ?? pair.device_b_id);

      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          authenticated: true,
          pair: {
            id: pair.id,
            status: pair.status,
            hasDeviceA,
            hasDeviceB,
          },
          room: {
            connectedClients: room.length,
          },
          transfer: {
            byType: pairStats.relayedByType,
            bytesRelayed: pairStats.bytesRelayed,
            lastRelayAt: pairStats.lastRelayAt,
          },
          server: {
            uptimeSec: Math.floor((Date.now() - serverStartedAtMs) / 1000),
            roomsActive: rooms.size,
            clientsConnected: totalConnectedClients(),
            packetsRelayedByType: aggregate.totals,
            bytesRelayed: aggregate.bytesRelayed,
          },
        }),
      );
      return;
    } catch (err) {
      console.error("/v1/diag auth error:", err);
      res.writeHead(401, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Unauthorized" }));
      return;
    }
  }

  if (path === "/v1/account-usage") {
    try {
      const authHeader = req.headers["authorization"] || "";
      let token: string | undefined;
      if (authHeader.toLowerCase().startsWith("bearer ")) {
        token = authHeader.slice(7).trim();
      } else if (parsed.searchParams.get("token")) {
        token = parsed.searchParams.get("token") || undefined;
      }

      if (!token) {
        res.writeHead(401, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Missing token" }));
        return;
      }

      const payload = jwt.verify(token, JWT_SECRET!);
      if (typeof payload === "string") throw new Error("Invalid token payload");

      const { pairId, deviceId, userId } = payload as {
        pairId: string;
        deviceId: string;
        userId: string;
      };

      if (!pairId || !deviceId || !userId) {
        res.writeHead(401, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Invalid token claims" }));
        return;
      }

      const { data: pair, error } = await supabase
        .from("device_pairs")
        .select("*")
        .eq("id", pairId)
        .single();

      if (error || !pair) {
        res.writeHead(403, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Invalid pair" }));
        return;
      }

      if (pair.user_id !== userId) {
        res.writeHead(403, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Unauthorized pair" }));
        return;
      }

      const usage = ensureUserUsage(userId);
      const pairStats = ensurePairStats(pairId);

      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          authenticated: true,
          userId,
          pairId,
          usage: {
            packetsRelayed: usage.packetsRelayed,
            relayedByType: usage.relayedByType,
            bytesRelayed: usage.bytesRelayed,
            iceIssued: usage.iceIssued,
            connectionsStarted: usage.connectionsStarted,
            connectionMs: usage.connectionMs,
            lastSeenAt: usage.lastSeenAt,
          },
          pairTransfer: {
            byType: pairStats.relayedByType,
            bytesRelayed: pairStats.bytesRelayed,
            lastRelayAt: pairStats.lastRelayAt,
          },
          estimatedCostUsd: buildCostEstimate(usage),
        }),
      );
      return;
    } catch (err) {
      console.error("/v1/account-usage auth error:", err);
      res.writeHead(401, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Unauthorized" }));
      return;
    }
  }

  if (path === "/v1/ice") {
    try {
      const authHeader = req.headers["authorization"] || "";
      let token: string | undefined;
      if (authHeader.toLowerCase().startsWith("bearer ")) {
        token = authHeader.slice(7).trim();
      } else if (parsed.searchParams.get("token")) {
        token = parsed.searchParams.get("token") || undefined;
      }
      if (!token) {
        res.writeHead(401, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Missing token" }));
        return;
      }

      const payload = jwt.verify(token, JWT_SECRET!);
      if (typeof payload === "string") throw new Error("Invalid token payload");

      const { pairId, deviceId, userId } = payload as {
        pairId: string;
        deviceId: string;
        userId: string;
      };

      if (!pairId || !deviceId || !userId) {
        res.writeHead(401, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Invalid token claims" }));
        return;
      }

      const rate = checkIceRate(userId);
      if (!rate.allowed) {
        res.writeHead(429, {
          "Content-Type": "application/json",
          "Retry-After": String(rate.resetIn),
        });
        res.end(
          JSON.stringify({
            error: "Rate limit exceeded",
            limit: ICE_RATE_MAX,
            windowSec: ICE_RATE_WINDOW_SEC,
            resetInSec: rate.resetIn,
          }),
        );
        return;
      }

      const { data: pair, error } = await supabase
        .from("device_pairs")
        .select("*")
        .eq("id", pairId)
        .single();

      if (error || !pair) {
        res.writeHead(403, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Invalid pair" }));
        return;
      }

      if (pair.user_id !== userId) {
        res.writeHead(403, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Unauthorized pair" }));
        return;
      }

      const isMember =
        pair.mobile_device_id === deviceId ||
        pair.server_device_id === deviceId ||
        pair.device_a_id === deviceId ||
        pair.device_b_id === deviceId;
      if (!isMember) {
        res.writeHead(403, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Device not in pair" }));
        return;
      }

      if (!TURN_REST_SECRET || TURN_URLS.length === 0) {
        res.writeHead(503, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "TURN is not configured" }));
        return;
      }

      const user = `${userId}:${pairId}:${deviceId}`;
      const { username, credential } = makeTurnCredentials(user, TURN_TTL);
      const now = Math.floor(Date.now() / 1000);
      const userUsage = ensureUserUsage(userId);
      userUsage.iceIssued += 1;
      userUsage.lastSeenAt = Date.now();

      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          urls: TURN_URLS,
          username,
          credential,
          ttl: TURN_TTL,
          realm: TURN_REALM,
          issuedAt: now,
          expiresAt: now + TURN_TTL,
          usage: {
            countInWindow: rate.count,
            maxInWindow: ICE_RATE_MAX,
            windowRemainingSec: rate.resetIn,
          },
        }),
      );
      return;
    } catch (err) {
      console.error("/v1/ice auth error:", err);
      res.writeHead(401, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Unauthorized" }));
      return;
    }
  }

  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ error: "Not found" }));
});

const wss = new WebSocketServer({ noServer: true });

function rejectUpgrade(socket: any, status: number, msg: string) {
  socket.write(
    `HTTP/1.1 ${status} ${msg}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n`,
  );
  socket.destroy();
}

server.on("upgrade", async (req: IncomingMessage, socket, head) => {
  try {
    const url = req.url || "";
    const parsed = new URL(url, `http://${req.headers.host || "localhost"}`);

    let token = parsed.searchParams.get("token") || "";
    if (!token) {
      const authHeader = (req.headers["authorization"] as string) || "";
      if (authHeader.toLowerCase().startsWith("bearer ")) {
        token = authHeader.slice(7).trim();
      }
    }
    if (!token) return rejectUpgrade(socket, 401, "Unauthorized");

    let payload: any;
    try {
      payload = jwt.verify(token, JWT_SECRET!);
    } catch {
      return rejectUpgrade(socket, 401, "Unauthorized");
    }
    if (typeof payload === "string") return rejectUpgrade(socket, 401, "Unauthorized");

    const { userId, pairId, deviceId } = payload as {
      userId?: string;
      pairId?: string;
      deviceId?: string;
    };
    if (!userId || !pairId || !deviceId)
      return rejectUpgrade(socket, 401, "Unauthorized");

    const { data: pair, error } = await supabase
      .from("device_pairs")
      .select("*")
      .eq("id", pairId)
      .single();

    if (error || !pair) return rejectUpgrade(socket, 403, "Forbidden");
    if (pair.user_id !== userId) return rejectUpgrade(socket, 403, "Forbidden");
    if (pair.status !== "active") return rejectUpgrade(socket, 403, "Forbidden");

    const isMember =
      pair.mobile_device_id === deviceId ||
      pair.server_device_id === deviceId ||
      pair.device_a_id === deviceId ||
      pair.device_b_id === deviceId;
    if (!isMember) return rejectUpgrade(socket, 403, "Forbidden");

    wss.handleUpgrade(req, socket as any, head, (ws) => {
      setWsMeta(ws, { userId, pairId, deviceId, connectedAtMs: Date.now() });
      wss.emit("connection", ws, req);
    });
  } catch {
    return rejectUpgrade(socket, 500, "Internal Server Error");
  }
});

wss.on("connection", (ws) => {
  const meta = wsMeta(ws)!;
  const { userId, pairId, deviceId } = meta;
  const userUsage = ensureUserUsage(userId);
  userUsage.connectionsStarted += 1;
  userUsage.lastSeenAt = Date.now();

  if (!rooms.has(pairId)) rooms.set(pairId, []);
  const clients = rooms.get(pairId)!;
  clients.push(ws);

  console.log(`Device ${deviceId} connected to room ${pairId} (user ${userId})`);

  ws.on("message", (message) => {
    let parsedMessage: SignalMessage;
    try {
      parsedMessage = JSON.parse(message.toString());
    } catch {
      console.log(`Invalid JSON from ${deviceId}`);
      return;
    }

    if (
      !parsedMessage.t ||
      !parsedMessage.pairId ||
      !["offer", "answer", "ice", "bye", "mode"].includes(parsedMessage.t)
    ) {
      console.log(
        `Message from ${deviceId} is missing required fields or has invalid type.`,
      );
      return;
    }

    if (parsedMessage.pairId !== pairId) {
      console.log(
        `Dropping message from ${deviceId}: pair mismatch (${parsedMessage.pairId} != ${pairId})`,
      );
      return;
    }

    if (
      (parsedMessage.t === "offer" || parsedMessage.t === "answer") &&
      !parsedMessage.sdp
    ) {
      console.log(`Dropping ${parsedMessage.t} without SDP from ${deviceId}`);
      return;
    }

    if (parsedMessage.t === "ice" && !parsedMessage.ice) {
      console.log(`Dropping ICE without payload from ${deviceId}`);
      return;
    }

    if (parsedMessage.t === "mode" && !parsedMessage.mode) {
      console.log(`Dropping mode without mode value from ${deviceId}`);
      return;
    }

    const roomClients = rooms.get(pairId);
    if (!roomClients) {
      console.log(`Room ${pairId} not found for message from ${deviceId}`);
      return;
    }

    const otherClient = roomClients.find((client) => client !== ws);
    if (otherClient && otherClient.readyState === WebSocket.OPEN) {
      console.log(
        `Relaying message of type '${parsedMessage.t}' from ${deviceId} in room ${pairId}`,
      );
      otherClient.send(message.toString());

      const stats = ensurePairStats(pairId);
      const typed = parsedMessage.t as PacketType;
      stats.relayedByType[typed] += 1;
      const relayedBytes = Buffer.byteLength(message.toString(), "utf8");
      stats.bytesRelayed += relayedBytes;
      stats.lastRelayAt = Date.now();

      userUsage.packetsRelayed += 1;
      userUsage.relayedByType[typed] += 1;
      userUsage.bytesRelayed += relayedBytes;
      userUsage.lastSeenAt = Date.now();

      if (parsedMessage.t === "bye") {
        roomClients.forEach((client) => {
          if (client.readyState === WebSocket.OPEN) {
            client.close(1000, "Call ended");
          }
        });
        rooms.delete(pairId);
      }
    } else {
      console.log(
        `No other peer connected in room ${pairId}. Message queued not supported.`,
      );
    }
  });

  ws.on("close", () => {
    console.log(`Device ${deviceId} disconnected from room ${pairId}`);
    const connectedAt = meta.connectedAtMs || Date.now();
    const durationMs = Math.max(0, Date.now() - connectedAt);
    userUsage.connectionMs += durationMs;
    userUsage.lastSeenAt = Date.now();

    const roomClients = rooms.get(pairId);
    if (roomClients) {
      const updatedClients = roomClients.filter((client) => client !== ws);
      if (updatedClients.length > 0) {
        rooms.set(pairId, updatedClients);
      } else {
        rooms.delete(pairId);
      }
    }
  });

  ws.on("error", (err) => {
    console.error(`WebSocket error for ${deviceId}:`, err);
  });
});

server.listen(PORT, () => {
  console.log(`🔌 Signal server listening on port ${PORT}`);
});
