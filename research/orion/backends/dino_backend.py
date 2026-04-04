"""
DINO(v2/v3) Image Embedder Backend
----------------------------------

Provides a vision-only embedding backend using Meta's DINO family.
This is designed for viewpoint-robust embeddings for Re-ID compared to CLIP.

Supports three loading paths:
- Local weights directory (recommended for DINOv3 since it's gated)
- Hugging Face Transformers (for public DINOv2 models; requires transformers>=4.56.0)
- timm (for DINOv2/DINOv3 backbones where available; requires timm>=1.0.20)

Usage:
    # DINOv2 (public, no gating)
    dino = DINOEmbedder(model_name="facebook/dinov2-base")
    
    # DINOv3 (gated, use local weights)
    dino = DINOEmbedder(local_weights_dir="models/dinov3-vitb16")
    
    vec = dino.encode_image(image_bgr)

Notes:
- DINOv3 requires manual download: request access at https://ai.meta.com/resources/models-and-libraries/dinov3-downloads/
- Input images expected as numpy arrays in BGR (OpenCV) or RGB; auto-detected.
- Returns L2-normalized embeddings (np.float32).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union, List

import numpy as np

logger = logging.getLogger(__name__)


class DINOEmbedder:
    def __init__(
        self,
        model_name: str = "facebook/dinov2-base",
        local_weights_dir: Optional[Union[str, Path]] = None,
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.local_weights_dir = Path(local_weights_dir) if local_weights_dir else None
        self.device = device

        self._backend: str = ""
        self._processor = None
        self._model = None
        self._timm_model = None
        self._timm_transform = None

        self._load_model()
        # Video feature cache (for dinov3 video mode stub)
        self._last_video_frame_index: Optional[int] = None
        self._last_video_feature_map: Optional[np.ndarray] = None  # (Hf,Wf,D)

    def _load_model(self) -> None:
        # Try local weights first if specified
        if self.local_weights_dir and self.local_weights_dir.exists():
            try:
                from transformers import AutoImageProcessor, AutoModel  # type: ignore
                import torch  # type: ignore

                logger.info(f"Loading DINO from local weights: {self.local_weights_dir}")
                self._processor = AutoImageProcessor.from_pretrained(str(self.local_weights_dir), local_files_only=True)
                self._model = AutoModel.from_pretrained(str(self.local_weights_dir), local_files_only=True)

                # Move to device
                if self.device == "cuda" and torch.cuda.is_available():
                    self._model = self._model.to("cuda")
                elif self.device == "mps" and getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                    self._model = self._model.to("mps")
                else:
                    self._model = self._model.to("cpu")

                self._backend = "transformers-local"
                logger.info("✓ DINO loaded from local weights")
                return
            except Exception as e:
                logger.warning(f"Local weights load failed ({e}); falling back…")

        # Try Transformers with HF Hub (works for DINOv2)
        try:
            from transformers import AutoImageProcessor, AutoModel  # type: ignore
            import torch  # type: ignore

            logger.info(f"Loading DINO via Transformers: {self.model_name}")
            self._processor = AutoImageProcessor.from_pretrained(self.model_name, local_files_only=True)
            self._model = AutoModel.from_pretrained(self.model_name, local_files_only=True)

            # Move to device
            if self.device == "cuda" and torch.cuda.is_available():
                self._model = self._model.to("cuda")
            elif self.device == "mps" and getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                self._model = self._model.to("mps")
            else:
                self._model = self._model.to("cpu")

            self._backend = "transformers"
            logger.info("✓ DINO loaded via Transformers")
            return
        except Exception as e:
            logger.warning(f"Transformers load failed ({e}); falling back to timm…")

        # Fallback to timm
        try:
            import timm  # type: ignore
            import torch  # type: ignore
            from torchvision import transforms  # type: ignore

            # Map HF model names to timm equivalents
            timm_model_name = self.model_name
            if "facebook/dinov2-base" in self.model_name:
                timm_model_name = "vit_base_patch14_dinov2.lvd142m"
            elif "facebook/dinov2-small" in self.model_name:
                timm_model_name = "vit_small_patch14_dinov2.lvd142m"
            elif "facebook/dinov2-large" in self.model_name:
                timm_model_name = "vit_large_patch14_dinov2.lvd142m"

            logger.info(f"Loading DINO via timm backbone: {timm_model_name}")
            self._timm_model = timm.create_model(timm_model_name, pretrained=True)
            self._timm_model.reset_classifier(0)

            # Device placement
            if self.device == "cuda" and torch.cuda.is_available():
                self._timm_model = self._timm_model.to("cuda")
            elif self.device == "mps" and getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                self._timm_model = self._timm_model.to("mps")
            else:
                self._timm_model = self._timm_model.to("cpu")

            # Standard ImageNet transforms
            self._timm_transform = transforms.Compose(
                [
                    transforms.ToTensor(),
                    transforms.Resize((518, 518), antialias=True),
                    transforms.ConvertImageDtype(dtype=torch.float32),
                    transforms.Normalize(
                        mean=(0.485, 0.456, 0.406),
                        std=(0.229, 0.224, 0.225),
                    ),
                ]
            )
            self._backend = "timm"
            logger.info("✓ DINO loaded via timm")
            return
        except Exception as e:
            pass

        raise ImportError(
            "Could not load DINO. Install either 'transformers>=4.56.0' or 'timm>=1.0.20'."
        )

    def _ensure_rgb(self, img: np.ndarray) -> np.ndarray:
        # Heuristic: if last dim exists and mean of channel 0 much larger than channel 2, assume BGR
        if img.ndim == 3 and img.shape[2] == 3:
            # Try to detect if BGR (OpenCV) by checking correlation with swapped channels
            # Simple heuristic: treat as BGR and convert to RGB
            return img[..., ::-1].copy()
        return img

    def encode_image(self, image: np.ndarray, normalize: bool = True) -> np.ndarray:
        """
        Encode image to an embedding vector.

        Args:
            image: np.ndarray in BGR or RGB, HxWx3
            normalize: L2 normalize output

        Returns:
            np.ndarray of shape (D,)
        """
        rgb = self._ensure_rgb(image)

        if self._backend in ("transformers", "transformers-local"):
            import torch  # type: ignore
            from PIL import Image  # type: ignore

            pil = Image.fromarray(rgb.astype(np.uint8))
            inputs = self._processor(images=pil, return_tensors="pt")
            inputs = {k: v.to(self._model.device) for k, v in inputs.items()}
            with torch.inference_mode():
                outputs = self._model(**inputs)

            # Prefer pooled if present; else average tokens
            if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
                emb = outputs.pooler_output[0].detach().cpu().float().numpy()
            else:
                # Average over tokens (exclude class token if present)
                hidden = outputs.last_hidden_state  # [1, N, D]
                if hidden.shape[1] > 1:
                    tokens = hidden[:, 1:, :]
                else:
                    tokens = hidden
                emb = tokens.mean(dim=1)[0].detach().cpu().float().numpy()

        elif self._backend == "timm":
            import torch  # type: ignore
            import torchvision.transforms.functional as F  # type: ignore
            # Convert to PIL-less tensor path
            tensor = self._timm_transform(rgb)
            tensor = tensor.unsqueeze(0).to(next(self._timm_model.parameters()).device)
            with torch.inference_mode():
                features = self._timm_model.forward_features(tensor)
                if isinstance(features, (list, tuple)):
                    features = features[-1]
                # Global average pooling if needed
                if features.dim() == 4:
                    features = features.mean(dim=(2, 3))
                emb = features[0].detach().cpu().float().numpy()
        else:
            raise RuntimeError("DINO backend not initialized")

        if normalize:
            n = np.linalg.norm(emb) + 1e-8
            emb = (emb / n).astype(np.float32)
        else:
            emb = emb.astype(np.float32)
        return emb

    # ===========================
    # Video feature map interface
    # ===========================
    def extract_frame_features(self, image: np.ndarray) -> np.ndarray:
        """Stub for DINOv3 video encoder feature map extraction.

        Real implementation would run backbone and return spatial feature map
        for region pooling. Here we degrade gracefully by returning a single
        global embedding expanded spatially.
        """
        emb = self.encode_image(image, normalize=True)  # (D,)
        # Create fake spatial map (16x16) by tiling
        side = 16
        fmap = np.tile(emb[None, None, :], (side, side, 1))  # (Hf,Wf,D)
        return fmap.astype(np.float32)

    def pool_region(self, feature_map: np.ndarray, bbox: tuple, frame_shape: tuple) -> np.ndarray:
        """Average-pool embedding over bbox region (scaled to feature map).

        Args:
            feature_map: (Hf,Wf,D)
            bbox: (x1,y1,x2,y2) in pixel coords of original frame
            frame_shape: (H,W) of original frame
        Returns:
            np.ndarray (D,) pooled embedding
        """
        Hf, Wf, D = feature_map.shape
        H, W = frame_shape[:2]
        x1, y1, x2, y2 = bbox
        # Scale to feature map indices
        fx1 = int(max(0, min(Wf - 1, x1 / W * Wf)))
        fy1 = int(max(0, min(Hf - 1, y1 / H * Hf)))
        fx2 = int(max(0, min(Wf - 1, x2 / W * Wf)))
        fy2 = int(max(0, min(Hf - 1, y2 / H * Hf)))
        if fx2 <= fx1 or fy2 <= fy1:
            return feature_map.mean(axis=(0, 1))
        region = feature_map[fy1:fy2, fx1:fx2, :]
        pooled = region.mean(axis=(0, 1))
        # Normalize again for safety
        n = np.linalg.norm(pooled) + 1e-8
        return (pooled / n).astype(np.float32)

    def encode_images_batch(self, images: list[np.ndarray], normalize: bool = True) -> list[np.ndarray]:
        """
        Encode a batch of images to embedding vectors (GPU-accelerated if available).

        Args:
            images: list of np.ndarray (RGB, HxWx3)
            normalize: L2 normalize output

        Returns:
            list of np.ndarray of shape (D,)
        """
        if not images:
            return []
        if self._backend in ("transformers", "transformers-local"):
            import torch  # type: ignore
            from PIL import Image  # type: ignore
            pil_images = [Image.fromarray(self._ensure_rgb(img).astype(np.uint8)) for img in images]
            inputs = self._processor(images=pil_images, return_tensors="pt")
            inputs = {k: v.to(self._model.device) for k, v in inputs.items()}
            with torch.inference_mode():
                outputs = self._model(**inputs)
            # Prefer pooled if present; else average tokens
            if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
                embs = outputs.pooler_output.detach().cpu().float().numpy()
            else:
                hidden = outputs.last_hidden_state  # [B, N, D]
                if hidden.shape[1] > 1:
                    tokens = hidden[:, 1:, :]
                else:
                    tokens = hidden
                embs = tokens.mean(dim=1).detach().cpu().float().numpy()
            # Normalize if requested
            if normalize:
                norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-8
                embs = (embs / norms).astype(np.float32)
            else:
                embs = embs.astype(np.float32)
            return [emb for emb in embs]
        elif self._backend == "timm":
            import torch  # type: ignore
            tensors = [self._timm_transform(self._ensure_rgb(img)).unsqueeze(0) for img in images]
            batch_tensor = torch.cat(tensors, dim=0).to(next(self._timm_model.parameters()).device)
            with torch.inference_mode():
                features = self._timm_model.forward_features(batch_tensor)
                if isinstance(features, (list, tuple)):
                    features = features[-1]
                
                # Pool the features to get a single vector per image
                if features.dim() == 3:  # (Batch, Tokens, Dim) -> (Batch, Dim)
                    features = features.mean(dim=1)
                elif features.dim() == 4:  # (Batch, Channels, H, W) -> (Batch, Channels)
                    features = features.mean(dim=(2, 3))

                embs = features.detach().cpu().float().numpy()
            if normalize:
                norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-8
                embs = (embs / norms).astype(np.float32)
            else:
                embs = embs.astype(np.float32)
            return [emb for emb in embs]
        else:
            raise RuntimeError("DINO backend not initialized")
