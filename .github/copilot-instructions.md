# Orion Research: AI Coding Agent Instructions

## Project Overview

**Orion** is a memory-centric video understanding system for persistent object tracking, spatial reasoning, and long-term scene memory. Built for Apple Silicon (M-series) with end-to-end perception → memory → query pipeline.

### Architecture Layers (understand dependencies)

1. **Perception Engine** (`orion/perception/engine.py`): Frame-level detection, embedding, tracking
   - Detectors: YOLO11, YOLO-World (configurable via `DetectionConfig.backend`)
   - Embedders: V-JEPA2 (video-native 3D-aware Re-ID) in `orion/backends/`
   - Trackers: EnhancedTracker with adaptive Re-ID thresholds (`orion/perception/trackers/enhanced.py`)
   - Depth: DepthAnythingV2 for spatial mapping
   - VLM: MLX-VLM (local FastVLM) for visual descriptions + SentenceTransformers for semantic filtering

2. **Scene Graph** (`orion/graph/`): Temporal object relationships
   - Per-frame: `SGNode` (objects) + `SGEdge` (relations: on, near, held_by)
   - Temporal: `VideoSceneGraph` aggregates frame graphs
   - Data flow: perception observations → scene graph → Memgraph export
   - Builder: `build_research_scene_graph()` in `orion/graph/scene_graph.py`

3. **Memory/Query** (Phase 3-4):
   - Re-ID Index: DINOv3 embeddings + cosine similarity matching
   - Vector Search: semantic object queries (planned)
   - Memgraph: persistent graph backend (`orion/graph/backends/memgraph.py`)
   - Spatial Memory: Zone-based object tracking (`orion/graph/spatial_memory.py`)

## Critical Data Structures

**Perception Flow:**
```
Frame → Observation (detections) 
  → PerceptionEntity (tracked object)
    → PerceptionResult (per-frame output with tracks, scene_graph, entities)
```

**Key Types:**
- `PerceptionConfig`: Detection, embedding, depth, tracking settings (presets: fast/balanced/accurate)
- `DetectionConfig`: Backend (yolo/yoloworld), thresholds, model size
- `EmbeddingConfig`: Backend (vjepa2), dimension, model name
- `SceneGraph`: nodes (SGNode: id, label, bbox, attributes) + edges (SGEdge: subject→predicate→object)

**Backend Architecture:**
- Detection backends in `orion/perception/detectors/`: YOLO, YOLO-World
- Embedding backends in `orion/backends/`: V-JEPA2 (video-native), CLIP (legacy)
- Each backend implements factory pattern with `validate()` called in config `__post_init__`

See [orion/perception/types.py](../orion/perception/types.py) and [orion/graph/types.py](../orion/graph/types.py).

## Episode & Results Format

**Input:** `data/examples/episodes/<episode_id>/meta.json` + `video.mp4`
**Output:** `results/<episode_id>/tracks.jsonl` + `scene_graph.jsonl` + `memory.json` (Phase 3+)

**Critical: JSONL Streaming Pattern**
- Results are **JSONL** (JSON Lines): one object per line, NOT a JSON array
- Load with: `for line in f: obj = json.loads(line)`
- Write with: `f.write(json.dumps(obj) + "\n")`
- Files: `tracks.jsonl`, `scene_graph.jsonl`, `events.jsonl`
- Never use `json.load()` on JSONL files (will fail on multi-line files)

Example:
```bash
python -c "from orion.config import list_episodes; print(list_episodes())"
python -m orion run --video data/examples/test.mp4 --episode test_demo
```

## Developer Workflows

### Running Perception
```bash
# End-to-end pipeline (detection → embedding → tracking → scene graph)
python -m orion run --video data/examples/test.mp4 --episode test_demo

# Reuse tracks, rebuild only scene graph & overlay
python -m orion run --video data/examples/test.mp4 --episode test_demo --skip-phase1

# Export to Memgraph (requires external Memgraph instance)
python -m orion run --video data/examples/test.mp4 --episode test_demo --memgraph --memgraph-host 127.0.0.1

# Standalone overlay regeneration
python -m orion overlay --video data/examples/test.mp4 --episode test_demo
```

### Testing & Validation
- Verify CLI parsing: `python -m orion --help`
- Verify showcase parser: `python -m orion.cli.run_showcase --help`
- Re-ID metrics are emitted under `run_metadata.json` and pipeline summaries
- Scene graph schema details: `docs/results_schema.md`

### Memgraph Integration
```bash
# Ensure Memgraph is running (Bolt port 7687)
# Then run Orion with ingest enabled:
python -m orion run --video data/examples/test.mp4 --episode test_demo --memgraph
```

