"""Utilities for exporting annotated scene graph samples from video frames."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2


@dataclass
class GraphSample:
    """Metadata about an exported scene graph sample."""

    frame: int
    image_path: Path
    report_path: Path
    node_count: int
    edge_count: int
    relations: Dict[str, int]


def _centroid(bbox: Sequence[float]) -> Tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (0.5 * (x1 + x2), 0.5 * (y1 + y2))


def _iou(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    aw, ah = max(0.0, ax2 - ax1), max(0.0, ay2 - ay1)
    bw, bh = max(0.0, bx2 - bx1), max(0.0, by2 - by1)
    ua = aw * ah + bw * bh - inter + 1e-8
    return float(inter / ua)


def _horiz_overlap_ratio(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, _, ax2, _ = a
    bx1, _, bx2, _ = b
    left = max(ax1, bx1)
    right = min(ax2, bx2)
    overlap = max(0.0, right - left)
    aw = max(1e-8, ax2 - ax1)
    bw = max(1e-8, bx2 - bx1)
    return float(overlap / min(aw, bw))


def _video_size(video_path: Path) -> Tuple[int, int]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return width, height


def _read_graphs(graph_path: Path) -> List[Dict[str, Any]]:
    graphs: List[Dict[str, Any]] = []
    with graph_path.open("r") as infile:
        for line in infile:
            line = line.strip()
            if line:
                graphs.append(json.loads(line))
    return graphs


def _sample_graphs(graphs: List[Dict[str, Any]], max_samples: int, require_edges: bool = True) -> List[Dict[str, Any]]:
    eligible = [g for g in graphs if (len(g.get("edges", [])) > 0 or not require_edges)]
    if not eligible:
        return []
    if len(eligible) <= max_samples:
        return eligible
    step = max(1, len(eligible) // max_samples)
    return eligible[::step][:max_samples]


def _extract_frame(video_path: Path, frame_id: int) -> Optional[Any]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None
    return frame


def _relation_counts(edges: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for edge in edges:
        rel = edge.get("relation", "unknown")
        counts[rel] = counts.get(rel, 0) + 1
    return counts


def draw_graph_on_frame(frame, graph: Dict[str, Any], frame_wh: Tuple[int, int]) -> Any:
    """Overlay node boxes and relation arrows onto a frame image."""

    img = frame.copy()
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_map = {n.get("memory_id"): n for n in nodes}

    for node in nodes:
        bbox = node.get("bbox")
        if not bbox:
            continue
        x1, y1, x2, y2 = [int(v) for v in bbox]
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"{node.get('memory_id')} ({node.get('class')})"
        cv2.putText(img, label, (x1, max(y1 - 5, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    for edge in edges:
        subj = node_map.get(edge.get("subject"))
        obj = node_map.get(edge.get("object"))
        if not subj or not obj:
            continue
        s_bbox = subj.get("bbox")
        o_bbox = obj.get("bbox")
        if not s_bbox or not o_bbox:
            continue
        cx_s, cy_s = _centroid(s_bbox)
        cx_o, cy_o = _centroid(o_bbox)
        relation = edge.get("relation", "?")
        cv2.arrowedLine(img, (int(cx_s), int(cy_s)), (int(cx_o), int(cy_o)), (255, 0, 0), 2, tipLength=0.2)
        mid_x, mid_y = int(0.5 * (cx_s + cx_o)), int(0.5 * (cy_s + cy_o))
        cv2.putText(img, relation, (mid_x, mid_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    return img


def _write_report(report_path: Path, graph: Dict[str, Any], frame_wh: Tuple[int, int]) -> None:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    diag = math.hypot(frame_wh[0], frame_wh[1]) if frame_wh[0] and frame_wh[1] else 1.0
    node_map = {n.get("memory_id"): n for n in nodes}

    with report_path.open("w") as handle:
        handle.write(f"Frame {graph.get('frame', 0)}\n")
        handle.write(f"{'=' * 60}\n\n")
        handle.write("Nodes:\n")
        for node in nodes:
            handle.write(
                f"  {node.get('memory_id', 'unknown'):10s} ({node.get('class', 'object'):10s})  bbox={node.get('bbox')}\n"
            )
        handle.write(f"\nEdges ({len(edges)}):\n")
        for edge in edges:
            relation = edge.get("relation", "?")
            subj = node_map.get(edge.get("subject"))
            obj = node_map.get(edge.get("object"))
            if not subj or not obj:
                continue
            subj_bbox = subj.get("bbox")
            obj_bbox = obj.get("bbox")
            if not subj_bbox or not obj_bbox:
                continue
            iou = _iou(subj_bbox, obj_bbox)
            cx_s, cy_s = _centroid(subj_bbox)
            cx_o, cy_o = _centroid(obj_bbox)
            dist = math.hypot(cx_s - cx_o, cy_s - cy_o)
            norm_dist = dist / diag if diag > 0 else 0.0
            horiz_overlap = _horiz_overlap_ratio(subj_bbox, obj_bbox)
            vgap = abs(obj_bbox[1] - subj_bbox[3]) / max(1.0, frame_wh[1])
            handle.write(f"  {edge.get('subject'):10s} --[{relation:8s}]--> {edge.get('object'):10s}\n")
            handle.write(f"    Subject bbox: {subj_bbox}\n")
            handle.write(f"    Object bbox:  {obj_bbox}\n")
            handle.write(
                f"    Metrics: IoU={iou:.3f}, norm_dist={norm_dist:.3f}, h_overlap={horiz_overlap:.3f}, vgap={vgap:.3f}\n\n"
            )


def export_graph_samples(
    graph_path: Path,
    video_path: Path,
    output_dir: Path,
    max_samples: int = 10,
    require_edges: bool = True,
) -> List[GraphSample]:
    """Export annotated samples for scene graph inspection."""

    if not graph_path.exists():
        raise FileNotFoundError(f"scene_graph.jsonl not found: {graph_path}")
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    graphs = _read_graphs(graph_path)
    selected = _sample_graphs(graphs, max_samples=max_samples, require_edges=require_edges)
    if not selected:
        return []

    frame_wh = _video_size(video_path)
    exports: List[GraphSample] = []

    for graph in selected:
        frame_id = int(graph.get("frame", 0))
        frame = _extract_frame(video_path, frame_id)
        if frame is None:
            continue
        annotated = draw_graph_on_frame(frame, graph, frame_wh)
        image_path = output_dir / f"frame_{frame_id:06d}.jpg"
        report_path = output_dir / f"frame_{frame_id:06d}.txt"
        cv2.imwrite(str(image_path), annotated)
        _write_report(report_path, graph, frame_wh)
        exports.append(
            GraphSample(
                frame=frame_id,
                image_path=image_path,
                report_path=report_path,
                node_count=len(graph.get("nodes", [])),
                edge_count=len(graph.get("edges", [])),
                relations=_relation_counts(graph.get("edges", [])),
            )
        )

    return exports