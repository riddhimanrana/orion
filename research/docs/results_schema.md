# Results Schema

## Overview

Each episode generates a standardized set of output artifacts in `results/<episode_id>/`. These artifacts support reproducibility, evaluation, and downstream analysis (QA, visualization, debugging).

## Directory Structure

```text
results/<episode_id>/
├── tracks.jsonl              # Per-frame detections and track assignments
├── memory.json              # Persistent object memory with embeddings
├── events.jsonl             # State change and lifecycle events
├── scene_graph.jsonl        # Per-frame scene graph snapshots (Phase 4)
├── graph_summary.json       # Episode-level scene graph summary (Phase 4)
├── entities.json            # Legacy: clustered entities (Phase 1)
├── camera_intrinsics.json   # Camera calibration parameters
├── qa.jsonl                 # Video QA responses (Phase 6)
└── viz/                     # Optional visualization outputs
    ├── tracks_overlay.mp4
    ├── depth_maps/
    └── annotated_frames/
```

## Core Artifact Schemas

### tracks.jsonl

Line-delimited JSON with one object per detection/track per frame. Enables frame-by-frame replay and IDF1/MOTA metrics.

**Example Lines:**

```jsonl
{"frame_id": 1, "track_id": 1, "bbox": [120.5, 340.2, 220.8, 480.1], "score": 0.94, "category": "mug", "embedding_id": "emb_001"}
{"frame_id": 1, "track_id": 2, "bbox": [450.0, 120.0, 650.0, 380.0], "category": "person", "score": 0.98, "embedding_id": "emb_002"}
{"frame_id": 2, "track_id": 1, "bbox": [122.0, 342.0, 222.0, 482.0], "score": 0.93, "category": "mug", "embedding_id": "emb_001"}
```

**Schema:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `frame_id` | integer | Yes | Frame number (1-indexed) |
| `track_id` | integer | Yes | Temporal track ID (short-term or persistent) |
| `bbox` | array[4 floats] | Yes | Bounding box `[x1, y1, x2, y2]` in pixels |
| `score` | float | Yes | Detection confidence (0–1) |
| `category` | string | Yes | Object class name |
| `embedding_id` | string | No | Reference to re-ID embedding in memory |
| `centroid` | array[2 floats] | No | 2D centroid `[x, y]` |
| `depth_mm` | float | No | Depth estimate in millimeters |
| `state` | object | No | Object-specific state (e.g., `{"held": true}`) |

### memory.json

Global object memory maintaining persistent identities across occlusions and time gaps.

**Example:**

```json
{
  "objects": [
    {
      "memory_id": "mem_001",
      "class": "mug",
      "first_seen_frame": 1,
      "last_seen_frame": 920,
      "total_observations": 687,
      "prototype_embedding": "emb_001",
      "appearance_history": [
        {"frame": 1, "track_id": 1, "confidence": 0.94},
        {"frame": 450, "track_id": 12, "confidence": 0.89},
        {"frame": 680, "track_id": 18, "confidence": 0.91}
      ],
      "current_state": "visible",
      "last_bbox": [340.0, 290.0, 440.0, 430.0],
      "metadata": {
        "description": "Blue ceramic mug",
        "room_id": "kitchen"
      }
    },
    {
      "memory_id": "mem_002",
      "class": "book",
      "first_seen_frame": 120,
      "last_seen_frame": 1200,
      "total_observations": 1080,
      "prototype_embedding": "emb_003",
      "current_state": "disappeared",
      "last_bbox": [560.0, 420.0, 680.0, 590.0],
      "metadata": {
        "description": "Red hardcover book",
        "room_id": "living_room"
      }
    }
  ],
  "embeddings": {
    "emb_001": [0.12, -0.34, 0.56, "... (512-dim or 1024-dim vector)"],
    "emb_002": [0.08, 0.22, -0.41, "..."],
    "emb_003": [-0.15, 0.67, 0.09, "..."]
  },
  "statistics": {
    "total_objects": 2,
    "active_objects": 1,
    "disappeared_objects": 1,
    "total_merges": 3,
    "total_reappearances": 2
  }
}
```

