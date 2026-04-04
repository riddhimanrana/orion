"""Core datatypes for scene-graph evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


@dataclass(frozen=True)
class BBox:
    """Axis-aligned bounding box in xyxy format."""

    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class ObjectInstance:
    """Object instance for a single frame."""

    object_id: int
    label: str
    bbox: Optional[BBox] = None


@dataclass(frozen=True)
class RelationInstance:
    """Directed relation between two objects in a frame."""

    subject_id: int
    predicate: str
    object_id: int
    score: float = 1.0


@dataclass
class FrameGraph:
    """Per-frame graph representation."""

    frame_index: int
    objects: List[ObjectInstance] = field(default_factory=list)
    relations: List[RelationInstance] = field(default_factory=list)


@dataclass
class VideoGraph:
    """Video-level container for a sequence of frame graphs."""

    video_id: str
    frames: Dict[int, FrameGraph] = field(default_factory=dict)
    metadata: Dict[str, object] = field(default_factory=dict)

    def ordered_frames(self) -> Sequence[FrameGraph]:
        return [self.frames[key] for key in sorted(self.frames.keys())]
