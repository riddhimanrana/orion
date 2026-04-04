# Action Genome SGA Evaluation

## Expected Action Genome layout

```
<data_root>/
  object_bbox_and_relationship.pkl
  frame_list.txt
  object_classes.txt
  relationship_classes.txt
```

This evaluator wraps `orion.vsgg.datasets.ActionGenomeSceneGraphDataset` and groups
frames into video sequences.

## How SGA evaluation works

Given a video with `T` frames and observation fraction `F`:

1. Observed prefix length = `floor(F * T)` (at least 1 frame).
2. Evaluation occurs only on future frames (index > prefix) that have predictions (GT ∩ Pred).
3. For each future frame, compute Recall@K and mR@K.
4. Average across future frames and then across videos.

This matches the HyperGLM SGA protocol where predictions are evaluated on
future segments only.
