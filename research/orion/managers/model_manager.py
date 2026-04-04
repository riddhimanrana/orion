"""
Unified Model Manager for Orion
================================

Single point of access for all models in the Orion pipeline.
Handles lazy loading, memory management, and device placement.

Architecture:
    YOLO11x    → Detection (what + where)
    CLIP       → Embeddings (re-ID + verification)
    FastVLM    → Descriptions (rich text)
    Gemma3:4b  → Q&A (via Ollama, not managed here)

Author: Orion Research Team
Date: October 2025
"""

import logging
from pathlib import Path
from typing import Any, Optional

import torch

logger = logging.getLogger(__name__)


class ModelManager:
    """
    Singleton manager for all Orion models.
    
    Benefits:
    - Lazy loading (models only loaded when needed)
    - Memory efficient (shared instances)
    - Device management (auto MPS/CUDA/CPU)
    - Easy to swap backends
    
    Usage:
        manager = ModelManager.get_instance()
        
        # Get YOLO detector
        yolo = manager.yolo
        results = yolo(image)
        
        # Get CLIP embedder
        clip = manager.clip
        embedding = clip.encode_image(image)
        
        # Get FastVLM describer
        fastvlm = manager.fastvlm
        description = fastvlm.generate(image, prompt)
    """
    
    _instance: Optional['ModelManager'] = None
    
    def __init__(self, models_dir: Optional[Path] = None):
        """
        Initialize model manager.
        
        Args:
            models_dir: Path to models directory (default: repo/models/)
        """
        if models_dir is None:
            # Auto-detect models directory
            try:
                from .asset_manager import AssetManager
                self.asset_manager = AssetManager()
                self.models_dir = self.asset_manager.cache_dir  # Fallback path
            except ImportError:
                # Fallback: try from parent directory
                try:
                    import sys
                    import os
                    # Add parent directory to path
                    parent_dir = Path(__file__).parent.parent.parent
                    if str(parent_dir) not in sys.path:
                        sys.path.insert(0, str(parent_dir))
                    from managers.asset_manager import AssetManager
                    self.asset_manager = AssetManager()
                    self.models_dir = self.asset_manager.cache_dir
                except ImportError:
                    logger.warning("Could not import AssetManager, using default paths")
                    self.asset_manager = None
                    self.models_dir = Path.home() / ".cache" / "orion" / "models"
        else:
            self.models_dir = models_dir
            self.asset_manager = None
        
        # Model instances (lazy loaded)
        self._yolo: Optional[Any] = None
        self._yoloworld: Optional[Any] = None
        self._gdino_model: Optional[Any] = None
        self._gdino_processor: Optional[Any] = None
        self._clip: Optional[Any] = None
        self._fastvlm: Optional[Any] = None
        self._vjepa2: Optional[Any] = None
        
        # Model configuration
        self.yolo_model_name = "yolo11m"  # Default to medium (balanced)
        self.yoloworld_model_name = "yolov8m-worldv2.pt"  # YOLO-World model
        self.yoloworld_classes: Optional[list] = None  # Classes to set for YOLO-World
        self.gdino_model_name = "IDEA-Research/grounding-dino-tiny" # Default to tiny for speed
        
        # LLM for contextual understanding
        self._ollama_client: Optional[Any] = None
        
        # Device management
        self.device = self._detect_device()
        logger.info(f"ModelManager initialized (device: {self.device})")
    
    @classmethod
    def get_instance(cls, models_dir: Optional[Path] = None) -> 'ModelManager':
        """Get or create singleton instance"""
        if cls._instance is None:
            cls._instance = cls(models_dir)
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """Reset singleton (for testing)"""
        if cls._instance is not None:
            cls._instance.cleanup()
            cls._instance = None
    
    def _detect_device(self) -> str:
        """Auto-detect best available device"""
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"  # Apple Silicon
        else:
            return "cpu"
    
    # ========================================================================
    # YOLO11x Detector
    # ========================================================================
    
    @property
    def yolo(self) -> Any:
        """
        Get YOLO11x detector (lazy loaded).
        
        Returns:
            YOLO model instance
        """
        if self._yolo is None:
            self._yolo = self._load_yolo()
        return self._yolo
    
    def _load_yolo(self) -> Any:
        """Load YOLO11 model (configurable variant)"""
        try:
            from ultralytics import YOLO
            
            model_name = self.yolo_model_name  # yolo11n, yolo11s, yolo11m, or yolo11x
            logger.info(f"Loading {model_name.upper()} detector...")
            
            # Try asset manager first
            if self.asset_manager:
                try:
                    asset_dir = self.asset_manager.ensure_asset(model_name)
                    model_path = asset_dir / f"{model_name}.pt"
                except:
                    # Fall back to default path
                    model_path = self.models_dir / "weights" / f"{model_name}.pt"
            else:
                model_path = self.models_dir / "weights" / f"{model_name}.pt"
            
            # If not found locally, ultralytics will auto-download
            if not model_path.exists():
                logger.warning(f"{model_name}.pt not found at {model_path}, will auto-download")
                model = YOLO(f"{model_name}.pt")
            else:
                model = YOLO(str(model_path))
            
            # Model specs
            specs = {
                "yolo11n": "2.6M params, fastest",
                "yolo11s": "9.4M params, fast", 
                "yolo11m": "20.1M params, balanced",
                "yolo11x": "56.9M params, most accurate"
            }
            logger.info(f"✓ {model_name.upper()} loaded ({specs.get(model_name, 'unknown specs')})")
            
            return model
            
        except Exception as e:
            logger.error(f"Failed to load YOLO11: {e}")
            raise

    # ========================================================================
    # YOLO-World Detector (Open Vocabulary)
    # ========================================================================
    
    @property
    def yoloworld(self) -> Any:
        """
        Get YOLO-World detector (lazy loaded).
        
        Returns:
            YOLO-World model instance with custom classes set
        """
        if self._yoloworld is None:
            self._yoloworld = self._load_yoloworld()
        return self._yoloworld
    
    def _load_yoloworld(self) -> Any:
        """Load YOLO-World model with open-vocabulary support"""
        try:
            from ultralytics import YOLO
            
            model_name = self.yoloworld_model_name
            logger.info(f"Loading YOLO-World ({model_name})...")
            
            # YOLO-World models auto-download from Ultralytics
            model = YOLO(model_name)

            # IMPORTANT: Move model to the active device *before* setting classes.
            # Ultralytics WorldModel.set_classes() caches a CLIP text model. If
            # set_classes() is run on CPU and the model is later moved to CUDA/MPS,
            # subsequent set_classes() calls can fail with CPU/CUDA tensor mismatch.
            try:
                if getattr(self, "device", None):
                    model.to(self.device)
            except Exception as e:
                logger.warning(f"Failed to move YOLO-World to device '{self.device}': {e}")
            
            # Set custom classes if provided
            if self.yoloworld_classes:
                logger.info(f"  Setting {len(self.yoloworld_classes)} custom classes for open-vocab detection")
                model.set_classes(self.yoloworld_classes)
                logger.info(f"  Classes: {self.yoloworld_classes[:5]}..." if len(self.yoloworld_classes) > 5 else f"  Classes: {self.yoloworld_classes}")
            
            logger.info(f"✓ YOLO-World loaded (open-vocabulary object detection)")
            
            return model
            
        except Exception as e:
            logger.error(f"Failed to load YOLO-World: {e}")
            raise
    
    # ========================================================================
    # GroundingDINO Detector (Transformers)
    # ========================================================================
    
    @property
    def gdino(self) -> tuple[Any, Any]:
        """
        Get GroundingDINO model and processor (lazy loaded).
        
        Returns:
            Tuple of (model, processor)
        """
        if self._gdino_model is None:
            self._gdino_model, self._gdino_processor = self._load_gdino()
        return self._gdino_model, self._gdino_processor
    
    def _load_gdino(self) -> tuple[Any, Any]:
        """Load GroundingDINO model via transformers"""
        try:
            from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
            
            model_id = self.gdino_model_name
            logger.info(f"Loading GroundingDINO ({model_id})...")
            
            processor = AutoProcessor.from_pretrained(model_id)
            model = AutoModelForZeroShotObjectDetection.from_pretrained(model_id).to(self.device)
            
            logger.info(f"✓ GroundingDINO loaded on {self.device}")
            return model, processor
            
        except Exception as e:
            logger.error(f"Failed to load GroundingDINO: {e}")
            raise
    
    # ========================================================================
    # CLIP Embedder
    # ========================================================================
    
    @property
    def clip(self) -> Any:
        """
        Get CLIP embedder (lazy loaded).
        
        Returns:
            CLIPEmbedder instance
        """
        if self._clip is None:
            self._clip = self._load_clip()
        return self._clip
    
    def _load_clip(self) -> Any:
        """Load CLIP model"""
        try:
            from orion.backends.clip_backend import CLIPEmbedder
            
            logger.info("Loading CLIP embedder...")
            
            embedder = CLIPEmbedder(
                model_name="openai/clip-vit-base-patch32",
                device=self.device
            )
            
            logger.info("✓ CLIP loaded (512-dim embeddings)")
            logger.info("  Multimodal: vision + text")
            
            return embedder
            
        except Exception as e:
            logger.error(f"Failed to load CLIP: {e}")
            raise

    # ========================================================================
    # V-JEPA2 Video Embedder (3D-aware for Re-ID)
    # ========================================================================

    @property
    def vjepa2(self) -> Any:
        """
        Get V-JEPA2 embedder (lazy loaded).

        V-JEPA2 is a 3D-aware video encoder that handles the same object
        from different viewing angles better than 2D encoders like CLIP/DINO.

        Returns:
            VJepa2Embedder instance
        """
        if self._vjepa2 is None:
            self._vjepa2 = self._load_vjepa2()
        return self._vjepa2

    def _load_vjepa2(self) -> Any:
        """Load V-JEPA2 model for 3D-aware video embeddings"""
        try:
            from orion.backends.vjepa2_backend import VJepa2Embedder

            logger.info("Loading V-JEPA2 embedder (3D-aware video encoder)…")

            embedder = VJepa2Embedder(
                model_name="facebook/vjepa2-vitl-fpc64-256",
                device=self.device,
            )

            logger.info("✓ V-JEPA2 loaded (3D-aware embeddings for Re-ID)")
            return embedder
        except Exception as e:
            logger.error(f"Failed to load V-JEPA2: {e}")
            raise

    @property
    def reid_embedder(self) -> Any:
        """
        Get the Re-ID embedder (V-JEPA2).

        V-JEPA2 is the only supported Re-ID backend (3D-aware video encoder).
        """
        return self.vjepa2

    # ========================================================================
    # FastVLM Describer
    # ========================================================================
    
    @property
    def fastvlm(self) -> Any:
        """
        Get FastVLM describer (lazy loaded).
        
        Returns:
            FastVLM backend instance
        """
        if self._fastvlm is None:
            self._fastvlm = self._load_fastvlm()
        return self._fastvlm
    
    def _load_fastvlm(self) -> Any:
        """Load FastVLM model"""
        try:
            # Import runtime to select backend
            from .runtime import get_active_backend, select_backend
            
            logger.info("Loading FastVLM describer...")
            
            # Auto-select backend
            backend = get_active_backend()
            if backend is None:
                backend = select_backend()
            
            logger.info(f"  Backend: {backend}")
            
            # Load appropriate backend
            if backend == "mlx":
                from orion.backends.mlx_fastvlm import FastVLMMLXWrapper
                model = FastVLMMLXWrapper()
            else:
                from orion.backends.torch_fastvlm import FastVLMTorchWrapper
                model = FastVLMTorchWrapper()
            
            logger.info("✓ FastVLM loaded (0.5B params)")
            
            return model
            
        except Exception as e:
            logger.error(f"Failed to load FastVLM: {e}")
            raise
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def cleanup(self):
        """Clean up all loaded models and free memory"""
        logger.info("Cleaning up models...")
        
        if self._yolo is not None:
            del self._yolo
            self._yolo = None
        
        if self._clip is not None:
            del self._clip
            self._clip = None
        
        if self._fastvlm is not None:
            del self._fastvlm
            self._fastvlm = None
        if self._vjepa2 is not None:
            del self._vjepa2
            self._vjepa2 = None
        
        # Clear GPU memory
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        elif torch.backends.mps.is_available():
            torch.mps.empty_cache()
        
        logger.info("✓ Cleanup complete")
    
    def unload_perception_models(self):
        """
        Unload perception models (YOLO, V-JEPA2, FastVLM) to free VRAM.
        
        Call this before loading the reasoning LLM to avoid VRAM conflicts.
        This implements the "active model swapping" strategy for limited VRAM.
        """
        logger.info("Unloading perception models for reasoning phase...")
        
        unloaded = []
        
        if self._yolo is not None:
            del self._yolo
            self._yolo = None
            unloaded.append("YOLO")
        
        if self._yoloworld is not None:
            del self._yoloworld
            self._yoloworld = None
            unloaded.append("YOLO-World")
        
        if self._vjepa2 is not None:
            del self._vjepa2
            self._vjepa2 = None
            unloaded.append("V-JEPA2")
        
        if self._fastvlm is not None:
            del self._fastvlm
            self._fastvlm = None
            unloaded.append("FastVLM")
        
        # Clear GPU memory
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        elif torch.backends.mps.is_available():
            torch.mps.empty_cache()
        
        if unloaded:
            logger.info(f"✓ Unloaded: {', '.join(unloaded)}")
        else:
            logger.info("  No perception models were loaded")
        
        return unloaded
    
    def get_vram_status(self) -> dict:
        """Get detailed VRAM status for debugging."""
        status = {
            "device": self.device,
            "models_loaded": {
                "yolo": self._yolo is not None,
                "yoloworld": self._yoloworld is not None,
                "clip": self._clip is not None,
                "fastvlm": self._fastvlm is not None,
                "vjepa2": self._vjepa2 is not None,
            },
        }
        
        if torch.cuda.is_available():
            status["gpu"] = {
                "name": torch.cuda.get_device_name(0),
                "total_memory_gb": torch.cuda.get_device_properties(0).total_memory / 1024**3,
                "allocated_gb": torch.cuda.memory_allocated() / 1024**3,
                "reserved_gb": torch.cuda.memory_reserved() / 1024**3,
                "free_gb": (torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_reserved()) / 1024**3,
            }
        elif torch.backends.mps.is_available():
            status["gpu"] = {
                "name": "Apple Silicon (MPS)",
                "allocated_gb": torch.mps.current_allocated_memory() / 1024**3 if hasattr(torch.mps, 'current_allocated_memory') else "unknown",
            }
        
        return status
    
    def get_memory_usage(self) -> dict:
        """Get current memory usage"""

        usage = {
            "yolo_loaded": self._yolo is not None,
            "yoloworld_loaded": self._yoloworld is not None,
            "clip_loaded": self._clip is not None,
            "fastvlm_loaded": self._fastvlm is not None,
            "vjepa2_loaded": self._vjepa2 is not None,
        }
        
        if torch.cuda.is_available():
            usage["gpu_memory_allocated"] = torch.cuda.memory_allocated() / 1024**3  # GB
            usage["gpu_memory_reserved"] = torch.cuda.memory_reserved() / 1024**3
        
        return usage
    
    def generate_with_ollama(
        self,
        prompt: str,
        model: str = "gemma3:4b",
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """
        Generate text using Ollama LLM.
        
        This is a convenience method for calling Ollama models.
        Requires ollama to be installed and running.
        
        Args:
            prompt: The prompt to send to the LLM
            model: Ollama model name (default: gemma3:4b)
            temperature: Sampling temperature (default: 0.7)
            max_tokens: Maximum tokens to generate (default: 1000)
            
        Returns:
            Generated text response
            
        Raises:
            ImportError: If ollama package is not installed
            RuntimeError: If ollama service is not running
        """
        try:
            import ollama
        except ImportError:
            raise ImportError(
                "Ollama package not installed. Install with: pip install ollama"
            )
        
        try:
            response = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            )
            return response['message']['content']
        except Exception as e:
            raise RuntimeError(f"Ollama generation failed: {e}")
    
    def __repr__(self) -> str:
        return (
            f"ModelManager(device={self.device}, "
            f"yolo={'loaded' if self._yolo else 'not loaded'}, "
            f"clip={'loaded' if self._clip else 'not loaded'}, "
            f"fastvlm={'loaded' if self._fastvlm else 'not loaded'})"
        )


# Convenience function for backward compatibility
def get_model_manager() -> ModelManager:
    """Get singleton ModelManager instance"""
    return ModelManager.get_instance()
