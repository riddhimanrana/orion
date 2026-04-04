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

interface ClientMeta {
  userId: string;
  pairId: string;
  deviceId: string;
}

// --- In-memory state ---
const rooms = new Map<string, WebSocket[]>();
const serverStartedAtMs = Date.now();
const packetStatsByPair = new Map<string, PairPacketStats>();
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
        .select("id, status, user_id, device_a_id, device_b_id")
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

      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          authenticated: true,
          pair: {
            id: pair.id,
            status: pair.status,
            hasDeviceA: Boolean(pair.device_a_id),
            hasDeviceB: Boolean(pair.device_b_id),
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
        .select("id, status, user_id, device_a_id, device_b_id")
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

      const isMember = pair.device_a_id === deviceId || pair.device_b_id === deviceId;
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
      .select("id, status, user_id, device_a_id, device_b_id")
      .eq("id", pairId)
      .single();

    if (error || !pair) return rejectUpgrade(socket, 403, "Forbidden");
    if (pair.user_id !== userId) return rejectUpgrade(socket, 403, "Forbidden");
    if (pair.status !== "active") return rejectUpgrade(socket, 403, "Forbidden");

    const isMember = pair.device_a_id === deviceId || pair.device_b_id === deviceId;
    if (!isMember) return rejectUpgrade(socket, 403, "Forbidden");

    wss.handleUpgrade(req, socket as any, head, (ws) => {
      setWsMeta(ws, { userId, pairId, deviceId });
      wss.emit("connection", ws, req);
    });
  } catch {
    return rejectUpgrade(socket, 500, "Internal Server Error");
  }
});

wss.on("connection", (ws) => {
  const meta = wsMeta(ws)!;
  const { userId, pairId, deviceId } = meta;

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
      stats.bytesRelayed += Buffer.byteLength(message.toString(), "utf8");
      stats.lastRelayAt = Date.now();

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
