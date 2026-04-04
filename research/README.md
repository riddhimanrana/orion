<div align="center">
  <img src="https://orionlive.ai/logo.png" alt="Orion Logo" width="120" />

  <h1>Orion</h1>
  <p><strong>A Fully Deterministic and Interpretable Pipeline for<br>Video Scene Graph Generation with Explicit Causal Influence Scoring</strong></p>

  <p>
    <a href="https://github.com/riddhimanrana/orion-research"><img src="https://img.shields.io/badge/GitHub-orion--research-181717?logo=github" alt="GitHub"></a>
    <a href="#citation"><img src="https://img.shields.io/badge/Paper-Accepted%20%40%20ES--Reasoning%20Workshop-green" alt="Paper"></a>
    <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python" alt="Python">
    <img src="https://img.shields.io/badge/Platform-Apple%20Silicon%20%7C%20CUDA%20%7C%20CPU-lightgrey" alt="Platform">
    <img src="https://img.shields.io/badge/Zero--shot-No%20Training%20Required-orange" alt="Zero-shot">
    <img src="https://img.shields.io/badge/License-MIT-blue" alt="License">
  </p>
</div>

---

## Overview

**Orion** is a zero-shot, fully deterministic pipeline for **Video Scene Graph Generation (VidSGG)**. It composes state-of-the-art pretrained foundation models — Grounding DINO, DINOv3, V-JEPA2, and FastVLM — into a modular, interpretable system that produces structured scene graphs and explicit causal relationship scores without any task-specific training or fine-tuning.

The pipeline's central contribution is the **Causal Influence Score (CIS)**: a hand-interpretable, parameter-free scoring function that aggregates temporal, spatial, motion, and semantic signals to explain *why* a relationship between two entities was predicted.

> **Accepted** · ES-Reasoning Workshop · ICLR 2026 companion workshops · *Poster presentation*

---

## Table of Contents

