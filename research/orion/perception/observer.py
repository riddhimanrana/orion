"""
Frame Observer & Object Detector
=================================

Handles video frame sampling and YOLO object detection.

Responsibilities:
- Sample frames from video at target FPS
- Run YOLO11x detection
- Filter detections by confidence and size
- Extract bounding boxes and class labels

Author: Orion Research Team
Date: October 2025
"""

import logging
from typing import Any, Dict, List, Tuple, Optional, Literal

import cv2
import numpy as np
from tqdm import tqdm

from orion.perception.taxonomy import COARSE_TO_FINE_PROMPTS

from orion.perception.types import ObjectClass, BoundingBox
from orion.perception.config import DetectionConfig
from orion.utils.profiling import profile
from orion.backends.dino_classifier import classify_detections_with_context

# Check if 3D perception is available
try:
    from orion.perception.perception_3d import Perception3DEngine
    PERCEPTION_3D_AVAILABLE = True
except ImportError:
    Perception3DEngine = None
    PERCEPTION_3D_AVAILABLE = False

# Temporal filtering
try:
    from orion.perception.temporal_filter import TemporalFilter
    TEMPORAL_FILTER_AVAILABLE = True
except ImportError:
    TemporalFilter = None
    TEMPORAL_FILTER_AVAILABLE = False

logger = logging.getLogger(__name__)


