"""Action Genome adapter: convert samples into VideoGraph objects."""

from __future__ import annotations

from typing import Dict, List

from orion.vsgg.datasets import VideoSceneGraphSample
from ..core.types import FrameGraph, ObjectInstance, RelationInstance, VideoGraph


def build_video_graphs(samples: List[VideoSceneGraphSample]) -> Dict[str, VideoGraph]:
    graphs: Dict[str, VideoGraph] = {}
    for sample in samples:
        graph = VideoGraph(video_id=sample.video_id)
        for frame in sample.frames:
            frame_graph = FrameGraph(frame_index=int(frame.frame_index))
            for idx, label in enumerate(frame.labels.tolist()):
                frame_graph.objects.append(ObjectInstance(object_id=idx, label=str(label)))
            for subj_idx, obj_idx, predicate in frame.relations.tolist():
                frame_graph.relations.append(
                    RelationInstance(
                        subject_id=int(subj_idx),
                        predicate=str(predicate),
                        object_id=int(obj_idx),
                        score=1.0,
                    )
                )
            graph.frames[frame.frame_index] = frame_graph
        graphs[sample.video_id] = graph
    return graphs
