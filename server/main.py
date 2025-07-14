"""Orion Computer Vision Server using MLX."""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Optional, Tuple
import time

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from rich.console import Console

from config import settings
from models import (
    Detection, DetectionFrame, ServerResponse, AnalysisResult, SystemStatus, HealthCheck, PacketEvent,
    WebSocketMessage, FrameDataMessage, UserPromptMessage, PromptResponse, ConfigurationMessage
)
from services.websocket_manager import WebSocketManager
from services.llm_processor import LLMProcessor
from services.context_memory import ContextMemory
from services.model_manager import ModelManager
from services.vision_processor import VisionProcessor # Import VisionProcessor
from utils.logger import setup_logger, get_logger

# Setup rich console and logging
console = Console()
logger = get_logger(__name__)

# Global service instances initialized as None
websocket_manager: Optional[WebSocketManager] = None
llm_processor: Optional[LLMProcessor] = None
context_memory: Optional[ContextMemory] = None
model_manager: Optional[ModelManager] = None
vision_processor: Optional[VisionProcessor] = None # Add vision_processor
frame_queue: Optional[asyncio.Queue] = None # The new task queue

def check_services() -> bool:
    """Check if all required services are initialized."""
    return all([
        websocket_manager is not None,
        llm_processor is not None,
        context_memory is not None,
        model_manager is not None,
        vision_processor is not None, # Check vision_processor
        frame_queue is not None
    ])

