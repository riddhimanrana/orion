"""Memory management for scene understanding context."""
from typing import Dict, List, Optional, Any
from collections import deque
import time
import json
import math

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
        self.max_frames = max_frames
        self.scene_analysis: Dict[str, Dict[str, Any]] = {}
        self.scene_understanding: Dict[str, Any] = {
            "ongoing_activities": [],
            "tracked_objects": {},
            "scene_state": {}
        }
        self.persistent_objects: Dict[str, Dict[str, Any]] = {}
        self.max_persistent_trajectory = 600
        self.max_spatial_history = 300
        self.max_cis_history = 300
        self.cis_threshold = 0.50
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

                # Update or create tracked object in active list
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

                # Update or create in persistent memory (permanence)
                if obj_id not in self.persistent_objects:
                    self.persistent_objects[obj_id] = {
                        "label": det.label,
                        "track_id": det.track_id,
                        "first_seen": frame.timestamp,
                        "last_seen": frame.timestamp,
                        "detection_count": 1,
                        "average_confidence": det.confidence,
                        "trajectory": [det.bbox],
                        "status": "present",
                        "last_near_objects": [],
                        "spatial_history": [],
                        "cis_history": []
                    }
                else:
                    p_obj = self.persistent_objects[obj_id]
                    p_obj["last_seen"] = frame.timestamp
                    p_obj["detection_count"] += 1
                    p_obj["average_confidence"] = (
                        (p_obj["average_confidence"] * (p_obj["detection_count"] - 1) +
                        det.confidence) / p_obj["detection_count"]
                    )
                    p_obj["trajectory"].append(det.bbox)
                    if len(p_obj["trajectory"]) > self.max_persistent_trajectory:
                        p_obj["trajectory"] = p_obj["trajectory"][-self.max_persistent_trajectory:]
                    p_obj["status"] = "present"

        # Update status for objects not currently seen
        current_time = frame.timestamp
        for obj_id, obj in self.persistent_objects.items():
            if obj_id not in current_objects and current_time - obj["last_seen"] > 2.0:
                obj["status"] = "absent"

        # Compute spatial proximity and lightweight live CIS relationships.
        for obj_a_id in current_objects:
            if obj_a_id not in self.persistent_objects:
                continue
            obj_a = self.persistent_objects[obj_a_id]
            bbox_a = obj_a["trajectory"][-1]
            centroid_a = ((bbox_a[0] + bbox_a[2]) / 2.0, (bbox_a[1] + bbox_a[3]) / 2.0)

            near_list = []
            cis_edges = []
            for obj_b_id in current_objects:
                if obj_b_id == obj_a_id:
                    continue
                if obj_b_id not in self.persistent_objects:
                    continue
                obj_b = self.persistent_objects[obj_b_id]
                bbox_b = obj_b["trajectory"][-1]
                centroid_b = ((bbox_b[0] + bbox_b[2]) / 2.0, (bbox_b[1] + bbox_b[3]) / 2.0)

                dist = math.hypot(centroid_a[0] - centroid_b[0], centroid_a[1] - centroid_b[1])
                # In normalized coordinates (0 to 1), a threshold of 0.25 represents proximity
                if dist < 0.25:
                    near_list.append(obj_b["label"])

                cis = self._compute_live_cis(obj_a, obj_b, frame.timestamp, dist)
                if cis["score"] >= self.cis_threshold:
                    cis_edges.append({
                        "target": obj_b["label"],
                        "target_track_id": obj_b.get("track_id"),
                        **cis
                    })

            if near_list:
                labels = sorted(set(near_list))
                obj_a["last_near_objects"] = labels
                obj_a.setdefault("spatial_history", []).append({
                    "timestamp": frame.timestamp,
                    "relation": "NEAR",
                    "objects": labels
                })
                if len(obj_a["spatial_history"]) > self.max_spatial_history:
                    obj_a["spatial_history"] = obj_a["spatial_history"][-self.max_spatial_history:]

            if cis_edges:
                obj_a.setdefault("cis_history", []).append({
                    "timestamp": frame.timestamp,
                    "edges": cis_edges
                })
                if len(obj_a["cis_history"]) > self.max_cis_history:
                    obj_a["cis_history"] = obj_a["cis_history"][-self.max_cis_history:]

        # Clean up old active objects (5 second TTL for UI dashboard list)
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
            "persistent_objects": len(self.persistent_objects),
            "ongoing_activities": len(self.scene_understanding["ongoing_activities"])
        }

    def _compute_live_cis(
        self,
        obj_a: Dict[str, Any],
        obj_b: Dict[str, Any],
        timestamp: float,
        dist: float
    ) -> Dict[str, Any]:
        """Deterministic live CIS proxy: temporal + spatial/depth + motion + semantic compatibility."""
        delta_t = abs(float(obj_a.get("last_seen", timestamp)) - float(obj_b.get("last_seen", timestamp)))
        temporal = math.exp(-delta_t / 1.0)
        spatial = max(0.0, 1.0 - min(dist / 0.25, 1.0))
        motion = self._motion_alignment(obj_a.get("trajectory", []), obj_b.get("trajectory", []))
        semantic = 1.0 if obj_a.get("label") == obj_b.get("label") else 0.25
        score = (0.30 * temporal) + (0.35 * spatial) + (0.20 * motion) + (0.15 * semantic)
        return {
            "score": round(score, 4),
            "components": {
                "temporal": round(temporal, 4),
                "spatial": round(spatial, 4),
                "motion": round(motion, 4),
                "semantic": round(semantic, 4)
            }
        }

    def _motion_alignment(self, traj_a: List[Any], traj_b: List[Any]) -> float:
        if len(traj_a) < 2 or len(traj_b) < 2:
            return 0.0

        def velocity(traj: List[Any]) -> tuple[float, float]:
            prev = traj[-2]
            curr = traj[-1]
            prev_center = ((prev[0] + prev[2]) / 2.0, (prev[1] + prev[3]) / 2.0)
            curr_center = ((curr[0] + curr[2]) / 2.0, (curr[1] + curr[3]) / 2.0)
            return (curr_center[0] - prev_center[0], curr_center[1] - prev_center[1])

        va = velocity(traj_a)
        vb = velocity(traj_b)
        norm_a = math.hypot(*va)
        norm_b = math.hypot(*vb)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return max(0.0, min(1.0, ((va[0] * vb[0]) + (va[1] * vb[1])) / (norm_a * norm_b)))

    def is_healthy(self) -> bool:
        """Check if memory system is healthy."""
        return len(self.frames) <= self.max_frames and len(self.scene_analysis) <= self.stats["frames_stored"]

    def clear(self) -> None:
        """Clear all stored context."""
        self.frames.clear()
        self.scene_analysis.clear()
        self.scene_understanding = {
            "ongoing_activities": [],
            "tracked_objects": {},
            "scene_state": {}
        }
        self.persistent_objects.clear()
        self.stats = {
            "frames_stored": 0,
            "analyses_stored": 0,
            "last_cleanup": time.time()
        }
        logger.info("Context memory cleared")
