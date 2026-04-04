"""Unified Orion CLI focused on deterministic pipeline execution.

Primary workflow:
  orion run --video /path/to/video.mp4

This command executes Orion end-to-end and writes:
  - tracks.jsonl
  - memory.json
  - scene_graph.jsonl
  - graph_summary.json
  - video_overlay_insights.mp4

to ``results/<episode>/``.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Sequence

logger = logging.getLogger("orion.cli")


def _derive_episode_id(video_path: Path) -> str:
    stem = video_path.stem.strip().lower()
    slug = re.sub(r"[^a-z0-9_-]+", "_", stem).strip("_")
    return slug or "episode"


def _resolve_video_path(video: str) -> Path:
    resolved = Path(video).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Video not found: {resolved}")
    return resolved


def _build_run_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    run_parser = subparsers.add_parser(
        "run",
        help="Run full Orion pipeline (video → tracks → memory → scene graph → overlay)",
    )
    run_parser.add_argument("--video", required=True, help="Path to input video")
    run_parser.add_argument(
        "--episode",
        help="Episode ID for output directory (default: derived from video filename)",
    )

    run_parser.add_argument("--fps", type=float, default=4.0, help="Target FPS for detection sampling")
    run_parser.add_argument("--device", default="auto", choices=["auto", "cuda", "mps", "cpu"])

    run_parser.add_argument(
        "--detector-backend",
        type=str,
        default="dinov3",
        choices=["dinov3", "groundingdino", "openvocab"],
        help="Detection backend for Phase 1",
    )
    run_parser.add_argument(
        "--gdino-model",
        type=str,
        default="IDEA-Research/grounding-dino-tiny",
        choices=["IDEA-Research/grounding-dino-tiny", "IDEA-Research/grounding-dino-base"],
        help="GroundingDINO model when using dinov3/groundingdino",
    )
    run_parser.add_argument("--openvocab-proposer", default="yoloworld_clip", choices=["owl", "yolo_clip", "yoloworld_clip"])
    run_parser.add_argument("--openvocab-vocab", default="lvis", choices=["lvis", "coco", "objects365"])
    run_parser.add_argument("--openvocab-top-k", type=int, default=5)

    run_parser.add_argument("--confidence", type=float, default=0.25, help="Detection confidence threshold")
    run_parser.add_argument("--iou", type=float, default=0.3, help="Tracker IoU threshold")
    run_parser.add_argument("--max-age", type=int, default=30, help="Tracker max age")
    run_parser.add_argument("--min-hits", type=int, default=1, help="Tracker minimum consecutive hits")

    run_parser.add_argument(
        "--embedding-backend",
        type=str,
        default="vjepa2",
        choices=["vjepa2", "clip", "dinov2"],
        help="Re-ID embedding backend",
    )
    run_parser.add_argument("--reid-threshold", type=float, default=0.70)

    run_parser.add_argument("--skip-phase1", action="store_true", help="Reuse existing tracks.jsonl")
    run_parser.add_argument("--skip-memory", action="store_true", help="Reuse existing memory.json")
    run_parser.add_argument("--skip-graph", action="store_true", help="Skip scene graph build")
    run_parser.add_argument("--force-phase1", action="store_true", help="Force regenerate tracks")
    run_parser.add_argument("--force-memory", action="store_true", help="Force regenerate memory")
    run_parser.add_argument("--force-graph", action="store_true", help="Force regenerate scene graph")

    run_parser.add_argument("--no-overlay", action="store_true", help="Skip overlay video generation")
    run_parser.add_argument("--overlay-output", help="Optional explicit overlay output path")

    run_parser.add_argument("--memgraph", action="store_true", help="Export results to Memgraph")
    run_parser.add_argument("--memgraph-host", default="127.0.0.1")
    run_parser.add_argument("--memgraph-port", type=int, default=7687)
    run_parser.add_argument("--memgraph-clear", action="store_true")

    run_parser.add_argument("--json", action="store_true", help="Print final summary as JSON")


def _build_episodes_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ep_parser = subparsers.add_parser(
        "episodes",
        help="List episodes and their result status",
    )
    ep_parser.add_argument("--json", action="store_true", help="Print as JSON")


def _build_inspect_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ins_parser = subparsers.add_parser(
        "inspect",
        help="Show results summary for a processed episode",
    )
    ins_parser.add_argument("episode", help="Episode ID")
    ins_parser.add_argument("--json", action="store_true", help="Print as JSON")


def _build_ask_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ask_parser = subparsers.add_parser(
        "ask",
        help="Ask a natural language question about a processed episode",
    )
    ask_parser.add_argument("episode", help="Episode ID")
    ask_parser.add_argument("-q", "--question", required=True, help="Question to ask")
    ask_parser.add_argument(
        "--llm",
        action="store_true",
        help="Use Ollama LLM for richer synthesis (requires Ollama running)",
    )
    ask_parser.add_argument("--llm-model", default="qwen2.5:14b-instruct-q8_0", help="Ollama model name")
    ask_parser.add_argument(
        "--memgraph",
        action="store_true",
        help="Query Memgraph graph database instead of local files",
    )
    ask_parser.add_argument("--memgraph-host", default="127.0.0.1")
    ask_parser.add_argument("--memgraph-port", type=int, default=7687)
    ask_parser.add_argument("--json", action="store_true", help="Print answer as JSON")


def _build_install_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    subparsers.add_parser(
        "install",
        help="Check that all required dependencies and model weights are available",
    )


def _build_overlay_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    overlay_parser = subparsers.add_parser(
        "overlay",
        help="Render or re-render overlay video from existing results",
    )
    overlay_parser.add_argument("--video", required=True, help="Source video path")
    overlay_parser.add_argument("--episode", required=True, help="Episode ID under results/")
    overlay_parser.add_argument("--output", help="Optional explicit output path for overlay video")
    overlay_parser.add_argument("--overlay-max-relations", type=int, default=4)
    overlay_parser.add_argument("--overlay-message-seconds", type=float, default=1.75)
    overlay_parser.add_argument("--overlay-max-messages", type=int, default=5)
    overlay_parser.add_argument("--overlay-refind-gap", type=int, default=45)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orion",
        description="Orion deterministic pipeline CLI",
        epilog=(
            "Examples:\n"
            "  orion run --video data/examples/test.mp4\n"
            "  orion run --video data/examples/test.mp4 --episode demo --fps 5\n"
            "  orion overlay --video data/examples/test.mp4 --episode demo"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _build_run_parser(subparsers)
    _build_overlay_parser(subparsers)
    _build_episodes_parser(subparsers)
    _build_inspect_parser(subparsers)
    _build_ask_parser(subparsers)
    _build_install_parser(subparsers)
    return parser


def _to_showcase_args(args: argparse.Namespace, video_path: Path, episode: str) -> argparse.Namespace:
    """Create a fully-populated showcase namespace from high-level CLI args."""
    from .run_showcase import build_parser as build_showcase_parser

    showcase_parser = build_showcase_parser()
    showcase_args = showcase_parser.parse_args(["--episode", episode])

    showcase_args.episode = episode
    showcase_args.video = str(video_path)
    showcase_args.fps = args.fps
    showcase_args.device = args.device

    showcase_args.detector_backend = args.detector_backend
    showcase_args.gdino_model = args.gdino_model
    showcase_args.openvocab_proposer = args.openvocab_proposer
    showcase_args.openvocab_vocab = args.openvocab_vocab
    showcase_args.openvocab_top_k = args.openvocab_top_k

    showcase_args.confidence = args.confidence
    showcase_args.iou = args.iou
    showcase_args.max_age = args.max_age
    showcase_args.min_hits = args.min_hits

    showcase_args.embedding_backend = args.embedding_backend
    showcase_args.reid_threshold = args.reid_threshold

    showcase_args.skip_phase1 = args.skip_phase1
    showcase_args.skip_memory = args.skip_memory
    showcase_args.skip_graph = args.skip_graph
    showcase_args.force_phase1 = args.force_phase1
    showcase_args.force_memory = args.force_memory
    showcase_args.force_graph = args.force_graph

    showcase_args.no_overlay = args.no_overlay
    showcase_args.overlay_output = args.overlay_output

    showcase_args.memgraph = args.memgraph
    showcase_args.memgraph_host = args.memgraph_host
    showcase_args.memgraph_port = args.memgraph_port
    showcase_args.memgraph_clear = args.memgraph_clear

    return showcase_args


def _handle_run(args: argparse.Namespace) -> int:
    from .run_showcase import run_pipeline

    video_path = _resolve_video_path(args.video)
    episode = args.episode or _derive_episode_id(video_path)

    showcase_args = _to_showcase_args(args, video_path=video_path, episode=episode)
    summary = run_pipeline(showcase_args)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print("✅ Orion pipeline complete")
        print(f"Episode: {summary['episode']}")
        print(f"Results: {summary['results_dir']}")
        print(f"Scene graph: {Path(summary['results_dir']) / 'scene_graph.jsonl'}")
        if summary.get("overlay"):
            print(f"Overlay: {summary['overlay']}")

    return 0


def _handle_overlay(args: argparse.Namespace) -> int:
    from orion.config import get_results_dir
    from orion.perception.viz_overlay import OverlayOptions, render_insight_overlay

    video_path = _resolve_video_path(args.video)
    results_dir = get_results_dir(args.episode)
    if not results_dir.exists():
        raise FileNotFoundError(
            f"Results directory does not exist for episode '{args.episode}': {results_dir}"
        )

    options = OverlayOptions(
        max_relations=args.overlay_max_relations,
        message_linger_seconds=args.overlay_message_seconds,
        max_state_messages=args.overlay_max_messages,
        gap_frames_for_refind=args.overlay_refind_gap,
        overlay_basename=(Path(args.output).name if args.output else "video_overlay_insights.mp4"),
    )
    output_path = Path(args.output).expanduser().resolve() if args.output else None
    rendered = render_insight_overlay(
        video_path=video_path,
        results_dir=results_dir,
        output_path=output_path,
        options=options,
    )
    print(f"✅ Overlay written to: {rendered}")
    return 0


def _handle_episodes(args: argparse.Namespace) -> int:
    from orion.config import list_results, results_dir, list_episodes

    known_data = set(list_episodes())
    has_results = set(list_results())
    all_ids = sorted(known_data | has_results)

    rows = []
    for ep_id in all_ids:
        in_data = ep_id in known_data
        in_results = ep_id in has_results
        status = "ready" if in_results else "no results"
        rows.append({"episode": ep_id, "has_data": in_data, "has_results": in_results, "status": status})

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        if not rows:
            print("No episodes found.")
            print(f"  data/examples/episodes/  — add episode directories here")
            print(f"  results/                  — processed results appear here")
            return 0
        col_w = max(len(r["episode"]) for r in rows) + 2
        print(f"{'EPISODE':<{col_w}}  STATUS        DATA    RESULTS")
        print("-" * (col_w + 32))
        for r in rows:
            d = "yes" if r["has_data"] else "no "
            rs = "yes" if r["has_results"] else "no "
            print(f"{r['episode']:<{col_w}}  {r['status']:<12}  {d}     {rs}")
        print(f"\n{len(rows)} episode(s) found. Run 'orion run --video <path> --episode <id>' to process.")
    return 0


def _handle_inspect(args: argparse.Namespace) -> int:
    from orion.config import get_results_dir

    results_path = get_results_dir(args.episode)
    if not results_path.exists():
        print(f"No results for episode '{args.episode}'. Run: orion run --video <path> --episode {args.episode}")
        return 1

    summary: dict = {"episode": args.episode, "results_dir": str(results_path)}

    # run_metadata
    meta_file = results_path / "run_metadata.json"
    if meta_file.exists():
        with open(meta_file) as f:
            meta = json.load(f)
        summary["processing_time_seconds"] = meta.get("processing_time_seconds")
        summary["detector"] = meta.get("detector")
        summary.update(meta.get("statistics", {}))

    # object class counts from tracks.jsonl
    tracks_file = results_path / "tracks.jsonl"
    if tracks_file.exists():
        class_counts: dict[str, int] = {}
        frame_ids: set = set()
        total_obs = 0
        with open(tracks_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    cls = obj.get("class_name") or obj.get("category") or "unknown"
                    class_counts[cls] = class_counts.get(cls, 0) + 1
                    if "frame_id" in obj:
                        frame_ids.add(obj["frame_id"])
                    total_obs += 1
                except json.JSONDecodeError:
                    pass
        summary["object_class_counts"] = dict(sorted(class_counts.items(), key=lambda x: -x[1]))
        summary["total_track_observations"] = total_obs
        summary["frames_with_detections"] = len(frame_ids)

    # graph_summary
    graph_file = results_path / "graph_summary.json"
    if graph_file.exists():
        with open(graph_file) as f:
            gs = json.load(f)
        summary["scene_graph"] = {k: gs[k] for k in ("total_frames", "total_nodes", "total_edges") if k in gs}

    # artefact presence
    summary["artefacts"] = {
        name: (results_path / name).exists()
        for name in [
            "tracks.jsonl",
            "memory.json",
            "scene_graph.jsonl",
            "graph_summary.json",
            "video_overlay_insights.mp4",
        ]
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"\nEpisode: {summary['episode']}")
        print(f"Results: {summary['results_dir']}")
        if summary.get("processing_time_seconds") is not None:
            print(f"Processing time: {summary['processing_time_seconds']:.1f}s")
        if summary.get("detector"):
            print(f"Detector: {summary['detector']}")
        print()
        sg = summary.get("scene_graph", {})
        if sg:
            print(f"Scene graph — frames: {sg.get('total_frames',0)}, nodes: {sg.get('total_nodes',0)}, edges: {sg.get('total_edges',0)}")
        print(f"Track observations: {summary.get('total_track_observations', 0)}")
        print(f"Frames with detections: {summary.get('frames_with_detections', 0)}")
        cc = summary.get("object_class_counts", {})
        if cc:
            print("\nObject classes detected:")
            for cls, cnt in cc.items():
                print(f"  {cls}: {cnt}")
        print("\nArtefacts:")
        for name, present in summary.get("artefacts", {}).items():
            mark = "+" if present else "-"
            print(f"  [{mark}] {name}")
    return 0


def _local_ask(episode: str, question: str) -> str:
    """Answer a question from local JSONL result files without an LLM."""
    from orion.config import get_results_dir

    results_path = get_results_dir(episode)
    q = question.lower()

    # collect objects from tracks.jsonl
    tracks_file = results_path / "tracks.jsonl"
    classes: dict[str, int] = {}
    track_ids: set = set()
    if tracks_file.exists():
        with open(tracks_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    cls = obj.get("class_name") or obj.get("category") or "unknown"
                    classes[cls] = classes.get(cls, 0) + 1
                    if "track_id" in obj:
                        track_ids.add(obj["track_id"])
                except json.JSONDecodeError:
                    pass

    # collect relations from scene_graph.jsonl
    predicates: dict[str, int] = {}
    sg_file = results_path / "scene_graph.jsonl"
    if sg_file.exists():
        with open(sg_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    sg = json.loads(line)
                    for edge in sg.get("edges", []):
                        pred = edge.get("predicate", "unknown")
                        predicates[pred] = predicates.get(pred, 0) + 1
                except json.JSONDecodeError:
                    pass

    # simple keyword routing
    if any(w in q for w in ("what object", "what is", "what are", "list object", "objects", "classes", "detected")):
        if not classes:
            return "No objects detected in this episode."
        parts = [f"{cls} ({cnt})" for cls, cnt in sorted(classes.items(), key=lambda x: -x[1])]
        return "Detected objects: " + ", ".join(parts)

    if any(w in q for w in ("how many track", "track count", "unique track")):
        return f"{len(track_ids)} unique tracks."

    if any(w in q for w in ("relation", "near", "on ", "held", "interaction", "edge", "spatial")):
        if not predicates:
            return "No spatial relations found in this episode."
        parts = [f"{p} ({c})" for p, c in sorted(predicates.items(), key=lambda x: -x[1])]
        return "Spatial relations: " + ", ".join(parts)

    if any(w in q for w in ("scene graph", "graph", "node", "frame")):
        from orion.config import get_results_dir
        gfile = results_path / "graph_summary.json"
        if gfile.exists():
            with open(gfile) as f:
                gs = json.load(f)
            return (
                f"Scene graph: {gs.get('total_frames',0)} frames, "
                f"{gs.get('total_nodes',0)} nodes, "
                f"{gs.get('total_edges',0)} edges."
            )
        return "No scene graph built for this episode yet."

    if any(w in q for w in ("overlay", "video", "output", "result")):
        ov = results_path / "video_overlay_insights.mp4"
        return f"Overlay video: {ov}" if ov.exists() else "No overlay video found. Run: orion overlay"

    # fallback — dump summary
    lines = [f"Episode '{episode}' results:"]
    if classes:
        lines.append("Objects: " + ", ".join(f"{k}({v})" for k, v in sorted(classes.items(), key=lambda x: -x[1])))
    if predicates:
        lines.append("Relations: " + ", ".join(f"{k}({v})" for k, v in sorted(predicates.items(), key=lambda x: -x[1])))
    lines.append(f"Tracks: {len(track_ids)}")
    lines.append("Tip: try asking 'what objects were detected?' or 'what relations exist?'")
    return "\n".join(lines)


def _handle_ask(args: argparse.Namespace) -> int:
    from orion.config import get_results_dir

    results_path = get_results_dir(args.episode)
    if not results_path.exists():
        print(f"No results for episode '{args.episode}'. Run: orion run --video <path> --episode {args.episode}")
        return 1

    if args.memgraph:
        # Use full RAG pipeline via Memgraph
        try:
            from orion.query.rag_v2 import OrionRAG
            rag = OrionRAG(host=args.memgraph_host, port=args.memgraph_port)
            use_llm = args.llm
            result = rag.query(args.question, use_llm=use_llm)
            if args.json:
                print(json.dumps({"question": result.question, "answer": result.answer,
                                   "confidence": result.confidence, "query_type": result.query_type}, indent=2))
            else:
                print(f"\nQ: {result.question}")
                print(f"A: {result.answer}")
                if result.confidence:
                    print(f"   [confidence: {result.confidence:.2f}]")
        except Exception as exc:
            print(f"Memgraph query failed: {exc}")
            print("Falling back to local file query...")
            answer = _local_ask(args.episode, args.question)
            print(f"\nQ: {args.question}")
            print(f"A: {answer}")
        return 0

    if args.llm:
        # Use Ollama LLM with local file context
        try:
            import ollama as _ollama  # noqa: F401 — verify available
            from orion.query.reasoning import ReasoningConfig, ReasoningModel

            # Build a context block from local files
            context_lines = [f"Episode: {args.episode}"]
            local_answer = _local_ask(args.episode, args.question)
            context_lines.append(f"Retrieved facts: {local_answer}")

            cfg = ReasoningConfig(model=args.llm_model)
            model = ReasoningModel(cfg)
            answer = model.synthesize_answer(question=args.question, evidence=[])
            if args.json:
                print(json.dumps({"question": args.question, "answer": answer}, indent=2))
            else:
                print(f"\nQ: {args.question}")
                print(f"A: {answer}")
        except ImportError:
            print("Ollama not available. Install with: pip install ollama")
            print("Then ensure Ollama is running: ollama serve")
            return 1
        except Exception as exc:
            print(f"LLM query failed: {exc}")
            return 1
        return 0

    # Default: fast local file-based answer
    answer = _local_ask(args.episode, args.question)
    if args.json:
        print(json.dumps({"question": args.question, "answer": answer}, indent=2))
    else:
        print(f"\nQ: {args.question}")
        print(f"A: {answer}")
    return 0


def _handle_install(args: argparse.Namespace) -> int:  # noqa: ARG001
    """Check dependencies and model weights; report what is missing."""
    import importlib
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent

    print("Orion dependency check\n" + "=" * 40)

    # Core Python packages
    packages = [
        ("torch", "PyTorch — deep learning backbone"),
        ("cv2", "OpenCV — video I/O"),
        ("ultralytics", "Ultralytics YOLO"),
        ("transformers", "HuggingFace Transformers — DINO / CLIP"),
        ("sentence_transformers", "SentenceTransformers — semantic Re-ID"),
        ("numpy", "NumPy"),
        ("scipy", "SciPy — spatial utilities"),
        ("PIL", "Pillow — image I/O"),
    ]
    optional_packages = [
        ("ollama", "Ollama — local LLM Q&A (optional)"),
        ("pymgclient", "pymgclient — Memgraph connectivity (optional)"),
        ("mlx_vlm", "mlx-vlm — local VLM on Apple Silicon (optional)"),
    ]

    all_ok = True
    for pkg, desc in packages:
        try:
            importlib.import_module(pkg)
            print(f"  [+] {desc}")
        except ImportError:
            print(f"  [-] MISSING: {desc}  →  pip install {pkg}")
            all_ok = False

    print()
    for pkg, desc in optional_packages:
        try:
            importlib.import_module(pkg)
            print(f"  [+] {desc}")
        except ImportError:
            print(f"  [~] not installed: {desc}")

    # PyTorch device detection
    print()
    try:
        import torch
        mps_ok = torch.backends.mps.is_available() if hasattr(torch.backends, "mps") else False
        cuda_ok = torch.cuda.is_available()
        if mps_ok:
            print("  [+] Apple Silicon MPS available (recommended)")
        elif cuda_ok:
            print(f"  [+] CUDA available: {torch.cuda.get_device_name(0)}")
        else:
            print("  [~] Running on CPU only — inference will be slow")
    except Exception:
        pass

    # Model weight files
    model_checks = [
        ("models/_torch/", "YOLO / depth model weights (downloaded on first run)"),
    ]
    print()
    for rel_path, desc in model_checks:
        full_path = project_root / rel_path
        if full_path.exists() and any(full_path.iterdir()):
            count = sum(1 for _ in full_path.glob("*.pt"))
            print(f"  [+] {desc} — {count} .pt file(s) found")
        else:
            print(f"  [~] {desc} — will be auto-downloaded on first 'orion run'")

    print()
    if all_ok:
        print("All required dependencies satisfied. Ready to run:")
        print("  orion run --video data/examples/test.mp4")
    else:
        print("Some required packages are missing. Install with:")
        print("  conda env create -f environment.yml && conda activate orion")
    return 0 if all_ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    try:
        if args.command == "run":
            return _handle_run(args)
        if args.command == "overlay":
            return _handle_overlay(args)
        if args.command == "episodes":
            return _handle_episodes(args)
        if args.command == "inspect":
            return _handle_inspect(args)
        if args.command == "ask":
            return _handle_ask(args)
        if args.command == "install":
            return _handle_install(args)
    except Exception as exc:  # pragma: no cover - runtime safety path
        logger.error("%s", exc)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
