// lib/websocket.ts

// Default to the new dashboard WebSocket endpoint
const WEBSOCKET_URL = process.env.NEXT_PUBLIC_WEBSOCKET_URL || 'ws://localhost:8000/ws/dashboard';

let socket: WebSocket | null = null;

interface WebSocketHandlers {
  onOpen?: (event: Event) => void;
  onMessage?: (event: MessageEvent) => void;
  onError?: (event: Event) => void;
  onClose?: (event: CloseEvent) => void;
}

export const initWebSocket = (handlers: WebSocketHandlers): WebSocket => {
  if (socket && socket.readyState !== WebSocket.CLOSED && socket.readyState !== WebSocket.CLOSING) {
    console.warn('WebSocket is already connected or connecting.');
    return socket;
  }

  socket = new WebSocket(WEBSOCKET_URL);

  socket.onopen = (event) => {
    console.log('WebSocket connection established:', event);
    if (handlers.onOpen) {
      handlers.onOpen(event);
    }
  };

  socket.onmessage = (event) => {
    console.log('WebSocket message received:', event.data);
    // TODO: Add more sophisticated message parsing and routing
    if (handlers.onMessage) {
      handlers.onMessage(event);
    }
  };

  socket.onerror = (event) => {
    console.error('WebSocket error:', event);
    if (handlers.onError) {
      handlers.onError(event);
    }
  };

  socket.onclose = (event) => {
    console.log('WebSocket connection closed:', event);
    if (handlers.onClose) {
      handlers.onClose(event);
    }
    socket = null; // Clear the socket instance on close
  };

  return socket;
};

export const closeWebSocket = () => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.close();
  }
};

export const sendWebSocketMessage = (message: string | ArrayBufferLike | Blob | ArrayBufferView) => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(message);
  } else {
    console.error('WebSocket is not connected. Cannot send message.');
  }
};

// You might want to expose the socket instance if direct access is needed,
// but usually, it's better to interact via these helper functions.
// export const getWebSocket = (): WebSocket | null => socket;