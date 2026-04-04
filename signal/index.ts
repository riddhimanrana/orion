// @ts-nocheck
import WebSocket, { WebSocketServer } from "ws";
import jwt from "jsonwebtoken";
import url from "url";
import crypto from "crypto";
import http from "http";
import { createClient } from "@supabase/supabase-js";

// Environment variables
const PORT = process.env.P2P_SIGNAL_PORT
  ? parseInt(process.env.P2P_SIGNAL_PORT, 10)
  : 3001;
const JWT_SECRET = process.env.P2P_SIGNAL_JWT_SECRET;
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
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
  : 600; // 10 min
const ICE_RATE_MAX = process.env.ICE_RATE_MAX
  ? parseInt(process.env.ICE_RATE_MAX, 10)
  : 20; // max requests per window per user

// Validations
if (!JWT_SECRET) {
  console.error(
    "FATAL: P2P_SIGNAL_JWT_SECRET environment variable is not set.",
  );
  process.exit(1);
}
if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY) {
  console.error("FATAL: Supabase environment variables are not set.");
  process.exit(1);
}
if (!TURN_REST_SECRET) {
  console.warn(
    "WARN: TURN_REST_SECRET is not set. /v1/ice endpoint will be disabled.",
  );
}

// Supabase client
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

// Create a standard HTTP server for health checks
// In-memory rate limiting state: userId -> { windowStart, count }
const iceRateState = new Map<string, { windowStart: number; count: number }>();

const server = http.createServer(async (req, res) => {
  const parsed = url.parse(req.url || "", true);
  const path = parsed.pathname || "/";
  // Basic CORS (adjust allowlist as needed)
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Authorization, Content-Type");

  if (req.method === "OPTIONS") {
    res.writeHead(204).end();
    return;
  }

  if (path === "/health") {
    res.writeHead(200, {
      "Content-Type": "application/json",
    });
    res.end(JSON.stringify({ status: "ok" }));
    return;
  }

  // Ephemeral TURN credentials endpoint
  if (path === "/v1/ice") {
    if (!TURN_REST_SECRET) {
      res.writeHead(503, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "ICE endpoint disabled" }));
      return;
    }

    try {
      // Extract token from Authorization: Bearer <token> or ?token=
      const authHeader = req.headers["authorization"] || "";
      let token: string | undefined;
      if (authHeader.toLowerCase().startsWith("bearer ")) {
        token = authHeader.slice(7).trim();
      } else if (parsed.query && typeof parsed.query.token === "string") {
        token = parsed.query.token;
      }

      if (!token) {
        res.writeHead(401, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Missing token" }));
        return;
      }

      // Verify JWT
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

      // Validate active pair belongs to user
      const { data: pair, error } = await supabase
        .from("device_pairs")
        .select("id, status, user_id")
        .eq("id", pairId)
        .eq("status", "active")
        .single();
      if (error || !pair || pair.user_id !== userId) {
        res.writeHead(403, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Invalid or unauthorized pair" }));
        return;
      }

      // Rate limiting per userId
      const nowSec = Math.floor(Date.now() / 1000);
      const entry = iceRateState.get(userId);
      if (!entry || nowSec - entry.windowStart >= ICE_RATE_WINDOW_SEC) {
        iceRateState.set(userId, { windowStart: nowSec, count: 0 });
      }
      const state = iceRateState.get(userId)!;
      if (state.count >= ICE_RATE_MAX) {
        const windowRemainingSec = Math.max(
          0,
          ICE_RATE_WINDOW_SEC - (nowSec - state.windowStart),
        );
        res.writeHead(429, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            error: "Rate limit exceeded",
            usage: {
              countInWindow: state.count,
              maxInWindow: ICE_RATE_MAX,
              windowRemainingSec,
            },
          }),
        );
        return;
      }

      // Generate ephemeral TURN credentials (use-auth-secret)
      const now = nowSec;
      const expiry = now + TURN_TTL;
      // username format: "expiry:userId" (can use pairId instead)
      const turnUsername = `${expiry}:${userId}`;
      const credential = crypto
        .createHmac("sha1", TURN_REST_SECRET)
        .update(turnUsername)
        .digest("base64");

      // Compose URLs (include STUN fallback)
      const urls = [...TURN_URLS, "stun:stun.l.google.com:19302"];

      // Increment usage count after successful generation
      state.count += 1;

      console.log(
        `ICE issued for user ${userId}, pair ${pairId}. count=${state.count}/${ICE_RATE_MAX}`,
      );
      // Persist a lightweight usage record (ignore errors)
      try {
        await supabase.from("ice_usage").insert({
          user_id: userId,
          pair_id: pairId,
          device_id: deviceId,
          issued_at: new Date(now * 1000).toISOString(),
          ttl: TURN_TTL,
        });
      } catch (e) {
        console.warn("ice_usage insert failed (non-blocking)");
      }

      const body = {
        urls,
        username: turnUsername,
        credential,
        ttl: TURN_TTL,
        realm: TURN_REALM,
        issuedAt: now,
        expiresAt: expiry,
        usage: {
          countInWindow: state.count,
          maxInWindow: ICE_RATE_MAX,
          windowRemainingSec: Math.max(
            0,
            ICE_RATE_WINDOW_SEC - (now - state.windowStart),
          ),
        },
      };

      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(body));
      return;
    } catch (err) {
      console.error("/v1/ice error:", err);
      res.writeHead(401, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Unauthorized" }));
      return;
    }
  }
  res.writeHead(404).end();
});

