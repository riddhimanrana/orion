"""GroundingDINO detection wrapper for Orion perception."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import torch
from PIL import Image
from transformers import (
    AutoModelForZeroShotObjectDetection,
    AutoProcessor,
)

logger = logging.getLogger(__name__)


def _resolve_torch_device(preferred: Optional[str] = None) -> torch.device:
    """Resolve torch device string into a valid ``torch.device`` object."""
    if preferred in {None, "auto"}:
        if torch.cuda.is_available():
            return torch.device("cuda")
        if torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    try:
        return torch.device(preferred)
    except RuntimeError:
        logger.warning("Unknown device '%s', falling back to CPU", preferred)
        return torch.device("cpu")


class GroundingDINOWrapper:
    """Thin convenience wrapper around the Hugging Face GroundingDINO models."""

    def __init__(
        self,
        model_id: str = "IDEA-Research/grounding-dino-base",
        device: Optional[str] = None,
        use_half_precision: bool = True,
    ) -> None:
        self.model_id = model_id
        self.device = _resolve_torch_device(device)
        self.use_half_precision = use_half_precision and self.device.type != "cpu"

        logger.info("Loading GroundingDINO (%s) on %s", model_id, self.device)
        # Use fast processor if available to avoid deprecation warning
        self.processor = AutoProcessor.from_pretrained(model_id, use_fast=True)
        self.model = AutoModelForZeroShotObjectDetection.from_pretrained(model_id)

        if self.use_half_precision:
            try:
                self.model = self.model.half()
            except Exception:  # pragma: no cover - best effort only
                logger.warning("GroundingDINO half precision requested but not supported; using fp32")
                self.use_half_precision = False

        self.model.to(self.device)
        self.model.eval()
        logger.info("✓ GroundingDINO ready (device=%s, half=%s)", self.device, self.use_half_precision)

    def detect(
        self,
        frame_bgr: np.ndarray,
        prompt: str,
        box_threshold: float,
        text_threshold: float,
        max_detections: int,
    ) -> List[Dict[str, Any]]:
        """Run zero-shot detection on a single frame."""
        if frame_bgr is None:
            return []

        image_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)

        inputs = self.processor(images=pil_image, text=prompt, return_tensors="pt")
        tensor_inputs = {
            key: value.to(self.device) if isinstance(value, torch.Tensor) else value
            for key, value in inputs.items()
        }

        if self.use_half_precision and isinstance(tensor_inputs.get("pixel_values"), torch.Tensor):
            tensor_inputs["pixel_values"] = tensor_inputs["pixel_values"].half()

        with torch.no_grad():
            outputs = self.model(**tensor_inputs)

        target_sizes = torch.tensor([[pil_image.height, pil_image.width]], device=self.device)
        processed = self.processor.post_process_grounded_object_detection(
            outputs=outputs,
            input_ids=tensor_inputs["input_ids"],
            target_sizes=target_sizes,
        )

        detections: List[Dict[str, Any]] = []
        if not processed:
            return detections

        result = processed[0]
        boxes = result.get("boxes")
        scores = result.get("scores")
        labels = result.get("labels")

        if boxes is None or scores is None or labels is None:
            return detections

        boxes = boxes.detach().cpu()
        scores = scores.detach().cpu()

        ordered_indices = torch.argsort(scores, descending=True)
        for idx in ordered_indices[:max_detections]:
            bbox = boxes[idx].tolist()
            label_index = int(idx.item()) if isinstance(idx, torch.Tensor) else int(idx)
            label_value = (
                labels[label_index]
                if isinstance(labels, list)
                else labels[idx]
            )
            detections.append(
                {
                    "bbox": [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])],
                    "confidence": float(scores[idx].item()),
                    "label": str(label_value),
                }
            )

        return detections

    def to(self, device: str) -> None:
        """Move detector to a new device at runtime."""
        self.device = _resolve_torch_device(device)
        self.model.to(self.device)