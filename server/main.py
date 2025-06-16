"""Orion Computer Vision Server using MLX."""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from rich.console import Console

from config import settings
from models import DetectionFrame, ServerResponse, AnalysisResult, SystemStatus, HealthCheck
from services.websocket_manager import WebSocketManager
from services.vision_processor import VisionProcessor
from services.llm_processor import LLMProcessor
from services.context_memory import ContextMemory
from services.model_manager import ModelManager
from utils.logger import setup_logger, get_logger

# Setup rich console and logging
console = Console()
logger = get_logger(__name__)

# Global service instances initialized as None
websocket_manager: Optional[WebSocketManager] = None
vision_processor: Optional[VisionProcessor] = None
llm_processor: Optional[LLMProcessor] = None
context_memory: Optional[ContextMemory] = None
model_manager: Optional[ModelManager] = None

def check_services() -> bool:
    """Check if all required services are initialized."""
    return all([
        websocket_manager is not None,
        vision_processor is not None,
        llm_processor is not None,
        context_memory is not None,
        model_manager is not None
    ])

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    global websocket_manager, vision_processor, llm_processor, context_memory, model_manager
    
    console.print("[bold green]🚀 Starting Orion Server (MLX)...[/bold green]")
    
    try:
        # Initialize model manager first
        model_manager = ModelManager()
        await model_manager.initialize()
        
        # Initialize core services
        context_memory = ContextMemory()
        vision_processor = VisionProcessor(model_manager)
        llm_processor = LLMProcessor(model_manager)
        websocket_manager = WebSocketManager()
        
        # Initialize processors
        await vision_processor.initialize()
        await llm_processor.initialize()
        
        if not check_services():
            raise RuntimeError("Failed to initialize all services")
        
        console.print("[bold green]✅ All services initialized successfully![/bold green]")
        logger.info("Server startup completed successfully")
        
        yield
        
    except Exception as e:
        console.print(f"[bold red]❌ Failed to initialize services: {e}[/bold red]")
        logger.error(f"Startup failed: {e}")
        raise
    
    finally:
        # Cleanup on shutdown
        console.print("[bold yellow]🛑 Shutting down Orion Server...[/bold yellow]")
        
        if websocket_manager:
            await websocket_manager.shutdown()
        if vision_processor:
            await vision_processor.cleanup()
        if llm_processor:
            await llm_processor.cleanup()
        if model_manager:
            await model_manager.cleanup()
            
        console.print("[bold green]✅ Shutdown completed successfully![/bold green]")
        logger.info("Server shutdown completed")

