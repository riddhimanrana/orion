"""
Entity Describer
================

Generates natural language descriptions for entities using FastVLM.
Applies spatial analysis and class correction for quality improvement.

Responsibilities:
- Select best frame for each entity
- Generate VLM description from best observation
- Enrich with spatial context
- Validate and correct classifications
- Optimize by describing each entity only once

Author: Orion Research Team
Date: October 2025
"""

import logging
from typing import List, Optional

import cv2
import numpy as np
from PIL import Image

from orion.perception.types import PerceptionEntity, Observation, BoundingBox
from orion.perception.config import DescriptionConfig
from orion.perception.corrector import ClassCorrector
from orion.utils.profiling import profile

logger = logging.getLogger(__name__)


def calculate_spatial_zone(bbox: BoundingBox, frame_width: float = 1920.0, frame_height: float = 1080.0) -> str:
    """Classify spatial zone from bounding box (simplified inline version)."""
    if frame_width <= 0 or frame_height <= 0:
        return "unknown"
    cx = (bbox.x1 + bbox.x2) / 2.0
    cy = (bbox.y1 + bbox.y2) / 2.0
    ny = max(0.0, min(1.0, cy / frame_height))
    if ny < 0.15:
        return "ceiling"
    elif ny < 0.35:
        return "wall_upper"
    elif ny < 0.65:
        return "wall_middle"
    elif ny < 0.75:
        return "wall_lower"
    else:
        return "floor"


