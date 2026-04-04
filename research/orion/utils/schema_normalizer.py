"""
Schema Normalization for Tracks.jsonl
=====================================

Canonical normalizer for Orion's track records. Handles schema drift between
different writers (run_showcase.py and tracker serialization).

Key issues identified in deep research:
1. `frame_id` vs `frame_number` vs `frame_idx` (all same concept)
2. `bbox` vs `bbox_2d` vs `bounding_box` (different formats)
3. `timestamp` units vary (seconds vs milliseconds)
4. `category` vs `class_name` vs `object_class` (label field)

This normalizer:
1. Reads any variant and produces canonical output
2. Adds v2 fields: `label_hypotheses_topk`, `verification_status`
3. Provides backward-compatible `to_dict()` for legacy consumers

Usage:
    record = normalize_track_record(raw_json)
    # Now safely access: record["frame_idx"], record["bbox_xyxy"], etc.

Author: Orion Research Team
Date: January 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema Version Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "2.0"

# Canonical field names (v2)
CANONICAL_FIELDS = {
    # Temporal
    "frame_idx": int,       # 0-indexed frame number
    "timestamp_s": float,   # Timestamp in seconds (float)
    
    # Spatial
    "bbox_xyxy": list,      # [x1, y1, x2, y2] in pixels
    "centroid": list,       # [cx, cy] center point
    
    # Identity
    "track_id": int,        # Track ID from tracker
    "label": str,           # Primary/canonical label
    "confidence": float,    # Detection confidence (0-1)
    
    # Open-vocab extensions (v2)
    "label_hypotheses_topk": list,  # List of {label, score, source, rank}
    "verification_status": str,      # 'verified', 'unverified', 'rejected', 'pending'
    "verification_source": str,      # 'vlm', 'temporal', 'manual', None
    
    # Provenance
    "detector_source": str,     # 'yolo', 'yoloworld', 'gdino', 'owlvit', etc.
    "embedding_id": str,        # Reference to embedding in memory store
    
    # Tracking metadata
    "track_age": int,           # Number of frames this track has existed
    "track_hits": int,          # Number of detections for this track
    "time_since_update": int,   # Frames since last detection match
    
    # Frame context
    "frame_width": int,
    "frame_height": int,
}


# Field aliases for backward compatibility
FIELD_ALIASES = {
    # Frame ID variants
    "frame_id": "frame_idx",
    "frame_number": "frame_idx",
    
    # Timestamp variants
    "timestamp": "timestamp_s",
    "timestamp_ms": "timestamp_s",  # Will be converted
    
    # Bbox variants
    "bbox": "bbox_xyxy",
    "bbox_2d": "bbox_xyxy",
    "bounding_box": "bbox_xyxy",
    
    # Label variants
    "category": "label",
    "class_name": "label",
    "object_class": "label",
    
    # Track metadata variants
    "id": "track_id",
    "age": "track_age",
    "hits": "track_hits",
    
    # V2 hypothesis field aliases
    "candidate_labels": "label_hypotheses_topk",
    "hypotheses": "label_hypotheses_topk",
}


def normalize_track_record(
    record: Dict[str, Any],
    frame_rate: Optional[float] = None,
    strict: bool = False,
) -> Dict[str, Any]:
    """
    Normalize a track record to canonical v2 schema.
    
    Args:
        record: Raw track record from any writer
        frame_rate: Video frame rate for timestamp inference
        strict: If True, raise on missing required fields
        
    Returns:
        Canonical v2 record with all fields normalized
        
    Raises:
        ValueError: If strict=True and required fields missing
    """
    result = {
        "_schema_version": SCHEMA_VERSION,
        "_original_keys": list(record.keys()),
    }
    
    # === Frame ID normalization ===
    frame_idx = _get_aliased(record, "frame_idx")
    if frame_idx is not None:
        result["frame_idx"] = int(frame_idx)
    elif strict:
        raise ValueError("Missing frame_idx (or frame_id/frame_number)")
    else:
        result["frame_idx"] = 0
    
    # === Timestamp normalization ===
    timestamp = _get_aliased(record, "timestamp_s")
    if timestamp is not None:
        # Check if it looks like milliseconds (> 1000 and frame_idx < 1000)
        frame_idx_val = result.get("frame_idx", 0)
        if timestamp > 1000 and frame_idx_val < 10000:
            # Likely milliseconds, convert to seconds
            result["timestamp_s"] = float(timestamp) / 1000.0
        else:
            result["timestamp_s"] = float(timestamp)
    elif frame_rate and result.get("frame_idx") is not None:
        # Infer from frame_idx
        result["timestamp_s"] = result["frame_idx"] / frame_rate
    else:
        result["timestamp_s"] = 0.0
    
    # === Bounding box normalization ===
    bbox = _get_aliased(record, "bbox_xyxy")
    if bbox is not None:
        result["bbox_xyxy"] = _normalize_bbox(bbox)
    elif strict:
        raise ValueError("Missing bbox_xyxy (or bbox/bbox_2d/bounding_box)")
    else:
        result["bbox_xyxy"] = [0.0, 0.0, 0.0, 0.0]
    
    # === Centroid ===
    centroid = record.get("centroid")
    if centroid is not None:
        result["centroid"] = [float(centroid[0]), float(centroid[1])]
    elif result["bbox_xyxy"]:
        # Compute from bbox
        x1, y1, x2, y2 = result["bbox_xyxy"]
        result["centroid"] = [(x1 + x2) / 2.0, (y1 + y2) / 2.0]
    else:
        result["centroid"] = [0.0, 0.0]
    
    # === Label normalization ===
    label = _get_aliased(record, "label")
    if label is not None:
        # Handle ObjectClass enum or string
        if hasattr(label, "value"):
            result["label"] = str(label.value)
        else:
            result["label"] = str(label)
    else:
        result["label"] = "unknown"
    
    # === Track ID ===
    track_id = _get_aliased(record, "track_id")
    result["track_id"] = int(track_id) if track_id is not None else -1
    
    # === Confidence ===
    confidence = record.get("confidence")
    result["confidence"] = float(confidence) if confidence is not None else 0.0
    
    # === Label hypotheses (v2) ===
    hypotheses = _get_aliased(record, "label_hypotheses_topk")
    if hypotheses:
        result["label_hypotheses_topk"] = _normalize_hypotheses(hypotheses)
    else:
        result["label_hypotheses_topk"] = []
    
    # === Verification status (v2) ===
    result["verification_status"] = record.get("verification_status", "unverified")
    result["verification_source"] = record.get("verification_source")
    
    # === Detector provenance ===
    result["detector_source"] = (
        record.get("detector_source") or
        record.get("detector_source_origin") or
        record.get("source") or
        "unknown"
    )
    
    # === Embedding reference ===
    result["embedding_id"] = record.get("embedding_id")
    
    # === Tracking metadata ===
    result["track_age"] = int(_get_aliased(record, "track_age") or 0)
    result["track_hits"] = int(_get_aliased(record, "track_hits") or 0)
    result["time_since_update"] = int(record.get("time_since_update") or 0)
    
    # === Frame dimensions ===
    result["frame_width"] = record.get("frame_width")
    result["frame_height"] = record.get("frame_height")
    
    # === Pass through extra fields (for debugging/compatibility) ===
    extra_keys = set(record.keys()) - set(FIELD_ALIASES.keys()) - set(CANONICAL_FIELDS.keys())
    for key in extra_keys:
        if not key.startswith("_"):  # Skip private fields
            result[f"_extra_{key}"] = record[key]
    
    return result


def _get_aliased(record: Dict[str, Any], canonical_name: str) -> Any:
    """Get value by canonical name or any of its aliases."""
    # Try canonical first
    if canonical_name in record:
        return record[canonical_name]
    
    # Try aliases
    for alias, target in FIELD_ALIASES.items():
        if target == canonical_name and alias in record:
            return record[alias]
    
    return None


def _normalize_bbox(bbox: Any) -> List[float]:
    """Normalize bbox to [x1, y1, x2, y2] format."""
    if isinstance(bbox, dict):
        # Handle {x1, y1, x2, y2} format
        return [
            float(bbox.get("x1", 0)),
            float(bbox.get("y1", 0)),
            float(bbox.get("x2", 0)),
            float(bbox.get("y2", 0)),
        ]
    elif isinstance(bbox, (list, tuple)):
        if len(bbox) == 4:
            return [float(x) for x in bbox]
        elif len(bbox) == 6:
            # bbox_3d format: [cx, cy, depth, w, h, d] - extract 2D
            # This is a legacy format, convert to xyxy
            cx, cy, _, w, h, _ = bbox
            return [
                float(cx - w/2),
                float(cy - h/2),
                float(cx + w/2),
                float(cy + h/2),
            ]
    
    logger.warning(f"Unknown bbox format: {type(bbox)}, {bbox}")
    return [0.0, 0.0, 0.0, 0.0]


def _normalize_hypotheses(hypotheses: List[Any]) -> List[Dict[str, Any]]:
    """Normalize label hypotheses to canonical format."""
    result = []
    
    for i, h in enumerate(hypotheses):
        if isinstance(h, dict):
            result.append({
                "label": str(h.get("label", h.get("category", "unknown"))),
                "score": float(h.get("score", h.get("confidence", 0.0))),
                "source": str(h.get("source", "unknown")),
                "rank": int(h.get("rank", i)),
            })
        elif isinstance(h, (list, tuple)) and len(h) >= 2:
            # (label, score) format
            result.append({
                "label": str(h[0]),
                "score": float(h[1]),
                "source": "legacy",
                "rank": i,
            })
        elif isinstance(h, str):
            # Just a label string
            result.append({
                "label": h,
                "score": 0.0,
                "source": "legacy",
                "rank": i,
            })
    
    return result


def to_legacy_dict(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert normalized record to legacy format for backward compatibility.
    
    This produces output compatible with existing overlay, Memgraph, and
    other consumers that expect the old schema.
    """
    return {
        # Use old field names
        "frame_id": record.get("frame_idx", 0),
        "timestamp": record.get("timestamp_s", 0.0),
        "bbox": record.get("bbox_xyxy", [0, 0, 0, 0]),
        "bbox_2d": record.get("bbox_xyxy", [0, 0, 0, 0]),
        "centroid": record.get("centroid", [0, 0]),
        "track_id": record.get("track_id", -1),
        "category": record.get("label", "unknown"),
        "class_name": record.get("label", "unknown"),
        "confidence": record.get("confidence", 0.0),
        "age": record.get("track_age", 0),
        "hits": record.get("track_hits", 0),
        "time_since_update": record.get("time_since_update", 0),
        "embedding_id": record.get("embedding_id"),
        
        # Include v2 fields for consumers that understand them
        "label_hypotheses_topk": record.get("label_hypotheses_topk", []),
        "verification_status": record.get("verification_status", "unverified"),
        "detector_source": record.get("detector_source", "unknown"),
    }


