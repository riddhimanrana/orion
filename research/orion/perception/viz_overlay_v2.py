"""
Simplified Video Overlay Renderer v2
=====================================

Renders detections directly onto sampled frames, outputting at detection FPS.
This avoids frame sync issues by only rendering frames that have detections.

Key improvements:
- Outputs at detection FPS (e.g., 5 FPS) not source FPS (30 FPS)
- Direct frame_id matching (no interpolation needed)
- Stable track visualization with persistent colors
- Clean, minimal annotation style
"""

from __future__ import annotations

import json
import logging
import colorsys
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class OverlayConfig:
    """Configuration for overlay rendering."""
    output_fps: float = 5.0  # Output video FPS (should match detection FPS)
    show_confidence: bool = True
    show_track_id: bool = True
    show_memory_id: bool = True
    box_thickness: int = 2
    font_scale: float = 0.6
    label_padding: int = 5
    show_frame_info: bool = True
    output_filename: str = "overlay_v2.mp4"
    debug_jsonl_filename: Optional[str] = None


def generate_color(seed: int) -> Tuple[int, int, int]:
    """Generate a consistent color for a given seed (track_id)."""
    hue = (seed * 37) % 360 / 360.0  # Golden ratio for color spacing
    saturation = 0.7
    value = 0.9
    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
    return (int(b * 255), int(g * 255), int(r * 255))  # BGR for OpenCV


