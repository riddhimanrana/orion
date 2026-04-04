"""
V-JEPA2 Embedder Backend for Orion v2

This replaces CLIP/DINO for Re-ID with a 3D-aware video encoder that
handles the same object from different viewing angles.

Based on Shivank's recommendation to use video encoders for better Re-ID.
"""

import logging
from pathlib import Path
from typing import Optional, Union
import numpy as np

import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class VJepa2Embedder:
    """
    V-JEPA2 video encoder for object embeddings.
    
    Key features:
    - 3D-aware: trained for prediction and robotics
    - Handles same object from different angles
    - Can treat single image as 1-frame video
    - Uses lightweight ViT encoder
    
    Two modes:
    - single: Best single frame per track (simpler, start here)
    - video: Multi-crop as mini-video (better, more complex)
    """
    
    def __init__(
        self,
        model_name: str = "facebook/vjepa2-vitl-fpc64-256",
        device: str = "cuda",
        dtype: torch.dtype = torch.float16,
    ):
        self.model_name = model_name
        self.device = device
        self.dtype = dtype
        self._model = None
        self._processor = None
        self._loaded = False
    
    def _ensure_loaded(self):
        """Lazy load model on first use."""
        if self._loaded:
            return
        
        logger.info(f"Loading V-JEPA2: {self.model_name}")
        
        try:
            from transformers import AutoVideoProcessor, AutoModel
            
            self._processor = AutoVideoProcessor.from_pretrained(self.model_name)
            self._model = AutoModel.from_pretrained(
                self.model_name,
                torch_dtype=self.dtype,
                device_map="auto" if self.device == "cuda" else None,
                attn_implementation="sdpa"  # Scaled dot-product attention (faster)
            )
            
            if self.device != "cuda":
                self._model = self._model.to(self.device)
            
            self._model.eval()
            self._loaded = True
            logger.info(f"✓ V-JEPA2 loaded on {self.device}")
            
        except Exception as e:
            logger.error(f"Failed to load V-JEPA2: {e}")
            raise
    
    @property
    def embedding_dim(self) -> int:
        """Output embedding dimension."""
        # V-JEPA2 ViT-L has 1024-dim features
        return 1024
    
    def embed_single_image(self, image: Union[np.ndarray, torch.Tensor]) -> torch.Tensor:
        """
        Embed a single image as a repeated-frame video.
        
        Per official V-JEPA2 docs: "To load an image, simply copy the image 
        to the desired number of frames."
        
        Args:
            image: Image as numpy array (H, W, C) or tensor (C, H, W)
            
        Returns:
            Embedding tensor of shape (1, embedding_dim)
        """
        self._ensure_loaded()
        
        # Convert to tensor if needed
        if isinstance(image, np.ndarray):
            # Assume HWC, convert to CHW
            if image.ndim == 3 and image.shape[-1] in [1, 3, 4]:
                image = np.transpose(image, (2, 0, 1))
            image = torch.from_numpy(image).float()
        
        # V-JEPA2 expects T x C x H x W format
        if image.ndim == 3:
            image = image.unsqueeze(0)  # Add time dimension: 1 x C x H x W
        
        # Process through V-JEPA2 processor
        inputs = self._processor(image, return_tensors="pt")
        inputs = {k: v.to(self._model.device) for k, v in inputs.items()}
        
        # Per docs: repeat image 16 times for single image embedding
        if 'pixel_values_videos' in inputs:
            inputs['pixel_values_videos'] = inputs['pixel_values_videos'].repeat(1, 16, 1, 1, 1)
        
        with torch.no_grad():
            # Use get_vision_features() per official docs
            # Returns [batch, num_patches, hidden_dim] - need to pool
            features = self._model.get_vision_features(**inputs)
            
            # Pool across patches (mean pooling)
            # Shape: [batch, num_patches, 1024] -> [batch, 1024]
            embedding = features.mean(dim=1)
            
            # L2 normalize for cosine similarity
            embedding = torch.nn.functional.normalize(embedding, p=2, dim=-1)
        
        return embedding.cpu().float()

    def embed_batch(
        self, 
        images: list[Union[np.ndarray, torch.Tensor]],
        batch_size: int = 8
    ) -> list[torch.Tensor]:
        """
        Batch embed multiple images for Re-ID efficiency.
        
        Process images in batches to maximize GPU utilization.
        
        Args:
            images: List of images as numpy arrays (H, W, C) or tensors (C, H, W)
            batch_size: Number of images to process at once
            
        Returns:
            List of embedding tensors, each of shape (1, embedding_dim)
        """
        self._ensure_loaded()
        
        if not images:
            return []
        
        # Process in batches
        all_embeddings = []
        
        for batch_start in range(0, len(images), batch_size):
            batch_images = images[batch_start:batch_start + batch_size]
            
            # Convert all images to tensors
            batch_tensors = []
            for image in batch_images:
                if isinstance(image, np.ndarray):
                    if image.ndim == 3 and image.shape[-1] in [1, 3, 4]:
                        image = np.transpose(image, (2, 0, 1))
                    image = torch.from_numpy(image).float()
                
                # Add time dimension: 1 x C x H x W
                if image.ndim == 3:
                    image = image.unsqueeze(0)
                batch_tensors.append(image)
            
            # Process each image through the processor individually
            # (V-JEPA2 processor may have inconsistent batch handling)
            processed_batch = []
            for img_tensor in batch_tensors:
                inputs = self._processor(img_tensor, return_tensors="pt")
                # Repeat for single-image embedding
                if 'pixel_values_videos' in inputs:
                    inputs['pixel_values_videos'] = inputs['pixel_values_videos'].repeat(1, 16, 1, 1, 1)
                processed_batch.append(inputs['pixel_values_videos'])
            
            # Stack into batch: [batch_size, 16, C, H, W]
            try:
                batch_input = torch.cat(processed_batch, dim=0).to(self._model.device)
            except RuntimeError:
                # Fallback to sequential if shapes don't match (different image sizes)
                logger.debug("Batch shapes mismatched, falling back to sequential")
                for img in batch_images:
                    all_embeddings.append(self.embed_single_image(img))
                continue
            
            with torch.no_grad():
                features = self._model.get_vision_features(pixel_values_videos=batch_input)
                embeddings = features.mean(dim=1)  # Pool across patches
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=-1)
            
            # Split back into individual embeddings
            for i in range(embeddings.shape[0]):
                all_embeddings.append(embeddings[i:i+1].cpu().float())
        
        return all_embeddings
    
    def embed_video_sequence(
        self, 
        frames: list[Union[np.ndarray, torch.Tensor]],
        max_frames: int = 64  # V-JEPA2 uses 64 frames (fpc64 in model name)
    ) -> torch.Tensor:
        """
        Embed a sequence of frames as a video.
        
        This is Option B from Shivank's recommendation:
        Combine all crops from a track into a video and use video encoder.
        Even if noisy, V-JEPA2 handles temporal noise well.
        
        Args:
            frames: List of frames as numpy arrays or tensors
            max_frames: Maximum number of frames to use (V-JEPA2-vitl-fpc64 uses 64)
            
        Returns:
            Embedding tensor of shape (1, embedding_dim)
        """
        self._ensure_loaded()
        
        if len(frames) == 0:
            raise ValueError("No frames provided")
        
        # Sample frames evenly if we have too many
        if len(frames) > max_frames:
            indices = np.linspace(0, len(frames) - 1, max_frames, dtype=int)
            frames = [frames[i] for i in indices]
        
        # Convert all frames to tensors
        tensors = []
        for frame in frames:
            if isinstance(frame, np.ndarray):
                if frame.ndim == 3 and frame.shape[-1] in [1, 3, 4]:
                    frame = np.transpose(frame, (2, 0, 1))
                frame = torch.from_numpy(frame).float()
            tensors.append(frame)
        
        # Stack as video: T x C x H x W
        video = torch.stack(tensors)
        
        # Process
        inputs = self._processor(video, return_tensors="pt")
        inputs = {k: v.to(self._model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            # Use get_vision_features() per official V-JEPA2 docs
            # Returns [batch, num_patches, hidden_dim] - need to pool
            features = self._model.get_vision_features(**inputs)
            
            # Pool across patches (mean pooling)
            embedding = features.mean(dim=1)
            
            # L2 normalize for cosine similarity
            embedding = torch.nn.functional.normalize(embedding, p=2, dim=-1)
        
        return embedding.cpu().float()
    
    def embed_track_crops(
        self,
        crops: list[np.ndarray],
        mode: str = "single",
        best_frame_idx: Optional[int] = None
    ) -> torch.Tensor:
        """
        Embed crops from a track.
        
        Args:
            crops: List of crop images from the track
            mode: "single" (best frame) or "video" (all frames as video)
            best_frame_idx: Index of best frame for single mode (default: middle)
            
        Returns:
            Embedding tensor of shape (1, embedding_dim)
        """
        if len(crops) == 0:
            raise ValueError("No crops provided")
        
        if mode == "single":
            # Use single best frame
            if best_frame_idx is None:
                best_frame_idx = len(crops) // 2  # Middle frame
            return self.embed_single_image(crops[best_frame_idx])
        
        elif mode == "video":
            # Use all frames as video
            return self.embed_video_sequence(crops)
        
        else:
            raise ValueError(f"Unknown mode: {mode}")
    
    def compute_similarity(
        self, 
        embedding1: torch.Tensor, 
        embedding2: torch.Tensor
    ) -> float:
        """
        Compute cosine similarity between two embeddings.
        """
        # Normalize
        e1 = F.normalize(embedding1.flatten(), dim=0)
        e2 = F.normalize(embedding2.flatten(), dim=0)
        
        # Cosine similarity
        return float(torch.dot(e1, e2))


class VideoMAEEmbedder:
    """
    Alternative: VideoMAE embedder.
    
    VideoMAE is heavier than V-JEPA2 but may work better for some cases.
    Use this if V-JEPA2 doesn't give good results.
    """
    
    def __init__(
        self,
        model_name: str = "MCG-NJU/videomae-base",
        device: str = "cuda",
    ):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._processor = None
        self._loaded = False
    
    def _ensure_loaded(self):
        if self._loaded:
            return
        
        logger.info(f"Loading VideoMAE: {self.model_name}")
        
        from transformers import VideoMAEImageProcessor, VideoMAEModel
        
        self._processor = VideoMAEImageProcessor.from_pretrained(self.model_name)
        self._model = VideoMAEModel.from_pretrained(self.model_name)
        self._model = self._model.to(self.device)
        self._model.eval()
        self._loaded = True
        logger.info(f"✓ VideoMAE loaded on {self.device}")
    
    @property
    def embedding_dim(self) -> int:
        return 768  # VideoMAE base
    
    def embed_video_sequence(
        self, 
        frames: list[np.ndarray],
        num_frames: int = 16
    ) -> torch.Tensor:
        """
        Embed a video sequence.
        
        VideoMAE expects exactly 16 frames by default.
        """
        self._ensure_loaded()
        
        # Ensure we have exactly num_frames
        if len(frames) < num_frames:
            # Repeat frames
            indices = np.linspace(0, len(frames) - 1, num_frames, dtype=int)
            frames = [frames[i] for i in indices]
        elif len(frames) > num_frames:
            # Sample frames
            indices = np.linspace(0, len(frames) - 1, num_frames, dtype=int)
            frames = [frames[i] for i in indices]
        
        # Process
        inputs = self._processor(frames, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self._model(**inputs)
        
        # Pool over sequence
        embedding = outputs.last_hidden_state.mean(dim=1)
        
        return embedding.cpu()


def get_embedder(
    backend: str = "vjepa2",
    device: str = "cuda",
    **kwargs
) -> Union[VJepa2Embedder, VideoMAEEmbedder]:
    """
    Factory function to get the appropriate embedder.
    
    Args:
        backend: "vjepa2" or "videomae"
        device: "cuda", "cpu", or "mps"
        **kwargs: Additional arguments for embedder
        
    Returns:
        Embedder instance
    """
    if backend == "vjepa2":
        return VJepa2Embedder(device=device, **kwargs)
    elif backend == "videomae":
        return VideoMAEEmbedder(device=device, **kwargs)
    else:
        raise ValueError(f"Unknown embedder backend: {backend}")
