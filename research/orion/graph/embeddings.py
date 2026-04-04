"""
Embedding Model Wrapper
Supports HuggingFace Transformers, Sentence Transformers, and Ollama.

Uses centralized config (ConfigManager) for Ollama settings.
"""

import logging
from typing import Any, List, Optional, Tuple

import numpy as np
import torch

try:  # Ensure shared model caches are configured before downloads
    from ..managers import AssetManager
except ImportError:  # pragma: no cover
    from managers import AssetManager  # type: ignore

from orion.settings import ConfigManager

logger = logging.getLogger(__name__)

DEFAULT_HF_MODEL = "openai/clip-vit-base-patch32"

_ASSET_MANAGER: Optional[AssetManager] = None


def _ensure_asset_environment() -> None:
    global _ASSET_MANAGER
    if _ASSET_MANAGER is None:
        _ASSET_MANAGER = AssetManager()


# Try to import available options
SENTENCE_TRANSFORMERS_AVAILABLE = False
OLLAMA_AVAILABLE = False
TRANSFORMERS_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except Exception:
    SentenceTransformer = None

try:
    import ollama
    OLLAMA_AVAILABLE = True
except Exception:
    ollama = None

try:
    from transformers import CLIPModel, CLIPProcessor
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    CLIPModel, CLIPProcessor = None, None


class EmbeddingModel:
    """Unified embedding model interface."""

    def __init__(self, backend: str = "auto", model: Optional[str] = None) -> None:
        self.requested_backend = backend
        self.primary_model = model
        self.model_type: Optional[str] = None
        self.embedding_dim: Optional[int] = None
        self.model: Optional[Any] = None
        self.processor: Optional[Any] = None
        self.device: Optional[str] = None
        self.ollama_model: Optional[str] = None
        self.hf_model_name: Optional[str] = None

        _ensure_asset_environment()
        self._initialize_model()

    def _initialize_model(self) -> None:
        attempts: List[Tuple[str, str]] = []
        backend_choice = (self.requested_backend or "auto").lower()
        
        config = ConfigManager.get_config()
        ollama_model = self.primary_model or config.ollama.embedding_model
        hf_model = self.primary_model or DEFAULT_HF_MODEL

        if backend_choice == "ollama":
            attempts.append(("ollama", ollama_model))
        elif backend_choice == "transformers":
            attempts.append(("transformers", hf_model))
        elif backend_choice == "sentence-transformer":
            attempts.append(("sentence-transformer", hf_model))
        else:  # auto
            # For auto, try transformers first for HF models, then ollama, then sentence-transformer
            if "/" in hf_model: # Heuristic for HF model
                attempts.append(("transformers", hf_model))
            attempts.append(("ollama", ollama_model))
            attempts.append(("sentence-transformer", hf_model))

        errors: List[str] = []
        for backend_name, model_name in attempts:
            if backend_name == "ollama":
                success, message = self._initialize_ollama(model_name)
            elif backend_name == "transformers":
                success, message = self._initialize_transformers(model_name)
            else:
                success, message = self._initialize_sentence_transformer(model_name)
            
            if success:
                return
            errors.append(message)

        message = "No embedding models available."
        if errors:
            message = f"{message} {' '.join(msg for msg in errors if msg)}"
        logger.error(message)
        raise RuntimeError(message)

    def _initialize_ollama(self, model_name: str) -> Tuple[bool, str]:
        if not OLLAMA_AVAILABLE or ollama is None:
            return False, "Ollama client is not available."
        
        try:
            probe = ollama.embeddings(model=model_name, prompt="ping")
        except Exception as exc:
            return False, f"Ollama model '{model_name}' unavailable: {exc}"

        self.model_type = "ollama"
        self.embedding_dim = len(probe.get("embedding", [])) or None
        self.ollama_model = model_name
        if self.embedding_dim is None:
            return False, f"Ollama model '{model_name}' did not return embeddings."
        logger.info("✓ Using Ollama embeddings (%s, dim=%d)", model_name, self.embedding_dim)
        return True, ""

    def _initialize_sentence_transformer(self, model_name: str) -> Tuple[bool, str]:
        if not SENTENCE_TRANSFORMERS_AVAILABLE or SentenceTransformer is None:
            return False, "sentence-transformers is not installed."

        try:
            transformer = SentenceTransformer(model_name)
        except Exception as exc:
            return False, f"SentenceTransformer '{model_name}' unavailable: {exc}"

        self.model_type = "sentence-transformer"
        self.model = transformer
        self.hf_model_name = model_name
        self.embedding_dim = transformer.get_sentence_embedding_dimension()
        logger.info("✓ Using sentence transformer %s (dim=%s)", model_name, self.embedding_dim)
        return True, ""

    def _initialize_transformers(self, model_name: str) -> Tuple[bool, str]:
        if not TRANSFORMERS_AVAILABLE or CLIPModel is None or CLIPProcessor is None:
            return False, "transformers library is not installed or CLIP models not available."

        try:
            if torch.cuda.is_available():
                self.device = "cuda"
            elif torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"

            self.model = CLIPModel.from_pretrained(model_name).to(self.device)
            self.processor = CLIPProcessor.from_pretrained(model_name)
            
            # Get embedding dimension from the model config
            self.embedding_dim = self.model.config.text_config.hidden_size

        except Exception as exc:
            return False, f"HuggingFace Transformers model '{model_name}' unavailable: {exc}"

        self.model_type = "transformers"
        self.hf_model_name = model_name
        logger.info("✓ Using HuggingFace Transformers CLIP model %s (dim=%s)", model_name, self.embedding_dim)
        return True, ""

    def encode(self, texts: List[str]) -> np.ndarray:
        """Encode texts to embeddings."""
        if isinstance(texts, str):
            texts = [texts]

        if self.model_type == "ollama":
            return self._encode_ollama(texts)
        if self.model_type == "sentence-transformer":
            return self._encode_sentence_transformer(texts)
        if self.model_type == "transformers":
            return self._encode_transformers(texts)
        raise RuntimeError("Embedding backend is not initialized.")

    def _encode_ollama(self, texts: List[str]) -> np.ndarray:
        if not OLLAMA_AVAILABLE or ollama is None or self.ollama_model is None:
            raise RuntimeError("Ollama embedding backend is not available")
        embeddings = []
        for text in texts:
            response = ollama.embeddings(model=self.ollama_model, prompt=text)
            embeddings.append(response["embedding"])
        return np.array(embeddings)

    def _encode_sentence_transformer(self, texts: List[str]) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Sentence transformer backend is not initialized")
        return self.model.encode(texts, convert_to_numpy=True)

    def _encode_transformers(self, texts: List[str]) -> np.ndarray:
        if self.model is None or self.processor is None or self.device is None:
            raise RuntimeError("Transformers (CLIP) backend is not initialized")
        
        inputs = self.processor(text=texts, return_tensors="pt", padding=True, truncation=True).to(self.device)
        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)
        
        embeddings = text_features.cpu().numpy()
        # Normalize embeddings
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        return embeddings / norms

    def compute_similarity(self, text1: str, text2: str) -> float:
        embeddings = self.encode([text1, text2])
        # Embeddings are already normalized
        dot_product = np.dot(embeddings[0], embeddings[1])
        return float(dot_product)

    def get_embedding_dimension(self) -> int:
        if self.embedding_dim is None:
            raise RuntimeError("Embedding model dimension is not initialized")
        return self.embedding_dim

    def get_model_info(self) -> dict:
        model_name = self.ollama_model if self.model_type == "ollama" else self.hf_model_name
        return {
            "type": self.model_type,
            "dimension": self.embedding_dim,
            "model_name": model_name,
        }