**Schema:**

| Field | Type | Description |
|-------|------|-------------|
| `memory_id` | string | Persistent object identifier |
| `class` | string | Object category |
| `first_seen_frame` | integer | Frame of first detection |
| `last_seen_frame` | integer | Frame of last detection |
| `total_observations` | integer | Number of frame appearances |
| `prototype_embedding` | string | Reference to embedding in `embeddings` map |
| `appearance_history` | array[object] | Key reappearances with track/frame references |
| `current_state` | string | `visible`, `occluded`, `disappeared` |
| `last_bbox` | array[4 floats] | Most recent bounding box |
| `metadata` | object | Auxiliary info (description, room, attributes) |

### events.jsonl

Lifecycle and state change events for temporal reasoning and QA.

**Example Lines:**

```jsonl
{"type": "appeared", "memory_id": "mem_001", "frame": 1, "track_id": 1, "details": "First detection of mug"}
{"type": "disappeared", "memory_id": "mem_001", "frame": 480, "track_id": 12, "reason": "occluded", "details": "Lost behind plant"}
{"type": "reappeared", "memory_id": "mem_001", "frame": 680, "track_id": 18, "gap_frames": 200, "details": "Reappeared after occlusion"}
{"type": "merged", "memory_id": "mem_001", "frame": 685, "merged_tracks": [18, 19], "details": "Duplicate tracks merged via re-ID"}
{"type": "state_change", "memory_id": "mem_001", "frame": 225, "state": "held_by_person", "details": "Mug picked up"}
{"type": "moved_room", "memory_id": "mem_002", "frame": 890, "from_room": "kitchen", "to_room": "living_room", "details": "Book carried to living room"}
```

**Schema:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Event category (see below) |
| `memory_id` | string | Yes | Reference to object in `memory.json` |
| `frame` | integer | Yes | Frame number where event occurred |
| `track_id` | integer | No | Associated track ID |
| `details` | string | No | Human-readable description |
| Additional fields vary by type | | | `reason`, `gap_frames`, `merged_tracks`, `state`, etc. |

**Event Types:**

- `appeared`: Object first detected
- `disappeared`: Object lost (occlusion, off-screen, or end)
- `reappeared`: Object re-detected after gap
- `merged`: Duplicate tracks consolidated
- `split`: Single track incorrectly split (correction event)
- `state_change`: Object state transition (held, moved, opened, etc.)
- `moved_room`: Object changed spatial region

### scene_graph.jsonl (Phase 4)

Per-frame temporal scene graph snapshots. Each line represents the graph state at a specific frame.

**Example Line:**

```jsonl
{"frame": 450, "nodes": [{"id": "mem_001", "class": "mug", "bbox": [340, 290, 440, 430], "states": ["held_by_person"]}, {"id": "mem_003", "class": "person", "bbox": [200, 50, 800, 1000]}], "edges": [{"source": "mem_001", "target": "mem_003", "relation": "held_by", "confidence": 0.95}], "timestamp": 15.0}
```

**Schema (per line):**

| Field | Type | Description |
|-------|------|-------------|
| `frame` | integer | Frame number |
| `timestamp` | float | Time in seconds since episode start |
| `nodes` | array[object] | Objects present in frame |
| `edges` | array[object] | Spatial/interaction relations |

**Node Schema:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Memory ID reference |
| `class` | string | Object category |
| `bbox` | array[4 floats] | Bounding box |
| `centroid_3d` | array[3 floats] | Optional 3D position `[x, y, z]` in mm |
| `states` | array[string] | Active states (e.g., `held`, `open`) |
| `room_id` | string | Spatial region identifier |

**Edge Schema:**

| Field | Type | Description |
|-------|------|-------------|
| `source` | string | Source memory ID |
| `target` | string | Target memory ID |
| `relation` | string | Relation type (`near`, `on`, `inside`, `held_by`, `left_of`) |
| `confidence` | float | Relation confidence (0–1) |