class FrameObserver:
    """
    Observes video frames and detects objects using YOLO.
    
    This is the first stage of perception - raw detection without
    tracking or identity.
    """
    
    def __init__(
        self,
        config: DetectionConfig,
        detector_backend: Literal["yolo", "yoloworld", "groundingdino", "hybrid", "openvocab", "dinov3"] = "yolo",
        yolo_model: Optional[Any] = None,
        yoloworld_model: Optional[Any] = None,
        gdino_model: Optional[Any] = None,
        gdino_processor: Optional[Any] = None,
        hybrid_detector: Optional[Any] = None,
        openvocab_pipeline: Optional[Any] = None,
        target_fps: float = 2.0,
        show_progress: bool = True,
        enable_3d: bool = False,
        depth_model: str = "midas",
        depth_model_size: str = "small",
        enable_occlusion: bool = False,
        enable_slam: bool = False,
    ):
        """
        Initialize observer.
        
        Args:
            detector_backend: Detection backend identifier ('yolo', 'yoloworld', 'groundingdino', 'openvocab')
            yolo_model: YOLO model instance from ModelManager
            yoloworld_model: YOLO-World model instance when backend='yoloworld'
            gdino_model: GroundingDINO model instance
            gdino_processor: GroundingDINO processor instance
            openvocab_pipeline: OpenVocabPipeline instance when backend='openvocab'
            config: Detection configuration
            target_fps: Target frames per second for processing
            show_progress: Show progress bar
            enable_3d: Enable 3D perception (depth, occlusion)
            depth_model: Depth model to use ("zoe" or "midas")
            enable_occlusion: Enable occlusion detection (requires enable_3d=True)
        """
        self.config = config
        self.target_fps = target_fps
        self.show_progress = show_progress
        self.detector_backend = detector_backend
        self.yolo = yolo_model if detector_backend in {"yolo", "hybrid"} else None
        self.yoloworld = yoloworld_model if detector_backend == "yoloworld" else None
        self.gdino = gdino_model if detector_backend in {"groundingdino", "hybrid", "dinov3"} else None
        self.gdino_processor = gdino_processor if detector_backend in {"groundingdino", "hybrid", "dinov3"} else None
        # Allow dinov3 backend: proposals come from groundingdino/hybrid/yolo and
        # then DINOv3 is used to refine/classify proposals. We still accept gdino
        # and yolo models as constructor params; FrameObserver will prefer provided
        # gdino when available.
        '''if detector_backend == "dinov3":
            # If the caller provided a grounding dino model, use it as proposer.
            # `self.gdino` and `self.gdino_processor` may already be set above.
            pass'''
        self.hybrid_detector = hybrid_detector if detector_backend == "hybrid" else None
        self.openvocab_pipeline = openvocab_pipeline if detector_backend == "openvocab" else None

        # YOLO-World can internally keep text feature tensors (e.g., txt_feats) on CPU
        # even when the model runs on CUDA/MPS. We track a preferred device and
        # synchronize text tensors after set_classes() to avoid device-mismatch errors.
        self._yoloworld_device: Optional[str] = None

        if self.detector_backend == "yolo" and self.yolo is None:
            raise ValueError("YOLO backend selected but yolo_model was not provided")
        if self.detector_backend == "yoloworld" and self.yoloworld is None:
            raise ValueError("YOLO-World backend selected but yoloworld_model was not provided")
        if self.detector_backend == "groundingdino" and (self.gdino is None or self.gdino_processor is None):
            raise ValueError("GroundingDINO backend selected but model/processor was not provided")
        if self.detector_backend == "dinov3" and (self.gdino is None or self.gdino_processor is None):
            raise ValueError("DINOv3 backend requires GroundingDINO proposer (model/processor missing)")
        if self.detector_backend == "hybrid":
            if self.yolo is None:
                raise ValueError("Hybrid backend selected but yolo_model was not provided")
            if self.gdino is None or self.gdino_processor is None:
                raise ValueError("Hybrid backend selected but GroundingDINO model/processor was not provided")
            if self.hybrid_detector is None:
                raise ValueError("Hybrid backend selected but hybrid_detector was not provided")
        if self.detector_backend == "openvocab" and self.openvocab_pipeline is None:
            raise ValueError("OpenVocab backend selected but openvocab_pipeline was not provided")

        # Detector class registry (used by downstream trackers)
        if self.detector_backend in {"yolo", "hybrid"} and hasattr(self.yolo, "names"):
            self.detector_classes = list(self.yolo.names.values())
        elif self.detector_backend == "yoloworld":
            use_custom = getattr(self.config, "yoloworld_use_custom_classes", True)
            if (not use_custom) and self.yoloworld is not None and hasattr(self.yoloworld, "names"):
                # Prefer the model's native/open-vocab label set
                self.detector_classes = list(getattr(self.yoloworld, "names").values())
            else:
                # Use the custom classes set via prompt/categories
                self.detector_classes = list(self.config.yoloworld_categories())
        else:
            self.detector_classes = list(self.config.grounding_categories())
            
        self._grounding_label_map = {
            label.lower(): idx for idx, label in enumerate(self.detector_classes)
        }
        
        # Initialize 3D perception engine if requested
        self.perception_engine = None
        if enable_3d and PERCEPTION_3D_AVAILABLE:
            try:
                self.perception_engine = Perception3DEngine(
                    enable_depth=True,
                    enable_hands=False,  # Hand tracking disabled (future work with HOT3D)
                    enable_occlusion=enable_occlusion,
                    enable_slam=enable_slam,
                    depth_model_size=depth_model_size,
                )
                logger.info("  ✓ Perception3DEngine initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize 3D perception: {e}")
                self.perception_engine = None
        elif enable_3d:
            logger.warning("3D perception requested but not available")
        
        # Scene context for early filtering (v2)
        self.scene_context_classes: Optional[set] = None  # Classes to keep based on scene
        self.scene_context_suppress: set = set()  # Classes to always suppress (e.g., outdoor objects in indoor scene)
        
        # Temporal filtering (NEW)
        self.temporal_filter: Optional[TemporalFilter] = None
        if getattr(config, "enable_temporal_filtering", False) and TEMPORAL_FILTER_AVAILABLE:
            try:
                self.temporal_filter = TemporalFilter(
                    min_consecutive_frames=getattr(config, "min_consecutive_frames", 2),
                    temporal_iou_threshold=getattr(config, "temporal_iou_threshold", 0.5),
                    temporal_memory_frames=getattr(config, "temporal_memory_frames", 5),
                    max_gap_frames=2,
                )
                logger.info(f"  ✓ Temporal filtering enabled (min_frames={self.temporal_filter.min_consecutive_frames})")
            except Exception as e:
                logger.warning(f"Failed to initialize temporal filter: {e}")
                self.temporal_filter = None
        
        # Adaptive confidence tracking (NEW)
        self.enable_adaptive_confidence = getattr(config, "enable_adaptive_confidence", False)
        self.base_confidence_threshold = config.confidence_threshold
        self.frame_detection_history: List[int] = []  # Track detection counts per frame
        
        logger.debug(
            "FrameObserver initialized: backend=%s, target_fps=%s, 3d_enabled=%s, temporal_filter=%s",
            self.detector_backend,
            target_fps,
            self.perception_engine is not None,
            self.temporal_filter is not None,
        )

    def _preferred_torch_device(self) -> str:
        """Pick the best available torch device for YOLO/YOLO-World."""
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda:0"
            if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
                return "mps"
        except Exception:
            pass
        return "cpu"

    def _sync_yoloworld_text_tensors(self) -> None:
        """Ensure YOLO-World text feature tensors live on the same device as model params.

        Ultralytics YOLOWorld stores text features under attributes like `txt_feats`.
        After calling `set_classes()`, those tensors are often created on CPU.
        If inference happens on CUDA/MPS, this can trigger device mismatch errors.
        """
        if self.yoloworld is None:
            return

        try:
            import torch

            # Ultralytics may keep both a base model (self.yoloworld.model) and a predictor
            # model (self.yoloworld.predictor.model). We need to sync text tensors in both.
            base_model = getattr(self.yoloworld, "model", None)
            predictor = getattr(self.yoloworld, "predictor", None)
            pred_model = getattr(predictor, "model", None) if predictor is not None else None

            model_objs = [m for m in (base_model, pred_model) if m is not None]
            for model in model_objs:
                try:
                    param_dev = next(model.parameters()).device
                except Exception:
                    continue

                candidates = [model, getattr(model, "model", None)]
                for obj in candidates:
                    if obj is None:
                        continue
                    for attr in (
                        "txt_feats",
                        "text_feats",
                        "text_features",
                        "text_embeds",
                        "text_embeddings",
                    ):
                        t = getattr(obj, attr, None)
                        if isinstance(t, torch.Tensor) and getattr(t, "device", None) != param_dev:
                            try:
                                setattr(obj, attr, t.to(param_dev))
                            except Exception:
                                # Best-effort: if ultralytics changes internals, avoid crashing.
                                pass
        except Exception:
            return

    def _ensure_yoloworld_device(self) -> None:
        """Move YOLO-World to the preferred device once and sync its text tensors."""
        if self.detector_backend != "yoloworld" or self.yoloworld is None:
            return

        if self._yoloworld_device is None:
            self._yoloworld_device = self._preferred_torch_device()
            try:
                # Ultralytics provides a .to() on the wrapper.
                self.yoloworld.to(self._yoloworld_device)
            except Exception as e:
                logger.warning(f"Failed to move YOLO-World to {self._yoloworld_device}: {e}")
                self._yoloworld_device = "cpu"

        # If a predictor is already initialized, keep it on the same device too.
        try:
            predictor = getattr(self.yoloworld, "predictor", None)
            pred_model = getattr(predictor, "model", None) if predictor is not None else None
            if pred_model is not None and hasattr(pred_model, "to"):
                pred_model.to(self._yoloworld_device)
        except Exception:
            pass

        # Ultralytics WorldModel caches a CLIP text model on first set_classes(). If
        # that cache was created on CPU and we later move the model to CUDA/MPS,
        # subsequent set_classes() calls can crash due to mixed-device tensors.
        # Clearing forces a rebuild on the current device at the next set_classes().
        try:
            base_world = getattr(self.yoloworld, "model", None)
            if base_world is not None and hasattr(base_world, "clip_model"):
                base_world.clip_model = None
        except Exception:
            pass
        try:
            predictor = getattr(self.yoloworld, "predictor", None)
            pred_world = getattr(predictor, "model", None) if predictor is not None else None
            if pred_world is not None and hasattr(pred_world, "clip_model"):
                pred_world.clip_model = None
        except Exception:
            pass

        # Even if model is already on device, text tensors may still be on CPU.
        self._sync_yoloworld_text_tensors()
    
    def set_scene_context(
        self,
        mentioned_objects: List[str],
        scene_type: Optional[str] = None,
    ):
        """Configure class filtering based on scene context.
        
        This allows early filtering of detections that don't make sense
        in the current scene (e.g., filtering 'car' in an indoor office).
        
        Args:
            mentioned_objects: List of objects mentioned in scene caption.
            scene_type: Optional scene type (e.g., 'indoor', 'outdoor', 'office').
        """
        # Classes that are contextually relevant
        self.scene_context_classes = set(obj.lower() for obj in mentioned_objects)
        
        # Suppress classes that don't fit the scene type
        if scene_type:
            scene_lower = scene_type.lower()
            if 'indoor' in scene_lower or 'office' in scene_lower or 'home' in scene_lower:
                # Suppress outdoor objects
                self.scene_context_suppress = {
                    'car', 'truck', 'bus', 'motorcycle', 'bicycle', 'train',
                    'airplane', 'boat', 'traffic light', 'fire hydrant', 
                    'stop sign', 'parking meter', 'bird', 'cow', 'horse',
                    'sheep', 'elephant', 'bear', 'zebra', 'giraffe',
                }
            elif 'outdoor' in scene_lower:
                # Suppress indoor objects
                self.scene_context_suppress = {
                    'bed', 'toilet', 'sink', 'oven', 'refrigerator',
                    'microwave', 'toaster',
                }
        
        logger.info(f"Scene context set: {len(self.scene_context_classes)} relevant objects, "
                    f"{len(self.scene_context_suppress)} suppressed classes")
    
    def _should_suppress_class(self, class_name: str) -> bool:
        """Check if a class should be suppressed based on scene context."""
        if not self.scene_context_suppress:
            return False
        return class_name.lower() in self.scene_context_suppress

    def update_camera_intrinsics(self, intrinsics: "CameraIntrinsics"):
        """Passes camera intrinsics update to the 3D perception engine."""
        if self.perception_engine:
            self.perception_engine.update_camera_intrinsics(intrinsics)
    
    @profile("observer_process_video")
    def process_video(self, video_path: str) -> List[Dict]:
        """
        Process video and detect objects in sampled frames.
        
        Args:
            video_path: Path to video file
            
        Returns:
            List of raw detections with frame metadata
        """
        logger.info("="*80)
        logger.info("PHASE 1A: FRAME OBSERVATION & DETECTION")
        logger.info("="*80)
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Failed to open video: {video_path}")
        
        # Get video properties
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / video_fps if video_fps > 0 else 0

        # === FIX: Detect and handle portrait video rotation ===
        needs_rotation = frame_height > frame_width
        if needs_rotation:
            logger.info("Portrait video detected. Frames will be rotated for processing.")
            # Swap width and height for processing logic
            frame_width, frame_height = frame_height, frame_width
        # === END FIX ===
        
        logger.info(f"Video: {video_path}")
        logger.info(f"  FPS: {video_fps:.2f}, Frames: {total_frames}, Duration: {duration:.2f}s")
        logger.info(f"  Resolution: {frame_width}x{frame_height}")
        
        # Calculate frame sampling interval
        frame_interval = max(1, int(video_fps / self.target_fps))
        expected_samples = total_frames // frame_interval
        
        logger.info(f"Sampling every {frame_interval} frames (target {self.target_fps} FPS)")
        logger.info(f"Expected ~{expected_samples} sampled frames")
        
        # Process frames
        detections = []
        frame_count = 0
        sampled_count = 0
        
        pbar = tqdm(
            total=total_frames,
            desc="Detecting objects",
            disable=not self.show_progress,
        )
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # === FIX: Apply rotation if needed ===
                if needs_rotation:
                    # Rotate frame 90 degrees counter-clockwise
                    frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
                # === END FIX ===

                # Sample frames at target FPS
                if frame_count % frame_interval == 0:
                    timestamp = frame_count / video_fps if video_fps > 0 else 0.0
                    
                    # Run detection
                    frame_detections = self.detect_objects(
                        frame=frame,
                        frame_number=frame_count,
                        timestamp=timestamp,
                        frame_width=frame_width,
                        frame_height=frame_height,
                        sample_index=sampled_count,
                    )
                    
                    detections.extend(frame_detections)
                    sampled_count += 1
                
                frame_count += 1
                pbar.update(1)
        
        finally:
            cap.release()
            pbar.close()
        
        logger.info(f"\n✓ Detected {len(detections)} objects across {sampled_count} sampled frames")
        logger.info(f"  Average: {len(detections) / max(sampled_count, 1):.1f} detections/frame")
        logger.info("="*80 + "\n")
        
        return detections

    def _run_detection_backend(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Dispatch to the configured detection backend."""
        if self.detector_backend == "yoloworld":
            return self._detect_with_yoloworld(frame)
        elif self.detector_backend == "groundingdino":
            return self._detect_with_groundingdino(frame)
        elif self.detector_backend == "hybrid":
            return self._detect_with_hybrid(frame)
        elif self.detector_backend == "dinov3":
            return self._detect_with_dinov3(frame)
        elif self.detector_backend == "openvocab":
            return self._detect_with_openvocab(frame)
        else:
            return self._detect_with_yolo(frame)

    @profile("observer_detect_with_hybrid")
    def _detect_with_hybrid(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Run HybridDetector and normalize outputs to the common schema."""
        if self.hybrid_detector is None:
            return []

        dets, meta = self.hybrid_detector.detect(frame)

        detections: List[Dict[str, Any]] = []
        for d in dets:
            bbox = d.get("bbox")
            if not bbox or len(bbox) != 4:
                continue
            detections.append(
                {
                    "bbox": [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])],
                    "confidence": float(d.get("confidence", 0.0)),
                    "class_id": int(d.get("class_id", -1) if d.get("class_id", -1) is not None else -1),
                    "class_name": str(d.get("class_name", "object")),
                    # Preserve origin where possible so downstream analysis can attribute detections.
                    # HybridDetector typically sets this to "yolo" or "gdino".
                    "source": str(d.get("source", "hybrid")),
                    # Lightweight per-frame hybrid metadata (duplicated per detection on that frame).
                    "hybrid_secondary_ran": bool(meta.get("secondary_ran", False)),
                    "hybrid_trigger_reason": meta.get("trigger_reason"),
                    "hybrid_primary_count": int(meta.get("primary_count", 0) or 0),
                    "hybrid_secondary_count": int(meta.get("secondary_count", 0) or 0),
                    "hybrid_merged_count": int(meta.get("merged_count", 0) or 0),
                }
            )
        return detections

    @profile("observer_detect_with_dinov3")
    def _detect_with_dinov3(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Use an underlying proposer (GroundingDINO/YOLO/Hybrid) for boxes,
        then classify/refine those proposals using DINOv3 full-frame features.

        This preserves the repository's existing proposal generators while
        improving label quality via DINOv3's scene-aware classification.
        """
        # Prefer GroundingDINO proposals if available
        proposals: List[Dict[str, Any]] = []
        try:
            if self.gdino is not None and self.gdino_processor is not None:
                proposals = self._detect_with_groundingdino(frame)
            elif self.hybrid_detector is not None:
                proposals = self._detect_with_hybrid(frame)
            elif self.yoloworld is not None:
                proposals = self._detect_with_yoloworld(frame)
            else:
                proposals = self._detect_with_yolo(frame)
        except Exception as e:
            logger.warning(f"Proposal generation for dinov3 failed: {e}")
            proposals = []

        if not proposals:
            return []

        # Run DINOv3 classification/refinement using the convenience helper.
        device = self._preferred_torch_device()
        try:
            refined = classify_detections_with_context(frame, proposals, device=device)
        except Exception as e:
            logger.warning(f"DINOv3 classification failed: {e}")
            return proposals

        # Normalize refined outputs into the expected detection schema
        normalized: List[Dict[str, Any]] = []
        for det in refined:
            # The classifier returns 'refined_class' and 'refinement_confidence'
            refined_class = det.get("refined_class") or det.get("class_name")
            refined_conf = float(det.get("refinement_confidence", det.get("confidence", 0.0)))

            normalized.append({
                "bbox": det.get("bbox", det.get("bounding_box") or [0, 0, 0, 0]),
                "confidence": refined_conf,
                "class_id": int(det.get("class_id", -1) if det.get("class_id", -1) is not None else -1),
                "class_name": str(refined_class),
                "source": "dinov3",
                # Preserve any candidate labels or metadata
                **{k: v for k, v in det.items() if k not in {"bbox", "confidence", "class_id", "class_name"}},
            })

        return normalized

    @profile("observer_detect_with_groundingdino")
    def _detect_with_groundingdino(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Run GroundingDINO inference and normalize outputs."""
        if self.gdino is None or self.gdino_processor is None:
            return []

        import torch
        from PIL import Image
        
        # Convert BGR to RGB PIL image for processor
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_frame)
        
        # Use categories from config (COCO or custom)
        categories = self.detector_classes
        text_prompt = " . ".join(categories) + " ."
        
        device = next(self.gdino.parameters()).device
        
        inputs = self.gdino_processor(images=pil_img, text=text_prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = self.gdino(**inputs)
        
        # Post-process
        target_sizes = torch.tensor([pil_img.size[::-1]]).to(device)
        results = self.gdino_processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            threshold=self.config.confidence_threshold,
            target_sizes=target_sizes
        )[0]
        
        detections: List[Dict[str, Any]] = []
        # In newer transformers, 'labels' returns string names if text_labels isn't used.
        # But let's be safe and use 'scores', 'boxes', 'labels'.
        boxes = results["boxes"].cpu().numpy().tolist()
        scores = results["scores"].cpu().numpy().tolist()
        
        # Check if version returns string labels or int IDs
        raw_labels = results.get("text_labels", results.get("labels", []))
        
        for i in range(len(boxes)):
            label = raw_labels[i]
            # Map back to standard class name if it's an ID
            if isinstance(label, int):
                class_name = categories[label] if label < len(categories) else f"class_{label}"
                class_id = label
            else:
                class_name = str(label)
                class_id = self._grounding_label_map.get(class_name.lower(), -1)

            detections.append(
                {
                    "bbox": boxes[i],
                    "confidence": float(scores[i]),
                    "class_id": class_id,
                    "class_name": class_name,
                    "source": "gdino",
                }
            )
        return detections

    def _detect_with_yoloworld(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Run YOLO-World inference and normalize outputs."""
        if self.yoloworld is None:
            return []

        # Ensure model + text tensors are on a consistent device.
        self._ensure_yoloworld_device()

        # YOLO-World uses the same inference API as standard YOLO
        results = self.yoloworld(
            frame,
            conf=self.config.confidence_threshold,
            iou=self.config.iou_threshold,
            verbose=False,
        )

        detections: List[Dict[str, Any]] = []
        for result in results:
            boxes = result.boxes
            for i in range(len(boxes)):
                bbox_xyxy = boxes.xyxy[i].cpu().numpy().astype(float).tolist()
                class_id = int(boxes.cls[i])
                # YOLO-World uses the custom class names we set
                names = getattr(result, "names", None)
                if isinstance(names, dict):
                    class_name = names.get(class_id, f"class_{class_id}")
                elif isinstance(names, (list, tuple)) and 0 <= class_id < len(names):
                    class_name = names[class_id]
                else:
                    class_name = f"class_{class_id}"
                detections.append(
                    {
                        "bbox": bbox_xyxy,
                        "confidence": float(boxes.conf[i]),
                        "class_id": class_id,
                        "class_name": class_name,
                        "source": "yoloworld",
                    }
                )
        return detections

    @profile("observer_detect_with_openvocab")
    def _detect_with_openvocab(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Run OpenVocab pipeline (Propose → Label) and normalize outputs.
        
        The OpenVocabPipeline uses:
        1. Proposer: Class-agnostic object proposals (OWL-ViT2 or YOLO+CLIP fallback)
        2. VocabularyBank: CLIP-based label matching against LVIS/COCO vocabulary
        3. EvidenceGates: Multi-level verification for label confidence
        """
        if self.openvocab_pipeline is None:
            return []

        # Run the propose→label pipeline
        results = self.openvocab_pipeline.detect(frame)

        detections: List[Dict[str, Any]] = []
        for det in results:
            bbox = det.get("bbox")
            if not bbox or len(bbox) != 4:
                continue
            
            # Build detection record with hypothesis information
            detection = {
                "bbox": [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])],
                "confidence": float(det.get("confidence", 0.0)),
                "class_id": det.get("class_id", -1),
                "class_name": str(det.get("label", "object")),
                "source": "openvocab",
                # Schema v2 hypothesis fields
                "label_hypotheses_topk": det.get("label_hypotheses", []),
                "verification_status": det.get("verification_status", "unverified"),
                "verification_source": det.get("verification_source"),
                "proposal_confidence": float(det.get("proposal_confidence", det.get("confidence", 0.0))),
            }
            detections.append(detection)
        
        return detections

    @profile("observer_detect_with_yolo")
    def _detect_with_yolo(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Run YOLO inference and normalize outputs."""
        if self.yolo is None:
            return []

        results = self.yolo(
            frame,
            conf=self.config.confidence_threshold,
            iou=self.config.iou_threshold,
            verbose=False,
        )

        detections: List[Dict[str, Any]] = []
        for result in results:
            boxes = result.boxes
            for i in range(len(boxes)):
                bbox_xyxy = boxes.xyxy[i].cpu().numpy().astype(float).tolist()
                detections.append(
                    {
                        "bbox": bbox_xyxy,
                        "confidence": float(boxes.conf[i]),
                        "class_id": int(boxes.cls[i]),
                        "class_name": result.names[int(boxes.cls[i])],
                        "source": "yolo",
                    }
                )
        return detections

    @profile("observer_detect_objects")
    def detect_objects(
        self,
        frame: np.ndarray,
        frame_number: int,
        timestamp: float,
        frame_width: int,
        frame_height: int,
        sample_index: Optional[int] = None,
    ) -> List[Dict]:
        """
        Detect objects in a single frame.
        
        Args:
            frame: Frame image (BGR format)
            frame_number: Frame index in video
            timestamp: Timestamp in seconds
            frame_width: Video frame width
            frame_height: Video frame height
            
        Returns:
            List of detection dictionaries
        """
        # Get initial detections
        detection_candidates = self._run_detection_backend(frame)
        
        # Adaptive confidence thresholding (NEW)
        if self.enable_adaptive_confidence:
            # Track detection count for adaptive thresholding
            self.frame_detection_history.append(len(detection_candidates) if detection_candidates else 0)
            if len(self.frame_detection_history) > 10:
                self.frame_detection_history.pop(0)
            
            # If recent frames have high detection density, raise threshold
            if len(self.frame_detection_history) >= 3:
                avg_detections = sum(self.frame_detection_history) / len(self.frame_detection_history)
                high_density_threshold = getattr(self.config, "adaptive_high_density_threshold", 20)
                confidence_boost = getattr(self.config, "adaptive_confidence_boost", 0.10)
                
                if avg_detections > high_density_threshold:
                    # Temporarily raise confidence threshold
                    adjusted_threshold = min(0.95, self.base_confidence_threshold + confidence_boost)
                    # Apply boost by filtering detection_candidates
                    detection_candidates = [
                        d for d in detection_candidates
                        if d.get("confidence", 0) >= adjusted_threshold
                    ]
        
        # Run 3D perception if enabled
        perception_3d = None
        if self.perception_engine is not None:
            # Convert YOLO results to format expected by PerceptionEngine
            yolo_detections = []
            for idx, detection in enumerate(detection_candidates):
                x1, y1, x2, y2 = [int(v) for v in detection["bbox"]]
                width = x2 - x1
                height = y2 - y1
                if width < self.config.min_object_size or height < self.config.min_object_size:
                    continue
                yolo_detections.append({
                    'entity_id': f'det_{frame_number}_{idx}',
                    'class': detection["class_name"],
                    'confidence': detection["confidence"],
                    'bbox': (x1, y1, x2, y2),
                })
            
            # Process with 3D perception
            try:
                perception_3d = self.perception_engine.process_frame(
                    frame, yolo_detections, frame_number, timestamp
                )
            except Exception as e:
                logger.warning(f"3D perception failed on frame {frame_number}: {e}")
                perception_3d = None
        
        detections = []
        
        # Create a map of 3D entities by entity_id
        entities_3d_map = {}
        if perception_3d and perception_3d.entities:
            for ent in perception_3d.entities:
                entities_3d_map[ent.entity_id] = ent
        
        for idx, detection_source in enumerate(detection_candidates):
            x1, y1, x2, y2 = [int(v) for v in detection_source["bbox"]]

            width = x2 - x1
            height = y2 - y1
            if width < self.config.min_object_size or height < self.config.min_object_size:
                continue

            confidence = float(detection_source["confidence"])
            class_id = int(detection_source.get("class_id", -1))
            class_name = detection_source["class_name"]

            # Per-class confidence threshold filtering (Gemini audit: hand/laptop hallucinate on backgrounds)
            class_conf_thresholds = getattr(self.config, "class_confidence_thresholds", {}) or {}
            class_key = class_name.lower()
            min_conf = class_conf_thresholds.get(class_key, float(self.config.confidence_threshold))
            if confidence < min_conf:
                continue

            # Suppress huge, low-confidence boxes (common YOLO-World failure mode on static backgrounds)
            frame_area = float(frame_width * frame_height) if frame_width > 0 and frame_height > 0 else 0.0
            bbox_area = float(max(0, width) * max(0, height))
            if frame_area > 0:
                area_ratio = bbox_area / frame_area
                
                # Per-class area filtering (e.g., person < 50%, door < 60%)
                class_area_ratios = getattr(self.config, "class_max_area_ratios", {}) or {}
                class_key = class_name.lower()
                class_max_ratio = class_area_ratios.get(class_key, float(getattr(self.config, "max_bbox_area_ratio", 1.0)))
                
                # Reject if bbox exceeds class-specific limit
                if area_ratio >= class_max_ratio:
                    continue
                    
                # Also apply original logic for low-confidence large boxes
                if (
                    area_ratio >= float(getattr(self.config, "max_bbox_area_ratio", 1.0))
                    and confidence < float(getattr(self.config, "max_bbox_area_lowconf_threshold", 0.0))
                ):
                    continue
            
            # Drop extreme aspect-ratio boxes when confidence is low (e.g., walls/strips)
            if width > 0 and height > 0:
                aspect = max(width / height, height / width)
                if aspect >= self.config.max_aspect_ratio and confidence < self.config.aspect_ratio_lowconf_threshold:
                    continue
            
            # Scene context filtering (v2): Skip classes that don't fit the scene
            if self._should_suppress_class(class_name):
                continue

            bbox = BoundingBox(x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2))
            centroid = bbox.center
            crop, padded_bbox = self._crop_with_padding(frame, bbox)
            spatial_zone = self._compute_spatial_zone(centroid, frame_width, frame_height)

            detection = {
                "frame_id": frame_number, # Add frame_id for compatibility
                "frame_number": frame_number,
                "timestamp": timestamp,
                "bounding_box": bbox,
                "bbox": [float(x1), float(y1), float(x2), float(y2)], # Add bbox for compatibility
                "centroid": centroid,
                "object_class": class_name,
                "class_name": class_name, # Add class_name for compatibility
                "class_id": class_id,
                "confidence": confidence,
                "crop": crop,
                "padded_bbox": padded_bbox,
                "frame_width": frame_width,
                "frame_height": frame_height,
                "spatial_zone": spatial_zone,
            }

            # Preserve detector provenance (useful for debugging hybrid vs baseline behavior).
            det_source = detection_source.get("source")
            if det_source is not None:
                detection["detector_source"] = det_source

            # Preserve lightweight hybrid metadata when present.
            if "hybrid_secondary_ran" in detection_source:
                detection["hybrid_secondary_ran"] = bool(detection_source.get("hybrid_secondary_ran"))
                detection["hybrid_trigger_reason"] = detection_source.get("hybrid_trigger_reason")
                detection["hybrid_primary_count"] = int(detection_source.get("hybrid_primary_count", 0) or 0)
                detection["hybrid_secondary_count"] = int(detection_source.get("hybrid_secondary_count", 0) or 0)
                detection["hybrid_merged_count"] = int(detection_source.get("hybrid_merged_count", 0) or 0)

            # Preserve schema v2 hypothesis/verification fields (from openvocab backend)
            for k in (
                "label_hypotheses",
                "label_hypotheses_topk",
                "verification_status",
                "verification_source",
                "proposal_confidence",
            ):
                if k in detection_source:
                    # Map label_hypotheses_topk to label_hypotheses for consistency
                    key = "label_hypotheses" if k == "label_hypotheses_topk" else k
                    detection[key] = detection_source[k]

            # Ensure YOLO-World detections have description and object_class fields
            if self.detector_backend == "yoloworld":
                detection["description"] = class_name
                detection["object_class"] = class_name

            # Merge 3D info using entity_id
            entity_id = f'det_{frame_number}_{idx}'
            if entity_id in entities_3d_map:
                ent_3d = entities_3d_map[entity_id]
                detection["depth_mm"] = ent_3d.depth_mean_mm
                detection["centroid_3d_mm"] = ent_3d.centroid_3d_mm
                if ent_3d.centroid_3d_mm:
                    cx, cy, cz = ent_3d.centroid_3d_mm
                    detection["bbox_3d"] = [cx, cy, cz, 0, 0, 0]
                detection["visibility_state"] = ent_3d.visibility_state.value
                detection["occlusion_ratio"] = ent_3d.occlusion_ratio
                detection["occluded_by"] = ent_3d.occluded_by

            if perception_3d is not None and perception_3d.hands:
                detection["hands_detected"] = len(perception_3d.hands)
                detection["hands"] = [h.to_dict() for h in perception_3d.hands]

            detections.append(detection)

        # Optional: crop-level refinement with YOLO-World on selected coarse classes
        detections = self._refine_with_yoloworld(detections, sample_index=sample_index)
        
        # Class-agnostic NMS: suppress overlapping boxes of different classes (e.g., box + laptop + notebook)
        if getattr(self.config, "class_agnostic_nms", False):
            ca_nms_iou = float(getattr(self.config, "class_agnostic_nms_iou", 0.65))
            detections = self._class_agnostic_nms(detections, iou_threshold=ca_nms_iou)
        
        # Post-NMS deduplication: merge highly overlapping same-class detections
        detections = self._post_nms_dedup(detections, iou_threshold=0.55)
        
        # Depth-based validation (NEW): Reject objects with impossible heights
        if getattr(self.config, "enable_depth_validation", False) and perception_3d is not None:
            detections = self._validate_detections_with_depth(
                detections, 
                frame_height,
                max_height_meters=getattr(self.config, "max_object_height_meters", 3.5),
                min_height_meters=getattr(self.config, "min_object_height_meters", 0.02),
            )
        
        # Temporal consistency filtering (NEW): Reject 1-frame detections
        if self.temporal_filter is not None:
            # Convert detections to temporal filter format
            temporal_detections = [
                {
                    "bbox": det.get("bbox", [0, 0, 0, 0]),
                    "class_name": det.get("class_name", "object"),
                    "confidence": det.get("confidence", 0.0),
                    **det  # Preserve all other fields
                }
                for det in detections
            ]
            
            # Apply temporal filter
            filtered_detections = self.temporal_filter.process_frame(
                temporal_detections,
                frame_number
            )
            
            # Restore original detection format
            detections = filtered_detections
        
        # Apply depth-based validation if enabled
        if self.config.enable_depth_validation and detections:
            detections = self._validate_detections_with_depth(
                detections,
                frame_height=frame.shape[0],
                max_height_meters=self.config.max_object_height_meters,
                min_height_meters=self.config.min_object_height_meters,
            )
        
        return detections
    
    def _class_agnostic_nms(
        self,
        detections: List[Dict],
        iou_threshold: float = 0.65,
    ) -> List[Dict]:
        """
        Class-agnostic NMS: suppress overlapping boxes regardless of class.
        
        This eliminates duplicate tracks where the same object is detected as
        multiple classes (e.g., 'box' + 'laptop' + 'notebook' for a notebook).
        Keeps the detection with highest confidence.
        
        Args:
            detections: List of detection dicts with 'bbox' and 'confidence'
            iou_threshold: IoU threshold for suppression (0.65 = 65% overlap)
            
        Returns:
            Filtered list with overlapping multi-class duplicates removed
        """
        if len(detections) <= 1:
            return detections
        
        # Sort by confidence descending (keep highest first)
        sorted_dets = sorted(detections, key=lambda d: d.get('confidence', 0), reverse=True)
        keep = []
        
        for det in sorted_dets:
            det_bbox = det.get('bbox', [0, 0, 0, 0])
            
            # Check if this detection overlaps too much with any already-kept detection
            # (regardless of class)
            should_keep = True
            for kept_det in keep:
                kept_bbox = kept_det.get('bbox', [0, 0, 0, 0])
                
                # Compute IoU (class-agnostic)
                iou = self._compute_iou(det_bbox, kept_bbox)
                if iou >= iou_threshold:
                    should_keep = False
                    break
            
            if should_keep:
                keep.append(det)
        
        return keep
    
    def _crop_with_padding(
        self,
        frame: np.ndarray,
        bbox: BoundingBox,
    ) -> Tuple[np.ndarray, BoundingBox]:
        """
        Crop object region with padding.
        
        Args:
            frame: Frame image
            bbox: Bounding box
            
        Returns:
            Tuple of (cropped image, padded bounding box)
        """
        h, w = frame.shape[:2]
        
        # Calculate padding
        padding = self.config.bbox_padding_percent
        width = bbox.width
        height = bbox.height
        
        # Apply padding
        x1_padded = max(0, int(bbox.x1 - width * padding))
        y1_padded = max(0, int(bbox.y1 - height * padding))
        x2_padded = min(w, int(bbox.x2 + width * padding))
        y2_padded = min(h, int(bbox.y2 + height * padding))
        
        # Crop
        crop = frame[y1_padded:y2_padded, x1_padded:x2_padded]
        padded_bbox = BoundingBox(
            x1=float(x1_padded),
            y1=float(y1_padded),
            x2=float(x2_padded),
            y2=float(y2_padded),
        )
        
        return crop, padded_bbox

    def _refine_with_yoloworld(self, detections: List[Dict], *, sample_index: Optional[int] = None) -> List[Dict]:
        """
        Run YOLO-World on crops of selected coarse detections to attach fine-grained
        candidate labels. This preserves the original coarse class and only adds
        non-committal hypotheses in `candidate_labels`.
        """
        if not getattr(self.config, "yoloworld_enable_crop_refinement", False):
            return detections
        if self.yoloworld is None:
            return detections

        # Optional throttling: run refinement only every N sampled frames.
        every_n = int(getattr(self.config, "yoloworld_refinement_every_n_sampled_frames", 1) or 1)
        if sample_index is not None and every_n > 1:
            if (int(sample_index) % every_n) != 0:
                return detections

        # Ensure model + text tensors are on a consistent device before any set_classes().
        self._ensure_yoloworld_device()

        # Build lookup of coarse class -> prompt list (lowercased keys)
        coarse_map = {k.lower(): v for k, v in COARSE_TO_FINE_PROMPTS.items() if v}
        if not coarse_map:
            return detections

        # Group candidate detections by coarse class
        groups: Dict[str, List[int]] = {}
        for idx, det in enumerate(detections):
            cls_name = str(det.get("class_name") or det.get("object_class", "")).lower()
            if cls_name in coarse_map and det.get("crop") is not None and getattr(det.get("crop"), "size", 0) > 0:
                groups.setdefault(cls_name, []).append(idx)

        if not groups:
            return detections

        # Preserve original classes to restore after refinement
        original_classes = None
        try:
            names_attr = getattr(self.yoloworld, "names", None)
            if isinstance(names_attr, dict):
                original_classes = list(names_attr.values())
        except Exception:
            original_classes = None
        if not original_classes:
            original_classes = self.detector_classes

        for coarse_class, indices in groups.items():
            prompts = coarse_map.get(coarse_class, [])
            if not prompts:
                continue

            # Cap refinement workload per coarse class.
            max_crops = int(getattr(self.config, "yoloworld_refinement_max_crops_per_class", 1000000) or 1000000)
            if max_crops > 0 and len(indices) > max_crops:
                indices = sorted(
                    indices,
                    key=lambda i: float(detections[i].get("confidence", 0.0) or 0.0),
                    reverse=True,
                )[:max_crops]

            # Collect crops in order
            crops = []
            valid_indices = []
            for idx in indices:
                crop = detections[idx].get("crop")
                if crop is None or getattr(crop, "size", 0) == 0:
                    continue
                crops.append(crop)
                valid_indices.append(idx)

            if not crops:
                continue

            try:
                self.yoloworld.set_classes(prompts)
                # set_classes() often rebuilds text tensors on CPU; sync them back to model device.
                self._sync_yoloworld_text_tensors()
            except Exception as e:
                logger.warning(f"Failed to set refinement prompts for '{coarse_class}': {e}")
                continue

            try:
                results = self.yoloworld(
                    crops,
                    conf=self.config.yoloworld_refinement_confidence,
                    iou=self.config.iou_threshold,
                    verbose=False,
                )
            except Exception as e:
                logger.warning(f"Refinement inference failed for '{coarse_class}': {e}")
                continue

            if not isinstance(results, list):
                results = [results]

            for det_idx, res in zip(valid_indices, results):
                if res is None or getattr(res, "boxes", None) is None:
                    continue
                boxes = res.boxes
                candidates: List[Dict[str, Any]] = []
                for j in range(len(boxes)):
                    cls_id = int(boxes.cls[j])
                    names = getattr(res, "names", None)
                    label = None
                    if isinstance(names, dict):
                        label = names.get(cls_id)
                    elif isinstance(names, (list, tuple)):
                        if 0 <= cls_id < len(names):
                            label = names[cls_id]
                    if not label:
                        label = prompts[cls_id] if cls_id < len(prompts) else f"class_{cls_id}"
                    candidates.append(
                        {
                            "label": label,
                            "score": float(boxes.conf[j]),
                            "source": "yoloworld_refine",
                        }
                    )
                candidates = sorted(candidates, key=lambda c: c.get("score", 0.0), reverse=True)
                if candidates:
                    detections[det_idx]["candidate_labels"] = candidates[: self.config.yoloworld_refinement_top_k]
                    detections[det_idx]["candidate_group"] = coarse_class

        # Restore original class set
        if original_classes:
            try:
                self.yoloworld.set_classes(original_classes)
                self._sync_yoloworld_text_tensors()
            except Exception as e:
                logger.warning(f"Failed to restore YOLO-World classes after refinement: {e}")

        return detections

    def _post_nms_dedup(
        self,
        detections: List[Dict],
        iou_threshold: float = 0.55,
    ) -> List[Dict]:
        """
        Post-NMS deduplication: merge highly overlapping boxes of the same class.
        
        This catches cases where NMS allows slightly offset duplicates through.
        Keeps the detection with highest confidence.
        
        Args:
            detections: List of detection dicts with 'bbox' and 'class_name'
            iou_threshold: IoU threshold for merging (0.55 = 55% overlap)
            
        Returns:
            Deduplicated list of detections
        """
        if len(detections) <= 1:
            return detections
        
        # Sort by confidence descending (keep highest first)
        sorted_dets = sorted(detections, key=lambda d: d.get('confidence', 0), reverse=True)
        keep = []
        
        for det in sorted_dets:
            det_bbox = det.get('bbox', [0, 0, 0, 0])
            det_class = det.get('class_name', det.get('object_class', ''))
            
            # Check if this detection overlaps too much with any already-kept detection
            should_keep = True
            for kept_det in keep:
                kept_bbox = kept_det.get('bbox', [0, 0, 0, 0])
                kept_class = kept_det.get('class_name', kept_det.get('object_class', ''))
                
                # Only merge same-class detections
                if det_class.lower() != kept_class.lower():
                    continue
                
                # Compute IoU
                iou = self._compute_iou(det_bbox, kept_bbox)
                if iou >= iou_threshold:
                    should_keep = False
                    break
            
            if should_keep:
                keep.append(det)
        
        return keep

    def _compute_iou(self, box1: List[float], box2: List[float]) -> float:
        """Compute IoU between two [x1, y1, x2, y2] boxes."""
        x1_inter = max(box1[0], box2[0])
        y1_inter = max(box1[1], box2[1])
        x2_inter = min(box1[2], box2[2])
        y2_inter = min(box1[3], box2[3])
        
        inter_width = max(0.0, x2_inter - x1_inter)
        inter_height = max(0.0, y2_inter - y1_inter)
        inter_area = inter_width * inter_height
        
        area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
        area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
        
        union = area1 + area2 - inter_area
        return inter_area / union if union > 0 else 0.0
    
    def _validate_detections_with_depth(
        self,
        detections: List[Dict],
        frame_height: int,
        max_height_meters: float = 3.5,
        min_height_meters: float = 0.02,
    ) -> List[Dict]:
        """
        Validate detections using depth information.
        
        Rejects detections with impossible physical properties:
        - Objects too tall (> max_height_meters, e.g., 10m chair)
        - Objects too small (< min_height_meters, e.g., 5mm object)
        
        Args:
            detections: List of detection dicts with depth_mm and bbox
            frame_height: Frame height in pixels
            max_height_meters: Maximum plausible object height
            min_height_meters: Minimum plausible object height
            
        Returns:
            Filtered detections with impossible sizes removed
        """
        valid_detections = []
        
        for det in detections:
            # Skip if no depth information
            depth_mm = det.get("depth_mm")
            if depth_mm is None or depth_mm <= 0:
                valid_detections.append(det)
                continue
            
            # Get bbox dimensions
            bbox = det.get("bbox", [0, 0, 0, 0])
            bbox_height_px = bbox[3] - bbox[1]
            
            if bbox_height_px <= 0:
                continue
            
            # Estimate object height using simple pinhole camera model
            # Assuming reasonable FOV (~60 degrees vertical)
            # height_meters ≈ (bbox_height_px / frame_height) * depth_meters * tan(FOV/2) * 2
            # Simplified: height_meters ≈ (bbox_height_px / frame_height) * depth_meters * 1.15
            depth_meters = depth_mm / 1000.0
            estimated_height_meters = (bbox_height_px / frame_height) * depth_meters * 1.15
            
            # Reject if height is impossible
            if estimated_height_meters > max_height_meters:
                logger.debug(
                    f"Rejecting {det.get('class_name', 'object')}: "
                    f"estimated height {estimated_height_meters:.2f}m > {max_height_meters}m"
                )
                continue
            
            if estimated_height_meters < min_height_meters:
                logger.debug(
                    f"Rejecting {det.get('class_name', 'object')}: "
                    f"estimated height {estimated_height_meters:.2f}m < {min_height_meters}m"
                )
                continue
            
            # Add estimated height to detection for downstream use
            det["estimated_height_meters"] = estimated_height_meters
            valid_detections.append(det)
        
        if len(valid_detections) < len(detections):
            logger.debug(
                f"Depth validation: kept {len(valid_detections)}/{len(detections)} detections"
            )
        
        return valid_detections
    
    def _compute_spatial_zone(
        self,
        centroid: tuple[float, float],
        frame_width: int,
        frame_height: int
    ) -> str:
        """
        Compute spatial zone for an object based on its centroid position.
        
        Divides frame into 9 zones (3x3 grid).
        
        Args:
            centroid: (cx, cy) normalized pixel coordinates
            frame_width: Frame width in pixels
            frame_height: Frame height in pixels
            
        Returns:
            Spatial zone string (e.g., "center", "top_left")
        """
        cx, cy = centroid
        
        # Horizontal zones
        if cx < frame_width / 3:
            h_zone = "left"
        elif cx < 2 * frame_width / 3:
            h_zone = "center"
        else:
            h_zone = "right"
        
        # Vertical zones
        if cy < frame_height / 3:
            v_zone = "top"
        elif cy < 2 * frame_height / 3:
            v_zone = "middle"
        else:
            v_zone = "bottom"
        
        # Combine
        if h_zone == "center" and v_zone == "middle":
            return "center"
        elif h_zone == "center":
            return v_zone
        elif v_zone == "middle":
            return h_zone
        else:
            return f"{v_zone}_{h_zone}"
