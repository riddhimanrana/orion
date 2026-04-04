# Episode Data Format

## Overview

Episodes are self-contained video segments with metadata and optional ground truth annotations. They serve as the primary input format for the Orion Memory Engine pipeline.

## Directory Structure

```
data/examples/episodes/<episode_id>/
├── meta.json           # Required: Episode metadata
├── gt.json            # Optional: Ground truth annotations
├── video.mp4          # Option 1: Single video file
└── frames/            # Option 2: Extracted frames (frame_0001.jpg, ...)
```

## Episode ID Convention

Episodes use timestamped slugs for reproducibility:
- Format: `YYYYMMDD-HHMM-<descriptive-name>`
- Example: `20251116-1430-kitchen-demo`
- Alternative: `demo_room`, `test_video` for curated examples

## meta.json Schema

Required metadata describing the episode source and properties.

```json
{
  "episode_id": "20251116-1430-kitchen-demo",
  "source": "iphone_15_pro",
  "device": {
    "model": "iPhone 15 Pro",
    "os_version": "iOS 17.1",
    "camera": "main_wide"
  },
  "video": {
    "fps": 30.0,
    "resolution": [1920, 1080],
    "duration_seconds": 45.2,
    "codec": "h264"
  },
  "capture": {
    "location": "kitchen",
    "lighting": "natural_indoor",
    "date": "2025-11-16",
    "time": "14:30:00"
  },
  "notes": "Walking through kitchen, picking up objects and placing them on counter. Good occlusion examples with mug behind plant.",
  "created_at": "2025-11-16T14:35:00Z",
  "tags": ["indoor", "manipulation", "occlusion", "multi-room"]
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `episode_id` | string | Yes | Unique identifier matching directory name |
| `source` | string | Yes | Recording device/system identifier |
| `device` | object | No | Device details (model, OS, camera) |
| `video` | object | Yes | Video properties (fps, resolution, duration, codec) |
| `capture` | object | No | Capture context (location, lighting, datetime) |
| `notes` | string | No | Free-form description of episode content |
| `created_at` | string | Yes | ISO 8601 timestamp of episode creation |
| `tags` | array[string] | No | Categorical tags for filtering/search |

## gt.json Schema (Optional)

Ground truth annotations for evaluation. Used to measure tracking accuracy, re-ID performance, and state change detection.

```json
{
  "objects": [
    {
      "id": "obj_001",
      "class": "mug",
      "description": "Blue ceramic coffee mug with handle",
      "spans": [
        {
          "start_frame": 1,
          "end_frame": 450,
          "visibility": "visible",
          "bbox_keyframes": [
            {"frame": 1, "bbox": [120, 340, 220, 480]},
            {"frame": 225, "bbox": [450, 320, 550, 460]},
            {"frame": 450, "bbox": [780, 300, 880, 440]}
          ]
        },
        {
          "start_frame": 680,
          "end_frame": 920,
          "visibility": "reappeared",
          "bbox_keyframes": [
            {"frame": 680, "bbox": [320, 280, 420, 420]},
            {"frame": 920, "bbox": [340, 290, 440, 430]}
          ]
        }
      ],
      "total_frames": 690
    },
    {
      "id": "obj_002",
      "class": "book",
      "description": "Red hardcover book",
      "spans": [
        {
          "start_frame": 120,
          "end_frame": 1200,
          "visibility": "visible"
        }
      ],
      "total_frames": 1080
    }
  ],
  "events": [
    {
      "type": "picked_up",
      "object_id": "obj_001",
      "frame": 225,
      "actor": "person",
      "details": "Mug picked up from table by right hand"
    },
    {
      "type": "placed_on",
      "object_id": "obj_001",
      "frame": 450,
      "target": "counter",
      "details": "Mug placed on kitchen counter"
    },
    {
      "type": "occluded_by",
      "object_id": "obj_001",
      "frame": 480,
      "occluder": "plant",
      "duration_frames": 200,
      "details": "Mug occluded behind potted plant"
    },
    {
      "type": "moved_room",
      "object_id": "obj_002",
      "frame": 890,
      "from_room": "kitchen",
      "to_room": "living_room",
      "details": "Book carried from kitchen to living room"
    }
  ],
  "notes": "Ground truth manually annotated with sparse keyframes. Linear interpolation assumed between keyframes.",
  "annotator": "research_team",
  "annotation_date": "2025-11-16"
}
```

### Ground Truth Field Descriptions

#### Objects Array

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique object identifier (stable across entire episode) |
| `class` | string | Object category (COCO class or custom) |
| `description` | string | Human-readable object description |
| `spans` | array[object] | Temporal spans where object is tracked |
| `total_frames` | integer | Total frames object is visible |

#### Spans Object

| Field | Type | Description |
|-------|------|-------------|
| `start_frame` | integer | First frame of span (1-indexed) |
| `end_frame` | integer | Last frame of span (inclusive) |
| `visibility` | string | `visible`, `occluded`, `reappeared` |
| `bbox_keyframes` | array[object] | Sparse bounding box annotations |

#### Events Array

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Event category (`picked_up`, `placed_on`, `occluded_by`, `moved_room`, `disappeared`, `reappeared`) |
| `object_id` | string | Reference to object ID |
| `frame` | integer | Frame number where event occurred |
| `details` | string | Free-form event description |
| Additional fields vary by event type | | Actor, target, occluder, from/to locations, duration |

## Usage Example

### Creating an Episode

```python
from pathlib import Path
import json

episode_id = "20251116-1430-kitchen-demo"
episode_dir = Path(f"data/examples/episodes/{episode_id}")
episode_dir.mkdir(parents=True, exist_ok=True)

# Create metadata
meta = {
    "episode_id": episode_id,
    "source": "iphone_15_pro",
    "video": {"fps": 30.0, "resolution": [1920, 1080], "duration_seconds": 45.2},
    "notes": "Kitchen walkthrough with object interactions",
    "created_at": "2025-11-16T14:35:00Z"
}

with open(episode_dir / "meta.json", "w") as f:
    json.dump(meta, f, indent=2)

# Copy video
import shutil
shutil.copy("my_recording.mp4", episode_dir / "video.mp4")
```

### Loading an Episode

```python
from orion.config.data_paths import load_episode_meta

episode_id = "20251116-1430-kitchen-demo"
meta = load_episode_meta(episode_id)

print(f"Episode: {meta['episode_id']}")
print(f"FPS: {meta['video']['fps']}")
print(f"Duration: {meta['video']['duration_seconds']}s")
```

## Validation

Use `tests/test_episode_conventions.py` to validate episode structure:

```bash
pytest tests/test_episode_conventions.py -v
```

## Best Practices

1. **Use descriptive episode IDs**: Include location/scenario in the name
2. **Document occlusions**: Note difficult re-ID scenarios in `notes`
3. **Sparse annotations**: For GT, annotate keyframes only; interpolate between
4. **Consistent lighting tags**: Use standard vocabulary (`natural_indoor`, `artificial`, `mixed`, `outdoor`)
5. **Include failure cases**: Episodes with tracking challenges are valuable for evaluation