async def frame_processor_worker():
    """Worker that processes frames from the queue."""
    logger.info("Frame processor worker started.")
    while True:
        try:
            client_id, frame = await frame_queue.get()
            
            # Notify dashboard that an item is being processed
            if websocket_manager and frame_queue:
                queue_contents = []
                for item in list(frame_queue._queue):
                    client_id_in_queue, frame_in_queue = item
                    queue_contents.append({
                        "frame_id": frame_in_queue.frame_id,
                        "timestamp": frame_in_queue.timestamp,
                        "device_id": frame_in_queue.device_id,
                        "status": "enqueued" # Indicate status in queue
                    })
                await websocket_manager.broadcast_event_to_dashboards(
                    "frame_processing_started",
                    {"queue_size": frame_queue.qsize(), "frame_id": frame.frame_id, "queue_contents": queue_contents}
                )
                
            await process_frame(client_id, frame)
            frame_queue.task_done()
        except asyncio.CancelledError:
            logger.info("Frame processor worker cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in frame processor worker: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    global websocket_manager, llm_processor, context_memory, model_manager, vision_processor, frame_queue
    
    console.print("[bold green]🚀 Starting Orion Server (MLX)...[/bold green]")
    
    try:
        # Initialize model manager first
        model_manager = ModelManager()
        await model_manager.initialize()
        
        # Initialize core services
        context_memory = ContextMemory()
        llm_processor = LLMProcessor(model_manager)
        vision_processor = VisionProcessor(model_manager) # Initialize vision_processor
        websocket_manager = WebSocketManager()
        frame_queue = asyncio.Queue()
        
        # Start the background worker
        worker_task = asyncio.create_task(frame_processor_worker())

        # Initialize processors
        await llm_processor.initialize()
        await vision_processor.initialize() # Initialize vision_processor
        
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
        
        # Stop the worker
        if 'worker_task' in locals() and not worker_task.done():
            worker_task.cancel()
            await asyncio.sleep(1) # Give it a moment to cancel

        if websocket_manager:
            await websocket_manager.shutdown()
        
        if llm_processor:
            await llm_processor.cleanup()
        if model_manager:
            await model_manager.cleanup()
        if vision_processor:
            await vision_processor.cleanup()
            
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
            "llm_processor": llm_processor.is_healthy() if llm_processor else False,
            "websocket_manager": websocket_manager.is_healthy() if websocket_manager else False,
            "context_memory": context_memory.is_healthy() if context_memory else False,
            "vision_processor": vision_processor.is_healthy() if vision_processor else False # Check vision_processor
        }
        
        all_healthy = all(services_status.values())
        
        return HealthCheck(
            status="healthy" if all_healthy else "degraded",
            timestamp=time.time(),
            services=services_status,
            version="1.0.0",
            error=None if all_healthy else "Some services are degraded"
        )
        
    except Exception as e:
        error_msg = f"Health check failed: {str(e)}"
        logger.error(error_msg)
        return HealthCheck(
            status="unhealthy",
            timestamp=time.time(),
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
            try:
                message_json = await websocket.receive_json()
                message_type = message_json.get("type")

                if message_type == "frame_data":
                    frame_data_message = FrameDataMessage.model_validate(message_json)
                    if settings.PROCESSING_MODE == "full":
                        # In full mode, process the frame directly and bypass the queue
                        await process_frame(client_id, frame_data_message)
                    else:
                        # In split mode, use the queue
                        await frame_queue.put((client_id, frame_data_message))
                        
                        # Notify dashboard about the new item in queue
                        if websocket_manager and frame_queue:
                            # Get current queue contents without removing them
                            queue_contents = []
                            for item in list(frame_queue._queue):
                                client_id_in_queue, frame_in_queue = item
                                queue_contents.append({
                                    "frame_id": frame_in_queue.frame_id,
                                    "timestamp": frame_in_queue.timestamp,
                                    "device_id": frame_in_queue.device_id,
                                    "status": "enqueued" # Indicate status in queue
                                })

                            await websocket_manager.broadcast_event_to_dashboards(
                                "frame_enqueued",
                                {"queue_size": frame_queue.qsize(), "frame_id": frame_data_message.frame_id, "queue_contents": queue_contents}
                            )
                elif message_type == "user_prompt":
                    user_prompt_message = UserPromptMessage.model_validate(message_json)
                    await process_user_prompt(client_id, user_prompt_message)
                elif message_type == "configuration":
                    config_message = ConfigurationMessage.model_validate(message_json)
                    settings.PROCESSING_MODE = config_message.processing_mode
                    logger.info(f"Server processing mode set to: {settings.PROCESSING_MODE}")
                    # Optionally send an acknowledgment back to the client
                    await websocket_manager.send_to_ios_client(client_id, {
                        "type": "configuration_ack",
                        "processing_mode": settings.PROCESSING_MODE
                    })
                elif message_type == "request_config":
                    # Respond to dashboard's request for config
                    await websocket.send_json({
                        "type": "server_config",
                        "processing_mode": settings.PROCESSING_MODE
                    })
                    logger.info(f"Sent server_config to dashboard client {client_id}")
                else:
                    logger.warning(f"Unknown message type received from {client_id}: {message_type}")
                    await websocket_manager.send_to_ios_client(client_id, {
                        "type": "error",
                        "message": "Unknown message type",
                        "details": f"Received type: {message_type}"
                    })
            except WebSocketDisconnect:
                logger.info(f"iOS client {client_id} disconnected")
                break
            except Exception as e:
                logger.error(f"Error receiving or processing message from {client_id}: {e}")
                await websocket_manager.send_to_ios_client(client_id, {
                    "type": "error",
                    "message": "Error processing message",
                    "details": str(e)
                })
                # Depending on the error, you might want to break or continue
                # For now, let's break to prevent a loop of errors
                break
            
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


async def process_frame(client_id: str, frame: FrameDataMessage):
    """Process incoming frame from iOS app."""
    if not check_services():
        if websocket_manager:
            await websocket_manager.send_to_ios_client(client_id, {
                "type": "error",
                "message": "Server services not ready"
            })
        return
        
    packet_events = [] # Initialize list to store packet events
    processing_start_time = time.time()

    try:
        logger.info(f"Received frame {frame.frame_id} from {client_id} (Device: {frame.device_id}, Timestamp: {frame.timestamp}). Image data present: {frame.image_data is not None}. Detections count: {len(frame.detections) if frame.detections else 0}")

        # Event: iOS Frame Received
        packet_events.append(PacketEvent(
            event_type="ios_frame_received",
            timestamp=time.time(),
            source="iOS Device",
            destination="Server",
            summary=f"Frame {frame.frame_id} received. Mode: {settings.PROCESSING_MODE}",
            payload={
                "frame_id": frame.frame_id,
                "device_id": frame.device_id,
                "image_data_present": frame.image_data is not None,
                "detections_count": len(frame.detections) if frame.detections else 0
            }
        ).model_dump())
        await websocket_manager.broadcast_event_to_dashboards("ios_frame_received", {"frame_id": frame.frame_id, "detections_count": len(frame.detections) if frame.detections else 0})

        assert context_memory is not None
        assert llm_processor is not None
        assert websocket_manager is not None
        assert vision_processor is not None # Assert vision_processor is not None

        # Process vision (YOLO + VLM) based on processing mode
        vision_analysis_start_time = time.time()
        vision_analysis = await vision_processor.analyze_frame(frame)
        
        # Ensure vision_analysis is not None or empty before proceeding
        if not vision_analysis or not isinstance(vision_analysis, dict):
            logger.error(f"Vision analysis failed or returned invalid data for frame {frame.frame_id}")
            if websocket_manager:
                await websocket_manager.send_to_ios_client(client_id, {
                    "type": "error",
                    "message": "Vision analysis failed",
                    "details": f"Frame {frame.frame_id}: No valid vision analysis data."
                })
            return # Stop processing this frame

        vision_analysis_duration = time.time() - vision_analysis_start_time

        if settings.PROCESSING_MODE == "full":
            packet_events.append(PacketEvent(
                event_type="yolo_analysis_complete",
                timestamp=time.time(),
                source="Server",
                destination="Server",
                summary=f"YOLO analysis complete for frame {frame.frame_id}. Detections: {len(vision_analysis.get("detections", []))}",
                payload={
                    "frame_id": frame.frame_id,
                    "detections_count": len(vision_analysis.get("detections", [])),
                    "duration": vision_analysis_duration # This is actually vision_analysis duration, not just YOLO
                }
            ).model_dump())

        packet_events.append(PacketEvent(
            event_type="vlm_analysis_complete",
            timestamp=time.time(),
            source="Server",
            destination="Server",
            summary=f"VLM analysis complete for frame {frame.frame_id}. Description: {vision_analysis.get("description", "N/A")[:50]}...",
            payload={
                "frame_id": frame.frame_id,
                "description": vision_analysis.get("description"),
                "confidence": vision_analysis.get("confidence"),
                "duration": vision_analysis_duration
            }
        ).model_dump())
        await websocket_manager.broadcast_event_to_dashboards("vlm_analysis_complete", {"frame_id": frame.frame_id, "vlm_description": vision_analysis.get("description", "N/A")})

        # Store in context memory
        # Note: context_memory.add_frame expects DetectionFrame, not FrameDataMessage directly
        # We need to construct a DetectionFrame from the processed data or the original if split mode
        processed_frame = DetectionFrame(
            frame_id=frame.frame_id,
            timestamp=frame.timestamp,
            image_data=frame.image_data, # Keep original image data if present
            detections=[Detection(**d) for d in vision_analysis.get("detections", [])], # Use processed detections
            device_id=frame.device_id,
            vlm_description=vision_analysis.get("description"),
            vlm_confidence=vision_analysis.get("confidence")
        )
        context_memory.add_frame(processed_frame)

        # Get context for LLM
        context = context_memory.get_recent_context(frame.frame_id)

        # Process with LLM
        llm_reasoning_start_time = time.time()
        llm_result = await llm_processor.analyze_scene(
            processed_frame, # Pass the processed frame
            vision_analysis,
            context
        )
        logger.info(f"LLM analysis result for frame {frame.frame_id}: {llm_result.get('scene_description', 'N/A')}")
        llm_reasoning_duration = time.time() - llm_reasoning_start_time

        packet_events.append(PacketEvent(
            event_type="llm_reasoning_complete",
            timestamp=time.time(),
            source="Server",
            destination="Server",
            summary=f"LLM reasoning complete for frame {frame.frame_id}. Scene: {llm_result.get("scene_description", "N/A")[:50]}...",
            payload={
                "frame_id": frame.frame_id,
                "scene_description": llm_result.get("scene_description"),
                "duration": llm_reasoning_duration
            }
        ).model_dump())
        await websocket_manager.broadcast_event_to_dashboards("llm_reasoning_complete", {"frame_id": frame.frame_id, "scene_description": llm_result.get("scene_description", "N/A")})

        # Create response
        response = ServerResponse(
            frame_id=frame.frame_id,
            analysis=AnalysisResult(
                scene_description=llm_result.get("scene_description", "No description available"),
                contextual_insights=llm_result.get("contextual_insights", []),
                enhanced_detections=llm_result.get("enhanced_detections", []),
                confidence=llm_result.get("confidence", 0.0)
            ),
            timestamp=time.time(),
            error=None
        )

        # Send response back to iOS
        await websocket_manager.send_to_ios_client(client_id, response.model_dump())

        # Send acknowledgment to iOS client to request next frame
        packet_events.append(PacketEvent(
            event_type="response_sent_to_ios",
            timestamp=time.time(),
            source="Server",
            destination="iOS Device",
            summary=f"Response sent to iOS for frame {frame.frame_id}. Total processing time: {(time.time() - processing_start_time):.2f}s",
            payload={
                "frame_id": response.frame_id,
                "scene_description": response.analysis.scene_description,
                "total_processing_time": (time.time() - processing_start_time)
            }
        ).model_dump())
        await websocket_manager.send_to_ios_client(client_id, {"type": "frame_processed", "frame_id": frame.frame_id})
        
        # Create a copy of packet_events before broadcasting to avoid "dictionary changed size during iteration"
        # if the list is modified elsewhere or during asynchronous processing.
        packet_events_copy = list(packet_events)

        await websocket_manager.broadcast_event_to_dashboards("response_sent_to_ios", {
            "frame_id": response.frame_id,
            "scene_description": response.analysis.scene_description,
            "llm_reasoning": llm_result, # Include LLM reasoning
            "vlm_analysis": vision_analysis, # Include VLM analysis (contains detections)
            "packet_events": packet_events_copy, # Use the copy
            "final_ios_response_summary": {"error": response.error},
            "server_status": {
                "processing_mode": settings.PROCESSING_MODE,
                "model_health": model_manager.get_model_health(),
                "queue_size": frame_queue.qsize(),
                "llm_processing_stats": llm_processor.get_stats(),
                "vision_processing_stats": vision_processor.get_stats()
            },
            "context": context,
            "image_data": frame.image_data, # Include image data for dashboard
            "detections": frame.detections # Include detections for dashboard
        })

        # Broadcast a separate event for successful frame processing, including updated queue size
        if websocket_manager and frame_queue:
            queue_contents = []
            for item in list(frame_queue._queue):
                client_id_in_queue, frame_in_queue = item
                queue_contents.append({
                    "frame_id": frame_in_queue.frame_id,
                    "timestamp": frame_in_queue.timestamp,
                    "device_id": frame_in_queue.device_id,
                    "status": "enqueued" # Indicate status in queue
                })
            await websocket_manager.broadcast_event_to_dashboards(
                "frame_processed_successfully",
                {"queue_size": frame_queue.qsize(), "frame_id": frame.frame_id, "queue_contents": queue_contents}
            )

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

async def process_user_prompt(client_id: str, prompt_message: UserPromptMessage):
    """Process incoming user prompt from iOS app."""
    if not check_services():
        if websocket_manager:
            await websocket_manager.send_to_ios_client(client_id, {
                "type": "error",
                "message": "Server not ready to process prompts"
            })
        return

    logger.info(f"Received user prompt {prompt_message.prompt_id} from {client_id}: {prompt_message.question}")

    try:
        assert llm_processor is not None
        assert context_memory is not None
        assert websocket_manager is not None

        # Get relevant context for the question
        # For now, let's get the most recent context. This can be enhanced later.
        context = context_memory.get_recent_context(prompt_message.prompt_id, limit=10) # Get more context for prompts

        # Process the question with LLM
        answer = await llm_processor.answer_question(prompt_message.question, context)

        response = PromptResponse(
            response_id=prompt_message.prompt_id,
            question=prompt_message.question,
            answer=answer,
            timestamp=time.time(),
            error=None
        )
        
        await websocket_manager.send_to_ios_client(client_id, response.model_dump())
        logger.info(f"Sent response for prompt {prompt_message.prompt_id} to {client_id}")

        # Broadcast to dashboards as well
        dashboard_message = {
            "type": "user_prompt_response",
            "timestamp": asyncio.get_event_loop().time(),
            "prompt_id": prompt_message.prompt_id,
            "question": prompt_message.question,
            "answer": answer,
            "source_client_id": client_id
        }
        await websocket_manager.broadcast_to_dashboards(dashboard_message)

    except Exception as e:
        error_msg = f"Error processing user prompt: {str(e)}"
        logger.error(f"Error processing user prompt from {client_id}: {e}")
        if websocket_manager:
            await websocket_manager.send_to_ios_client(client_id, {
                "type": "error",
                "message": "Failed to process prompt",
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