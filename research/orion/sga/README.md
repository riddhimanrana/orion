# Scene Graph Anticipation (SGA) Module

Scene Graph Anticipation predicts **future** scene graph relationships from
observed video frames. This module implements the full SGA pipeline for
Action Genome dataset evaluation.

## Pipeline Overview

```
Part 1: Data Loading & Frame Splitting
  └── Load AG annotations, split into observed/future by fraction F

Part 2: Object Detection & Tracking
  └── Detect objects in observed frames using GroundingDINO/YOLO
  └── Track objects across observed frames

Part 3: Observed Scene Graph Generation
  └── Build scene graphs for observed frames (what the model "sees")

Part 4: Future Anticipation
  └── Predict scene graphs for future frames (the actual SGA task)

Part 5: Evaluation
  └── Compute R@K, mR@K against ground truth future relations
```

## Input Fraction (F)

- F = 0.3 → model sees first 30% of frames → predicts last 70% (hardest)
- F = 0.9 → model sees first 90% of frames → predicts last 10% (easiest)

## Testing Modes

1. **AGS** (Action Genome Scenes) - Raw video only (hardest, most realistic)
2. **PGAGS** (Partially Grounded) - GT boxes for observed, no labels
3. **GAGS** (Grounded) - GT boxes + labels for observed (easiest)

## Usage

```python
from orion.sga import ActionGenomeLoader, SGAEvaluator

# Load data
loader = ActionGenomeLoader("data/ag_ground_truth_full.json")
videos = loader.load_videos(max_videos=100)

# Split by fraction
fraction = 0.5  # observe 50%, predict 50%
for video in videos:
    observed, future = video.split_by_fraction(fraction)
    
    # Run your model on observed frames
    predictions = your_model.predict_future(observed)
    
    # Evaluate
    metrics = evaluator.evaluate(predictions, future)
```