- [Key Contributions](#key-contributions)
- [How It Works](#how-it-works)
- [Causal Influence Score (CIS)](#causal-influence-score-cis)
- [Pipeline Architecture](#pipeline-architecture)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
- [Output Artifacts](#output-artifacts)
- [Platform Support](#platform-support)
- [Development Process](#development-process)
- [Authors](#authors)
- [Peer Review & Reception](#peer-review--reception)
- [Citation](#citation)

---

## Key Contributions

| Contribution | Description |
|---|---|
| **Deterministic relational layer** | CIS scoring, scene graph construction, and spatial predicates are fully deterministic — no stochastic sampling, no fine-tuning |
| **Zero-shot VidSGG** | Competitive performance with supervised methods on standard benchmarks, without any task-specific training |
| **Interpretable CIS** | Each predicted relationship ships with a per-component score breakdown: temporal (T), spatial (S), motion (M), semantic (Se) |
| **Modular, swappable design** | Every component (detector, embedder, VLM) is a pluggable backend — upgrade one module without touching the rest |
| **End-to-end CLI** | Single command runs the full video → tracks → memory → scene graph → overlay pipeline |

---

## How It Works

Orion processes video through four sequential stages:

```
Video
  │
  ▼
┌──────────────────────────────────┐
│  Stage 1 · Perception Engine     │
│  GroundingDINO + DINOv3 Re-ID    │
│  V-JEPA2 embeddings              │
│  DepthAnythingV2 (3D depth)      │
│  EnhancedTracker (IoU + Re-ID)   │
└──────────────┬───────────────────┘
               │  tracks.jsonl
               ▼
┌──────────────────────────────────┐
│  Stage 2 · Scene Graph Build     │
│  Per-frame SGNode (objects)      │
│  SGEdge (on / near / held_by)    │
│  CIS causal edges                │
└──────────────┬───────────────────┘
               │  scene_graph.jsonl
               ▼
┌──────────────────────────────────┐
│  Stage 3 · Memory & Identity     │
│  Long-term Re-ID index           │
│  Zone-based spatial memory       │
│  FastVLM visual descriptions     │
└──────────────┬───────────────────┘
               │  memory.json
               ▼
┌──────────────────────────────────┐
│  Stage 4 · Query & Overlay       │
│  Natural language Q&A            │
│  Memgraph persistent graph       │
│  Video overlay rendering         │
└──────────────────────────────────┘
               │  video_overlay_insights.mp4
               ▼
           results/<episode>/
```

---

## Causal Influence Score (CIS)

The CIS is the interpretable scoring function at the heart of Orion's relational reasoning layer. It assigns a scalar score to any pair of tracked entities, with each sub-score individually auditable:

$$\text{CIS} = w_t \cdot T + w_s \cdot S + w_m \cdot M + w_{se} \cdot Se + H$$

| Component | Formula | Description |
|---|---|---|
| **T** (Temporal) | $e^{-\|\Delta t\| / \tau}$ | Exponential decay over temporal gap; entities close in time get higher scores |
| **S** (Spatial) | $\max\!\left(0,\, 1 - \left(\tfrac{D_{3D}}{D_{\max}}\right)^2\right)$ | 3D proximity computed from DepthAnythingV2 estimates; gated by depth threshold to prevent foreground/background hallucinations |
| **M** (Motion) | $\max(0, \cos \theta_{\mathbf{v}})$ | Cosine alignment of 3D velocity vectors; high score = entities moving together |
| **Se** (Semantic) | $0.6 \cdot \text{emb\_sim} + 0.4 \cdot \text{type\_compat}$ | DINOv3 embedding cosine similarity combined with class-type heuristics |
| **H** (Interaction) | discrete bonus $\in \{0.05, 0.15, 0.30\}$ | Hand-proximity bonus for near, touching, grasping |

**Default weights:** $w_t = 0.30$, $w_s = 0.44$, $w_m = 0.21$, $w_{se} = 0.06$

A CIS edge is emitted when the total score exceeds the configurable threshold (default: 0.50). The resulting edge record gives full per-component traceability — you can inspect exactly which signal drove a relationship prediction.

---

## Pipeline Architecture

### Foundation model backends

| Role | Default | Alternatives |
|---|---|---|
| Detection | GroundingDINO (tiny / base) | YOLO-World, YOLO11 |
| Re-ID Embedder | DINOv3 (ViT-B) | V-JEPA2, CLIP |
| Temporal Embedder | V-JEPA2 | — |
| Depth | DepthAnythingV2 | — |
| VLM (descriptions) | FastVLM (Apple MLX) | Gemini (cloud) |
| Graph store | Local JSONL | Memgraph (Bolt) |

### Spatial predicates

Scene graph edges use three spatial predicates inferred from 3D depth + bounding box geometry:

- `near` — centroid distance within threshold
- `on` — vertical stacking + surface contact heuristic
- `held_by` — hand-proximity + motion alignment (overlaps with CIS H component)

---

## Quick Start

### 1. Create environment

```bash
conda env create -f environment.yml
conda activate orion
```

> If shell activation is restricted, prefix commands with `conda run -n orion`.

### 2. Check your setup

```bash
orion install
```

Reports available packages, hardware device (MPS / CUDA / CPU), and model weight status.

### 3. Run the full pipeline

```bash
orion run --video data/examples/test.mp4 --episode my_demo
```

This single command runs all four stages and writes all artifacts to `results/my_demo/`.

---

## CLI Reference

All commands support `--help` for full option listings.

### `orion run` — full pipeline

```bash
# Basic run (episode name derived from filename)
orion run --video path/to/video.mp4

# Named episode with custom FPS
orion run --video path/to/video.mp4 --episode demo --fps 5

# Apple Silicon — explicit MPS
orion run --video path/to/video.mp4 --device mps

# Reuse existing tracks, rebuild scene graph + overlay only
orion run --video path/to/video.mp4 --episode demo --skip-phase1 --skip-memory

# Export to Memgraph (requires Memgraph running on port 7687)
orion run --video path/to/video.mp4 --episode demo --memgraph

# Machine-readable JSON summary
orion run --video path/to/video.mp4 --json
```

**Key flags:**

| Flag | Default | Description |
|---|---|---|
| `--fps` | `4.0` | Target detection sampling rate |
| `--device` | `auto` | `auto` / `mps` / `cuda` / `cpu` |
| `--detector-backend` | `dinov3` | Detection backend |
| `--embedding-backend` | `vjepa2` | Re-ID embedding backend |
| `--confidence` | `0.25` | Detection confidence threshold |
| `--reid-threshold` | `0.70` | Re-ID cosine similarity threshold |
| `--skip-phase1` | — | Reuse existing `tracks.jsonl` |
| `--skip-memory` | — | Reuse existing `memory.json` |
| `--skip-graph` | — | Skip scene graph build |
| `--no-overlay` | — | Skip overlay video generation |

### `orion overlay` — re-render overlay

```bash
orion overlay --video path/to/video.mp4 --episode my_demo
orion overlay --video path/to/video.mp4 --episode my_demo --output custom_path.mp4
```

Reads existing `tracks.jsonl` + `scene_graph.jsonl` and re-renders the annotated overlay without re-running detection.

### `orion episodes` — list episodes

```bash
orion episodes          # table view
orion episodes --json   # machine-readable
```

Shows all episodes in `data/examples/episodes/` and `results/`, indicating which have been processed.

### `orion inspect` — episode summary

```bash
orion inspect my_demo
orion inspect my_demo --json
```

Prints: object class breakdown, track count, scene-graph stats (frames / nodes / edges), processing time, and artefact checklist.

### `orion ask` — natural language Q&A

```bash
# Fast file-based (no LLM)
orion ask my_demo -q "what objects were detected?"
orion ask my_demo -q "what spatial relations exist?"
orion ask my_demo -q "how many tracks?"

# Richer synthesis via Ollama (requires: ollama serve)
orion ask my_demo -q "describe the scene" --llm
orion ask my_demo -q "describe the scene" --llm --llm-model llama3.2

# Full graph RAG via Memgraph
orion ask my_demo -q "where did the person interact with the laptop?" --memgraph

# JSON output
orion ask my_demo -q "what objects were detected?" --json
```

### `orion install` — dependency check

```bash
orion install
```

Validates all required Python packages, detects available compute device, and reports model weight readiness. Missing items are listed with fix instructions.

---

## Output Artifacts

After `orion run`, results are written to `results/<episode>/`:

```text
results/<episode>/
├── tracks.jsonl           # Per-detection observations (JSONL, one object per line)
├── run_metadata.json      # Pipeline config, timing, detector info, statistics
├── memory.json            # Long-term Re-ID memory index
├── scene_graph.jsonl      # Per-frame scene graphs (JSONL)
├── graph_summary.json     # Aggregate scene graph statistics
├── cis_edges.jsonl        # CIS causal edge records with per-component scores
└── video_overlay_insights.mp4   # Annotated overlay video
```

> **JSONL convention:** `tracks.jsonl`, `scene_graph.jsonl`, and `cis_edges.jsonl` are JSON Lines files — one JSON object per line. Do not use `json.load()` on these files; iterate line by line with `json.loads(line)`.

### CIS edge record format

```json
{
  "agent_id": 1,
  "patient_id": 3,
  "agent_class": "person",
  "patient_class": "laptop",
  "cis_score": 0.7812,
  "relation_type": "grasps",
  "frame_id": 42,
  "timestamp": 10.5,
  "components": {
    "temporal": 0.9200,
    "spatial": 0.8100,
    "motion": 0.6500,
    "semantic": 0.5300,
    "hand_bonus": 0.3000
  }
}
```

---

## Platform Support

### Apple Silicon (M-series) — recommended

```bash
orion run --video path/to/video.mp4 --device mps --fps 3
```

- MPS is auto-detected; `--device auto` resolves to `mps` on M-series Macs
- If a specific op is unsupported on MPS, fall back with `--device cpu`
- Reduce memory pressure: lower `--fps` or use `--skip-phase1` to skip re-detection

### CUDA (NVIDIA)

```bash
# Verify CUDA visibility first
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"

orion run --video path/to/video.mp4 --device cuda
```

If `cuda.is_available()` is `False`, reinstall PyTorch with the matching CUDA wheel for your driver.

### CPU (any platform)

```bash
orion run --video path/to/video.mp4 --device cpu --fps 1
```

Works everywhere; significantly slower. Use low `--fps` and reuse flags to iterate quickly.

---

## Development Process

Orion was developed iteratively across six research stages:

| Stage | Focus |
|---|---|
| **1 — Perception** | Multi-backend object detection (GroundingDINO, YOLO-World), DINOv3 + V-JEPA2 Re-ID embeddings, EnhancedTracker with adaptive IoU + cosine thresholds |
| **2 — Scene Graph** | Per-frame `SGNode`/`SGEdge` construction, 3D-aware spatial predicates via DepthAnythingV2, temporal `VideoSceneGraph` aggregation |
| **3 — Causal Scoring** | CIS formulation (T + S + M + Se + H), 3D depth gating to suppress foreground/background hallucinations, per-component auditability |
| **4 — Memory** | Long-term identity Re-ID index, zone-based spatial memory, FastVLM visual descriptions for semantic enrichment |
| **5 — Query** | Memgraph persistent graph backend, RAG retrieval pipeline, natural language Q&A over video memory |
| **6 — CLI & Evaluation** | Single-command deterministic CLI, Gemini-assisted validation, benchmark evaluation on PVSG and Action Genome |

The codebase operates entirely on local models — no cloud API calls required in the default configuration. The optional Memgraph and Ollama integrations are additive and gated by explicit flags.

---

## Authors

<table>
  <tr>
    <td align="center"><strong>Riddhiman Rana</strong><br><a href="mailto:riddhiman.rana@gmail.com">riddhiman.rana@gmail.com</a></td>
    <td align="center"><strong>Aryav Semwal</strong><br><a href="mailto:aryavsemwal17@gmail.com">aryavsemwal17@gmail.com</a></td>
    <td align="center"><strong>Yogesh Atluru</strong><br><a href="mailto:yatluru@gmail.com">yatluru@gmail.com</a></td>
  </tr>
</table>

---

## Peer Review & Reception

Orion was submitted to the **ES-Reasoning Workshop at ICLR 2026** and received the following outcome:

> **Decision: Accept (Poster)**  
> *"Solid system paper and the modular and interpretable pipeline, with explicit scene graphs and the Causal Influence Score, fits well with our ES-Reasoning workshop. The zero-shot, modular design is also a practical strength."*  
> — Area Chair

**Reviewer highlights:**

- *"The modular design enables components to be swapped as newer foundation models emerge without retraining the entire pipeline."*
- *"The CIS formulation allows developers to inspect exactly why a relationship was predicted."*
- *"Impressive zero-shot results competitive with supervised methods."*

**Identified areas for future work** (from reviewer feedback):
- Ablation studies on CIS weight sensitivity across datasets and camera setups
- Broader clarification of the scope of "determinism" (relational layer vs. end-to-end)
- Runtime / memory / scalability analysis
- Empirical evidence connecting improved interpretability to downstream decision quality

---

## Citation

```bibtex
@inproceedings{rana2026orion,
  title     = {Orion: A Fully Deterministic and Interpretable Pipeline for
               Video Scene Graph Generation with Explicit Causal Influence Scoring},
  author    = {Rana, Riddhiman and Semwal, Aryav and Atluru, Yogesh},
  booktitle = {ES-Reasoning Workshop, ICLR 2026},
  year      = {2026},
  url       = {https://github.com/riddhimanrana/orion-research}
}
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

