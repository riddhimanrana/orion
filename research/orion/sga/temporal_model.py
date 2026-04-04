"""
Temporal Scene Graph Anticipation Model

A Transformer-based model for predicting FUTURE scene graphs from observed frames.
Inspired by STTran (ICCV 2021) but designed for SGA (anticipation, not recognition).

Architecture:
1. Object Encoder: Encode per-object features (appearance + position + class embedding)
2. Spatial Encoder: Model intra-frame spatial relationships  
3. Temporal Encoder: Model cross-frame temporal evolution
4. Anticipation Decoder: Predict relations at future timesteps

Key Innovation: Instead of just recognizing relations in observed frames,
this model explicitly predicts what relations will exist at FUTURE timesteps.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Sequence
from collections import defaultdict

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class TemporalSGAConfig:
    """Configuration for Temporal SGA Model."""
    
    # Embedding dimensions
    object_embed_dim: int = 512
    relation_embed_dim: int = 256
    position_embed_dim: int = 128
    hidden_dim: int = 512
    
    # Number of classes (Action Genome)
    num_object_classes: int = 36
    num_predicate_classes: int = 26
    
    # Transformer architecture
    num_spatial_layers: int = 2
    num_temporal_layers: int = 3
    num_decoder_layers: int = 2
    num_heads: int = 8
    dropout: float = 0.1
    
    # Sequence parameters
    max_objects_per_frame: int = 20
    max_observed_frames: int = 10
    max_future_frames: int = 5
    
    # Training
    lr: float = 1e-4
    weight_decay: float = 1e-5
    
    # Device
    device: str = "cpu"
    
    def __post_init__(self):
        if torch.cuda.is_available():
            self.device = "cuda"
        elif torch.backends.mps.is_available():
            self.device = "mps"


# ============================================================================
# POSITIONAL ENCODINGS
# ============================================================================

class SinusoidalPositionalEncoding(nn.Module):
    """Sinusoidal positional encoding for temporal sequences."""
    
    def __init__(self, d_model: int, max_len: int = 100, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        
        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model))
        
        pe = torch.zeros(max_len, d_model)
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        
        self.register_buffer('pe', pe)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Tensor of shape (batch, seq_len, dim)
        """
        x = x + self.pe[:x.size(1)]
        return self.dropout(x)


class LearnablePositionalEncoding(nn.Module):
    """Learnable positional encoding."""
    
    def __init__(self, d_model: int, max_len: int = 100, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        self.pe = nn.Embedding(max_len, d_model)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        seq_len = x.size(1)
        positions = torch.arange(seq_len, device=x.device)
        return self.dropout(x + self.pe(positions))


# ============================================================================
# SPATIAL ENCODER (Intra-frame relationships)
# ============================================================================

class SpatialEncoder(nn.Module):
    """
    Encode spatial relationships within a single frame.
    Uses self-attention over all objects in one frame.
    """
    
    def __init__(self, config: TemporalSGAConfig):
        super().__init__()
        self.config = config
        
        # Object feature projection
        self.object_proj = nn.Linear(
            config.object_embed_dim + config.position_embed_dim,
            config.hidden_dim
        )
        
        # Transformer encoder for spatial relationships
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.hidden_dim,
            nhead=config.num_heads,
            dim_feedforward=config.hidden_dim * 4,
            dropout=config.dropout,
            activation='gelu',
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(
            encoder_layer,
            num_layers=config.num_spatial_layers,
        )
        
        self.norm = nn.LayerNorm(config.hidden_dim)
    
    def forward(
        self,
        object_features: torch.Tensor,
        position_features: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Args:
            object_features: (batch, num_objects, object_embed_dim)
            position_features: (batch, num_objects, position_embed_dim)
            mask: (batch, num_objects) - True for valid objects
            
        Returns:
            spatial_features: (batch, num_objects, hidden_dim)
        """
        # Combine object and position features
        combined = torch.cat([object_features, position_features], dim=-1)
        x = self.object_proj(combined)
        
        # Create attention mask (True = masked out)
        attn_mask = None
        if mask is not None:
            attn_mask = ~mask  # Invert for transformer
        
        # Apply spatial transformer
        x = self.transformer(x, src_key_padding_mask=attn_mask)
        x = self.norm(x)
        
        return x


# ============================================================================
# TEMPORAL ENCODER (Cross-frame evolution)
# ============================================================================

class TemporalEncoder(nn.Module):
    """
    Model temporal evolution of scene graphs across frames.
    Uses attention across time dimension.
    """
    
    def __init__(self, config: TemporalSGAConfig):
        super().__init__()
        self.config = config
        
        # Frame-level pooling (aggregate object features per frame)
        self.frame_pool = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.hidden_dim),
        )
        
        # Temporal positional encoding
        self.temporal_pe = LearnablePositionalEncoding(
            config.hidden_dim, 
            max_len=config.max_observed_frames + config.max_future_frames,
            dropout=config.dropout,
        )
        
        # Temporal transformer
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.hidden_dim,
            nhead=config.num_heads,
            dim_feedforward=config.hidden_dim * 4,
            dropout=config.dropout,
            activation='gelu',
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(
            encoder_layer,
            num_layers=config.num_temporal_layers,
        )
        
        self.norm = nn.LayerNorm(config.hidden_dim)
    
    def forward(
        self,
        frame_features: torch.Tensor,
        frame_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Args:
            frame_features: (batch, num_frames, num_objects, hidden_dim)
            frame_mask: (batch, num_frames) - True for valid frames
            
        Returns:
            temporal_features: (batch, num_frames, hidden_dim)
        """
        batch_size, num_frames, num_objects, hidden_dim = frame_features.shape
        
        # Pool objects within each frame (mean pooling)
        # Shape: (batch, num_frames, hidden_dim)
        pooled = frame_features.mean(dim=2)
        pooled = self.frame_pool(pooled)
        
        # Add temporal positional encoding
        pooled = self.temporal_pe(pooled)
        
        # Create attention mask
        attn_mask = None
        if frame_mask is not None:
            attn_mask = ~frame_mask
        
        # Apply temporal transformer
        x = self.transformer(pooled, src_key_padding_mask=attn_mask)
        x = self.norm(x)
        
        return x


# ============================================================================
# ANTICIPATION DECODER (Predict future relations)
# ============================================================================

class AnticipationDecoder(nn.Module):
    """
    Decode future scene graph predictions.
    Takes encoded temporal context and predicts relations at future timesteps.
    """
    
    def __init__(self, config: TemporalSGAConfig):
        super().__init__()
        self.config = config
        
        # Future timestep queries (learnable)
        self.future_queries = nn.Embedding(
            config.max_future_frames,
            config.hidden_dim
        )
        
        # Cross-attention decoder
        decoder_layer = nn.TransformerDecoderLayer(
            d_model=config.hidden_dim,
            nhead=config.num_heads,
            dim_feedforward=config.hidden_dim * 4,
            dropout=config.dropout,
            activation='gelu',
            batch_first=True,
        )
        self.decoder = nn.TransformerDecoder(
            decoder_layer,
            num_layers=config.num_decoder_layers,
        )
        
        # Relation prediction head
        # For each pair of objects, predict predicate distribution
        self.pair_encoder = nn.Sequential(
            nn.Linear(config.hidden_dim * 3, config.hidden_dim),  # subj + obj + context
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim, config.hidden_dim),
        )
        
        # Predicate classifier
        self.predicate_classifier = nn.Linear(
            config.hidden_dim, 
            config.num_predicate_classes
        )
        
        # Existence classifier (whether relation exists at all)
        self.existence_classifier = nn.Linear(config.hidden_dim, 1)
        
        self.norm = nn.LayerNorm(config.hidden_dim)
    
    def forward(
        self,
        temporal_context: torch.Tensor,
        object_features: torch.Tensor,
        num_future_frames: int = 1,
        object_mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            temporal_context: (batch, observed_frames, hidden_dim)
            object_features: (batch, num_objects, hidden_dim) - from last observed frame
            num_future_frames: Number of future frames to predict
            object_mask: (batch, num_objects) - True for valid objects
            
        Returns:
            predicate_logits: (batch, num_future, num_pairs, num_predicates)
            existence_logits: (batch, num_future, num_pairs, 1)
        """
        batch_size = temporal_context.size(0)
        num_objects = object_features.size(1)
        device = temporal_context.device
        
        # Get future queries
        future_indices = torch.arange(num_future_frames, device=device)
        queries = self.future_queries(future_indices)  # (num_future, hidden_dim)
        queries = queries.unsqueeze(0).expand(batch_size, -1, -1)  # (batch, num_future, hidden_dim)
        
        # Decode future context
        future_context = self.decoder(queries, temporal_context)  # (batch, num_future, hidden_dim)
        future_context = self.norm(future_context)
        
        # Generate all subject-object pairs
        # Typically person (subject) to all objects
        # Shape: (batch, num_future, num_pairs, hidden_dim * 3)
        num_pairs = num_objects * (num_objects - 1)  # All ordered pairs
        
        pair_features_list = []
        for f in range(num_future_frames):
            ctx = future_context[:, f, :]  # (batch, hidden_dim)
            
            for i in range(num_objects):
                for j in range(num_objects):
                    if i == j:
                        continue
                    
                    subj_feat = object_features[:, i, :]  # (batch, hidden_dim)
                    obj_feat = object_features[:, j, :]   # (batch, hidden_dim)
                    
                    # Combine subject, object, and temporal context
                    pair_feat = torch.cat([subj_feat, obj_feat, ctx], dim=-1)  # (batch, hidden_dim * 3)
                    pair_features_list.append(pair_feat)
        
        if not pair_features_list:
            # No valid pairs
            return (
                torch.zeros(batch_size, num_future_frames, 0, self.config.num_predicate_classes, device=device),
                torch.zeros(batch_size, num_future_frames, 0, 1, device=device),
            )
        
        # Stack pair features: (batch, num_future * num_pairs, hidden_dim * 3)
        pair_features = torch.stack(pair_features_list, dim=1)
        
        # Encode pairs
        pair_encoded = self.pair_encoder(pair_features)  # (batch, num_future * num_pairs, hidden_dim)
        
        # Classify predicates and existence
        predicate_logits = self.predicate_classifier(pair_encoded)  # (batch, ..., num_predicates)
        existence_logits = self.existence_classifier(pair_encoded)  # (batch, ..., 1)
        
        # Reshape to separate future frames and pairs
        total_items = num_future_frames * num_pairs
        predicate_logits = predicate_logits.view(batch_size, num_future_frames, num_pairs, -1)
        existence_logits = existence_logits.view(batch_size, num_future_frames, num_pairs, 1)
        
        return predicate_logits, existence_logits


# ============================================================================
# FULL TEMPORAL SGA MODEL
# ============================================================================

class TemporalSGAModel(nn.Module):
    """
    Full Temporal Scene Graph Anticipation Model.
    
    Pipeline:
    1. Encode object features (appearance + bbox + class)
    2. Apply spatial encoder per frame
    3. Apply temporal encoder across frames
    4. Decode future relations with anticipation decoder
    """
    
    def __init__(self, config: TemporalSGAConfig):
        super().__init__()
        self.config = config
        
        # Object class embedding
        self.object_class_embed = nn.Embedding(
            config.num_object_classes + 1,  # +1 for padding
            config.object_embed_dim // 2
        )
        
        # Appearance feature projection (from visual backbone)
        self.appearance_proj = nn.Linear(
            2048,  # Typical ResNet feature dim
            config.object_embed_dim // 2
        )
        
        # Position encoder (bbox → embedding)
        self.position_encoder = nn.Sequential(
            nn.Linear(4, config.position_embed_dim // 2),  # x1, y1, x2, y2
            nn.GELU(),
            nn.Linear(config.position_embed_dim // 2, config.position_embed_dim),
        )
        
        # Encoders
        self.spatial_encoder = SpatialEncoder(config)
        self.temporal_encoder = TemporalEncoder(config)
        
        # Decoder
        self.anticipation_decoder = AnticipationDecoder(config)
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize weights with Xavier/Kaiming initialization."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, mean=0, std=0.02)
    
    def encode_objects(
        self,
        class_ids: torch.Tensor,
        bboxes: torch.Tensor,
        appearance_features: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Encode objects into feature vectors.
        
        Args:
            class_ids: (batch, num_frames, num_objects) - object class indices
            bboxes: (batch, num_frames, num_objects, 4) - normalized bboxes
            appearance_features: (batch, num_frames, num_objects, 2048) - visual features
            
        Returns:
            object_features: (batch, num_frames, num_objects, object_embed_dim)
            position_features: (batch, num_frames, num_objects, position_embed_dim)
        """
        # Class embeddings
        class_embeds = self.object_class_embed(class_ids)  # (..., embed_dim // 2)
        
        # Appearance features (use zeros if not provided)
        if appearance_features is not None:
            appearance_embeds = self.appearance_proj(appearance_features)
        else:
            # Use random features (for testing) or zeros
            appearance_embeds = torch.zeros(
                *class_ids.shape, self.config.object_embed_dim // 2,
                device=class_ids.device
            )
        
        # Combine class and appearance
        object_features = torch.cat([class_embeds, appearance_embeds], dim=-1)
        
        # Position encoding
        position_features = self.position_encoder(bboxes)
        
        return object_features, position_features
    
    def forward(
        self,
        class_ids: torch.Tensor,
        bboxes: torch.Tensor,
        appearance_features: Optional[torch.Tensor] = None,
        object_mask: Optional[torch.Tensor] = None,
        frame_mask: Optional[torch.Tensor] = None,
        num_future_frames: int = 1,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass for anticipation.
        
        Args:
            class_ids: (batch, num_frames, num_objects)
            bboxes: (batch, num_frames, num_objects, 4)
            appearance_features: (batch, num_frames, num_objects, 2048)
            object_mask: (batch, num_frames, num_objects) - True for valid
            frame_mask: (batch, num_frames) - True for valid frames
            num_future_frames: Number of future frames to predict
            
        Returns:
            Dict with:
                - predicate_logits: (batch, num_future, num_pairs, num_predicates)
                - existence_logits: (batch, num_future, num_pairs, 1)
        """
        batch_size, num_frames, num_objects = class_ids.shape
        
        # 1. Encode objects
        object_features, position_features = self.encode_objects(
            class_ids, bboxes, appearance_features
        )
        
        # 2. Apply spatial encoder per frame
        spatial_features_list = []
        for t in range(num_frames):
            obj_feat = object_features[:, t]  # (batch, num_objects, dim)
            pos_feat = position_features[:, t]
            mask = object_mask[:, t] if object_mask is not None else None
            
            spatial_feat = self.spatial_encoder(obj_feat, pos_feat, mask)
            spatial_features_list.append(spatial_feat)
        
        # Stack: (batch, num_frames, num_objects, hidden_dim)
        spatial_features = torch.stack(spatial_features_list, dim=1)
        
        # 3. Apply temporal encoder
        temporal_features = self.temporal_encoder(spatial_features, frame_mask)
        
        # 4. Decode future predictions
        # Use object features from last observed frame
        last_object_features = spatial_features[:, -1]  # (batch, num_objects, hidden_dim)
        last_object_mask = object_mask[:, -1] if object_mask is not None else None
        
        predicate_logits, existence_logits = self.anticipation_decoder(
            temporal_features,
            last_object_features,
            num_future_frames,
            last_object_mask,
        )
        
        return {
            'predicate_logits': predicate_logits,
            'existence_logits': existence_logits,
            'temporal_features': temporal_features,
        }
    
    def predict(
        self,
        class_ids: torch.Tensor,
        bboxes: torch.Tensor,
        appearance_features: Optional[torch.Tensor] = None,
        object_mask: Optional[torch.Tensor] = None,
        frame_mask: Optional[torch.Tensor] = None,
        num_future_frames: int = 1,
        threshold: float = 0.5,
    ) -> List[Dict]:
        """
        Predict future relations.
        
        Returns:
            List of predictions per batch item, each containing:
                - future_frame: int
                - subject_idx: int
                - object_idx: int
                - predicate: int
                - confidence: float
        """
        self.eval()
        with torch.no_grad():
            outputs = self.forward(
                class_ids, bboxes, appearance_features,
                object_mask, frame_mask, num_future_frames
            )
        
        predicate_logits = outputs['predicate_logits']
        existence_logits = outputs['existence_logits']
        
        batch_size = predicate_logits.size(0)
        num_objects = class_ids.size(2)
        
        predictions = []
        
        for b in range(batch_size):
            batch_preds = []
            
            pair_idx = 0
            for i in range(num_objects):
                for j in range(num_objects):
                    if i == j:
                        continue
                    
                    for f in range(num_future_frames):
                        # Check existence
                        exist_prob = torch.sigmoid(existence_logits[b, f, pair_idx, 0]).item()
                        
                        if exist_prob < threshold:
                            continue
                        
                        # Get predicate
                        pred_probs = F.softmax(predicate_logits[b, f, pair_idx], dim=-1)
                        pred_class = pred_probs.argmax().item()
                        pred_conf = pred_probs[pred_class].item()
                        
                        batch_preds.append({
                            'future_frame': f,
                            'subject_idx': i,
                            'object_idx': j,
                            'predicate': pred_class,
                            'confidence': exist_prob * pred_conf,
                        })
                    
                    pair_idx += 1
            
            predictions.append(batch_preds)
        
        return predictions


# ============================================================================
# LOSS FUNCTIONS
# ============================================================================

class SGALoss(nn.Module):
    """Combined loss for SGA training."""
    
    def __init__(
        self,
        predicate_weight: float = 1.0,
        existence_weight: float = 1.0,
        class_weights: Optional[torch.Tensor] = None,
    ):
        super().__init__()
        self.predicate_weight = predicate_weight
        self.existence_weight = existence_weight
        
        self.predicate_loss = nn.CrossEntropyLoss(
            weight=class_weights,
            reduction='mean',
            ignore_index=-1,
        )
        self.existence_loss = nn.BCEWithLogitsLoss(reduction='mean')
    
    def forward(
        self,
        predicate_logits: torch.Tensor,
        existence_logits: torch.Tensor,
        target_predicates: torch.Tensor,
        target_existence: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute loss.
        
        Args:
            predicate_logits: (batch, num_future, num_pairs, num_predicates)
            existence_logits: (batch, num_future, num_pairs, 1)
            target_predicates: (batch, num_future, num_pairs) - class indices
            target_existence: (batch, num_future, num_pairs) - 0/1
        """
        batch_size, num_future, num_pairs, num_preds = predicate_logits.shape
        
        # Reshape for loss computation
        pred_flat = predicate_logits.view(-1, num_preds)
        target_pred_flat = target_predicates.view(-1)
        
        exist_flat = existence_logits.view(-1)
        target_exist_flat = target_existence.view(-1).float()
        
        # Compute losses
        loss_predicate = self.predicate_loss(pred_flat, target_pred_flat)
        loss_existence = self.existence_loss(exist_flat, target_exist_flat)
        
        total_loss = (
            self.predicate_weight * loss_predicate +
            self.existence_weight * loss_existence
        )
        
        return {
            'total': total_loss,
            'predicate': loss_predicate,
            'existence': loss_existence,
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_model(
    num_object_classes: int = 36,
    num_predicate_classes: int = 26,
    device: str = "auto",
) -> TemporalSGAModel:
    """Create a temporal SGA model with default settings."""
    config = TemporalSGAConfig(
        num_object_classes=num_object_classes,
        num_predicate_classes=num_predicate_classes,
    )
    
    if device == "auto":
        if torch.cuda.is_available():
            config.device = "cuda"
        elif torch.backends.mps.is_available():
            config.device = "mps"
        else:
            config.device = "cpu"
    else:
        config.device = device
    
    model = TemporalSGAModel(config)
    return model.to(config.device)


def load_pretrained(
    checkpoint_path: str,
    device: str = "auto",
) -> TemporalSGAModel:
    """Load a pretrained model from checkpoint."""
    checkpoint = torch.load(checkpoint_path, map_location='cpu')
    
    config = checkpoint.get('config', TemporalSGAConfig())
    model = TemporalSGAModel(config)
    model.load_state_dict(checkpoint['model_state_dict'])
    
    if device == "auto":
        if torch.cuda.is_available():
            device = "cuda"
        elif torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
    
    return model.to(device)


if __name__ == "__main__":
    # Quick test
    print("Testing TemporalSGAModel...")
    
    config = TemporalSGAConfig(
        num_object_classes=36,
        num_predicate_classes=26,
    )
    
    model = TemporalSGAModel(config)
    print(f"Model created with {sum(p.numel() for p in model.parameters()):,} parameters")
    
    # Create dummy input
    batch_size = 2
    num_frames = 5
    num_objects = 4
    
    class_ids = torch.randint(0, 36, (batch_size, num_frames, num_objects))
    bboxes = torch.rand(batch_size, num_frames, num_objects, 4)
    object_mask = torch.ones(batch_size, num_frames, num_objects, dtype=torch.bool)
    frame_mask = torch.ones(batch_size, num_frames, dtype=torch.bool)
    
    # Forward pass
    outputs = model(
        class_ids, bboxes,
        object_mask=object_mask,
        frame_mask=frame_mask,
        num_future_frames=2,
    )
    
    print(f"Predicate logits shape: {outputs['predicate_logits'].shape}")
    print(f"Existence logits shape: {outputs['existence_logits'].shape}")
    print("✓ Test passed!")
