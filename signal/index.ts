import WebSocket, { WebSocketServer } from 'ws';
import jwt from 'jsonwebtoken';
import url from 'url';
import http from 'http';
import { createClient } from '@supabase/supabase-js';

// Environment variables
const PORT = process.env.P2P_SIGNAL_PORT ? parseInt(process.env.P2P_SIGNAL_PORT, 10) : 3001;
const JWT_SECRET = process.env.P2P_SIGNAL_JWT_SECRET;
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

// Validations
if (!JWT_SECRET) {
  console.error('FATAL: P2P_SIGNAL_JWT_SECRET environment variable is not set.');
  process.exit(1);
}
if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY) {
  console.error('FATAL: Supabase environment variables are not set.');
  process.exit(1);
}

// Supabase client
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

// Create a standard HTTP server for health checks
const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify({ status: 'ok' }));
    return;
  }
  res.writeHead(404).end();
});

// Attach the WebSocket server to the HTTP server
const wss = new WebSocketServer({ noServer: true });

server.on('upgrade', (request, socket, head) => {
  wss.handleUpgrade(request, socket, head, (ws) => {
    wss.emit('connection', ws, request);
  });
});

// In-memory room storage
const rooms = new Map<string, WebSocket[]>();

wss.on('connection', async (ws, req) => {
  const { query } = url.parse(req.url || '', true);
  const token = query.token as string | undefined;

  if (!token) {
    return ws.close(1008, 'No token provided');
  }

  let decoded: jwt.JwtPayload;
  try {
    const payload = jwt.verify(token, JWT_SECRET);
    if (typeof payload === 'string') throw new Error('Invalid token payload');
    decoded = payload;
  } catch (err) {
    console.log('Connection rejected: Invalid token.', (err as Error).message);
    return ws.close(1008, 'Invalid token');
  }

  const { pairId, deviceId, userId } = decoded as { pairId: string; deviceId: string; userId: string };

  if (!pairId || !deviceId || !userId) {
    return ws.close(1008, 'Token missing required claims');
  }

  // **[NEW] Validate pairId against Supabase**
  try {
    const { data: pair, error } = await supabase
      .from('device_pairs')
      .select('id, status, user_id')
      .eq('id', pairId)
      .eq('status', 'active')
      .single();

    if (error || !pair) {
      console.log(`Connection rejected: Invalid or inactive pairId ${pairId}`);
      return ws.close(1008, 'Invalid or inactive pair');
    }

    // Ensure the user in the token matches the owner of the pair
    if (pair.user_id !== userId) {
        console.log(`Connection rejected: User ${userId} does not own pair ${pairId}`);
        return ws.close(1008, 'Unauthorized pair');
    }

  } catch (dbError) {
    console.error('Supabase validation error:', dbError);
    return ws.close(1011, 'Server error during validation');
  }

  // Add client to the room
  if (!rooms.has(pairId)) {
    rooms.set(pairId, []);
  }
  const room = rooms.get(pairId)!;

  if (room.length >= 2) {
    console.log(`Connection rejected: Room ${pairId} is full.`);
    return ws.close(1011, 'Room is full');
  }

  room.push(ws);
  console.log(`Client with deviceId ${deviceId} connected to room ${pairId}. Room size: ${room.length}`);

  ws.on('message', (message: WebSocket.RawData) => {
    let parsedMessage;
    try {
      parsedMessage = JSON.parse(message.toString());
    } catch (e) {
      console.log(`Invalid JSON from ${deviceId}.`);
      return;
    }

    // **[NEW] Validate message schema and pairId consistency**
    if (!parsedMessage.t || !parsedMessage.pairId || !['offer', 'answer', 'ice', 'bye'].includes(parsedMessage.t)) {
      console.log(`Message from ${deviceId} is missing required fields or has invalid type.`);
      return;
    }

    if (parsedMessage.pairId !== pairId) {
      console.log(`Message pairId ${parsedMessage.pairId} from ${deviceId} does not match token's pairId ${pairId}.`);
      return;
    }

    // Relay message to the other client in the room
    const otherClient = room.find(client => client !== ws);
    if (otherClient && otherClient.readyState === WebSocket.OPEN) {
      console.log(`Relaying message of type '${parsedMessage.t}' from ${deviceId} in room ${pairId}`);
      otherClient.send(message.toString());
    } else {
      console.log(`No other client in room ${pairId} to relay message to.`);
    }
  });

  ws.on('close', () => {
    console.log(`Client with deviceId ${deviceId} disconnected from room ${pairId}.`);
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

  ws.on('error', (error) => {
    console.error(`WebSocket error for deviceId ${deviceId} in room ${pairId}:`, error);
  });
});

server.listen(PORT, () => {
  console.log(`🚀 P2P Signaling Server listening on ws://localhost:${PORT}`);
  console.log(`   Health check available at http://localhost:${PORT}/health`);
});