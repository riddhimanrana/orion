"""  
Entity Tracker (HDBSCAN)
========================

Clusters observations into unique tracked entities using HDBSCAN.

Responsibilities:
- Cluster observations by embedding similarity
- Group observations into unique entities
- Compute entity statistics (appearance count, temporal bounds)

Author: Orion Research Team
Date: October 2025
"""

import logging
from collections import defaultdict
from typing import List

import numpy as np

from orion.perception.types import Observation, PerceptionEntity
from orion.perception.config import PerceptionConfig

# Import shared protocols and utils if needed, or just to re-export if we want to be nice,
# but for a revamp we should encourage importing from .base
# from .base import TrackerProtocol, MotionTracker, MotionData  # Not used in this class

try:
    import hdbscan
    HDBSCAN_AVAILABLE = True
except ImportError:
    hdbscan = None
    HDBSCAN_AVAILABLE = False

logger = logging.getLogger(__name__)


class EntityTracker:
    """
    Tracks entities by clustering observations.
    
    Uses HDBSCAN to cluster observations by embedding similarity,
    identifying unique objects across the video.
    """
    
    def __init__(self, config: PerceptionConfig):
        """
        Initialize tracker.
        
        Args:
            config: Perception configuration
        """
        self.config = config
        
        if not HDBSCAN_AVAILABLE:
            logger.warning("HDBSCAN not available - falling back to simple clustering")
        
        logger.debug(
            f"EntityTracker initialized: min_cluster_size=3, "
            f"metric=euclidean"
        )
    
    def cluster_observations(
        self,
        observations: List[Observation],
    ) -> List[PerceptionEntity]:
        """
        Cluster observations into entities.
        
        Args:
            observations: List of observations from detection + embedding
            
        Returns:
            List of tracked entities
        """
        logger.info("="*80)
        logger.info("PHASE 1C: ENTITY CLUSTERING & TRACKING")
        logger.info("="*80)
        
        if not observations:
            logger.warning("No observations to cluster")
            return []
        
        logger.info(f"Clustering {len(observations)} observations...")
        
        if not HDBSCAN_AVAILABLE:
            return self._fallback_clustering(observations)

        min_cluster_size = getattr(self.config, "clustering_min_cluster_size", 4)
        min_samples = getattr(self.config, "clustering_min_samples", 1)
        epsilon = getattr(self.config, "clustering_cluster_selection_epsilon", 0.25)
        min_cluster_size = max(2, int(min_cluster_size))
        min_samples = max(1, int(min_samples))
        epsilon = max(0.0, float(epsilon))
        
        # Group observations by class to prevent cross-class clustering
        observations_by_class = defaultdict(list)
        for obs in observations:
            observations_by_class[obs.object_class].append(obs)
            
        all_entities = []
        global_cluster_id = 0
        
        for obj_class, class_obs in observations_by_class.items():
            if not class_obs:
                continue
                
            logger.info(f"  Clustering {len(class_obs)} observations for class '{obj_class}'...")
            
            # Extract and normalize embeddings for this class
            embeddings = np.array([obs.visual_embedding for obs in class_obs])
            
            # Ensure embeddings are 2D
            if embeddings.ndim == 3 and embeddings.shape[1] == 1:
                embeddings = np.squeeze(embeddings, axis=1)
            elif embeddings.ndim != 2:
                logger.error(f"  [ERROR] Unexpected embedding shape for class '{obj_class}': {embeddings.shape}. Skipping clustering for this class.")
                continue

            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings_normalized = embeddings / (norms + 1e-8)
            
            # Run HDBSCAN for this class
            if HDBSCAN_AVAILABLE and len(class_obs) >= min_cluster_size:
                clusterer = hdbscan.HDBSCAN(
                    min_cluster_size=min_cluster_size,
                    min_samples=min_samples,
                    metric="euclidean",
                    cluster_selection_epsilon=epsilon,
                    cluster_selection_method="eom",
                )
                labels = clusterer.fit_predict(embeddings_normalized)
            else:
                # Fallback if too few samples or HDBSCAN missing
                logger.debug(f"    Using fallback clustering for {obj_class} (n={len(class_obs)})")
                labels = np.zeros(len(class_obs), dtype=int)

            # Process clusters for this class
            unique_labels = set(labels)
            
            # Group by cluster label
            clusters = defaultdict(list)
            for obs, label in zip(class_obs, labels):
                if label != -1:
                    clusters[label].append(obs)
            
            # Create entities
            for label, cluster_obs in clusters.items():
                entity_id = f"entity_{global_cluster_id}"
                
                # Back-populate entity_id to observations
                for obs in cluster_obs:
                    obs.entity_id = entity_id
                    
                entity = PerceptionEntity(
                    entity_id=entity_id,
                    object_class=obj_class, # Guaranteed to be this class
                    observations=cluster_obs,
                )
                all_entities.append(entity)
                global_cluster_id += 1
                
        entities = all_entities
        
        # Sort by appearance count (descending)
        entities.sort(key=lambda e: e.appearance_count, reverse=True)
        
        # Log summary
        logger.info(f"\n✓ Tracked {len(entities)} unique entities")
        logger.info("  Top entities by appearance:")
        for i, entity in enumerate(entities[:10]):
            logger.info(
                f"    {i+1}. {entity.entity_id}: {entity.object_class.value} "
                f"({entity.appearance_count} appearances, "
                f"frames {entity.first_seen_frame}-{entity.last_seen_frame})"
            )
        
        if len(entities) > 10:
            logger.info(f"    ... and {len(entities) - 10} more")
        
        logger.info("="*80 + "\n")
        
        return entities
    
    def _fallback_clustering(
        self,
        observations: List[Observation],
    ) -> List[PerceptionEntity]:
        """
        Simple fallback clustering when HDBSCAN unavailable.
        
        Groups observations by class name + temporal proximity.
        """
        logger.warning("Using fallback clustering (class + temporal)")
        
        # Group by class
        class_groups = defaultdict(list)
        for obs in observations:
            class_groups[obs.object_class].append(obs)
        
        entities = []
        entity_id = 0
        
        for object_class, class_obs in class_groups.items():
            # Sort by frame number
            class_obs.sort(key=lambda o: o.frame_number)
            
            # Create entities (one per continuous appearance window)
            current_entity_obs = []
            last_frame = -100
            
            for obs in class_obs:
                # Start new entity if gap > 30 frames
                if obs.frame_number - last_frame > 30:
                    if current_entity_obs:
                        entity = PerceptionEntity(
                            entity_id=f"entity_{entity_id}",
                            object_class=object_class,
                            observations=current_entity_obs,
                        )
                        entity.compute_average_embedding()
                        entities.append(entity)
                        entity_id += 1
                    
                    current_entity_obs = []
                
                current_entity_obs.append(obs)
                last_frame = obs.frame_number
            
            # Add final entity
            if current_entity_obs:
                entity = PerceptionEntity(
                    entity_id=f"entity_{entity_id}",
                    object_class=object_class,
                    observations=current_entity_obs,
                )
                entity.compute_average_embedding()
                entities.append(entity)
                entity_id += 1
        
        logger.info(f"✓ Created {len(entities)} entities (fallback method)")
        
        return entities