// Attach the WebSocket server to the HTTP server
const wss = new WebSocketServer({ noServer: true });

server.on("upgrade", (request, socket, head) => {
  wss.handleUpgrade(request, socket, head, (ws) => {
    wss.emit("connection", ws, request);
  });
});

// In-memory room storage
const rooms = new Map<string, WebSocket[]>();

wss.on("connection", async (ws, req) => {
  const { query } = url.parse(req.url || "", true);
  const token = query.token as string | undefined;

  if (!token) {
    return ws.close(1008, "No token provided");
  }

  let decoded: jwt.JwtPayload;
  try {
    const payload = jwt.verify(token, JWT_SECRET);
    if (typeof payload === "string") throw new Error("Invalid token payload");
    decoded = payload;
  } catch (err) {
    console.log("Connection rejected: Invalid token.", (err as Error).message);
    return ws.close(1008, "Invalid token");
  }

  const { pairId, deviceId, userId } = decoded as {
    pairId: string;
    deviceId: string;
    userId: string;
  };

  if (!pairId || !deviceId || !userId) {
    return ws.close(1008, "Token missing required claims");
  }

  // **[NEW] Validate pairId against Supabase**
  try {
    const { data: pair, error } = await supabase
      .from("device_pairs")
      .select("id, status, user_id")
      .eq("id", pairId)
      .eq("status", "active")
      .single();

    if (error || !pair) {
      console.log(`Connection rejected: Invalid or inactive pairId ${pairId}`);
      return ws.close(1008, "Invalid or inactive pair");
    }

    // Ensure the user in the token matches the owner of the pair
    if (pair.user_id !== userId) {
      console.log(
        `Connection rejected: User ${userId} does not own pair ${pairId}`,
      );
      return ws.close(1008, "Unauthorized pair");
    }
  } catch (dbError) {
    console.error("Supabase validation error:", dbError);
    return ws.close(1011, "Server error during validation");
  }

  // Add client to the room
  if (!rooms.has(pairId)) {
    rooms.set(pairId, []);
  }
  const room = rooms.get(pairId)!;

  if (room.length >= 2) {
    console.log(`Connection rejected: Room ${pairId} is full.`);
    return ws.close(1011, "Room is full");
  }

  room.push(ws);
  console.log(
    `Client with deviceId ${deviceId} connected to room ${pairId}. Room size: ${room.length}`,
  );

  ws.on("message", (message: WebSocket.RawData) => {
    let parsedMessage;
    try {
      parsedMessage = JSON.parse(message.toString());
    } catch (e) {
      console.log(`Invalid JSON from ${deviceId}.`);
      return;
    }

    // **[NEW] Validate message schema and pairId consistency**
    if (
      !parsedMessage.t ||
      !parsedMessage.pairId ||
      !["offer", "answer", "ice", "bye"].includes(parsedMessage.t)
    ) {
      console.log(
        `Message from ${deviceId} is missing required fields or has invalid type.`,
      );
      return;
    }

    if (parsedMessage.pairId !== pairId) {
      console.log(
        `Message pairId ${parsedMessage.pairId} from ${deviceId} does not match token's pairId ${pairId}.`,
      );
      return;
    }

    // Optional: sanity checks for payload shape
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

    // Relay message to the other client in the room
    const otherClient = room.find((client) => client !== ws);
    if (otherClient && otherClient.readyState === WebSocket.OPEN) {
      console.log(
        `Relaying message of type '${parsedMessage.t}' from ${deviceId} in room ${pairId}`,
      );
      otherClient.send(message.toString());

      // If this is a 'bye', proactively close both sides to cleanup
      if (parsedMessage.t === "bye") {
        try {
          otherClient.close(1000, "peer bye");
        } catch {}
        try {
          ws.close(1000, "bye sent");
        } catch {}
      }
    } else {
      console.log(`No other client in room ${pairId} to relay message to.`);
      if (parsedMessage.t === "bye") {
        try {
          ws.close(1000, "bye; empty room");
        } catch {}
      }
    }
  });

  ws.on("close", () => {
    console.log(
      `Client with deviceId ${deviceId} disconnected from room ${pairId}.`,
    );
    const currentRoom = rooms.get(pairId);
    if (currentRoom) {
      const index = currentRoom.indexOf(ws);
      if (index > -1) currentRoom.splice(index, 1);
      if (currentRoom.length === 0) {
        console.log(`Room ${pairId} is now empty, removing.`);
        rooms.delete(pairId);
      }
    }
  });

  ws.on("error", (error: unknown) => {
    console.error(
      `WebSocket error for deviceId ${deviceId} in room ${pairId}:`,
      error,
    );
  });
});

server.listen(PORT, () => {
  console.log(`🚀 P2P Signaling Server listening on ws://localhost:${PORT}`);
  console.log(`   Health check available at http://localhost:${PORT}/health`);
});