# Initialize FastAPI app
app = FastAPI(
    title="Orion - Computer Vision Server (MLX)",
    description="Real-time computer vision processing with Apple MLX",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Check service status
        services_status = {
            "model_manager": model_manager.is_healthy() if model_manager else False,
            "vision_processor": vision_processor.is_healthy() if vision_processor else False,
            "llm_processor": llm_processor.is_healthy() if llm_processor else False,
            "websocket_manager": websocket_manager.is_healthy() if websocket_manager else False,
            "context_memory": context_memory.is_healthy() if context_memory else False
        }
        
        all_healthy = all(services_status.values())
        
        return HealthCheck(
            status="healthy" if all_healthy else "degraded",
            timestamp=asyncio.get_event_loop().time(),
            services=services_status,
            version="1.0.0",
            error=None if all_healthy else "Some services are degraded"
        )
        
    except Exception as e:
        error_msg = f"Health check failed: {str(e)}"
        logger.error(error_msg)
        return HealthCheck(
            status="unhealthy",
            timestamp=asyncio.get_event_loop().time(),
            services={},
            version="1.0.0",
            error=error_msg
        )

@app.websocket("/ios")
async def ios_websocket(websocket: WebSocket):
    """WebSocket endpoint for iOS app connections."""
    if not websocket_manager or not check_services():
        await websocket.close(code=1013, reason="Server not ready")
        return
        
    client_id = f"ios_{id(websocket)}"
    
    try:
        await websocket_manager.add_ios_client(websocket, client_id)
        
        # Send a connection acknowledgment to the iOS client
        try:
            await websocket.send_json({"type": "connection_ack", "status": "connected", "client_id": client_id})
            logger.info(f"Sent connection_ack to iOS client {client_id}")
        except Exception as e:
            logger.error(f"Failed to send connection_ack to {client_id}: {e}")
            # Optionally, remove client if ack fails, or let the main loop handle disconnect
            if websocket_manager:
                await websocket_manager.remove_ios_client(client_id)
            return # Exit if we can't even send an ack

        while True:
            # Receive frame data from iOS
            data = await websocket.receive_text()
            
            # Process the frame
            await process_frame(client_id, data)
            
    except WebSocketDisconnect:
        logger.info(f"iOS client {client_id} disconnected")
    except Exception as e:
        logger.error(f"iOS WebSocket error for {client_id}: {e}")
    finally:
        if websocket_manager:
            await websocket_manager.remove_ios_client(client_id)

@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """WebSocket endpoint for dashboard web client connections."""
    if not websocket_manager or not check_services():
        await websocket.close(code=1013, reason="Server not ready")
        return

    client_id = f"dashboard_{id(websocket)}"
    try:
        await websocket_manager.add_dashboard_client(websocket, client_id)
        
        # Send a connection acknowledgment to the dashboard client
        try:
            await websocket.send_json({"type": "connection_ack", "status": "connected", "client_id": client_id})
            logger.info(f"Sent connection_ack to dashboard client {client_id}")
        except Exception as e:
            logger.error(f"Failed to send connection_ack to dashboard {client_id}: {e}")
            if websocket_manager:
                await websocket_manager.remove_dashboard_client(client_id)
            return

        # Keep the connection alive, listen for potential messages (e.g., settings changes from dashboard)
        # For now, it's mostly a one-way street (server to dashboard)
        while True:
            try:
                # Dashboards might not send data, or might send control messages in future
                # Set a timeout to periodically check connection or allow server to send updates
                # For now, just keep it open. If dashboard sends data, it would be received here.
                # data = await websocket.receive_text()
                # logger.debug(f"Received from dashboard {client_id}: {data}")
                await asyncio.sleep(0.01) # Keep loop running, prevent tight loop if no receive_text
                # This loop is mainly to keep the connection open from the server side.
                # Actual data is broadcast from process_frame.
            except WebSocketDisconnect:
                logger.info(f"Dashboard client {client_id} disconnected (explicitly by client or timeout).")
                break # Exit loop on disconnect
            except asyncio.CancelledError:
                logger.info(f"Dashboard client {client_id} connection task cancelled.")
                break
            except Exception as e:
                # Handle other errors, e.g. if client sends unexpected data type
                logger.error(f"Dashboard WebSocket error for {client_id}: {e}")
                # Depending on error, might break or continue
                break


    except WebSocketDisconnect: # This handles cases where accept() fails or initial handshake issues
        logger.info(f"Dashboard client {client_id} disconnected (before or during main loop).")
    except Exception as e:
        logger.error(f"Dashboard WebSocket error for {client_id} (outer): {e}")
    finally:
        if websocket_manager:
            await websocket_manager.remove_dashboard_client(client_id)


async def process_frame(client_id: str, data: str):
    """Process incoming frame from iOS app."""
    if not check_services():
        if websocket_manager:
            await websocket_manager.send_to_ios_client(client_id, {
                "type": "error",
                "message": "Server services not ready"
            })
        return
        
    try:
        # Parse detection frame
        frame = DetectionFrame.model_validate_json(data)
        logger.debug(f"Received frame {frame.frame_id} from {client_id}")
        
        assert context_memory is not None
        assert vision_processor is not None
        assert llm_processor is not None
        assert websocket_manager is not None
        
        # Store in context memory
        context_memory.add_frame(frame)
        
        # Process with vision model
        vision_analysis = await vision_processor.analyze_frame(frame)
        
        # Get context for LLM
        context = context_memory.get_recent_context(frame.frame_id)
        
        # Process with LLM
        llm_result = await llm_processor.analyze_scene(
            frame,
            vision_analysis,
            context
        )
        
        # Create response
        response = ServerResponse(
            frame_id=frame.frame_id,
            analysis=AnalysisResult(
                scene_description=llm_result.get("scene_description", "No description available"),
                contextual_insights=llm_result.get("contextual_insights", []),
                enhanced_detections=llm_result.get("enhanced_detections", []),
                confidence=llm_result.get("confidence", 0.0)
            ),
            timestamp=asyncio.get_event_loop().time(),
            error=None
        )
        
        # Send response back to iOS
        await websocket_manager.send_to_ios_client(client_id, response.model_dump())
        
        # Prepare and broadcast data to dashboards
        dashboard_message = {
            "type": "live_update",
            "timestamp": asyncio.get_event_loop().time(),
            "frame_id": frame.frame_id,
            "ios_frame_summary": { # Sending only a summary to avoid too much data initially
                "frame_id": frame.frame_id,
                "timestamp": frame.timestamp,
                "device_id": frame.device_id,
                "detections_count": len(frame.detections),
                # Not sending full image_data to dashboard by default, can be added if needed
            },
            "vlm_analysis": vision_analysis, # Contains description, confidence, scene_features
            "llm_reasoning": llm_result,     # Contains scene_description, contextual_insights, enhanced_detections
            "final_ios_response_summary": { # Summary of what was sent to iOS
                "frame_id": response.frame_id,
                "scene_description": response.analysis.scene_description,
                "contextual_insights_count": len(response.analysis.contextual_insights),
                "enhanced_detections_count": len(response.analysis.enhanced_detections),
                "error": response.error
            }
            # Optionally add logs or other system stats here
        }
        await websocket_manager.broadcast_to_dashboards(dashboard_message)
        
        logger.debug(f"Processed frame {frame.frame_id} successfully and broadcast to dashboards")
        
    except Exception as e:
        error_msg = f"Error processing frame: {str(e)}"
        logger.error(f"Error processing frame from {client_id}: {e}")
        
        # Send error response
        if websocket_manager:
            await websocket_manager.send_to_ios_client(client_id, {
                "type": "error",
                "message": "Failed to process frame",
                "details": error_msg
            })

if __name__ == "__main__":
    # Setup logging
    setup_logger(settings.LOG_LEVEL)
    
    # Run server
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )