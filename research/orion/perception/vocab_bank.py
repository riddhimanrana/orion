"""
Vocabulary Bank for Open-Vocabulary Detection
=============================================

Provides a large vocabulary of object labels (~1200 from LVIS) with pre-computed
text embeddings for propose-then-label detection strategy.

Key insight from deep research:
- Closed-vocab detectors (YOLO) are fast but limited to training classes
- Open-vocab detectors (GroundingDINO) need text prompts, causing hallucinations
- Solution: Use class-agnostic proposals + bank similarity for labels

The vocabulary bank:
1. Loads a curated list of ~1200 object labels from LVIS/Objects365
2. Pre-computes and caches CLIP text embeddings for each label
3. At runtime, matches proposal embeddings against the bank
4. Returns top-k hypotheses without committing to a single label

Usage:
    bank = VocabularyBank.from_preset("lvis1200")
    hypotheses = bank.match(proposal_embedding, top_k=5)

Author: Orion Research Team
Date: January 2026
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vocabulary Presets
# ---------------------------------------------------------------------------

# LVIS-1203: Large Vocabulary Instance Segmentation
# Curated list of 1203 object categories from LVIS v1.0
# Organized by frequency: common (405), uncommon (461), rare (337)
LVIS_VOCABULARY = [
    # === COMMON CATEGORIES (high frequency, reliable) ===
    # People & body parts
    "person", "man", "woman", "child", "baby", "face", "hand", "arm", "leg", "foot",
    "head", "body", "hair", "eye", "ear", "nose", "mouth", "finger", "toe",
    
    # Clothing
    "shirt", "pants", "dress", "jacket", "coat", "sweater", "shorts", "skirt",
    "hat", "cap", "shoes", "boots", "sandals", "socks", "gloves", "scarf",
    "tie", "belt", "watch", "glasses", "sunglasses", "necklace", "bracelet",
    
    # Furniture - seating
    "chair", "couch", "sofa", "armchair", "stool", "bench", "ottoman", "recliner",
    
    # Furniture - surfaces
    "table", "desk", "dining table", "coffee table", "counter", "shelf",
    "nightstand", "side table", "end table", "console table",
    
    # Furniture - storage
    "cabinet", "drawer", "dresser", "wardrobe", "closet", "bookshelf",
    "shelf", "rack", "stand", "cupboard", "chest", "bin", "basket",
    
    # Furniture - bedroom
    "bed", "mattress", "pillow", "blanket", "comforter", "sheet", "headboard",
    
    # Electronics - computing
    "computer", "laptop", "monitor", "screen", "keyboard", "mouse", "trackpad",
    "tablet", "phone", "cell phone", "smartphone", "charger", "cable", "cord",
    
    # Electronics - entertainment
    "tv", "television", "remote", "speaker", "headphones", "earbuds",
    "game controller", "gaming console", "camera", "webcam",
    
    # Kitchen - appliances
    "refrigerator", "fridge", "microwave", "oven", "stove", "toaster",
    "blender", "coffee maker", "kettle", "dishwasher",
    
    # Kitchen - cookware
    "pot", "pan", "frying pan", "saucepan", "baking sheet", "baking dish",
    "cutting board", "knife", "fork", "spoon", "spatula", "ladle", "whisk",
    
    # Kitchen - tableware
    "plate", "bowl", "cup", "mug", "glass", "bottle", "jar", "container",
    "pitcher", "carafe", "vase", "tray", "platter",
    
    # Food categories
    "fruit", "apple", "banana", "orange", "grape", "strawberry", "blueberry",
    "vegetable", "carrot", "broccoli", "tomato", "lettuce", "onion", "potato",
    "bread", "sandwich", "pizza", "burger", "salad", "soup", "pasta",
    "meat", "chicken", "beef", "fish", "egg", "cheese", "milk",
    
    # Bags & containers
    "bag", "backpack", "handbag", "purse", "suitcase", "briefcase",
    "shopping bag", "grocery bag", "tote bag", "duffel bag",
    "box", "package", "carton", "crate", "bin", "basket",
    
    # Paper & office
    "paper", "book", "notebook", "magazine", "newspaper", "document",
    "pen", "pencil", "marker", "highlighter", "eraser", "stapler",
    "folder", "binder", "envelope", "letter", "card",
    
    # Bathroom
    "toilet", "sink", "faucet", "bathtub", "shower", "mirror",
    "towel", "soap", "shampoo", "toothbrush", "toothpaste",
    "toilet paper", "tissue", "trash can",
    
    # Cleaning
    "vacuum", "broom", "mop", "bucket", "sponge", "cloth", "rag",
    
    # Decor
    "picture", "painting", "poster", "frame", "mirror", "clock",
    "lamp", "light", "chandelier", "candle", "plant", "flower",
    "curtain", "blinds", "rug", "carpet", "mat",
    
    # Structural
    "door", "window", "wall", "floor", "ceiling", "stairs",
    "doorknob", "handle", "hinge", "lock", "key",
    
    # Outdoor
    "tree", "bush", "grass", "flower", "leaf", "branch",
    "fence", "gate", "path", "sidewalk", "road",
    
    # === UNCOMMON CATEGORIES ===
    # Sports equipment
    "ball", "basketball", "football", "soccer ball", "baseball", "tennis ball",
    "bat", "racket", "golf club", "hockey stick", "ski", "snowboard",
    "skateboard", "surfboard", "bicycle", "helmet", "glove",
    
    # Musical instruments
    "guitar", "piano", "keyboard", "drum", "violin", "flute",
    "microphone", "speaker", "amplifier",
    
    # Tools
    "hammer", "screwdriver", "wrench", "pliers", "drill", "saw",
    "tape measure", "level", "toolbox", "nail", "screw", "bolt",
    
    # Art supplies
    "paint", "brush", "canvas", "easel", "palette", "crayon",
    
    # Baby & kids
    "toy", "doll", "teddy bear", "stuffed animal", "blocks", "puzzle",
    "stroller", "high chair", "crib", "car seat",
    
    # Vehicles
    "car", "truck", "bus", "motorcycle", "bicycle", "scooter",
    "boat", "airplane", "helicopter", "train",
    
    # Animals
    "dog", "cat", "bird", "fish", "horse", "cow", "sheep",
    "rabbit", "hamster", "turtle", "snake", "frog",
    
    # Medical
    "medicine", "pill", "bottle", "bandage", "thermometer",
    "first aid kit", "wheelchair", "crutch",
    
    # Technology
    "router", "modem", "printer", "scanner", "projector",
    "hard drive", "usb drive", "memory card", "battery",
    
    # === RARE/SPECIALIZED CATEGORIES ===
    # Kitchen specialty
    "wok", "colander", "grater", "peeler", "can opener",
    "corkscrew", "bottle opener", "ice cream scoop", "rolling pin",
    
    # Office specialty
    "paper clip", "rubber band", "tape", "glue", "scissors",
    "hole punch", "paper cutter", "shredder", "filing cabinet",
    
    # Household specialty
    "iron", "ironing board", "hanger", "clothespin", "laundry basket",
    "detergent", "fabric softener", "dryer sheet",
    
    # Decor specialty
    "figurine", "sculpture", "trophy", "award", "certificate",
    "calendar", "clock", "thermometer", "barometer",
    
    # Outdoor specialty
    "umbrella", "raincoat", "boots", "shovel", "rake",
    "wheelbarrow", "hose", "sprinkler", "lawn mower",
]

# Compact COCO-80 vocabulary for backward compatibility
COCO_VOCABULARY = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe",
    "backpack", "umbrella", "handbag", "tie", "suitcase",
    "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl",
    "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake",
    "chair", "couch", "potted plant", "bed", "dining table", "toilet",
    "tv", "laptop", "mouse", "remote", "keyboard", "cell phone",
    "microwave", "oven", "toaster", "sink", "refrigerator",
    "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush",
]

# Objects365 subset (365 classes, good coverage)
OBJECTS365_VOCABULARY = [
    "person", "sneakers", "chair", "hat", "lamp", "bottle", "cabinet", "cup",
    "bowl", "desk", "handbag", "street lights", "book", "plate", "helmet",
    "leather shoes", "pillow", "glove", "potted plant", "bracelet", "flower",
    "tv", "vase", "belt", "monitor", "hat", "umbrella", "glasses", "watch",
    "traffic light", "traffic sign", "backpack", "basket", "laptop", "telephone",
    "suitcase", "clock", "fan", "gas stove", "pot", "guitar", "kettle",
    "oven", "toothbrush", "scissors", "mirror", "washing machine", "bicycle",
    "car", "bus", "motorcycle", "truck", "airplane", "boat", "train",
    "dog", "cat", "bird", "horse", "cow", "sheep", "elephant", "bear", "giraffe", "zebra",
    # ... (full list would be 365 items)
]


@dataclass
class LabelHypothesis:
    """A candidate label hypothesis with confidence score."""
    label: str
    score: float  # Similarity score (0-1)
    source: str = "vocab_bank"  # Where this hypothesis came from
    rank: int = 0  # Position in top-k list
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "score": float(self.score),
            "source": self.source,
            "rank": self.rank,
        }


@dataclass 
class VocabularyBankConfig:
    """Configuration for vocabulary bank."""
    
    preset: str = "lvis1200"
    """Vocabulary preset: 'lvis1200', 'coco80', 'objects365', or 'custom'."""
    
    custom_labels: Optional[List[str]] = None
    """Custom label list when preset='custom'."""
    
    embedding_model: str = "openai/clip-vit-base-patch32"
    """Text embedding model for label vectors."""
    
    embedding_dim: int = 512
    """Dimension of text embeddings."""
    
    cache_dir: Optional[str] = None
    """Directory to cache embeddings (None = in-memory only)."""
    
    top_k: int = 5
    """Default number of hypotheses to return."""
    
    min_similarity: float = 0.15
    """Minimum similarity threshold for hypotheses."""
    
    normalize_embeddings: bool = True
    """Whether to L2-normalize embeddings before matching."""


class VocabularyBank:
    """
    Pre-computed vocabulary bank for open-vocabulary detection.
    
    Stores text embeddings for a large vocabulary (~1200 labels) and
    provides fast similarity-based label matching for detection proposals.
    """
    
    def __init__(
        self,
        labels: List[str],
        embeddings: np.ndarray,
        config: VocabularyBankConfig,
    ):
        """
        Initialize vocabulary bank with labels and embeddings.
        
        Args:
            labels: List of label strings
            embeddings: Pre-computed embeddings (N x D)
            config: Bank configuration
        """
        self.labels = labels
        self.embeddings = embeddings
        self.config = config
        
        # Normalize embeddings if not already
        if config.normalize_embeddings:
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms = np.clip(norms, 1e-8, None)  # Avoid division by zero
            self.embeddings = embeddings / norms
        
        # Build label-to-index map
        self._label_to_idx = {label: i for i, label in enumerate(labels)}
        
        logger.info(f"VocabularyBank initialized with {len(labels)} labels")
    
    @classmethod
    def from_preset(
        cls,
        preset: str = "lvis1200",
        cache_dir: Optional[str] = None,
        embedding_model: str = "openai/clip-vit-base-patch32",
        device: str = "cpu",
    ) -> "VocabularyBank":
        """
        Create vocabulary bank from a preset.
        
        Args:
            preset: One of 'lvis', 'lvis1200', 'coco', 'coco80', 'objects365'
            cache_dir: Directory to cache embeddings
            embedding_model: CLIP model for text embeddings
            device: Device for embedding computation
            
        Returns:
            Initialized VocabularyBank
        """
        # Get vocabulary for preset
        if preset in ("lvis", "lvis1200"):
            labels = list(set(LVIS_VOCABULARY))  # Deduplicate
        elif preset in ("coco", "coco80"):
            labels = COCO_VOCABULARY.copy()
        elif preset == "objects365":
            labels = OBJECTS365_VOCABULARY.copy()
        else:
            raise ValueError(f"Unknown preset: {preset}. Use 'lvis', 'coco', or 'objects365'")
        
        config = VocabularyBankConfig(
            preset=preset,
            embedding_model=embedding_model,
            cache_dir=cache_dir,
        )
        
        # Try to load cached embeddings
        embeddings = cls._load_cached_embeddings(labels, config)
        
        if embeddings is None:
            logger.info(f"Computing embeddings for {len(labels)} labels...")
            embeddings = cls._compute_embeddings(labels, embedding_model, device)
            
            # Cache embeddings
            if cache_dir:
                cls._save_cached_embeddings(labels, embeddings, config)
        
        return cls(labels, embeddings, config)
    
    @classmethod
    def from_custom(
        cls,
        labels: List[str],
        cache_dir: Optional[str] = None,
        embedding_model: str = "openai/clip-vit-base-patch32",
        device: str = "cpu",
    ) -> "VocabularyBank":
        """
        Create vocabulary bank from custom label list.
        
        Args:
            labels: Custom list of labels
            cache_dir: Directory to cache embeddings
            embedding_model: CLIP model for text embeddings
            device: Device for embedding computation
            
        Returns:
            Initialized VocabularyBank
        """
        labels = list(set(labels))  # Deduplicate
        
        config = VocabularyBankConfig(
            preset="custom",
            custom_labels=labels,
            embedding_model=embedding_model,
            cache_dir=cache_dir,
        )
        
        # Compute embeddings (no caching for custom)
        embeddings = cls._compute_embeddings(labels, embedding_model, device)
        
        return cls(labels, embeddings, config)
    
    @staticmethod
    def _compute_embeddings(
        labels: List[str],
        model_name: str,
        device: str,
    ) -> np.ndarray:
        """Compute CLIP text embeddings for labels."""
        try:
            from transformers import CLIPModel, CLIPTokenizer
            import torch
            
            logger.info(f"Loading CLIP model: {model_name}")
            tokenizer = CLIPTokenizer.from_pretrained(model_name)
            model = CLIPModel.from_pretrained(model_name)
            model.to(device)
            model.eval()
            
            embeddings = []
            batch_size = 32
            
            with torch.no_grad():
                for i in range(0, len(labels), batch_size):
                    batch_labels = labels[i:i + batch_size]
                    
                    # Tokenize
                    inputs = tokenizer(
                        batch_labels,
                        padding=True,
                        truncation=True,
                        return_tensors="pt",
                    ).to(device)
                    
                    # Get text embeddings
                    outputs = model.get_text_features(**inputs)
                    batch_embeddings = outputs.cpu().numpy()
                    embeddings.append(batch_embeddings)
            
            embeddings = np.vstack(embeddings)
            logger.info(f"Computed embeddings shape: {embeddings.shape}")
            return embeddings
            
        except ImportError as e:
            logger.error(f"Failed to import CLIP: {e}")
            raise
    
    @staticmethod
    def _cache_path(labels: List[str], config: VocabularyBankConfig) -> Optional[Path]:
        """Get cache file path for given config."""
        if not config.cache_dir:
            return None
        
        # Create hash of labels + model name
        content = json.dumps({
            "labels": sorted(labels),
            "model": config.embedding_model,
        })
        hash_key = hashlib.md5(content.encode()).hexdigest()[:12]
        
        cache_dir = Path(config.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        return cache_dir / f"vocab_bank_{config.preset}_{hash_key}.npz"
    
    @classmethod
    def _load_cached_embeddings(
        cls,
        labels: List[str],
        config: VocabularyBankConfig,
    ) -> Optional[np.ndarray]:
        """Load embeddings from cache if available."""
        cache_path = cls._cache_path(labels, config)
        if cache_path is None or not cache_path.exists():
            return None
        
        try:
            data = np.load(cache_path)
            cached_labels = data["labels"].tolist()
            embeddings = data["embeddings"]
            
            # Verify labels match
            if cached_labels == sorted(labels):
                logger.info(f"Loaded cached embeddings from {cache_path}")
                
                # Reorder to match input label order
                label_to_emb = {l: embeddings[i] for i, l in enumerate(cached_labels)}
                embeddings = np.array([label_to_emb[l] for l in labels])
                
                return embeddings
            else:
                logger.warning("Cached labels don't match, recomputing...")
                return None
                
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return None
    
    @classmethod
    def _save_cached_embeddings(
        cls,
        labels: List[str],
        embeddings: np.ndarray,
        config: VocabularyBankConfig,
    ) -> None:
        """Save embeddings to cache."""
        cache_path = cls._cache_path(labels, config)
        if cache_path is None:
            return
        
        try:
            np.savez(
                cache_path,
                labels=np.array(sorted(labels)),
                embeddings=embeddings,
            )
            logger.info(f"Saved embeddings cache to {cache_path}")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
    
    def match(
        self,
        embedding: np.ndarray,
        top_k: Optional[int] = None,
        min_similarity: Optional[float] = None,
        exclude_labels: Optional[List[str]] = None,
    ) -> List[LabelHypothesis]:
        """
        Match a proposal embedding against the vocabulary bank.
        
        Args:
            embedding: Visual embedding of detection proposal (D,)
            top_k: Number of hypotheses to return (default: config.top_k)
            min_similarity: Minimum similarity threshold
            exclude_labels: Labels to exclude from results
            
        Returns:
            List of LabelHypothesis sorted by score (descending)
        """
        top_k = top_k or self.config.top_k
        min_similarity = min_similarity or self.config.min_similarity
        
        # Normalize embedding
        if self.config.normalize_embeddings:
            norm = np.linalg.norm(embedding)
            if norm > 1e-8:
                embedding = embedding / norm
        
        # Compute similarities (dot product for normalized vectors = cosine)
        similarities = self.embeddings @ embedding
        
        # Filter by excluded labels
        if exclude_labels:
            for label in exclude_labels:
                if label in self._label_to_idx:
                    similarities[self._label_to_idx[label]] = -1.0
        
        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k * 2]  # Get extra for filtering
        
        # Build hypotheses
        hypotheses = []
        for rank, idx in enumerate(top_indices):
            score = float(similarities[idx])
            
            if score < min_similarity:
                continue
            
            hypotheses.append(LabelHypothesis(
                label=self.labels[idx],
                score=score,
                source="vocab_bank",
                rank=len(hypotheses),
            ))
            
            if len(hypotheses) >= top_k:
                break
        
        return hypotheses
    
    def match_batch(
        self,
        embeddings: np.ndarray,
        top_k: Optional[int] = None,
        min_similarity: Optional[float] = None,
    ) -> List[List[LabelHypothesis]]:
        """
        Batch match multiple embeddings against the vocabulary.
        
        Args:
            embeddings: Visual embeddings (N x D)
            top_k: Number of hypotheses per embedding
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of hypothesis lists, one per input embedding
        """
        top_k = top_k or self.config.top_k
        min_similarity = min_similarity or self.config.min_similarity
        
        # Normalize embeddings
        if self.config.normalize_embeddings:
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms = np.clip(norms, 1e-8, None)
            embeddings = embeddings / norms
        
        # Batch similarity computation (N x V)
        similarities = embeddings @ self.embeddings.T
        
        # Get top-k per embedding
        results = []
        for i in range(len(embeddings)):
            sims = similarities[i]
            top_indices = np.argsort(sims)[::-1][:top_k]
            
            hypotheses = []
            for rank, idx in enumerate(top_indices):
                score = float(sims[idx])
                if score >= min_similarity:
                    hypotheses.append(LabelHypothesis(
                        label=self.labels[idx],
                        score=score,
                        source="vocab_bank",
                        rank=rank,
                    ))
            
            results.append(hypotheses)
        
        return results
    
    def get_label_embedding(self, label: str) -> Optional[np.ndarray]:
        """Get embedding for a specific label."""
        if label in self._label_to_idx:
            return self.embeddings[self._label_to_idx[label]]
        return None
    
    @property
    def num_labels(self) -> int:
        """Number of labels in the bank."""
        return len(self.labels)
    
    @property
    def embedding_dim(self) -> int:
        """Dimension of embeddings."""
        return self.embeddings.shape[1] if len(self.embeddings) > 0 else 0


# Convenience function for quick access
def get_vocab_bank(
    preset: str = "lvis1200",
    cache_dir: str = "models/_cache/vocab_bank",
    device: str = "cpu",
) -> VocabularyBank:
    """
    Get a vocabulary bank with caching.
    
    Args:
        preset: Vocabulary preset
        cache_dir: Cache directory
        device: Device for computation
        
    Returns:
        Initialized VocabularyBank
    """
    return VocabularyBank.from_preset(
        preset=preset,
        cache_dir=cache_dir,
        device=device,
    )