### graph_summary.json (Phase 4)

Episode-level scene graph summary for QA prompting.

**Example:**

```json
{
  "episode_id": "20251116-1430-kitchen-demo",
  "total_frames": 920,
  "duration_seconds": 30.67,
  "objects": [
    {
      "memory_id": "mem_001",
      "class": "mug",
      "lifetime_frames": 687,
      "key_events": ["appeared@1", "picked_up@225", "placed_on@450", "occluded@480", "reappeared@680"],
      "final_location": "kitchen_counter"
    },
    {
      "memory_id": "mem_002",
      "class": "book",
      "lifetime_frames": 1080,
      "key_events": ["appeared@120", "moved_room@890"],
      "final_location": "living_room_table"
    }
  ],
  "relations": [
    {"source": "mem_001", "target": "kitchen_counter", "relation": "on", "frame_range": [450, 920]},
    {"source": "mem_002", "target": "mem_003", "relation": "held_by", "frame_range": [850, 920]}
  ],
  "statistics": {
    "unique_objects": 5,
    "total_interactions": 8,
    "room_changes": 1
  }
}
```

## Legacy Artifacts (Phase 1)

### entities.json

Clustered entities from the original perception pipeline. Kept for backward compatibility; will be superseded by `memory.json` in Phase 3+.

**Example:**

```json
{
  "total_entities": 3,
  "entities": [
    {
      "id": 0,
      "class": "mug",
      "confidence": 0.92,
      "observation_count": 450,
      "first_frame": 1,
      "last_frame": 450,
      "description": "Blue ceramic coffee mug with white handle"
    }
  ]
}
```

### camera_intrinsics.json

Camera calibration parameters for 3D backprojection.

**Example:**

```json
{
  "fx": 1200.5,
  "fy": 1205.3,
  "cx": 960.0,
  "cy": 540.0,
  "width": 1920,
  "height": 1080,
  "note": "iPhone 15 Pro main camera intrinsics"
}
```

### slam_trajectory.npy

NumPy array of camera poses (4×4 transformation matrices) per frame. Used for camera motion compensation and 3D visualization.

**Loading:**

```python
import numpy as np
poses = np.load("results/demo_room/slam_trajectory.npy")
# Shape: (num_frames, 4, 4)
```

## Validation

Validate results schema compliance:

```bash
pytest tests/test_results_schema.py -v
```

## Usage Example

### Loading Results

```python
import json
from pathlib import Path

episode_id = "20251116-1430-kitchen-demo"
results_dir = Path(f"results/{episode_id}")

# Load memory
with open(results_dir / "memory.json") as f:
    memory = json.load(f)

print(f"Total objects: {memory['statistics']['total_objects']}")

# Load events
import jsonlines
with jsonlines.open(results_dir / "events.jsonl") as reader:
    events = list(reader)

reappearances = [e for e in events if e["type"] == "reappeared"]
print(f"Total reappearances: {len(reappearances)}")
```

### Computing Metrics

```python
from orion.eval.metrics import compute_idf1, compute_reid_recall

# Load tracks and ground truth
tracks = load_tracks_jsonl(results_dir / "tracks.jsonl")
gt = load_gt_json(f"data/examples/episodes/{episode_id}/gt.json")

# Compute IDF1 (tracking accuracy)
idf1 = compute_idf1(tracks, gt)

# Compute re-ID recall (identity persistence)
reid_recall = compute_reid_recall(memory, gt, k=1)

print(f"IDF1: {idf1:.3f}, Re-ID Recall@1: {reid_recall:.3f}")
```

## Best Practices

1. **Use JSONL for per-frame data**: Enables streaming and incremental analysis
2. **Store embeddings separately**: Large vectors should reference IDs, not inline
3. **Compress large episodes**: Use `gzip` for `.jsonl` files in production
4. **Version results**: Include pipeline version and config hash in metadata
5. **Atomic writes**: Write to temp file, then rename to avoid corruption