@dataclass
class TrackRecord:
    """
    Typed track record with v2 schema.
    
    Use this class when you want type-safe access to track fields.
    """
    # Required fields
    frame_idx: int
    timestamp_s: float
    bbox_xyxy: List[float]
    track_id: int
    label: str
    confidence: float
    
    # Optional v2 fields
    centroid: List[float] = field(default_factory=lambda: [0.0, 0.0])
    label_hypotheses_topk: List[Dict[str, Any]] = field(default_factory=list)
    verification_status: str = "unverified"
    verification_source: Optional[str] = None
    detector_source: str = "unknown"
    embedding_id: Optional[str] = None
    
    # Tracking metadata
    track_age: int = 0
    track_hits: int = 0
    time_since_update: int = 0
    
    # Frame context
    frame_width: Optional[int] = None
    frame_height: Optional[int] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], normalize: bool = True) -> "TrackRecord":
        """Create from dict, optionally normalizing first."""
        if normalize:
            data = normalize_track_record(data)
        
        return cls(
            frame_idx=data.get("frame_idx", 0),
            timestamp_s=data.get("timestamp_s", 0.0),
            bbox_xyxy=data.get("bbox_xyxy", [0, 0, 0, 0]),
            track_id=data.get("track_id", -1),
            label=data.get("label", "unknown"),
            confidence=data.get("confidence", 0.0),
            centroid=data.get("centroid", [0.0, 0.0]),
            label_hypotheses_topk=data.get("label_hypotheses_topk", []),
            verification_status=data.get("verification_status", "unverified"),
            verification_source=data.get("verification_source"),
            detector_source=data.get("detector_source", "unknown"),
            embedding_id=data.get("embedding_id"),
            track_age=data.get("track_age", 0),
            track_hits=data.get("track_hits", 0),
            time_since_update=data.get("time_since_update", 0),
            frame_width=data.get("frame_width"),
            frame_height=data.get("frame_height"),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to canonical dict."""
        return {
            "_schema_version": SCHEMA_VERSION,
            "frame_idx": self.frame_idx,
            "timestamp_s": self.timestamp_s,
            "bbox_xyxy": self.bbox_xyxy,
            "centroid": self.centroid,
            "track_id": self.track_id,
            "label": self.label,
            "confidence": self.confidence,
            "label_hypotheses_topk": self.label_hypotheses_topk,
            "verification_status": self.verification_status,
            "verification_source": self.verification_source,
            "detector_source": self.detector_source,
            "embedding_id": self.embedding_id,
            "track_age": self.track_age,
            "track_hits": self.track_hits,
            "time_since_update": self.time_since_update,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
        }
    
    def to_legacy_dict(self) -> Dict[str, Any]:
        """Convert to legacy format for backward compatibility."""
        return to_legacy_dict(self.to_dict())
    
    @property
    def bbox_width(self) -> float:
        return self.bbox_xyxy[2] - self.bbox_xyxy[0]
    
    @property
    def bbox_height(self) -> float:
        return self.bbox_xyxy[3] - self.bbox_xyxy[1]
    
    @property
    def bbox_area(self) -> float:
        return self.bbox_width * self.bbox_height
    
    @property
    def top_hypothesis(self) -> Optional[Dict[str, Any]]:
        """Get the highest-scoring hypothesis, if any."""
        if self.label_hypotheses_topk:
            return max(self.label_hypotheses_topk, key=lambda h: h.get("score", 0))
        return None
    
    @property
    def is_verified(self) -> bool:
        return self.verification_status == "verified"


def load_tracks_jsonl(
    path: str,
    normalize: bool = True,
    frame_rate: Optional[float] = None,
) -> List[TrackRecord]:
    """
    Load tracks from JSONL file with normalization.
    
    Args:
        path: Path to tracks.jsonl
        normalize: Whether to normalize to v2 schema
        frame_rate: Video frame rate for timestamp inference
        
    Returns:
        List of TrackRecord objects
    """
    import json
    from pathlib import Path
    
    tracks_path = Path(path)
    if not tracks_path.exists():
        raise FileNotFoundError(f"Tracks file not found: {path}")
    
    records = []
    with open(tracks_path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                record = TrackRecord.from_dict(data, normalize=normalize)
                records.append(record)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON at line {line_num}: {e}")
            except Exception as e:
                logger.warning(f"Error parsing record at line {line_num}: {e}")
    
    logger.info(f"Loaded {len(records)} track records from {path}")
    return records


def save_tracks_jsonl(
    records: List[Union[TrackRecord, Dict[str, Any]]],
    path: str,
    legacy_format: bool = False,
) -> None:
    """
    Save tracks to JSONL file.
    
    Args:
        records: List of TrackRecord objects or dicts
        path: Output path
        legacy_format: If True, use legacy field names
    """
    import json
    from pathlib import Path
    
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        for record in records:
            if isinstance(record, TrackRecord):
                data = record.to_legacy_dict() if legacy_format else record.to_dict()
            elif isinstance(record, dict):
                data = to_legacy_dict(record) if legacy_format else record
            else:
                logger.warning(f"Unknown record type: {type(record)}")
                continue
            
            f.write(json.dumps(data, default=str) + "\n")
    
    logger.info(f"Saved {len(records)} track records to {path}")
