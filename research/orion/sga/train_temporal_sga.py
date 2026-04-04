"""
Training Script for Temporal SGA Model

This script trains the temporal scene graph anticipation model on Action Genome.
It follows the proper SGA protocol:
1. Observe first F% of frames
2. Predict relations for future (1-F)% frames
3. Evaluate predictions against ground truth future relations

Usage:
    python -m orion.sga.train_temporal_sga \
        --annotation_path datasets/ActionGenome/annotations/object_bbox_and_relationship.pkl \
        --input_fraction 0.5 \
        --epochs 50 \
        --batch_size 8
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from tqdm import tqdm

from .temporal_model import TemporalSGAModel, TemporalSGAConfig, SGALoss
from .ag_dataset import (
    ActionGenomeDataset, 
    SGABatch, 
    create_sga_dataloaders,
    AG_ALL_PREDICATES,
    AG_OBJECT_CLASSES,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# METRICS
# ============================================================================

def compute_recall_at_k(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    existence_mask: torch.Tensor,
    k_values: List[int] = [10, 20, 50],
) -> Dict[str, float]:
    """
    Compute Recall@K for predictions.
    
    Args:
        predictions: (batch, num_future, num_pairs, num_predicates) - logits
        targets: (batch, num_future, num_pairs) - ground truth predicate indices
        existence_mask: (batch, num_future, num_pairs) - 1 where GT relation exists
        k_values: List of K values for R@K
        
    Returns:
        Dict with R@K for each K
    """
    batch_size = predictions.size(0)
    num_future = predictions.size(1)
    num_pairs = predictions.size(2)
    num_preds = predictions.size(3)
    
    metrics = {}
    
    # Flatten for easier processing
    # predictions: (batch * num_future * num_pairs, num_predicates)
    pred_flat = predictions.view(-1, num_preds)
    target_flat = targets.view(-1)
    mask_flat = existence_mask.view(-1)
    
    # Get confidence scores for each prediction
    # For each (batch, future, pair), get max predicate confidence
    pred_probs = F.softmax(pred_flat, dim=-1)
    pred_classes = pred_probs.argmax(dim=-1)
    pred_confs = pred_probs.max(dim=-1).values
    
    # Only consider positions with GT relations
    valid_mask = mask_flat > 0
    
    if valid_mask.sum() == 0:
        return {f'R@{k}': 0.0 for k in k_values}
    
    # Get valid predictions and targets
    valid_pred_classes = pred_classes[valid_mask]
    valid_pred_confs = pred_confs[valid_mask]
    valid_targets = target_flat[valid_mask]
    
    # Check correctness
    correct = (valid_pred_classes == valid_targets).float()
    
    # Sort by confidence
    sorted_indices = valid_pred_confs.argsort(descending=True)
    sorted_correct = correct[sorted_indices]
    
    # Compute R@K
    num_gt = valid_mask.sum().item()
    
    for k in k_values:
        top_k = min(k, len(sorted_correct))
        hits = sorted_correct[:top_k].sum().item()
        recall = hits / num_gt if num_gt > 0 else 0.0
        metrics[f'R@{k}'] = recall * 100  # As percentage
    
    return metrics


def compute_mean_recall_at_k(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    existence_mask: torch.Tensor,
    k_values: List[int] = [10, 20, 50],
    num_predicates: int = 23,
) -> Dict[str, float]:
    """
    Compute mean Recall@K (per-predicate average).
    
    This is more balanced - doesn't let frequent predicates dominate.
    """
    batch_size = predictions.size(0)
    num_future = predictions.size(1)
    num_pairs = predictions.size(2)
    
    # Flatten
    pred_flat = predictions.view(-1, predictions.size(-1))
    target_flat = targets.view(-1)
    mask_flat = existence_mask.view(-1)
    
    # Get predictions
    pred_probs = F.softmax(pred_flat, dim=-1)
    pred_classes = pred_probs.argmax(dim=-1)
    pred_confs = pred_probs.max(dim=-1).values
    
    metrics = {}
    
    for k in k_values:
        per_class_recalls = []
        
        for cls in range(num_predicates):
            # Get samples of this class
            cls_mask = (target_flat == cls) & (mask_flat > 0)
            
            if cls_mask.sum() == 0:
                continue
            
            # Get predictions for this class
            cls_pred_classes = pred_classes[cls_mask]
            cls_pred_confs = pred_confs[cls_mask]
            
            # Correct predictions
            correct = (cls_pred_classes == cls).float()
            
            # Sort by confidence and take top-k
            sorted_indices = cls_pred_confs.argsort(descending=True)
            sorted_correct = correct[sorted_indices]
            
            top_k = min(k, len(sorted_correct))
            hits = sorted_correct[:top_k].sum().item()
            recall = hits / cls_mask.sum().item()
            
            per_class_recalls.append(recall)
        
        mean_recall = sum(per_class_recalls) / len(per_class_recalls) if per_class_recalls else 0.0
        metrics[f'mR@{k}'] = mean_recall * 100
    
    return metrics


# ============================================================================
# TRAINING LOOP
# ============================================================================

class SGATrainer:
    """Trainer for Temporal SGA Model."""
    
    def __init__(
        self,
        model: TemporalSGAModel,
        train_loader,
        val_loader,
        config: Dict,
        output_dir: str = "checkpoints/sga",
    ):
        self.model = model
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Device
        self.device = next(model.parameters()).device
        
        # Loss
        self.loss_fn = SGALoss(
            predicate_weight=1.0,
            existence_weight=0.5,
        )
        
        # Optimizer
        self.optimizer = AdamW(
            model.parameters(),
            lr=config.get('lr', 1e-4),
            weight_decay=config.get('weight_decay', 1e-5),
        )
        
        # Scheduler
        self.scheduler = CosineAnnealingLR(
            self.optimizer,
            T_max=config.get('epochs', 50),
            eta_min=1e-6,
        )
        
        # Tracking
        self.best_recall = 0.0
        self.history = {
            'train_loss': [],
            'val_loss': [],
            'val_recall': [],
        }
    
    def train_epoch(self, epoch: int) -> Dict[str, float]:
        """Train for one epoch."""
        self.model.train()
        
        total_loss = 0.0
        total_pred_loss = 0.0
        total_exist_loss = 0.0
        num_batches = 0
        
        pbar = tqdm(self.train_loader, desc=f"Epoch {epoch}")
        
        for batch in pbar:
            # Move to device
            class_ids = batch.class_ids.to(self.device)
            bboxes = batch.bboxes.to(self.device)
            object_mask = batch.object_mask.to(self.device)
            frame_mask = batch.frame_mask.to(self.device)
            target_predicates = batch.target_predicates.to(self.device)
            target_existence = batch.target_existence.to(self.device)
            
            # Forward pass
            outputs = self.model(
                class_ids=class_ids,
                bboxes=bboxes,
                object_mask=object_mask,
                frame_mask=frame_mask,
                num_future_frames=batch.num_future_frames,
            )
            
            # Compute loss
            losses = self.loss_fn(
                outputs['predicate_logits'],
                outputs['existence_logits'],
                target_predicates,
                target_existence,
            )
            
            # Backward pass
            self.optimizer.zero_grad()
            losses['total'].backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            
            self.optimizer.step()
            
            # Track losses
            total_loss += losses['total'].item()
            total_pred_loss += losses['predicate'].item()
            total_exist_loss += losses['existence'].item()
            num_batches += 1
            
            pbar.set_postfix({
                'loss': f"{losses['total'].item():.4f}",
                'pred': f"{losses['predicate'].item():.4f}",
            })
        
        return {
            'loss': total_loss / num_batches,
            'pred_loss': total_pred_loss / num_batches,
            'exist_loss': total_exist_loss / num_batches,
        }
    
    @torch.no_grad()
    def validate(self) -> Dict[str, float]:
        """Validate on test set."""
        self.model.eval()
        
        total_loss = 0.0
        all_predictions = []
        all_targets = []
        all_existence = []
        num_batches = 0
        
        for batch in tqdm(self.val_loader, desc="Validating"):
            # Move to device
            class_ids = batch.class_ids.to(self.device)
            bboxes = batch.bboxes.to(self.device)
            object_mask = batch.object_mask.to(self.device)
            frame_mask = batch.frame_mask.to(self.device)
            target_predicates = batch.target_predicates.to(self.device)
            target_existence = batch.target_existence.to(self.device)
            
            # Forward pass
            outputs = self.model(
                class_ids=class_ids,
                bboxes=bboxes,
                object_mask=object_mask,
                frame_mask=frame_mask,
                num_future_frames=batch.num_future_frames,
            )
            
            # Compute loss
            losses = self.loss_fn(
                outputs['predicate_logits'],
                outputs['existence_logits'],
                target_predicates,
                target_existence,
            )
            
            total_loss += losses['total'].item()
            num_batches += 1
            
            # Store for metrics
            all_predictions.append(outputs['predicate_logits'].cpu())
            all_targets.append(target_predicates.cpu())
            all_existence.append(target_existence.cpu())
        
        # Concatenate all predictions
        all_predictions = torch.cat(all_predictions, dim=0)
        all_targets = torch.cat(all_targets, dim=0)
        all_existence = torch.cat(all_existence, dim=0)
        
        # Compute metrics
        recall_metrics = compute_recall_at_k(
            all_predictions, all_targets, all_existence,
            k_values=[10, 20, 50]
        )
        
        mean_recall_metrics = compute_mean_recall_at_k(
            all_predictions, all_targets, all_existence,
            k_values=[10, 20, 50],
            num_predicates=len(AG_ALL_PREDICATES),
        )
        
        return {
            'loss': total_loss / num_batches,
            **recall_metrics,
            **mean_recall_metrics,
        }
    
    def train(self, epochs: int):
        """Full training loop."""
        logger.info(f"Starting training for {epochs} epochs")
        logger.info(f"Output directory: {self.output_dir}")
        
        for epoch in range(1, epochs + 1):
            # Train
            train_metrics = self.train_epoch(epoch)
            self.history['train_loss'].append(train_metrics['loss'])
            
            # Validate
            val_metrics = self.validate()
            self.history['val_loss'].append(val_metrics['loss'])
            self.history['val_recall'].append(val_metrics.get('R@20', 0))
            
            # Update scheduler
            self.scheduler.step()
            
            # Log
            logger.info(
                f"Epoch {epoch}: "
                f"Train Loss={train_metrics['loss']:.4f}, "
                f"Val Loss={val_metrics['loss']:.4f}, "
                f"R@20={val_metrics.get('R@20', 0):.2f}%, "
                f"mR@20={val_metrics.get('mR@20', 0):.2f}%"
            )
            
            # Save best model
            if val_metrics.get('R@20', 0) > self.best_recall:
                self.best_recall = val_metrics['R@20']
                self.save_checkpoint(epoch, val_metrics, is_best=True)
                logger.info(f"  → New best model! R@20={self.best_recall:.2f}%")
            
            # Save periodic checkpoint
            if epoch % 10 == 0:
                self.save_checkpoint(epoch, val_metrics)
        
        # Save final model
        self.save_checkpoint(epochs, val_metrics, is_final=True)
        
        logger.info(f"Training complete! Best R@20: {self.best_recall:.2f}%")
        
        return self.history
    
    def save_checkpoint(
        self, 
        epoch: int, 
        metrics: Dict, 
        is_best: bool = False,
        is_final: bool = False,
    ):
        """Save model checkpoint."""
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict(),
            'metrics': metrics,
            'config': self.config,
            'history': self.history,
        }
        
        if is_best:
            path = self.output_dir / 'best_model.pt'
        elif is_final:
            path = self.output_dir / 'final_model.pt'
        else:
            path = self.output_dir / f'checkpoint_epoch_{epoch}.pt'
        
        torch.save(checkpoint, path)
        logger.info(f"Saved checkpoint to {path}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Train Temporal SGA Model")
    
    # Data
    parser.add_argument(
        '--annotation_path', 
        type=str,
        default='datasets/ActionGenome/annotations/object_bbox_and_relationship.pkl',
        help='Path to AG annotations'
    )
    parser.add_argument(
        '--input_fraction', 
        type=float, 
        default=0.5,
        help='Fraction of frames to observe (F)'
    )
    
    # Model
    parser.add_argument('--hidden_dim', type=int, default=512)
    parser.add_argument('--num_spatial_layers', type=int, default=2)
    parser.add_argument('--num_temporal_layers', type=int, default=3)
    parser.add_argument('--num_decoder_layers', type=int, default=2)
    parser.add_argument('--num_heads', type=int, default=8)
    parser.add_argument('--dropout', type=float, default=0.1)
    
    # Training
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--batch_size', type=int, default=8)
    parser.add_argument('--lr', type=float, default=1e-4)
    parser.add_argument('--weight_decay', type=float, default=1e-5)
    parser.add_argument('--num_workers', type=int, default=4)
    
    # Data processing
    parser.add_argument('--max_objects', type=int, default=15)
    parser.add_argument('--max_observed_frames', type=int, default=8)
    parser.add_argument('--max_future_frames', type=int, default=4)
    
    # Output
    parser.add_argument(
        '--output_dir', 
        type=str, 
        default='checkpoints/sga',
        help='Directory for checkpoints'
    )
    
    args = parser.parse_args()
    
    # Check annotation file exists
    if not Path(args.annotation_path).exists():
        logger.error(f"Annotation file not found: {args.annotation_path}")
        logger.error("Please download Action Genome annotations first.")
        sys.exit(1)
    
    # Create dataloaders
    logger.info("Creating dataloaders...")
    train_loader, val_loader = create_sga_dataloaders(
        annotation_path=args.annotation_path,
        input_fraction=args.input_fraction,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        max_objects=args.max_objects,
        max_observed_frames=args.max_observed_frames,
        max_future_frames=args.max_future_frames,
    )
    
    logger.info(f"Train batches: {len(train_loader)}, Val batches: {len(val_loader)}")
    
    # Create model
    logger.info("Creating model...")
    config = TemporalSGAConfig(
        num_object_classes=len(AG_OBJECT_CLASSES),
        num_predicate_classes=len(AG_ALL_PREDICATES),
        hidden_dim=args.hidden_dim,
        num_spatial_layers=args.num_spatial_layers,
        num_temporal_layers=args.num_temporal_layers,
        num_decoder_layers=args.num_decoder_layers,
        num_heads=args.num_heads,
        dropout=args.dropout,
        max_objects_per_frame=args.max_objects,
        max_observed_frames=args.max_observed_frames,
        max_future_frames=args.max_future_frames,
    )
    
    model = TemporalSGAModel(config)
    
    # Move to device
    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    
    model = model.to(device)
    logger.info(f"Model on device: {device}")
    logger.info(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Create trainer
    trainer_config = {
        'lr': args.lr,
        'weight_decay': args.weight_decay,
        'epochs': args.epochs,
        'input_fraction': args.input_fraction,
    }
    
    trainer = SGATrainer(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        config=trainer_config,
        output_dir=args.output_dir,
    )
    
    # Train
    history = trainer.train(args.epochs)
    
    # Save training history
    history_path = Path(args.output_dir) / 'training_history.json'
    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2)
    
    logger.info(f"Training history saved to {history_path}")


if __name__ == "__main__":
    main()