# Convenience function for backward compatibility
def create_embedding_model(
    prefer_ollama: bool = True,
    *,
    backend: Optional[str] = None,
    model: Optional[str] = None,
) -> EmbeddingModel:
    """Factory helper with backward-compatible defaults."""

    if backend is None:
        resolved_backend = "auto"
    else:
        resolved_backend = backend

    resolved_model = model
    if resolved_backend in ("sentence-transformer", "transformers") and resolved_model is None:
        resolved_model = DEFAULT_HF_MODEL
    if resolved_backend == "ollama" and resolved_model is None:
        config = ConfigManager.get_config()
        resolved_model = config.ollama.embedding_model

    return EmbeddingModel(resolved_backend, resolved_model)


if __name__ == "__main__":
    # Test the embedding model
    print("Testing embedding models...")

    try:
        model = create_embedding_model()
        print(f"\n✓ Model loaded: {model.get_model_info()}")

        # Test encoding
        texts = [
            "A person is walking down the street",
            "Someone is strolling on the sidewalk",
            "A car is driving on the road",
        ]

        print(f"\nTesting with {len(texts)} sentences...")
        embeddings = model.encode(texts)
        print(f"✓ Embeddings shape: {embeddings.shape}")

        # Test similarity
        sim1 = model.compute_similarity(texts[0], texts[1])
        sim2 = model.compute_similarity(texts[0], texts[2])

        print("\nSimilarity scores:")
        print(f"  '{texts[0]}' vs '{texts[1]}': {sim1:.3f}")
        print(f"  '{texts[0]}' vs '{texts[2]}': {sim2:.3f}")
        print(f"\n✓ Higher similarity for similar sentences: {sim1 > sim2}")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nTo use all features, ensure you have installed necessary packages and configured services:")
        print("  - pip install sentence-transformers transformers torch")
        print("  - To use Ollama: ollama pull <model_name>")