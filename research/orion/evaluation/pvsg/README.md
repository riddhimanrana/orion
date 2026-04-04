# PVSG SGG Evaluation

## Expected PVSG layout

```
<data_root>/
  annotations/
    train.json
    val.json
    test.json
  metadata/
    object_classes.txt
    predicate_classes.txt
  videos/
```

## Annotation assumptions

The evaluator expects each annotation entry to contain:

- `video_id` (or `id` / `name`)
- `frames`: list of frames with
  - `frame_index` (or `frame_id` / `frame`)
  - `objects`: list with `label` and optional `bbox`
  - `relations`: list of triplets or dicts

## How evaluation works

For each annotated frame that has a prediction (GT ∩ Pred), predictions are ranked by score and evaluated by:

- **Recall@K**: fraction of GT relations recovered in top K predictions.
- **mR@K**: mean recall across predicate classes.

The evaluator computes per-frame recall and averages across all frames.