class SimpleOverlayRenderer:
    """
    Renders detection overlays by extracting only sampled frames from source video.
    
    This approach:
    1. Reads tracks.jsonl to get all detections with their frame_ids
    2. Groups detections by frame_id
    3. Seeks to each frame_id in the source video
    4. Draws detections and writes to output at detection FPS
    """
    
    def __init__(
        self,
        video_path: Path,
        results_dir: Path,
        config: Optional[OverlayConfig] = None,
    ):
        self.video_path = Path(video_path)
        self.results_dir = Path(results_dir)
        self.config = config or OverlayConfig()
        
        self.tracks_path = self.results_dir / "tracks.jsonl"
        self.memory_path = self.results_dir / "memory.json"
        
        if not self.tracks_path.exists():
            raise FileNotFoundError(f"tracks.jsonl not found in {results_dir}")
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        # Load data
        self.detections_by_frame: Dict[int, List[Dict]] = defaultdict(list)
        self.track_colors: Dict[int, Tuple[int, int, int]] = {}
        self.track_to_memory: Dict[int, str] = {}
        self.memory_info: Dict[str, Dict] = {}
        
        self._load_tracks()
        self._load_memory()
        
        logger.info(f"Loaded {sum(len(v) for v in self.detections_by_frame.values())} detections "
                    f"across {len(self.detections_by_frame)} frames")
    
    def _load_tracks(self) -> None:
        """Load tracks and group by frame_id."""
        with open(self.tracks_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                det = json.loads(line)
                frame_id = det.get("frame_id")
                if frame_id is not None:
                    self.detections_by_frame[frame_id].append(det)
                    
                    # Assign consistent color per track
                    track_id = det.get("track_id")
                    if track_id is not None and track_id not in self.track_colors:
                        self.track_colors[track_id] = generate_color(track_id)
    
    def _load_memory(self) -> None:
        """Load memory.json if available to map tracks to memory IDs."""
        if not self.memory_path.exists():
            return
            
        try:
            with open(self.memory_path) as f:
                data = json.load(f)
            
            for obj in data.get("objects", []):
                mem_id = obj.get("memory_id")
                if not mem_id:
                    continue
                self.memory_info[mem_id] = obj
                
                # Map tracks to memory
                for segment in obj.get("appearance_history", []):
                    track_id = segment.get("track_id")
                    if track_id is not None:
                        self.track_to_memory[int(track_id)] = mem_id
        except Exception as e:
            logger.warning(f"Failed to load memory.json: {e}")
    
    def _draw_detection(
        self,
        frame: np.ndarray,
        det: Dict,
        frame_h: int,
        frame_w: int,
    ) -> None:
        """Draw a single detection on the frame."""
        bbox = det.get("bbox_2d", det.get("bbox"))
        if not bbox or len(bbox) != 4:
            return

        # Detections for portrait videos are often produced on frames rotated 90° CCW
        # (see FrameObserver), which yields bbox coordinates in a landscape space
        # (rot_w = orig_h, rot_h = orig_w). If we render on the original portrait
        # frames, we must un-rotate those coordinates.
        x1, y1, x2, y2 = map(float, bbox)

        is_portrait = frame_h > frame_w
        looks_rotated = is_portrait and (max(x1, x2) > frame_w + 2 or max(y1, y2) > frame_h + 2)
        if looks_rotated:
            # Inverse mapping of 90° CCW rotation:
            # original -> rotated: x' = y, y' = (W-1) - x
            # rotated  -> original: x = (W-1) - y', y = x'
            # Use original W (frame_w) for the inverse.
            orig_w = frame_w
            corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
            unrot = []
            for xr, yr in corners:
                xo = (orig_w - 1) - yr
                yo = xr
                unrot.append((xo, yo))
            xs = [p[0] for p in unrot]
            ys = [p[1] for p in unrot]
            x1, x2 = min(xs), max(xs)
            y1, y2 = min(ys), max(ys)

        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
        
        # Clamp to frame bounds
        x1 = max(0, min(x1, frame_w - 1))
        x2 = max(0, min(x2, frame_w - 1))
        y1 = max(0, min(y1, frame_h - 1))
        y2 = max(0, min(y2, frame_h - 1))
        
        if x2 <= x1 or y2 <= y1:
            return
        
        track_id = det.get("track_id", -1)
        color = self.track_colors.get(track_id, (128, 128, 128))
        
        # Draw bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, self.config.box_thickness)
        
        # Build label
        class_name = det.get("class_name", "object")
        label_parts = [class_name]
        
        if self.config.show_confidence:
            conf = det.get("confidence", 0)
            label_parts.append(f"{conf:.2f}")
        
        if self.config.show_track_id and track_id >= 0:
            label_parts.append(f"T{track_id}")
        
        if self.config.show_memory_id and track_id in self.track_to_memory:
            mem_id = self.track_to_memory[track_id]
            label_parts.append(f"M{mem_id[-4:]}")

        # DepthAnythingV3 depth stats (if present in tracks)
        depth_mm = det.get("depth_mm")
        if depth_mm is not None:
            try:
                depth_m = float(depth_mm) / 1000.0
                if np.isfinite(depth_m) and depth_m > 0:
                    label_parts.append(f"Z{depth_m:.2f}m")
            except Exception:
                pass
        
        label = " | ".join(label_parts)
        
        # Draw label background
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = self.config.font_scale
        thickness = 2
        (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)
        
        label_y = y1 - self.config.label_padding
        if label_y - text_h < 0:
            label_y = y2 + text_h + self.config.label_padding
        
        # Background rectangle
        cv2.rectangle(
            frame,
            (x1, label_y - text_h - baseline),
            (x1 + text_w + 2 * self.config.label_padding, label_y + baseline),
            color,
            -1,
        )
        
        # Text (black for contrast)
        cv2.putText(
            frame,
            label,
            (x1 + self.config.label_padding, label_y),
            font,
            font_scale,
            (0, 0, 0),
            thickness,
            cv2.LINE_AA,
        )
    
    def _draw_frame_info(
        self,
        frame: np.ndarray,
        frame_id: int,
        timestamp: float,
        num_detections: int,
    ) -> None:
        """Draw frame info overlay in corner."""
        if not self.config.show_frame_info:
            return
        
        info_lines = [
            f"Frame: {frame_id}",
            f"Time: {timestamp:.2f}s",
            f"Detections: {num_detections}",
        ]
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1
        line_height = 20
        padding = 10
        
        # Calculate panel size
        max_width = max(cv2.getTextSize(line, font, font_scale, thickness)[0][0] for line in info_lines)
        panel_w = max_width + 2 * padding
        panel_h = len(info_lines) * line_height + padding
        
        # Draw semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (5, 5), (5 + panel_w, 5 + panel_h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        
        # Draw text
        y = padding + 15
        for line in info_lines:
            cv2.putText(frame, line, (padding, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
            y += line_height
    
    def render(self) -> Path:
        """
        Render the overlay video.
        
        Processes frames at the detection sampling cadence, outputting at detection FPS.
        This renders a "full" overlay timeline including sampled frames with 0 detections.
        """
        output_path = self.results_dir / self.config.output_filename
        
        # Open source video
        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Failed to open video: {self.video_path}")
        
        # Get video properties
        source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        logger.info(f"Source video: {frame_w}x{frame_h} @ {source_fps:.1f} FPS, {total_frames} frames")
        
        # Get sorted frame IDs that have detections
        detection_frame_ids = sorted(self.detections_by_frame.keys())
        if not detection_frame_ids:
            raise RuntimeError("No detections found to render")

        # Infer the sampling interval (FrameObserver uses an integer frame step).
        diffs = [b - a for a, b in zip(detection_frame_ids, detection_frame_ids[1:]) if b > a]
        if diffs:
            sample_interval, _ = Counter(diffs).most_common(1)[0]
            sample_interval = max(1, int(sample_interval))
        else:
            sample_interval = 1

        sampled_frame_ids = list(range(0, total_frames, sample_interval))

        logger.info(f"Rendering {len(sampled_frame_ids)} sampled frames (interval={sample_interval})")
        logger.info(f"Detection frame range: {detection_frame_ids[0]} to {detection_frame_ids[-1]}")
        
        # Initialize video writer at detection FPS
        output_fps = self.config.output_fps
        codecs = ["avc1", "mp4v", "XVID"]
        writer = None
        
        for codec in codecs:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            writer = cv2.VideoWriter(str(output_path), fourcc, output_fps, (frame_w, frame_h))
            if writer.isOpened():
                logger.info(f"Using codec: {codec}, output FPS: {output_fps}")
                break
            writer.release()
            writer = None
        
        if writer is None:
            raise RuntimeError("Failed to create video writer")
        
        debug_f = None
        if self.config.debug_jsonl_filename:
            debug_path = self.results_dir / self.config.debug_jsonl_filename
            debug_f = open(debug_path, "w")
            logger.info(f"Writing overlay debug JSONL → {debug_path}")

        try:
            frames_written = 0
            sampled_set = set(sampled_frame_ids)
            sampled_count = len(sampled_frame_ids)
            frame_idx = 0

            debug_max_abs_delta_ms = 0.0
            debug_delta_ms_values: List[float] = []

            # Sequential decode to avoid codec seek drift from cap.set().
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx in sampled_set:
                    detections = self.detections_by_frame.get(frame_idx, [])
                    track_ts = (
                        float(detections[0].get("timestamp"))
                        if detections and detections[0].get("timestamp") is not None
                        else None
                    )
                    computed_ts = frame_idx / source_fps
                    timestamp = track_ts if track_ts is not None else computed_ts

                    # Cheap frame fingerprint to validate decode determinism (iterative debug)
                    try:
                        small = cv2.resize(frame, (64, 64), interpolation=cv2.INTER_AREA)
                        frame_md5 = hashlib.md5(small.tobytes()).hexdigest()
                    except Exception:
                        frame_md5 = None

                    # Draw all detections
                    for det in detections:
                        self._draw_detection(frame, det, frame_h, frame_w)

                    # Draw frame info
                    self._draw_frame_info(frame, frame_idx, timestamp, len(detections))

                    # Write frame
                    writer.write(frame)
                    frames_written += 1

                    if debug_f is not None:
                        pos_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                        pos_frames = cap.get(cv2.CAP_PROP_POS_FRAMES)
                        delta_ms = (track_ts - computed_ts) * 1000.0 if track_ts is not None else None
                        if delta_ms is not None and np.isfinite(delta_ms):
                            debug_delta_ms_values.append(float(delta_ms))
                            debug_max_abs_delta_ms = max(debug_max_abs_delta_ms, abs(float(delta_ms)))
                        debug_f.write(
                            json.dumps(
                                {
                                    "requested_frame_id": int(frame_idx),
                                    "decoded_frame_idx": int(frame_idx),
                                    "decoded_pos_frames_next": float(pos_frames) if pos_frames is not None else None,
                                    "decoded_pos_msec": float(pos_msec) if pos_msec is not None else None,
                                    "source_fps": float(source_fps),
                                    "computed_timestamp_sec": float(computed_ts),
                                    "track_timestamp_sec": float(track_ts) if track_ts is not None else None,
                                    "delta_ms": float(delta_ms) if delta_ms is not None else None,
                                    "num_detections": int(len(detections)),
                                    "frame_md5_64x64": frame_md5,
                                }
                            )
                            + "\n"
                        )

                    if frames_written % 50 == 0:
                        logger.info(f"  Rendered {frames_written}/{sampled_count} frames")

                    # Early exit when we've written the full sampled timeline.
                    if frames_written >= sampled_count:
                        break

                frame_idx += 1

        finally:
            cap.release()
            writer.release()
            if debug_f is not None:
                debug_f.close()
        
        duration = frames_written / output_fps
        logger.info(f"✓ Wrote {frames_written} frames to {output_path}")
        logger.info(f"  Output: {frame_w}x{frame_h} @ {output_fps} FPS, {duration:.1f}s duration")

        if self.config.debug_jsonl_filename and debug_delta_ms_values:
            arr = np.array(debug_delta_ms_values, dtype=np.float32)
            logger.info(
                "Overlay debug timing: max_abs_delta_ms=%.1f, p50=%.1f, p95=%.1f",
                float(debug_max_abs_delta_ms),
                float(np.percentile(arr, 50)),
                float(np.percentile(arr, 95)),
            )
        
        return output_path


def render_simple_overlay(
    video_path: Path,
    results_dir: Path,
    output_fps: float = 5.0,
    output_filename: str = "overlay_v2.mp4",
) -> Path:
    """Convenience function for rendering simple overlay."""
    config = OverlayConfig(output_fps=output_fps, output_filename=output_filename)
    renderer = SimpleOverlayRenderer(video_path, results_dir, config)
    return renderer.render()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Render detection overlay video")
    parser.add_argument("--video", type=str, required=True, help="Source video path")
    parser.add_argument("--results", type=str, required=True, help="Results directory with tracks.jsonl")
    parser.add_argument("--fps", type=float, default=5.0, help="Output FPS (should match detection FPS)")
    parser.add_argument("--output", type=str, default="overlay_v2.mp4", help="Output filename")
    parser.add_argument(
        "--debug-jsonl",
        type=str,
        default=None,
        help="Optional debug JSONL filename (written into --results dir)",
    )
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    config = OverlayConfig(
        output_fps=args.fps,
        output_filename=args.output,
        debug_jsonl_filename=args.debug_jsonl,
    )
    renderer = SimpleOverlayRenderer(
        video_path=Path(args.video),
        results_dir=Path(args.results),
        config=config,
    )
    output = renderer.render()
    print(f"Output saved to: {output}")
