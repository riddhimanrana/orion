"""Memory management for scene understanding context."""
from typing import Dict, List, Optional, Any
from collections import deque
import time
import json

from models import DetectionFrame
from utils.logger import get_logger

logger = get_logger(__name__)

class ContextMemory:
    """Manages temporal context and scene understanding history."""

    def __init__(self, max_frames: int = 300000):
        """
        Initialize context memory.

        Args:
            max_frames: Maximum frames to keep in memory (default 1s at 30fps)
        """
        self.frames = deque(maxlen=max_frames)
        self.scene_analysis: Dict[str, Dict[str, Any]] = {}
        self.scene_understanding: Dict[str, Any] = {
            "ongoing_activities": [],
            "tracked_objects": {},
            "scene_state": {}
        }
        self.stats = {
            "frames_stored": 0,
            "analyses_stored": 0,
            "last_cleanup": time.time()
        }
        logger.info(f"ContextMemory initialized with {max_frames} frame capacity")

    def add_frame(self, frame: DetectionFrame) -> None:
        """
        Add frame to memory.

        Args:
            frame: Frame to store
        """
        self.frames.append(frame)
        self.stats["frames_stored"] += 1

        # Track objects based on detection track_ids
        self._update_object_tracking(frame)

    def add_analysis(
        self,
        frame_id: str,
        analysis: Dict[str, Any]
    ) -> None:
        """
        Store scene analysis results.

        Args:
            frame_id: Frame identifier
            analysis: Analysis results
        """
        self.scene_analysis[frame_id] = {
            "timestamp": time.time(),
            "analysis": analysis
        }
        self.stats["analyses_stored"] += 1

        # Update scene understanding
        self._update_scene_understanding(analysis)

    def get_recent_context(
        self,
        current_frame_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get recent context for a frame.

        Args:
            current_frame_id: Current frame ID
            limit: Maximum context entries

        Returns:
            List of recent context entries
        """
        context = []
        seen_frames = set()

        # Add recent frames and their analysis
        for frame in reversed(self.frames):
            if len(context) >= limit:
                break

            if frame.frame_id == current_frame_id:
                continue

            if frame.frame_id in seen_frames:
                continue

            # Get analysis for this frame
            analysis = self.scene_analysis.get(
                frame.frame_id,
                {"analysis": {}}
            )["analysis"]

            context_entry = {
                "frame_id": frame.frame_id,
                "timestamp": frame.timestamp,
                "detections": [d.model_dump() for d in frame.detections],
                "vlm_description": frame.vlm_description, # Add vlm_description
                "analysis": analysis
            }

            # Add ongoing activities and tracked objects
            context_entry.update({
                "ongoing_activities": self.scene_understanding["ongoing_activities"],
                "tracked_objects": {
                    k: v for k, v in self.scene_understanding["tracked_objects"].items()
                    if v["last_seen"] >= frame.timestamp - 5.0  # Objects seen in last 5s
                }
            })

            context.append(context_entry)
            seen_frames.add(frame.frame_id)

        return list(reversed(context))  # Return in chronological order

    def _update_object_tracking(self, frame: DetectionFrame) -> None:
        """Update tracked objects from frame detections."""
        current_objects = set()

        for det in frame.detections:
            if det.track_id is not None:
                obj_id = f"{det.label}_{det.track_id}"
                current_objects.add(obj_id)

                # Update or create tracked object
                if obj_id not in self.scene_understanding["tracked_objects"]:
                    self.scene_understanding["tracked_objects"][obj_id] = {
                        "label": det.label,
                        "track_id": det.track_id,
                        "first_seen": frame.timestamp,
                        "last_seen": frame.timestamp,
                        "detection_count": 1,
                        "average_confidence": det.confidence,
                        "trajectory": [det.bbox]
                    }
                else:
                    obj = self.scene_understanding["tracked_objects"][obj_id]
                    obj["last_seen"] = frame.timestamp
                    obj["detection_count"] += 1
                    obj["average_confidence"] = (
                        (obj["average_confidence"] * (obj["detection_count"] - 1) +
                        det.confidence) / obj["detection_count"]
                    )
                    obj["trajectory"].append(det.bbox)

        # Clean up old objects
        current_time = frame.timestamp
        self.scene_understanding["tracked_objects"] = {
            k: v for k, v in self.scene_understanding["tracked_objects"].items()
            if v["last_seen"] >= current_time - 5.0 or k in current_objects
        }

    def _update_scene_understanding(self, analysis: Dict[str, Any]) -> None:
        """Update ongoing scene understanding."""
        # Update activities from new analysis
        if "contextual_insights" in analysis:
            # Add new activities
            current_activities = set(self.scene_understanding["ongoing_activities"])
            new_activities = set(analysis["contextual_insights"])

            # Keep recent activities
            self.scene_understanding["ongoing_activities"] = list(
                current_activities | new_activities
            )[-5:]  # Keep last 5 activities

        # Update scene state
        if "scene_description" in analysis:
            self.scene_understanding["scene_state"] = {
                "last_description": analysis["scene_description"],
                "confidence": analysis.get("confidence", 0.0),
                "timestamp": time.time()
            }

    def cleanup_old_entries(self) -> None:
        """Remove old entries to free memory."""
        current_time = time.time()
        if current_time - self.stats["last_cleanup"] < 300:  # 5 minutes
            return

        # Remove old analysis results
        frame_ids = {frame.frame_id for frame in self.frames}
        self.scene_analysis = {
            k: v for k, v in self.scene_analysis.items()
            if k in frame_ids
        }

        # Update stats
        self.stats["last_cleanup"] = current_time
        logger.debug("Cleaned up old context entries")

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "frames_in_memory": len(self.frames),
            "total_frames_seen": self.stats["frames_stored"],
            "analyses_in_memory": len(self.scene_analysis),
            "total_analyses": self.stats["analyses_stored"],
            "tracked_objects": len(self.scene_understanding["tracked_objects"]),
            "ongoing_activities": len(self.scene_understanding["ongoing_activities"])
        }

    def is_healthy(self) -> bool:
        """Check if memory system is healthy."""
        max_memory_usage = len(self.frames) + len(self.scene_analysis)
        return max_memory_usage < 1000  # Arbitrary limit

    def clear(self) -> None:
        """Clear all stored context."""
        self.frames.clear()
        self.scene_analysis.clear()
        self.scene_understanding = {
            "ongoing_activities": [],
            "tracked_objects": {},
            "scene_state": {}
        }
        self.stats = {
            "frames_stored": 0,
            "analyses_stored": 0,
            "last_cleanup": time.time()
        }
        logger.info("Context memory cleared")
