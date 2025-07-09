"""Data models for the Orion server."""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, field_validator

class Detection(BaseModel):
    """Object detection result."""
    label: str
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2]
    track_id: Optional[int] = None
    contextual_label: Optional[str] = None # e.g., "person (center)"
    
    @field_validator('bbox')
    @classmethod
    def validate_bbox(cls, v: List[float]) -> List[float]:
        """Validate and clamp bounding box coordinates to be between 0 and 1."""
        if len(v) != 4:
            raise ValueError("bbox must have exactly 4 coordinates")
        
        # Clamp values to be within [0, 1]
        clamped_v = [max(0.0, min(1.0, coord)) for coord in v]
        
        return clamped_v

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Validate confidence score."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        return v

class DetectionFrame(BaseModel):
    """Frame data with detections."""
    frame_id: str
    timestamp: float
    image_data: Optional[str] = None  # Base64 encoded image
    detections: List[Detection] = []
    device_id: Optional[str] = None # Added to match iOS FrameData
    vlm_description: Optional[str] = None # On-device VLM description
    vlm_confidence: Optional[float] = None # On-device VLM confidence

class PromptResponse(BaseModel):
    """Response to a user prompt."""
    response_id: str
    question: str
    answer: str
    timestamp: float
    error: Optional[str] = None

class WebSocketMessage(BaseModel):
    """Base model for all WebSocket messages."""
    type: str

class FrameDataMessage(WebSocketMessage):
    """WebSocket message containing frame data."""
    type: str = "frame_data"
    frame_id: str
    timestamp: float
    image_data: Optional[str] = None
    detections: Optional[List[Detection]] = None
    device_id: Optional[str] = None
    vlm_description: Optional[str] = None # On-device VLM description (optional, for split mode)
    vlm_confidence: Optional[float] = None # On-device VLM confidence (optional, for split mode)

class UserPromptMessage(WebSocketMessage):
    """WebSocket message containing a user prompt/question."""
    type: str = "user_prompt"
    prompt_id: str
    question: str
    timestamp: float
    device_id: Optional[str] = None

class AnalysisResult(BaseModel):
    """Enhanced analysis result."""
    scene_description: str
    contextual_insights: List[str] = []
    enhanced_detections: List[Dict[str, Any]] = []
    confidence: float
    
    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Validate confidence score."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        return v

class ServerResponse(BaseModel):
    """Server response message."""
    frame_id: str
    analysis: AnalysisResult
    timestamp: float
    error: Optional[str] = None

class SystemStatus(BaseModel):
    """System status information."""
    total_frames: int = 0
    total_detections: int = 0
    average_confidence: float = 0.0
    active_connections: int = 0
    model_status: Dict[str, bool] = {}
    memory_usage: Dict[str, float] = {}
    
    @field_validator('average_confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Validate confidence score."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("average_confidence must be between 0 and 1")
        return v

class HealthCheck(BaseModel):
    """Health check response."""
    status: str  # "healthy", "degraded", or "unhealthy"
    timestamp: float
    services: Dict[str, bool]  # Service health status
    version: str
    error: Optional[str] = None
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate health status."""
        valid_statuses = {"healthy", "degraded", "unhealthy"}
        if v not in valid_statuses:
            raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")
        return v

class PacketEvent(BaseModel):
    """Represents a single event or 'packet' in the data flow."""
    event_type: str  # e.g., "ios_frame_received", "vlm_analysis_complete", "llm_reasoning_complete", "response_sent"
    timestamp: float
    source: str      # e.g., "iOS Device", "Server"
    destination: str # e.g., "Server", "Dashboard", "iOS Device"
    summary: str     # A brief description of the event
    payload: Dict[str, Any] # A summary of the data being passed, or full data if small

class ConfigurationMessage(WebSocketMessage):
    """WebSocket message containing configuration settings."""
    type: str = "configuration"
    processing_mode: str

class ConfigurationMessage(WebSocketMessage):
    """WebSocket message containing configuration settings."""
    type: str = "configuration"
    processing_mode: str