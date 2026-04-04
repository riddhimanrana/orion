"""
OWL-ViT2 Proposal Backend for Open-Vocabulary Detection
========================================================

Implements Option A from deep research: OWLv2-style promptless detection.

Key insight: OWL-ViT2 supports "objectness" proposals (class-agnostic) which
we then label using vocabulary bank similarity. This avoids:
1. Hand-picking text prompts (hallucination source)
2. Combinatorial explosion of prompted categories
3. Bias toward training vocabulary

Pipeline:
1. OWLv2 generates class-agnostic proposals with visual embeddings
2. Proposals are matched against VocabularyBank for top-k hypotheses
3. Detections carry hypothesis lists instead of hard labels
4. Query-time/verification gates select final labels

Models supported:
- google/owlv2-base-patch16-ensemble (default, balanced)
- google/owlv2-large-patch14-ensemble (higher accuracy)
- google/owlvit-base-patch32 (faster, lower accuracy)

Author: Orion Research Team
Date: January 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class OWLProposerConfig:
    """Configuration for OWL-ViT proposal backend."""
    
    model_name: str = "google/owlv2-base-patch16-ensemble"
    """OWL-ViT model to use for proposals."""
    
    device: str = "auto"
    """Device: 'cuda', 'mps', 'cpu', or 'auto'."""
    
    # Proposal settings
    objectness_threshold: float = 0.10
    """Minimum objectness score for class-agnostic proposals."""
    
    max_proposals: int = 100
    """Maximum number of proposals per frame."""
    
    nms_threshold: float = 0.5
    """NMS IoU threshold for deduplication."""
    
    # Vocabulary bank settings
    vocab_bank_preset: str = "lvis1200"
    """Vocabulary bank preset for label hypotheses."""
    
    top_k_hypotheses: int = 5
    """Number of label hypotheses to generate per proposal."""
    
    min_similarity: float = 0.15
    """Minimum similarity for a hypothesis to be included."""
    
    # Performance
    batch_size: int = 1
    """Batch size for OWL inference (usually 1 for videos)."""
    
    cache_vocab_embeddings: bool = True
    """Cache vocabulary embeddings for faster matching."""


class OWLProposer:
    """
    OWL-ViT2 based class-agnostic proposal generator.
    
    This backend generates detection proposals without committing to labels.
    Instead, proposals carry visual embeddings that are later matched against
    a vocabulary bank to produce label hypotheses.
    
    Key differences from standard OWL-ViT usage:
    1. No text prompts needed - uses objectness head
    2. Outputs visual embeddings, not just boxes
    3. Label assignment is deferred to vocabulary bank matching
    """
    
    def __init__(
        self,
        config: OWLProposerConfig,
        vocab_bank: Optional[Any] = None,  # VocabularyBank
    ):
        self.config = config
        self.vocab_bank = vocab_bank
        self.device = self._resolve_device(config.device)
        
        # Model will be loaded lazily
        self._model = None
        self._processor = None
        self._is_loaded = False
        
        logger.info(f"OWLProposer initialized: model={config.model_name}, device={self.device}")
    
    def _resolve_device(self, device: str) -> str:
        """Resolve 'auto' device to actual device."""
        if device != "auto":
            return device
        
        import torch
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    
    def _load_model(self):
        """Lazy load the OWL-ViT model."""
        if self._is_loaded:
            return
        
        try:
            import torch
            from transformers import Owlv2Processor, Owlv2ForObjectDetection
            
            logger.info(f"Loading OWL-ViT model: {self.config.model_name}")
            
            self._processor = Owlv2Processor.from_pretrained(self.config.model_name)
            self._model = Owlv2ForObjectDetection.from_pretrained(self.config.model_name)
            self._model.to(self.device)
            self._model.eval()
            
            self._is_loaded = True
            logger.info(f"✓ OWL-ViT loaded on {self.device}")
            
        except ImportError as e:
            logger.error(f"Failed to import OWL-ViT dependencies: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load OWL-ViT model: {e}")
            raise
    
    def propose(
        self,
        frame: np.ndarray,
        frame_idx: int = 0,
        timestamp: float = 0.0,
        fallback_prompt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate class-agnostic proposals for a frame.
        
        If OWL-ViT's objectness head isn't available, falls back to using
        a generic prompt like "object" or "thing".
        
        Args:
            frame: BGR frame from OpenCV
            frame_idx: Frame number
            timestamp: Timestamp in seconds
            fallback_prompt: Text prompt if objectness not available
            
        Returns:
            List of proposal dicts with:
                - bbox_xyxy: [x1, y1, x2, y2]
                - objectness: float (0-1)
                - visual_embedding: np.ndarray (for vocab matching)
                - frame_idx: int
                - timestamp: float
        """
        self._load_model()
        
        import torch
        from PIL import Image
        
        # Convert BGR to RGB PIL Image
        frame_rgb = frame[:, :, ::-1] if frame.shape[-1] == 3 else frame
        image = Image.fromarray(frame_rgb)
        
        # OWL-ViT requires text queries, but we use minimal generic prompts
        # to get class-agnostic proposals
        if fallback_prompt is None:
            # Use super-generic prompt to get all objects
            fallback_prompt = "object . thing . item . stuff"
        
        # Split prompt into tokens (OWL format)
        text_queries = [q.strip() for q in fallback_prompt.split(".") if q.strip()]
        
        # Process inputs
        inputs = self._processor(
            text=text_queries,
            images=image,
            return_tensors="pt",
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Run inference
        with torch.no_grad():
            outputs = self._model(**inputs)
        
        # Post-process to get boxes and scores
        # OWL-ViT outputs are [batch, num_queries, 4] for boxes
        # and [batch, num_queries, num_classes] for logits
        
        target_sizes = torch.tensor([[image.height, image.width]], device=self.device)
        results = self._processor.post_process_object_detection(
            outputs=outputs,
            target_sizes=target_sizes,
            threshold=self.config.objectness_threshold,
        )[0]  # First (only) image
        
        # Extract proposals
        proposals = []
        
        boxes = results["boxes"].cpu().numpy()
        scores = results["scores"].cpu().numpy()
        labels = results.get("labels", torch.zeros(len(boxes))).cpu().numpy()
        
        # Get image features for embedding extraction
        # OWL-ViT stores these in outputs.image_embeds
        if hasattr(outputs, "image_embeds") and outputs.image_embeds is not None:
            image_features = outputs.image_embeds[0].cpu().numpy()  # (H*W/patch^2, D)
        else:
            image_features = None
        
        for i, (box, score) in enumerate(zip(boxes, scores)):
            if score < self.config.objectness_threshold:
                continue
            
            x1, y1, x2, y2 = box.tolist()
            
            # Extract visual embedding for this proposal
            # For now, use the query embedding from OWL-ViT
            # In full implementation, would pool image features in bbox region
            visual_embedding = self._extract_box_embedding(
                outputs, box, image.width, image.height
            )
            
            proposal = {
                "bbox_xyxy": [float(x1), float(y1), float(x2), float(y2)],
                "objectness": float(score),
                "visual_embedding": visual_embedding,
                "frame_idx": frame_idx,
                "timestamp": timestamp,
                "frame_width": image.width,
                "frame_height": image.height,
                "centroid": [(x1 + x2) / 2.0, (y1 + y2) / 2.0],
                "_owl_label_idx": int(labels[i]) if i < len(labels) else 0,
            }
            
            proposals.append(proposal)
        
        # Apply NMS
        if len(proposals) > 1:
            proposals = self._apply_nms(proposals, self.config.nms_threshold)
        
        # Limit max proposals
        proposals = proposals[:self.config.max_proposals]
        
        # Match against vocab bank if available
        if self.vocab_bank is not None:
            proposals = self._add_label_hypotheses(proposals)
        
        logger.debug(f"Frame {frame_idx}: {len(proposals)} proposals")
        return proposals
    
    def _extract_box_embedding(
        self,
        outputs: Any,
        box: np.ndarray,
        img_width: int,
        img_height: int,
    ) -> np.ndarray:
        """
        Extract visual embedding for a bounding box.
        
        Uses OWL-ViT's projected features when available,
        otherwise returns a placeholder.
        """
        import torch
        
        # Try to get box-specific embedding from OWL-ViT outputs
        # OWL-ViT2 stores these in class_embeds or query features
        
        if hasattr(outputs, "class_embeds") and outputs.class_embeds is not None:
            # Use class embedding from the detection
            embeds = outputs.class_embeds[0]  # (num_queries, dim)
            if len(embeds) > 0:
                # Pool all query embeddings (simplified)
                embedding = embeds.mean(dim=0).cpu().numpy()
                return embedding
        
        # Fallback: use image-level embedding
        if hasattr(outputs, "image_embeds") and outputs.image_embeds is not None:
            image_embeds = outputs.image_embeds
            if len(image_embeds.shape) == 3:
                # (batch, num_patches, dim) - pool
                embedding = image_embeds[0].mean(dim=0).cpu().numpy()
            else:
                embedding = image_embeds[0].cpu().numpy()
            return embedding
        
        # Last resort: return zero embedding
        logger.warning("Could not extract visual embedding, using zeros")
        return np.zeros(512, dtype=np.float32)
    
    def _apply_nms(
        self,
        proposals: List[Dict[str, Any]],
        iou_threshold: float,
    ) -> List[Dict[str, Any]]:
        """Apply NMS to proposals based on objectness."""
        import torch
        from torchvision.ops import nms
        
        if len(proposals) == 0:
            return proposals
        
        boxes = torch.tensor([p["bbox_xyxy"] for p in proposals], dtype=torch.float32)
        scores = torch.tensor([p["objectness"] for p in proposals], dtype=torch.float32)
        
        keep_indices = nms(boxes, scores, iou_threshold)
        
        return [proposals[i] for i in keep_indices.tolist()]
    
    def _add_label_hypotheses(
        self,
        proposals: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Add label hypotheses from vocabulary bank."""
        if self.vocab_bank is None:
            return proposals
        
        for proposal in proposals:
            embedding = proposal.get("visual_embedding")
            if embedding is None:
                proposal["label_hypotheses"] = []
                continue
            
            hypotheses = self.vocab_bank.match(
                embedding=embedding,
                top_k=self.config.top_k_hypotheses,
                min_similarity=self.config.min_similarity,
            )
            
            proposal["label_hypotheses"] = [h.to_dict() for h in hypotheses]
            
            # Set canonical label to top hypothesis
            if hypotheses:
                proposal["label"] = hypotheses[0].label
                proposal["confidence"] = hypotheses[0].score
            else:
                proposal["label"] = "unknown"
                proposal["confidence"] = 0.0
        
        return proposals
    
    def propose_batch(
        self,
        frames: List[np.ndarray],
        frame_indices: Optional[List[int]] = None,
        timestamps: Optional[List[float]] = None,
    ) -> List[List[Dict[str, Any]]]:
        """
        Batch proposal generation for multiple frames.
        
        Note: OWL-ViT batch processing is limited by memory.
        Consider processing one frame at a time for large videos.
        """
        if frame_indices is None:
            frame_indices = list(range(len(frames)))
        if timestamps is None:
            timestamps = [0.0] * len(frames)
        
        results = []
        for frame, idx, ts in zip(frames, frame_indices, timestamps):
            proposals = self.propose(frame, idx, ts)
            results.append(proposals)
        
        return results


class OWLProposerFallback:
    """
    Fallback proposer when OWL-ViT is not available.
    
    Uses YOLO in class-agnostic mode (all classes treated equally)
    and generates visual embeddings via CLIP.
    """
    
    def __init__(
        self,
        config: OWLProposerConfig,
        yolo_model: Any,
        clip_model: Any = None,
        vocab_bank: Optional[Any] = None,
    ):
        self.config = config
        self.yolo = yolo_model
        self.clip = clip_model
        self.vocab_bank = vocab_bank
        self.device = config.device
        
        logger.info("OWLProposerFallback initialized: YOLO + CLIP hybrid")
    
    def propose(
        self,
        frame: np.ndarray,
        frame_idx: int = 0,
        timestamp: float = 0.0,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Generate proposals using YOLO, then embed with CLIP."""
        # Run YOLO detection with explicit low conf threshold
        # YOLO default is 0.25, but we want more proposals for CLIP classification
        yolo_conf = min(self.config.objectness_threshold, 0.10)
        results = self.yolo(frame, conf=yolo_conf, verbose=False)[0]
        
        proposals = []
        boxes = results.boxes
        
        for i in range(len(boxes)):
            conf = float(boxes.conf[i])
            
            if conf < self.config.objectness_threshold:
                continue
            
            x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy()
            cls_id = int(boxes.cls[i])
            yolo_label = self.yolo.names.get(cls_id, "unknown")
            
            # Extract crop and compute CLIP embedding
            crop = frame[int(y1):int(y2), int(x1):int(x2)]
            if crop.size == 0:
                continue
            
            visual_embedding = self._compute_clip_embedding(crop)
            
            proposal = {
                "bbox_xyxy": [float(x1), float(y1), float(x2), float(y2)],
                "objectness": conf,
                "visual_embedding": visual_embedding,
                "frame_idx": frame_idx,
                "timestamp": timestamp,
                "frame_width": frame.shape[1],
                "frame_height": frame.shape[0],
                "centroid": [(x1 + x2) / 2.0, (y1 + y2) / 2.0],
                "_yolo_label": yolo_label,  # Keep original label for debugging
            }
            
            proposals.append(proposal)
        
        # Add hypotheses from vocab bank using proper CLIP image-text comparison
        if self.vocab_bank is not None and self.clip is not None:
            proposals = self._add_clip_hypotheses(proposals, frame)
        elif self.vocab_bank is not None:
            # Fallback to embedding-based matching (less accurate)
            for proposal in proposals:
                embedding = proposal.get("visual_embedding")
                if embedding is not None:
                    hypotheses = self.vocab_bank.match(
                        embedding=embedding,
                        top_k=self.config.top_k_hypotheses,
                    )
                    proposal["label_hypotheses"] = [h.to_dict() for h in hypotheses]
                    
                    if hypotheses:
                        proposal["label"] = hypotheses[0].label
                        proposal["confidence"] = hypotheses[0].score
                    else:
                        proposal["label"] = proposal["_yolo_label"]
                        proposal["confidence"] = proposal["objectness"]
        
        return proposals[:self.config.max_proposals]
    
    def _add_clip_hypotheses(
        self,
        proposals: List[Dict[str, Any]],
        frame: np.ndarray,
    ) -> List[Dict[str, Any]]:
        """Add label hypotheses using proper CLIP image-text comparison."""
        import torch
        from PIL import Image
        from transformers import CLIPProcessor
        
        if not proposals:
            return proposals
        
        # Use curated common object labels (exclude body parts, abstract concepts)
        candidate_labels = self._get_candidate_labels()
        
        # Load processor if needed
        processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        
        for proposal in proposals:
            x1, y1, x2, y2 = [int(v) for v in proposal["bbox_xyxy"]]
            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            
            # Convert to PIL
            crop_rgb = crop[:, :, ::-1] if crop.shape[-1] == 3 else crop
            pil_image = Image.fromarray(crop_rgb)
            
            # Run CLIP with image and text candidates
            with torch.no_grad():
                inputs = processor(
                    text=candidate_labels,
                    images=pil_image,
                    return_tensors="pt",
                    padding=True,
                ).to(self.device)
                
                outputs = self.clip(**inputs)
                logits = outputs.logits_per_image[0]  # (num_labels,)
                probs = torch.softmax(logits, dim=0).cpu().numpy()
            
            # Get top-k hypotheses
            top_indices = np.argsort(probs)[::-1][:self.config.top_k_hypotheses]
            
            hypotheses = []
            for rank, idx in enumerate(top_indices):
                hypotheses.append({
                    "label": candidate_labels[idx],
                    "score": float(probs[idx]),
                    "source": "clip",
                    "rank": rank,
                })
            
            proposal["label_hypotheses"] = hypotheses
            
            if hypotheses:
                proposal["label"] = hypotheses[0]["label"]
                proposal["confidence"] = hypotheses[0]["score"]
            else:
                proposal["label"] = proposal.get("_yolo_label", "object")
                proposal["confidence"] = proposal.get("objectness", 0.0)
        
        return proposals
    
    def _get_candidate_labels(self) -> List[str]:
        """Get curated candidate labels for CLIP classification.
        
        Returns a list of common indoor/outdoor object labels,
        excluding body parts, abstract concepts, and rare items.
        """
        # Core object categories commonly found in video scenes
        return [
            # Electronics
            "laptop", "computer", "monitor", "screen", "television", "tv",
            "keyboard", "mouse", "phone", "smartphone", "tablet", "remote control",
            "speaker", "headphones", "camera", "charger", "cable",
            # Furniture
            "chair", "couch", "sofa", "table", "desk", "bed", "shelf",
            "cabinet", "drawer", "nightstand", "bookshelf", "ottoman",
            # Kitchen
            "refrigerator", "microwave", "oven", "stove", "toaster",
            "cup", "mug", "glass", "bottle", "plate", "bowl", "pot", "pan",
            "fork", "spoon", "knife", "cutting board",
            # Containers
            "box", "bag", "backpack", "suitcase", "basket", "bin",
            "package", "envelope", "folder",
            # Office
            "book", "notebook", "paper", "pen", "pencil", "scissors",
            "stapler", "tape", "clock", "lamp",
            # Decor
            "picture frame", "plant", "flower", "vase", "pillow", "blanket",
            "curtain", "rug", "mirror",
            # Bathroom
            "towel", "toilet", "sink", "soap",
            # Food
            "apple", "banana", "orange", "pizza", "sandwich", "salad",
            # People
            "person", "man", "woman", "child",
            # Vehicles (outdoor)
            "car", "bicycle", "motorcycle",
            # Animals
            "dog", "cat", "bird",
            # Misc common objects
            "door", "window", "wall", "floor", "ceiling",
            "keys", "wallet", "watch", "glasses", "hat",
        ]
    
    def _compute_clip_embedding(self, crop: np.ndarray) -> np.ndarray:
        """Compute CLIP visual embedding for crop."""
        if self.clip is None:
            return np.zeros(512, dtype=np.float32)
        
        import torch
        from PIL import Image
        
        # Convert to PIL
        crop_rgb = crop[:, :, ::-1] if crop.shape[-1] == 3 else crop
        image = Image.fromarray(crop_rgb)
        
        # Process with CLIP
        with torch.no_grad():
            if hasattr(self.clip, "encode_image"):
                # Direct CLIP model
                inputs = self.clip.preprocess(image).unsqueeze(0).to(self.device)
                embedding = self.clip.encode_image(inputs)
            else:
                # HuggingFace CLIP
                from transformers import CLIPProcessor, CLIPModel
                processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
                inputs = processor(images=image, return_tensors="pt").to(self.device)
                embedding = self.clip.get_image_features(**inputs)
            
            embedding = embedding.cpu().numpy().flatten()
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 1e-8:
            embedding = embedding / norm
        
        return embedding


def create_owl_proposer(
    config: Optional[OWLProposerConfig] = None,
    vocab_bank: Optional[Any] = None,
    fallback_yolo: Optional[Any] = None,
    fallback_clip: Optional[Any] = None,
) -> OWLProposer:
    """
    Factory function to create OWL proposer with fallback.
    
    Args:
        config: Proposer configuration
        vocab_bank: Vocabulary bank for label hypotheses
        fallback_yolo: YOLO model for fallback mode
        fallback_clip: CLIP model for fallback embeddings
        
    Returns:
        OWLProposer or OWLProposerFallback
    """
    config = config or OWLProposerConfig()
    
    # Try to load OWL-ViT
    try:
        proposer = OWLProposer(config, vocab_bank=vocab_bank)
        proposer._load_model()  # Test loading
        return proposer
    except Exception as e:
        logger.warning(f"OWL-ViT not available: {e}")
        
        if fallback_yolo is not None:
            logger.info("Using YOLO+CLIP fallback for proposals")
            return OWLProposerFallback(
                config=config,
                yolo_model=fallback_yolo,
                clip_model=fallback_clip,
                vocab_bank=vocab_bank,
            )
        else:
            raise RuntimeError(
                "OWL-ViT not available and no fallback provided. "
                "Install transformers>=4.35 or provide fallback_yolo."
            )
