"""WebSocket manager for iOS client communication."""
import json
from typing import Dict, Any, Optional
import logging
from fastapi import WebSocket, WebSocketDisconnect

from utils.logger import get_logger

logger = get_logger(__name__)

class WebSocketManager:
    """Manages WebSocket connections with iOS clients."""
    
    def __init__(self):
        """Initialize WebSocket manager."""
        self.ios_clients: Dict[str, WebSocket] = {}
        self.dashboard_clients: Dict[str, WebSocket] = {} # For web dashboard clients
        self.active_connections = set() # Might want to differentiate or expand this
        self.stats = {
            "total_frames": 0,
            "total_messages": 0,
            "active_clients": 0, # Could be total or split by type
            "active_ios_clients": 0,
            "active_dashboard_clients": 0
        }
        logger.info("WebSocketManager initialized")

    async def add_ios_client(self, websocket: WebSocket, client_id: str) -> None:
        """
        Add new iOS client connection.
        
        Args:
            websocket: WebSocket connection
            client_id: Unique client identifier
        """
        await websocket.accept()
        self.ios_clients[client_id] = websocket
        # self.active_connections.add(client_id) # Keep this generic or specify type
        self.stats["active_ios_clients"] += 1
        self.stats["active_clients"] = self.stats["active_ios_clients"] + self.stats["active_dashboard_clients"]
        logger.info(f"iOS client {client_id} connected")
        
    async def remove_ios_client(self, client_id: str) -> None:
        """
        Remove iOS client connection.
        
        Args:
            client_id: Client to remove
        """
        if client_id in self.ios_clients:
            try:
                await self.ios_clients[client_id].close()
            except:
                pass
            del self.ios_clients[client_id]
            # self.active_connections.discard(client_id)
            if self.stats["active_ios_clients"] > 0: # Ensure it doesn't go negative
                self.stats["active_ios_clients"] -= 1
            self.stats["active_clients"] = self.stats["active_ios_clients"] + self.stats["active_dashboard_clients"]
            logger.info(f"iOS client {client_id} disconnected")

    async def add_dashboard_client(self, websocket: WebSocket, client_id: str) -> None:
        """
        Add new dashboard client connection.
        """
        await websocket.accept()
        self.dashboard_clients[client_id] = websocket
        self.stats["active_dashboard_clients"] += 1
        self.stats["active_clients"] = self.stats["active_ios_clients"] + self.stats["active_dashboard_clients"]
        logger.info(f"Dashboard client {client_id} connected")

    async def remove_dashboard_client(self, client_id: str) -> None:
        """
        Remove dashboard client connection.
        """
        if client_id in self.dashboard_clients:
            try:
                # May not need to explicitly close if client initiated disconnect
                await self.dashboard_clients[client_id].close()
            except Exception: # Broad catch for already closed sockets
                pass
            del self.dashboard_clients[client_id]
            if self.stats["active_dashboard_clients"] > 0:
                self.stats["active_dashboard_clients"] -= 1
            self.stats["active_clients"] = self.stats["active_ios_clients"] + self.stats["active_dashboard_clients"]
            logger.info(f"Dashboard client {client_id} disconnected")
            
    async def send_to_ios_client(
        self,
        client_id: str,
        message: Dict[str, Any]
    ) -> None:
        """
        Send message to specific iOS client.
        
        Args:
            client_id: Target client
            message: Message to send
        """
        if client_id in self.ios_clients:
            try:
                await self.ios_clients[client_id].send_json(message)
                self.stats["total_messages"] += 1
            except Exception as e:
                logger.error(f"Error sending to iOS client {client_id}: {e}")
                await self.remove_ios_client(client_id)
                
    async def send_processing_status(
        self,
        client_id: str,
        status: str,
        details: Optional[str] = None
    ) -> None:
        """
        Send processing status update to client.
        
        Args:
            client_id: Target client
            status: Status message
            details: Optional status details
        """
        await self.send_to_ios_client(client_id, {
            "type": "status",
            "status": status,
            "details": details
        })
        
    def update_stats(self, frame_processed: bool = False) -> None:
        """
        Update manager statistics.
        
        Args:
            frame_processed: Whether a frame was processed
        """
        if frame_processed:
            self.stats["total_frames"] += 1
            
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        return {
            "total_frames": self.stats["total_frames"],
            "total_messages": self.stats["total_messages"],
            "active_clients": self.stats["active_clients"],
            "active_ios_clients": self.stats["active_ios_clients"],
            "active_dashboard_clients": self.stats["active_dashboard_clients"],
            "average_fps": (
                self.stats["total_frames"] / (self.stats["total_messages"] or 1) # This FPS might be misleading
            )
        }
        
    def is_healthy(self) -> bool:
        """Check manager health."""
        return True  # Basic check, could be enhanced
        
    async def broadcast_error(
        self,
        error: str,
        details: Optional[str] = None
    ) -> None:
        """
        Broadcast error to all clients.
        
        Args:
            error: Error message
            details: Optional error details
        """
        error_msg = {
            "type": "error",
            "error": error,
            "details": details
        }
        
        disconnected = []
        for client_id in self.ios_clients:
            try:
                await self.send_to_ios_client(client_id, error_msg)
            except:
                disconnected.append(client_id)
                
        # Clean up disconnected clients
        for client_id in disconnected:
            await self.remove_ios_client(client_id)

    async def broadcast_to_dashboards(self, message: Dict[str, Any]) -> None:
        """
        Broadcast message to all connected dashboard clients.
        """
        disconnected_dashboards = []
        for client_id, websocket in self.dashboard_clients.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to dashboard client {client_id}: {e}")
                disconnected_dashboards.append(client_id)
        
        for client_id in disconnected_dashboards:
            await self.remove_dashboard_client(client_id) # Use the correct remove method
            
    async def shutdown(self) -> None:
        """Clean up all connections."""
        # Notify iOS clients of shutdown
        await self.broadcast_error("Server shutting down") # This goes to iOS clients
        
        # Notify dashboard clients of shutdown (optional, or send a specific message)
        dashboard_shutdown_message = {"type": "system_message", "event": "shutdown", "message": "Server is shutting down."}
        await self.broadcast_to_dashboards(dashboard_shutdown_message)

        # Close all iOS connections
        for client_id in list(self.ios_clients.keys()):
            await self.remove_ios_client(client_id)
        
        # Close all dashboard connections
        for client_id in list(self.dashboard_clients.keys()):
            await self.remove_dashboard_client(client_id)
            
        self.stats = {
            "total_frames": 0,
            "total_messages": 0,
            "active_clients": 0,
            "active_ios_clients": 0,
            "active_dashboard_clients": 0
        }
        logger.info("WebSocket manager shut down")