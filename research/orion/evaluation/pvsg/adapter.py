"""PVSG adapter: converts raw annotations into VideoGraph objects."""

from __future__ import annotations

from typing import Dict, List

from ..core.types import FrameGraph, ObjectInstance, RelationInstance, VideoGraph, BBox


def _parse_bbox(entry: Dict[str, object]) -> BBox | None:
    bbox = entry.get("bbox") or entry.get("box")
    if not bbox:
        return None
    return BBox(x1=float(bbox[0]), y1=float(bbox[1]), x2=float(bbox[2]), y2=float(bbox[3]))


def build_video_graph(entry: Dict[str, object]) -> VideoGraph:
    video_id = str(entry.get("video_id") or entry.get("id") or entry.get("name"))
    frames = entry.get("frames") or []

    graph = VideoGraph(video_id=video_id)
    for frame_entry in frames:
        frame_index = int(
            frame_entry.get("frame_index")
            or frame_entry.get("frame_id")
            or frame_entry.get("frame")
            or 0
        )
        frame_graph = FrameGraph(frame_index=frame_index)
        objects = frame_entry.get("objects") or []
        for idx, obj in enumerate(objects):
            label = str(obj.get("label") or obj.get("class") or obj.get("category") or "unknown")
            bbox = _parse_bbox(obj)
            frame_graph.objects.append(ObjectInstance(object_id=idx, label=label, bbox=bbox))

        relations = frame_entry.get("relations") or frame_entry.get("triplets") or []
        for rel in relations:
            if isinstance(rel, dict):
                subj = rel.get("subject") or rel.get("subj") or rel.get("subject_id")
                obj = rel.get("object") or rel.get("obj") or rel.get("object_id")
                pred = rel.get("predicate") or rel.get("relation") or rel.get("pred")
                score = float(rel.get("score", 1.0))
            else:
                subj, obj, pred = rel[:3]
                score = float(rel[3]) if len(rel) > 3 else 1.0
            if subj is None or obj is None or pred is None:
                continue
            frame_graph.relations.append(
                RelationInstance(subject_id=int(subj), predicate=str(pred), object_id=int(obj), score=score)
            )

        graph.frames[frame_index] = frame_graph

    graph.metadata = {"raw": entry}
    return graph