### Configuration Patterns
- **Presets**: `PerceptionConfig(mode="fast"|"balanced"|"accurate")` sets all thresholds automatically
- **Override**: Create `PerceptionConfig(mode="balanced")`, then `.detection.model = "yolo11x"`
- **Validation**: All `@dataclass` configs have `__post_init__` validation with clear error messages
- **Device**: Auto-detects MPS (Apple Silicon), CUDA, else CPU. Override with `detection.device = "mps"`

## Code Patterns & Conventions

### Detection & Embedding Backend Abstraction
```python
# DetectionConfig.backend ∈ {yolo, yoloworld}
# EmbeddingConfig.backend ∈ {vjepa2}
# Instantiation happens in PerceptionEngine.__init__() via factory pattern
# Each backend has validate() method called in config __post_init__
```

### Re-ID Adaptive Thresholds
- `EnhancedTracker` uses class-specific `reid_thresholds.py` (tuned empirically)
- Threshold is multiplied by `motion_factor` (faster objects → stricter matching)
- `max_gallery_size` limits appearance history per track (default: 30 frames)
- See `orion/perception/reid_manager.py` for similarity calculation

### Scene Graph Generation
```python
# Per-frame: PerceptionEngine.process_frame() calls:
# 1. Detect: get observations (detections + embeddings)
# 2. Track: match to existing tracks (PerceptionEntity)
# 3. Build SG: call build_research_scene_graph(tracks, depth, spatial_zones)
# 4. Serialize: scene_graph.to_dict() → JSON line in tracks.jsonl
```

### Spatial Relationships (Phase 3 readiness)
- Zones: Define with `shapely` polygons in config (e.g., "kitchen", "living_room")
- Relations: Compute with depth + bbox overlaps + heuristics
- Confidence: Each edge has `confidence` (0-1) reflecting spatial certainty

## Integration Points & External Dependencies

**Model Weights:**
- YOLO: `models/_torch/yolo11*.pt` (auto-download from Ultralytics)
- CLIP/DINO: HuggingFace `transformers` (auto-cached)
- DepthAnythingV3: `models/_torch/depth_anything_v3.pth`
- SAM2: `orion/models/external/segment-anything-2/checkpoints/sam2_hiera_small.pt`

**Backends:**
- Memgraph (Docker): For Phase 4 persistent graph (optional)
- Neo4j (deprecated, legacy CLI refs only)
- OLLAMA: For local LLM reasoning (optional, used in query stage)

**Video I/O:**
- OpenCV: Frame reading + overlay rendering
- MediaPipe: Face/pose detection (optional, separate pipeline)

## Common Pitfalls & Fixes

1. **Missing model weights**: Scripts auto-download, but slow first run. Check `models/` directory.
2. **Device mismatch**: Tensors must match detector device. Use `to(device)` in perception modules.
3. **JSON JSONL confusion**: Results are JSONL (one JSON object per line), not single array.
4. **Threshold tuning**: Don't hardcode values in code. Always use `PerceptionConfig` + `reid_thresholds.py`.
5. **Scene graph edges missing**: Ensure `build_research_scene_graph()` is called with valid tracks + depth. Check spatial zone config.
6. **Memgraph ingest fails**: Verify `orion/graph/backends/memgraph.py` matches schema (Entity, Frame, NEAR edge, etc.).
7. **MPS out of memory**: Apple Silicon GPUs have limited memory. Use smaller models (`yolo11n`, `clip-vit-base-patch32`) or reduce batch sizes.
8. **Import errors**: Memgraph imports are optional. Wrap in try/except and check `MemgraphBackend is not None` before use.

## Getting Started on New Features

1. **Add detection backend**: Extend `DetectionConfig.backend` enum, implement wrapper in `perception/engine.py`
2. **Add embedding model**: Extend `EmbeddingConfig.backend`, add to `embedder.py` factory
3. **Improve Re-ID**: Tune `reid_thresholds.py` per object class, test with `eval_reid.py`
4. **Add spatial relations**: Extend predicate types in `SGEdge.predicate`, implement in `build_research_scene_graph()`
5. **Phase 4 memory**: Use `MemgraphBackend.add_entity_observation()` in `PerceptionEngine.process_frame()`

## References

- **Detailed schemas**: [docs/episodes.md](../docs/episodes.md), [docs/results_schema.md](../docs/results_schema.md)
- **Config reference**: [orion/perception/config.py](../orion/perception/config.py) (150+ lines, all documented)
- **CLI entry**: [orion/cli/main.py](../orion/cli/main.py)
- **Core engine**: [orion/perception/engine.py](../orion/perception/engine.py) (~1400 lines, main logic)

**Apple Silicon note:** Project built & tested on M-series. MPS (Metal Performance Shaders) is default device. No special setup needed beyond standard PyTorch with MPS support.
