"""
CLIP Backend for Orion
=======================

OpenAI CLIP for multimodal vision+text embeddings.

Used for:
- Object re-identification (tracking across frames)
- Semantic verification (does image match YOLO's class?)
- Multimodal understanding (vision + text)

Why CLIP?
- Multimodal: Understands both images and text
- Semantic: Groups by meaning, not just appearance
- Fast: 15ms per embedding on Apple Silicon
- Proven: Industry standard for vision+text

Author: Orion Research Team
Date: October 2025
"""

import logging
from typing import Optional, Union
import numpy as np
from PIL import Image
import torch

logger = logging.getLogger(__name__)

try:
    from transformers import CLIPModel, CLIPProcessor
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("transformers not available. Install: pip install transformers")


class CLIPEmbedder:
    """
    OpenAI CLIP for multimodal embeddings.
    
    Features:
    - Vision embeddings (512-dim)
    - Text embeddings (512-dim)
    - Multimodal embeddings (vision + text combined)
    - Semantic verification
    
    Usage:
        embedder = CLIPEmbedder()
        
        # Vision only
        img_emb = embedder.encode_image(pil_image)
        
        # Vision + text (multimodal)
        multimodal_emb = embedder.encode_multimodal(pil_image, "a bottle")
        
        # Verify classification
        is_match = embedder.verify_classification(pil_image, "bottle", threshold=0.7)
    """
    
    def __init__(
        self,
        model_name: str = "openai/clip-vit-base-patch32",
        device: Optional[str] = None,
        local_files_only: bool = True,
    ):
        """
        Initialize CLIP model
        
        Args:
            model_name: HuggingFace model name (CLIP variant)
            device: Device to use (None = auto-detect)
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers required. Install: pip install transformers")
        
        self.model_name = model_name
        
        # Auto-detect device
        if device is None:
            if torch.cuda.is_available():
                self.device = "cuda"
            elif torch.backends.mps.is_available():
                self.device = "mps"  # Apple Silicon
            else:
                self.device = "cpu"
        else:
            self.device = device
        
        logger.info(f"Loading CLIP: {model_name}")
        logger.info(f"Device: {self.device}")
        
        # Load model and processor
        self.local_files_only = bool(local_files_only)

        def _load(local_only: bool):
            # Use safetensors format to bypass torch CVE-2025-32434
            processor = CLIPProcessor.from_pretrained(model_name, local_files_only=local_only)
            model = CLIPModel.from_pretrained(
                model_name,
                torch_dtype=torch.float16 if self.device != "cpu" else torch.float32,
                use_safetensors=True,
                local_files_only=local_only,
            ).to(self.device)
            model.eval()
            return processor, model

        try:
            self.processor, self.model = _load(self.local_files_only)
            logger.info("✓ CLIP loaded successfully")
        except Exception as e:
            if self.local_files_only:
                logger.warning(
                    "CLIP not found in local cache; retrying download from HuggingFace. Error: %s",
                    e,
                )
                self.processor, self.model = _load(False)
                logger.info("✓ CLIP loaded successfully (downloaded)")
            else:
                logger.error(f"Failed to load CLIP: {e}")
                raise

    def encode_images(
        self,
        images: list[Union[Image.Image, np.ndarray]],
        normalize: bool = True,
    ) -> np.ndarray:
        """Batch encode images to embeddings.

        Returns:
            (N, D) float32 array.
        """
        if not images:
            return np.zeros((0, 512), dtype=np.float32)

        pil_images: list[Image.Image] = []
        for img in images:
            if isinstance(img, np.ndarray):
                pil_images.append(Image.fromarray(img))
            else:
                pil_images.append(img)

        inputs = self.processor(images=pil_images, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            feats = self.model.get_image_features(**inputs)

        embs = feats.detach().cpu().float().numpy()
        if normalize and embs.size:
            norms = np.linalg.norm(embs, axis=1, keepdims=True)
            embs = embs / np.clip(norms, 1e-12, None)
        return embs

    def encode_texts(self, texts: list[str], normalize: bool = True) -> np.ndarray:
        """Batch encode texts to embeddings.

        Returns:
            (N, D) float32 array.
        """
        if not texts:
            return np.zeros((0, 512), dtype=np.float32)

        inputs = self.processor(
            text=texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=77,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            feats = self.model.get_text_features(**inputs)

        embs = feats.detach().cpu().float().numpy()
        if normalize and embs.size:
            norms = np.linalg.norm(embs, axis=1, keepdims=True)
            embs = embs / np.clip(norms, 1e-12, None)
        return embs
    
    def encode_image(
        self,
        image: Union[Image.Image, np.ndarray],
        normalize: bool = True
    ) -> np.ndarray:
        """
        Encode image to embedding (vision only)
        
        Args:
            image: PIL Image or numpy array (H, W, C)
            normalize: Whether to L2 normalize the embedding
        
        Returns:
            Embedding vector (numpy array)
        """
        # Convert numpy to PIL if needed
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)
        
        # Process image - CLIP processor expects images parameter
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Generate embedding using vision encoder
        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)
        
        # Convert to numpy
        embedding = image_features.cpu().numpy()[0]
        
        # Normalize if requested
        if normalize:
            embedding = embedding / np.linalg.norm(embedding)
        
        return embedding
    
    def encode_multimodal(
        self,
        image: Union[Image.Image, np.ndarray],
        text: str,
        normalize: bool = True
    ) -> np.ndarray:
        """
        Encode image + text to multimodal embedding
        
        This creates an embedding by combining both image and text features.
        For CLIP, we can compute the similarity between image and text embeddings.
        
        Args:
            image: PIL Image or numpy array
            text: Text to condition on (e.g., YOLO class name)
            normalize: Whether to L2 normalize
        
        Returns:
            Combined image+text embedding vector
        """
        # Convert numpy to PIL if needed
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)
        
        # Process both image and text with CLIP
        inputs = self.processor(
            images=image,
            text=text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=77,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Get both image and text features
        with torch.no_grad():
            image_features = self.model.get_image_features(pixel_values=inputs['pixel_values'])
            text_features = self.model.get_text_features(input_ids=inputs['input_ids'])
            
            # Combine features (average)
            embedding = (image_features + text_features) / 2.0
        
        # Convert to numpy
        embedding = embedding.cpu().numpy()[0]
        
        # Normalize if requested
        if normalize:
            embedding = embedding / np.linalg.norm(embedding)
        
        return embedding
    
    def encode_text(self, text: str, normalize: bool = True) -> np.ndarray:
        """
        Encode text to embedding (for comparison with image embeddings)
        
        Args:
            text: Text to encode
            normalize: Whether to L2 normalize
        
        Returns:
            Text embedding vector
        """
        inputs = self.processor(
            text=text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=77,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)
        
        embedding = text_features.cpu().numpy()[0]
        
        if normalize:
            embedding = embedding / np.linalg.norm(embedding)
        
        return embedding
    
    def verify_classification(
        self,
        image: Union[Image.Image, np.ndarray],
        class_name: str,
        threshold: float = 0.7
    ) -> dict:
        """
        Verify if an image matches a class name
        
        This compares the image embedding with the class name embedding
        to check if they're semantically similar.
        
        Args:
            image: Image to verify
            class_name: Class name from YOLO
            threshold: Similarity threshold (0-1)
        
        Returns:
            dict with 'is_match', 'similarity', 'confidence'
        """
        # Get embeddings
        img_emb = self.encode_image(image, normalize=True)
        text_emb = self.encode_text(f"a {class_name}", normalize=True)
        
        # Compute cosine similarity
        similarity = float(np.dot(img_emb, text_emb))
        
        return {
            'is_match': similarity >= threshold,
            'similarity': similarity,
            'confidence': 'high' if similarity > 0.8 else 'medium' if similarity > 0.6 else 'low',
            'class_name': class_name
        }
    
    def get_embedding_dim(self) -> int:
        """Return embedding dimension"""
        # EmbeddingGemma typically uses 2048 or 768 dim
        # We'll do a quick check
        test_image = Image.new('RGB', (224, 224), color='white')
        test_emb = self.encode_image(test_image)
        return len(test_emb)
    
    def __del__(self):
        """Cleanup"""
        if hasattr(self, 'model'):
            del self.model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# Singleton instance for efficiency
_clip_instance: Optional[CLIPEmbedder] = None


def get_clip_embedder(model_name: str = "openai/clip-vit-base-patch32") -> CLIPEmbedder:
    """
    Get or create singleton CLIP embedder instance.
    
    Args:
        model_name: CLIP model to use (default: ViT-B/32)
    
    Returns:
        CLIPEmbedder instance
    """
    global _clip_instance
    
    if _clip_instance is None:
        _clip_instance = CLIPEmbedder(model_name=model_name)
    
    return _clip_instance


# Backward compatibility alias (deprecated)
def get_embedding_gemma(model_name: str = "openai/clip-vit-base-patch32") -> CLIPEmbedder:
    """
    DEPRECATED: Use get_clip_embedder() instead.
    
    Kept for backward compatibility.
    """
    logger.warning(
        "get_embedding_gemma() is deprecated. Use get_clip_embedder() instead."
    )
    return get_clip_embedder(model_name)