class EntityDescriber:
    """
    Describes entities using FastVLM.
    
    Generates rich natural language descriptions by selecting
    the best observation for each entity.
    """
    
    def __init__(
        self,
        vlm_model,
        config: DescriptionConfig,
        enable_class_correction: bool = True,
        enable_spatial_analysis: bool = True,
    ):
        """
        Initialize describer.
        
        Args:
            vlm_model: FastVLM model instance from ModelManager
            config: Description configuration
            enable_class_correction: Enable YOLO class correction
            enable_spatial_analysis: Enable spatial zone analysis
        """
        self.vlm = vlm_model
        self.config = config
        self.enable_class_correction = enable_class_correction
        self.enable_spatial_analysis = enable_spatial_analysis
        
        # Initialize quality improvement modules
        self.class_corrector = (
            ClassCorrector(sentence_model_name=self.config.sentence_model_name)
            if enable_class_correction
            else None
        )
        
        logger.debug(
            f"EntityDescriber initialized: max_tokens={config.max_tokens}, "
            f"temperature={config.temperature}, describe_once={config.describe_once}, "
            f"class_correction={enable_class_correction}, spatial_analysis={enable_spatial_analysis}"
        )

    def describe_scene(self, frame: np.ndarray, prompt: str = "Describe this scene in detail.") -> str:
        """
        Generate a description for the entire scene/frame.
        
        Args:
            frame: Full video frame (BGR numpy array)
            prompt: Prompt for the VLM
            
        Returns:
            Scene description string
        """
        if self.vlm is None:
            return ""
            
        try:
            # Convert BGR to RGB PIL Image
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)
            
            description = self.vlm.generate_description(
                pil_image,
                prompt,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            return description.strip()
        except Exception as e:
            logger.error(f"Failed to describe scene: {e}")
            return ""
    
    @profile("describer_describe_entities")
    def describe_entities(
        self,
        entities: List[PerceptionEntity],
    ) -> List[PerceptionEntity]:
        """
        Add descriptions to entities.
        
        Args:
            entities: List of entities from tracker
            
        Returns:
            Same entities with descriptions added
        """
        logger.info("="*80)
        logger.info("PHASE 1D: ENTITY DESCRIPTION")
        logger.info("="*80)
        
        if not entities:
            logger.warning("No entities to describe")
            return entities
        
        logger.info(f"Describing {len(entities)} entities...")
        logger.info(f"  Mode: {'Describe once (from best frame)' if self.config.describe_once else 'Describe all observations'}")
        
        described_count = 0
        
        for i, entity in enumerate(entities):
            # Select best observation
            best_obs = entity.get_best_observation()
            
            if best_obs is None:
                logger.warning(f"  Entity {entity.entity_id}: No valid observation for description")
                continue
            
            # Generate description
            description = self.describe_observation(best_obs)
            
            # Attach to entity
            entity.description = description
            entity.description_frame = best_obs.frame_number
            
            described_count += 1
            
            if (i + 1) % 10 == 0 or i == len(entities) - 1:
                logger.info(f"  Described {i + 1}/{len(entities)} entities")
        
        logger.info(f"\n✓ Generated {described_count} descriptions")
        
        # Apply quality improvements
        if self.enable_spatial_analysis or self.enable_class_correction:
            logger.info("\nApplying quality improvements...")
            entities = self._apply_quality_improvements(entities)
        
        # Report correction statistics
        if self.class_corrector:
            stats = self.class_corrector.get_statistics()
            if stats['corrections_attempted'] > 0:
                logger.info(f"\n📊 Class Correction Statistics:")
                logger.info(f"  Attempted: {stats['corrections_attempted']}")
                logger.info(f"  Applied: {stats['corrections_applied']}")
                logger.info(f"  Success rate: {stats['correction_rate']:.1%}")
        
        logger.info("  Sample descriptions:")
        for i, entity in enumerate(entities[:5]):
            if entity.description:
                desc_preview = entity.description[:80] + "..." if len(entity.description) > 80 else entity.description
                
                # Show correction if it happened
                class_info = entity.object_class.value
                if hasattr(entity, 'corrected_class') and entity.corrected_class:
                    class_info = f"{entity.object_class.value} → {entity.corrected_class}"
                
                logger.info(f"    {i+1}. {entity.entity_id} ({class_info}): {desc_preview}")
        
        logger.info("="*80 + "\n")
        
        return entities
    
    def _apply_quality_improvements(
        self,
        entities: List[PerceptionEntity],
    ) -> List[PerceptionEntity]:
        """
        Apply spatial analysis and class correction to entities.
        
        Args:
            entities: Entities with descriptions
            
        Returns:
            Enriched entities
        """
        spatial_count = 0
        correction_count = 0
        
        for entity in entities:
            # Get best observation for analysis
            best_obs = entity.get_best_observation()
            if not best_obs:
                continue
            
            # Apply spatial analysis
            if self.enable_spatial_analysis and best_obs.bounding_box:
                # Use frame dimensions from observation if available, else fallback
                frame_width = getattr(best_obs, 'frame_width', 1920.0)
                frame_height = getattr(best_obs, 'frame_height', 1080.0)
                best_obs.spatial_zone = calculate_spatial_zone(
                    best_obs.bounding_box,
                    frame_width=frame_width,
                    frame_height=frame_height,
                )
                spatial_count += 1
            
            # Apply class correction
            if self.enable_class_correction and self.class_corrector and entity.description:
                # Calculate average confidence
                avg_confidence = sum(obs.confidence for obs in entity.observations) / len(entity.observations)
                
                # Attempt correction
                entity = self.class_corrector.correct_entity_class(
                    entity,
                    entity.description,
                    avg_confidence,
                )
                
                if hasattr(entity, 'corrected_class') and entity.corrected_class:
                    correction_count += 1
        
        if spatial_count > 0:
            logger.info(f"  ✓ Added spatial context to {spatial_count} entities")
        
        if correction_count > 0:
            logger.info(f"  ✓ Corrected {correction_count} misclassifications")
        
        return entities
    
    @profile("describer_describe_observation")
    def describe_observation(self, observation: Observation) -> str:
        """
        Generate description for a single observation.
        
        Args:
            observation: Observation to describe
        Returns:
            Generated description string
        """
        # Fallback: if no image_patch, use raw_yolo_class or object_class as description
        if observation.image_patch is None:
            # Use detection's description if available (e.g., YOLO-World class name)
            if hasattr(observation, 'raw_yolo_class') and observation.raw_yolo_class:
                return str(observation.raw_yolo_class)
            return str(observation.object_class)
        return self._generate_description(
            observation.image_patch,
            observation.object_class,
        )
    
    @profile("describer_generate_description")
    def _generate_description(self, crop: np.ndarray, object_class: str) -> str:
        """Generate description using FastVLM."""
        try:
            # Convert to PIL
            crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(crop_rgb)
            
            # Generate prompt
            prompt = self.config.prompt_template.format(object_class=object_class)
            
            # Run VLM
            description = self.vlm.generate_description(
                pil_image,
                prompt,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
            
            return description
            
        except Exception as e:
            logger.error(f"VLM generation failed: {e}")
            return f"Failed to describe {object_class}."
    
    def select_best_observation(self, entity: PerceptionEntity) -> Optional[Observation]:
        """
        Select the best observation for description.
        
        Uses weighted scoring:
        - Size weight: Larger objects are clearer
        - Centrality weight: Objects closer to center are less occluded
        - Confidence weight: Higher confidence = better detection
        
        Args:
            entity: Entity to select from
            
        Returns:
            Best observation, or None if entity has no observations
        """
        if not entity.observations:
            return None
        
        best_obs = None
        best_score = -1
        
        for obs in entity.observations:
            # Compute score
            score = self._score_observation(obs)
            
            if score > best_score:
                best_score = score
                best_obs = obs
        
        return best_obs
    
    def _score_observation(self, obs: Observation) -> float:
        """
        Score an observation for description quality.
        
        Args:
            obs: Observation to score
            
        Returns:
            Score (higher is better)
        """
        # Size score (normalized by frame area)
        bbox = obs.bounding_box
        frame_area = obs.frame_number * 1.0  # Placeholder - should use actual frame size
        if frame_area > 0:
            size_score = bbox.area / max(frame_area, 1)
        else:
            size_score = bbox.area / 1000000  # Fallback
        
        # Centrality score (distance from frame center)
        # Assume frame center at (frame_width/2, frame_height/2)
        # For now, use a simple heuristic
        cx, cy = obs.centroid
        centrality_score = 1.0  # Placeholder - would need frame dimensions
        
        # Confidence score
        confidence_score = obs.confidence
        
        # Weighted combination
        total_score = (
            self.config.size_weight * size_score +
            self.config.centrality_weight * centrality_score +
            self.config.confidence_weight * confidence_score
        )
        
        return total_score

    def _is_crop_valid(self, crop: np.ndarray) -> bool:
        """Basic pixel-level sanity checks before trusting FastVLM output."""
        if crop is None or crop.size == 0:
            return False

        height, width = crop.shape[:2]
        if height < self.config.min_crop_size or width < self.config.min_crop_size:
            return False

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        if float(gray.std()) < self.config.min_crop_std:
            return False

        return True
