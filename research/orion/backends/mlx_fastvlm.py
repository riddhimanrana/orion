"""MLX-VLM implementation for FastVLM inference on Apple Silicon.

This backend uses MLX for optimized inference on Apple Silicon (M1/M2/M3).
It follows the ml-fastvlm model export workflow for maximum performance.

Author: Orion Research Team
"""

from __future__ import annotations

import logging
import platform
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

from PIL import Image

logger = logging.getLogger(__name__)

ImageInput = Union[str, Path, Image.Image]

# Default model path for Apple Silicon
APPLE_MLX_MODEL_PATH = "models/fastvlm-0.5b-mlx"


def _resolve_default_model_path() -> str:
    """Return the path to the Apple fp16 MLX model with CoreML vision tower.
    
    This uses the pre-converted model from Apple CDN which includes:
    - CoreML mlpackage for optimized vision encoding on Apple Silicon  
    - fp16 weights for the language model
    """
    try:
        from ..managers.asset_manager import AssetManager

        asset_manager = AssetManager()
        asset_path = asset_manager.ensure_asset("fastvlm-0.5b-mlx")
        return str(asset_path)
    except Exception as exc:
        logger.warning("Falling back to default MLX model path: %s", exc)
        return APPLE_MLX_MODEL_PATH


def _is_apple_silicon() -> bool:
    """Check if running on Apple Silicon (M1/M2/M3/etc)."""
    return platform.system() == "Darwin" and platform.processor() == "arm"


def _ensure_image(image: ImageInput) -> Image.Image:
    """Convert image input to PIL Image."""
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    path = Path(image)
    if not path.exists():
        raise FileNotFoundError(f"Image path does not exist: {path}")
    return Image.open(path).convert("RGB")


class FastVLMMLXWrapper:
    """FastVLM inference using MLX for Apple Silicon optimization."""

    def __init__(
        self,
        model_source: Optional[str] = None,
        *,
        adapter_path: Optional[str] = None,
    ) -> None:
        """Initialize FastVLM with MLX backend.

        Args:
            model_source: Local model path. Defaults to official Apple fp16 checkpoint.
            adapter_path: Optional path to LoRA adapters
        """
        # Use managed Apple fp16 model for Apple Silicon (includes CoreML mlpackage)
        default_model = _resolve_default_model_path()
        self.model_path = model_source if model_source is not None else default_model
        self.adapter_path = adapter_path
        self._model = None
        self._processor = None
        self._config = None
        
        logger.info("FastVLM MLX backend initialized (model will load on first use)")
        logger.info("Model path: %s", self.model_path)
    
    def _ensure_loaded(self):
        """Lazy load model on first use. Uses CoreML mlpackage for vision tower."""
        if self._model is not None:
            return
        
        logger.info("Loading FastVLM with MLX backend from: %s", self.model_path)
        
        # Add mlx-vlm to sys.path if not already there
        import sys
        mlx_vlm_path = Path(__file__).parent.parent.parent / "mlx-vlm"
        if mlx_vlm_path.exists() and str(mlx_vlm_path) not in sys.path:
            sys.path.insert(0, str(mlx_vlm_path))
            logger.debug(f"Added {mlx_vlm_path} to sys.path")
        
        try:
            # Import MLX-VLM utilities
            from mlx_vlm import load
            from mlx_vlm.prompt_utils import apply_chat_template
            from mlx_vlm.utils import generate
        except ImportError as e:
            logger.error(f"Failed to import mlx_vlm: {e}")
            logger.error("MLX-VLM is required for MLX backend. Install it or use torch backend.")
            raise ImportError(f"mlx_vlm not available: {e}") from e
        
        # Store references to MLX functions
        self._apply_chat_template = apply_chat_template
        self._mlx_generate = generate
        
        # Load model and processor
        # MLX-VLM will automatically detect and use the CoreML mlpackage for vision
        result = load(
            self.model_path,
            adapter_path=self.adapter_path,
            trust_remote_code=True
        )
        if len(result) == 3:
            self._model, self._processor, self._config = result
        else:
            self._model, self._processor = result
            self._config = getattr(self._model, 'config', None)
        
        logger.info("✓ FastVLM MLX loaded (CoreML vision tower + MLX LLM)")
    
    @property
    def model(self):
        """Get the loaded model."""
        self._ensure_loaded()
        return self._model
    
    @property
    def processor(self):
        """Get the loaded processor."""
        self._ensure_loaded()
        return self._processor
    
    @property
    def config(self):
        """Get the model config."""
        self._ensure_loaded()
        return self._config

    def generate_description(
        self,
        image: ImageInput,
        prompt: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.2,
        top_p: Optional[float] = None,
        **kwargs,
    ) -> str:
        """Generate description for a single image using MLX-optimized inference.
        
        This uses the mlx_vlm.generate API which leverages CoreML for vision
        and MLX for the language model, providing optimal Apple Silicon performance.
        
        Args:
            image: Image file path, Path object, or PIL Image
            prompt: Text prompt for the model
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0 = greedy)
            top_p: Nucleus sampling parameter
            **kwargs: Additional generation parameters
            
        Returns:
            Generated text description
        """
        import tempfile
        import os
        
        # Ensure model is loaded (lazy initialization)
        self._ensure_loaded()
        
        # Convert image to path string if needed
        temp_path = None
        if isinstance(image, Image.Image):
            # mlx_vlm.generate expects image path, so save temporarily
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
                image.save(f.name)
                image_path = f.name
                temp_path = f.name
        else:
            image_path = str(image)
        
        try:
            # Format prompt with chat template
            formatted_prompt = self._apply_chat_template(
                self.processor,
                self.config,
                prompt,
                num_images=1
            )
            
            # Generate using mlx_vlm.generate (CoreML vision + MLX LLM)
            output = self._mlx_generate(
                self.model,
                self.processor,
                formatted_prompt,
                image=image_path,  # Single image path
                max_tokens=max_tokens,
                temperature=temperature,
                verbose=False,
                **kwargs
            )
            
            return output.strip()
            
        finally:
            # Clean up temp file if we created one
            if temp_path:
                try:
                    os.unlink(temp_path)
                except:
                    pass

    def generate(
        self,
        image: ImageInput,
        prompt: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.2,
        top_p: Optional[float] = None,
        **kwargs,
    ) -> str:
        """Alias for generate_description() for compatibility."""
        return self.generate_description(
            image=image,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            **kwargs
        )

    def batch_generate(
        self,
        images: Sequence[ImageInput],
        prompt: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.2,
        top_p: Optional[float] = None,
        **kwargs,
    ) -> List[str]:
        """Generate descriptions for multiple images with the same prompt.
        
        Note: MLX-VLM doesn't have efficient batching, so we process sequentially.
        """
        results: List[str] = []
        for image in images:
            result = self.generate_description(
                image,
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                **kwargs
            )
            results.append(result)
        return results

    def describe_many(
        self, 
        prompts: Iterable[tuple[ImageInput, str]],
        **kwargs
    ) -> List[str]:
        """Generate descriptions for multiple image-prompt pairs."""
        results: List[str] = []
        for image, prompt in prompts:
            result = self.generate_description(image, prompt, **kwargs)
            results.append(result)
        return results


__all__ = [
    "FastVLMMLXWrapper",
    "APPLE_MLX_MODEL_PATH",
]
