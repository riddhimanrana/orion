from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class SGNode:
    """Represents an object in the scene graph."""
    id: str  # Unique identifier (e.g., memory_id or track_id)
    label: str  # Object class (e.g., "person", "cup")
    bbox: Optional[List[float]] = None  # [x1, y1, x2, y2]
    confidence: float = 1.0
    attributes: List[str] = field(default_factory=list)  # e.g., ["red", "sitting"]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SGEdge:
    """Represents a relationship between two objects."""
    subject_id: str
    predicate: str  # e.g., "holding", "on", "next_to"
    object_id: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SceneGraph:
    """Represents the scene graph for a single frame or a temporal window."""
    frame_index: int
    timestamp: float
    nodes: List[SGNode] = field(default_factory=list)
    edges: List[SGEdge] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "timestamp": self.timestamp,
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "bbox": n.bbox,
                    "confidence": n.confidence,
                    "attributes": n.attributes,
                    "metadata": n.metadata
                } for n in self.nodes
            ],
            "edges": [
                {
                    "subject_id": e.subject_id,
                    "predicate": e.predicate,
                    "object_id": e.object_id,
                    "confidence": e.confidence,
                    "metadata": e.metadata
                } for e in self.edges
            ]
        }

@dataclass
class VideoSceneGraph:
    """Collection of scene graphs for a video."""
    video_id: str
    graphs: List[SceneGraph] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_id": self.video_id,
            "metadata": self.metadata,
            "graphs": [g.to_dict() for g in self.graphs]
        }
