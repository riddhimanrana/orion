"""Data models for the Orion Live server."""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, field_validator

class Detection(BaseModel):
    """Object detection result."""
    label: str
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2]
    track_id: Optional[int] = None
    
    @field_validator('bbox')
    @classmethod
    def validate_bbox(cls, v: List[float]) -> List[float]:
        """Validate bounding box coordinates."""
        if len(v) != 4:
            raise ValueError("bbox must have exactly 4 coordinates")
        if not all(0.0 <= x <= 1.0 for x in v):
            raise ValueError("bbox coordinates must be between 0 and 1")
        return v

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