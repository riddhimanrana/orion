#!/usr/bin/env python3
"""End-to-end perception showcase with overlay + Memgraph export."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from orion.config import ensure_results_dir, get_episode_video_path

logger = logging.getLogger("orion.showcase")


def _resolve_video_path(args: argparse.Namespace) -> Path:
    if args.video:
        return Path(args.video)
    video = get_episode_video_path(args.episode)
    if video is None:
        raise FileNotFoundError(
            f"Could not locate video for episode '{args.episode}'. Provide --video explicitly."
        )
    return video


def _phase1(args: argparse.Namespace, video_path: Path, results_dir: Path) -> Dict:
    from orion.cli.run_tracks import process_video_to_tracks

    tracks_path = results_dir / "tracks.jsonl"
    meta_path = results_dir / "run_metadata.json"
    if args.skip_phase1:
        if not tracks_path.exists():
            raise FileNotFoundError("tracks.jsonl missing; cannot skip Phase 1")
        if meta_path.exists():
            return json.loads(meta_path.read_text())
        return {}

    if tracks_path.exists() and not args.force_phase1:
        logger.info("[Phase 1] Reusing existing tracks in %s", results_dir)
        if meta_path.exists():
            return json.loads(meta_path.read_text())
        return {}

    logger.info("[Phase 1] Running detection + tracking")
    return process_video_to_tracks(
        video_path=str(video_path),
        episode_id=args.episode,
        target_fps=args.fps,
        detector_backend=args.detector_backend,
        gdino_model=args.gdino_model,
        openvocab_proposer=getattr(args, 'openvocab_proposer', 'yoloworld_clip'),
        openvocab_vocab=getattr(args, 'openvocab_vocab', 'lvis'),
        openvocab_top_k=getattr(args, 'openvocab_top_k', 5),
        confidence_threshold=args.confidence,
        iou_threshold=args.iou,
        max_age=args.max_age,
        min_hits=args.min_hits,
        device=args.device,
        save_viz=args.save_viz,
        enable_hand_detector=args.detect_hands,
        hand_max_hands=args.hand_max,
        hand_detection_confidence=args.hand_det_conf,
        hand_tracking_confidence=args.hand_track_conf,
        enable_3d=args.enable_3d,
        enable_cis=(not args.disable_cis),
        cis_threshold=args.cis_threshold,
        cis_compute_every=args.cis_compute_every,
        cis_depth_gate_mm=args.cis_depth_gate_mm,
    )


def _phase2(args: argparse.Namespace, video_path: Path, results_dir: Path) -> Dict:
    from orion.perception.reid.matcher import build_memory_from_tracks

    memory_path = results_dir / "memory.json"
    if args.skip_memory:
        if not memory_path.exists():
            raise FileNotFoundError("memory.json missing; cannot skip Phase 2")
        return json.loads(memory_path.read_text())

    if memory_path.exists() and not args.force_memory:
        logger.info("[Phase 2] Reusing memory.json")
        return json.loads(memory_path.read_text())

    tracks_path = results_dir / "tracks.jsonl"
    if not tracks_path.exists():
        raise FileNotFoundError("tracks.jsonl missing; run Phase 1 first")

    # V-JEPA2 is the only Re-ID backend
    from orion.managers.model_manager import ModelManager
    mm = ModelManager.get_instance()
    logger.info(f"[Phase 2] Building memory.json (Re-ID backend: {args.embedding_backend})")
    
    build_memory_from_tracks(
        episode_id=args.episode,
        video_path=video_path,
        tracks_path=tracks_path,
        results_dir=results_dir,
        cosine_threshold=args.reid_threshold,
        max_crops_per_track=args.max_crops_per_track,
        reid_batch_size=args.reid_batch_size,
        class_thresholds=None,
        embedding_backend=args.embedding_backend,
    )
    return json.loads(memory_path.read_text())


def _phase3_graph(args: argparse.Namespace, results_dir: Path) -> Dict:
    from orion.graph import (
        build_graph_summary,
        build_scene_graphs,
        load_memory,
        load_tracks,
        save_graph_summary,
        save_scene_graphs,
    )

    graph_path = results_dir / "scene_graph.jsonl"
    summary_path = results_dir / "graph_summary.json"
    if args.skip_graph:
        if summary_path.exists():
            return json.loads(summary_path.read_text())
        # Return empty summary if skipping and no graph exists
        logger.info("[Graph] Skipped (--skip-graph)")
        return {"nodes": 0, "edges": 0, "skipped": True}

    if graph_path.exists() and summary_path.exists() and not args.force_graph:
        logger.info("[Graph] Reusing existing scene graph")
        return json.loads(summary_path.read_text())

    memory_path = results_dir / "memory.json"
    tracks_path = results_dir / "tracks.jsonl"
    if not memory_path.exists() or not tracks_path.exists():
        raise FileNotFoundError("memory.json or tracks.jsonl missing for graph stage")

    memory = load_memory(memory_path)
    tracks = load_tracks(tracks_path)
    logger.info("[Graph] Building scene graph (%d tracks)", len(tracks))
    graphs = build_scene_graphs(
        memory,
        tracks,
        relations=args.relations,
        near_dist_norm=args.near_dist,
        on_h_overlap=args.on_overlap,
        on_vgap_norm=args.on_vgap,
        on_subj_overlap_min=args.on_subj_overlap,
        on_subj_within_obj=args.on_subj_within,
        on_small_subject_area=args.on_small_area,
        on_small_overlap=args.on_small_overlap,
        on_small_vgap=args.on_small_vgap,
        held_by_iou=args.held_iou,
        near_small_dist_norm=args.near_small_dist,
        near_small_area=args.near_small_area,
        exclude_on_pairs=[tuple(pair.split(":")) for pair in (args.exclude_on_pair or [])],
        use_pose_for_held=args.use_pose_held,
        pose_hand_dist=args.pose_hand_dist,
        enable_class_filtering=not args.no_class_filter,
        # Temporal smoothing (Deep Research v3)
        enable_temporal_smoothing=args.temporal_smoothing,
        temporal_window_size=args.temporal_window,
        temporal_near_threshold=args.temporal_near_thresh,
        temporal_on_threshold=args.temporal_on_thresh,
        temporal_held_by_threshold=args.temporal_held_thresh,
    )
    save_scene_graphs(graphs, graph_path)
    summary = build_graph_summary(graphs)
    save_graph_summary(summary, summary_path)
    return summary


def _render_overlay(args: argparse.Namespace, video_path: Path, results_dir: Path) -> Optional[Path]:
    if args.no_overlay:
        return None
    from orion.perception.viz_overlay import OverlayOptions, render_insight_overlay

    logger.info("[Overlay] Rendering insight overlay")
    options = OverlayOptions(
        max_relations=args.overlay_max_relations,
        message_linger_seconds=args.overlay_message_seconds,
        max_state_messages=args.overlay_max_messages,
        gap_frames_for_refind=args.overlay_refind_gap,
        overlay_basename=(Path(args.overlay_output).name if args.overlay_output else "video_overlay_insights.mp4"),
    )
    output_path = Path(args.overlay_output) if args.overlay_output else None
    return render_insight_overlay(video_path=video_path, results_dir=results_dir, output_path=output_path, options=options)


def _export_memgraph(args: argparse.Namespace, video_path: Path, results_dir: Path) -> Optional[Any]:
    if not args.memgraph:
        return None
    from orion.graph.backends.exporter import export_results_to_memgraph

    logger.info("[Memgraph] Exporting results to %s:%d", args.memgraph_host, args.memgraph_port)
    return export_results_to_memgraph(
        results_dir=results_dir,
        video_path=video_path,
        host=args.memgraph_host,
        port=args.memgraph_port,
        clear_existing=args.memgraph_clear,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run perception showcase on a video")
    parser.add_argument("--episode", required=True, help="Episode ID for saving results")
    parser.add_argument("--video", help="Override video path (defaults to episode video)")
    parser.add_argument("--fps", type=float, default=4.0, help="Target FPS for detection sampling")
    # Detector backend selection (mirrors orion.cli.run_tracks)
    parser.add_argument(
        "--detector-backend",
        type=str,
        default="dinov3",
        choices=["dinov3", "groundingdino", "openvocab"],
        help="Detection backend for Phase 1 (default: dinov3)",
    )
    parser.add_argument(
        "--gdino-model",
        type=str,
        default="IDEA-Research/grounding-dino-tiny",
        choices=["IDEA-Research/grounding-dino-tiny", "IDEA-Research/grounding-dino-base"],
        help="GroundingDINO model ID (used for --detector-backend groundingdino|dinov3)",
    )
    
    # OpenVocab backend settings (propose→label architecture)
    parser.add_argument(
        "--openvocab-proposer",
        type=str,
        default="yoloworld_clip",
        choices=["owl", "yolo_clip", "yoloworld_clip"],
        help="OpenVocab proposer backend (default: yoloworld_clip)",
    )
    parser.add_argument(
        "--openvocab-vocab",
        type=str,
        default="lvis",
        choices=["lvis", "coco", "objects365"],
        help="Vocabulary bank preset for openvocab backend",
    )
    parser.add_argument(
        "--openvocab-top-k",
        type=int,
        default=5,
        help="Number of label hypotheses per detection (openvocab backend)",
    )
    parser.add_argument(
        "--disable-cis",
        action="store_true",
        help="Disable CIS edge extraction",
    )
    parser.add_argument(
        "--cis-threshold",
        type=float,
        default=0.50,
        help="Minimum CIS score to persist (default: 0.50)",
    )
    parser.add_argument(
        "--cis-compute-every",
        type=int,
        default=5,
        help="Compute CIS edges every N frames (default: 5)",
    )
    parser.add_argument(
        "--cis-depth-gate-mm",
        type=float,
        default=2000.0,
        help="Depth gating threshold in mm (default: 2000.0)",
    )

    parser.add_argument("--confidence", type=float, default=0.25, help="Detection confidence threshold")
    parser.add_argument("--iou", type=float, default=0.3, help="Tracker IoU threshold")
    parser.add_argument("--max-age", type=int, default=30, help="Tracker max age")
    parser.add_argument(
        "--min-hits",
        type=int,
        default=1,
        help="Min consecutive hits before a track is emitted (default: 1)",
    )
    # Default to auto so this works both on Apple Silicon (MPS) and Linux GPUs (CUDA)
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "mps", "cpu"])
    parser.add_argument("--save-viz", action="store_true", help="Persist detector debug outputs")
    parser.add_argument("--detect-hands", action="store_true")
    parser.add_argument("--hand-max", type=int, default=2)
    parser.add_argument("--hand-det-conf", type=float, default=0.5)
    parser.add_argument("--hand-track-conf", type=float, default=0.3)
    parser.add_argument("--enable-3d", action="store_true", help="Enable 3D perception (Depth/SLAM)")
    parser.add_argument(
        "--embedding-backend",
        type=str,
        default="vjepa2",
        choices=["vjepa2", "clip", "dinov2"],
        help="Embedding backend for Re-ID (default: vjepa2)"
    )
    parser.add_argument("--reid-threshold", type=float, default=0.70)
    parser.add_argument("--max-crops-per-track", type=int, default=5)
    parser.add_argument(
        "--reid-batch-size",
        type=int,
        default=8,
        help="Batch size for V-JEPA2 Re-ID embedding in Phase 2",
    )

    parser.add_argument("--skip-phase1", action="store_true")
    parser.add_argument("--skip-memory", action="store_true")
    parser.add_argument("--skip-graph", action="store_true")
    parser.add_argument("--force-phase1", action="store_true")
    parser.add_argument("--force-memory", action="store_true")
    parser.add_argument("--force-graph", action="store_true")

    parser.add_argument("--relations", nargs="+", default=["near", "on", "held_by"])
    parser.add_argument("--near-dist", type=float, default=0.08)
    parser.add_argument("--near-small-dist", type=float, default=0.06)
    parser.add_argument("--near-small-area", type=float, default=0.05)
    parser.add_argument("--on-overlap", type=float, default=0.3)
    parser.add_argument("--on-vgap", type=float, default=0.02)
    parser.add_argument("--on-subj-overlap", type=float, default=0.5)
    parser.add_argument("--on-subj-within", type=float, default=0.0)
    parser.add_argument("--on-small-area", type=float, default=0.05)
    parser.add_argument("--on-small-overlap", type=float, default=0.15)
    parser.add_argument("--on-small-vgap", type=float, default=0.06)
    parser.add_argument("--held-iou", type=float, default=0.3)
    parser.add_argument("--pose-hand-dist", type=float, default=0.03)
    parser.add_argument("--use-pose-held", action="store_true")
    parser.add_argument("--no-class-filter", action="store_true")
    parser.add_argument("--exclude-on-pair", action="append", help="Exclude class pair from 'on' relation (classA:classB)")
    
    # Temporal smoothing (Deep Research v3)
    parser.add_argument("--temporal-smoothing", action="store_true", help="Enable temporal smoothing for scene graphs")
    parser.add_argument("--temporal-window", type=int, default=5, help="Rolling window size for temporal smoothing")
    parser.add_argument("--temporal-near-thresh", type=float, default=0.4, help="Threshold for 'near' relation")
    parser.add_argument("--temporal-on-thresh", type=float, default=0.6, help="Threshold for 'on' relation")
    parser.add_argument("--temporal-held-thresh", type=float, default=0.7, help="Threshold for 'held_by' relation")

    parser.add_argument("--no-overlay", action="store_true", help="Skip overlay rendering")
    parser.add_argument("--overlay-output", help="Explicit overlay path")
    parser.add_argument("--overlay-message-seconds", type=float, default=1.75)
    parser.add_argument("--overlay-max-messages", type=int, default=5)
    parser.add_argument("--overlay-refind-gap", type=int, default=45)
    parser.add_argument("--overlay-max-relations", type=int, default=4)

    parser.add_argument("--memgraph", action="store_true", help="Write outputs to Memgraph")
    parser.add_argument("--memgraph-host", default="127.0.0.1")
    parser.add_argument("--memgraph-port", type=int, default=7687)
    parser.add_argument("--memgraph-clear", action="store_true", help="Clear graph before ingesting")
    return parser


def run_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    """Run the full showcase pipeline and return a machine-readable summary."""
    results_dir = ensure_results_dir(args.episode)
    video_path = _resolve_video_path(args)

    phase1_meta = _phase1(args, video_path, results_dir)
    memory_data = _phase2(args, video_path, results_dir)
    graph_summary = _phase3_graph(args, results_dir)
    overlay_path = _render_overlay(args, video_path, results_dir)
    memgraph_result = _export_memgraph(args, video_path, results_dir)

    summary: Dict[str, Any] = {
        "episode": args.episode,
        "video": str(video_path),
        "results_dir": str(results_dir),
        "tracks": phase1_meta.get("statistics", {}),
        "memory_objects": len(memory_data.get("objects", [])),
        "graph": graph_summary,
        "overlay": str(overlay_path) if overlay_path else None,
        "memgraph": None,
    }

    if memgraph_result is not None:
        summary["memgraph"] = {
            "observations_written": memgraph_result.observations_written,
            "relations_written": memgraph_result.relations_written,
            "host": memgraph_result.output_host,
            "port": memgraph_result.output_port,
        }

    logger.info("\n=== SHOWCASE SUMMARY ===")
    logger.info("Episode: %s", summary["episode"])
    logger.info("Video: %s", summary["video"])

    tracks_stats = summary.get("tracks", {})
    if tracks_stats:
        logger.info(
            "Tracks: %s frames, %s unique",
            tracks_stats.get("frames_processed"),
            tracks_stats.get("unique_tracks"),
        )

    logger.info("Memory objects: %d", summary["memory_objects"])
    logger.info(
        "Graph: frames=%s edges/frame=%.2f",
        graph_summary.get("total_frames"),
        graph_summary.get("avg_edges_per_frame", 0.0),
    )

    if overlay_path:
        logger.info("Overlay: %s", overlay_path)

    if memgraph_result is not None:
        logger.info(
            "Memgraph: %d observations, %d relations → %s:%d",
            memgraph_result.observations_written,
            memgraph_result.relations_written,
            memgraph_result.output_host,
            memgraph_result.output_port,
        )

    return summary


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    run_pipeline(args)
if __name__ == "__main__":
    main()
