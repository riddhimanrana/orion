"""
Class Correction for Perception
================================

Validates and corrects YOLO classifications using:
- FastVLM descriptions (semantic matching)
- CLIP embeddings (visual verification)
- Confidence thresholds

Integrated into perception pipeline after description generation.

Author: Orion Research Team
Date: October 2025
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Valid COCO classes from YOLO11x (80 classes)
VALID_COCO_CLASSES = {
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
    'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench',
    'bird', 'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe',
    'backpack', 'umbrella', 'handbag', 'tie', 'suitcase',
    'frisbee', 'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove',
    'skateboard', 'surfboard', 'tennis racket',
    'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl',
    'banana', 'apple', 'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
    'donut', 'cake',
    'chair', 'couch', 'potted plant', 'bed', 'dining table', 'toilet',
    'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone',
    'microwave', 'oven', 'toaster', 'sink', 'refrigerator',
    'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
}

# Canonical term mappings (from rich descriptions to COCO classes)
CANONICAL_MAPPINGS = {
    # Hardware/appliances
    'knob': 'remote',
    'dial': 'remote',
    'switch': 'remote',
    'handle': 'remote',
    'lever': 'remote',
    
    # Furniture
    'sofa': 'couch',
    'settee': 'couch',
    'loveseat': 'couch',
    
    # Electronics
    'television': 'tv',
    'monitor': 'tv',
    'display': 'tv',
    'screen': 'tv',
    'notebook': 'laptop',
    'computer': 'laptop',
    
    # Kitchenware
    'mug': 'cup',
    'glass': 'cup',
    'tumbler': 'cup',
    'dish': 'bowl',
    'plate': 'bowl',
    
    # Personal items
    'phone': 'cell phone',
    'smartphone': 'cell phone',
    'mobile': 'cell phone',
    'bag': 'handbag',
    'purse': 'handbag',
    'wallet': 'handbag',
    'luggage': 'suitcase',
    'case': 'suitcase',
    
    # Sports
    'ball': 'sports ball',
    'racket': 'tennis racket',
    'bat': 'baseball bat',
    
    # Animals
    'puppy': 'dog',
    'kitten': 'cat',
    'pony': 'horse',
}


class ClassCorrector:
    """
    Validates and corrects YOLO classifications using:
    1. Unbiased FastVLM descriptions (semantic matching)
    2. CLIP visual embeddings (visual verification)
    3. Multi-factor confidence scoring
    
    This is the core of Phase 1 class correction.
    """
    
    def __init__(
        self, 
        confidence_threshold: float = 0.70,
        semantic_threshold: float = 0.40,
        use_clip_verification: bool = False,
        sentence_model_name: str = "all-MiniLM-L6-v2",
    ):
        """
        Initialize class corrector.
        
        Args:
            confidence_threshold: Trust YOLO above this confidence (0-1)
            semantic_threshold: Minimum semantic similarity for correction
            use_clip_verification: Use CLIP embeddings for visual verification (experimental)
        """
        self.confidence_threshold = confidence_threshold
        self.semantic_threshold = semantic_threshold
        self.use_clip_verification = use_clip_verification
        self.sentence_model_name = sentence_model_name
        
        self._sentence_model = None  # Lazy load
        self._class_embeddings_cache = None
        self._clip_model = None  # For visual verification
        
        # Statistics
        self.corrections_attempted = 0
        self.corrections_applied = 0
    
    def _get_sentence_model(self):
        """Lazy load Sentence Transformer for semantic matching"""
        if self._sentence_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._sentence_model = SentenceTransformer(self.sentence_model_name)
                logger.info("Loaded sentence transformer (%s) for class correction", self.sentence_model_name)
            except Exception as e:
                logger.warning(f"Failed to load sentence transformer: {e}")
                self._sentence_model = False
        return self._sentence_model if self._sentence_model is not False else None
    
    def _get_class_embeddings(self) -> Optional[Dict[str, np.ndarray]]:
        """Precompute embeddings for all COCO classes"""
        if self._class_embeddings_cache is not None:
            return self._class_embeddings_cache
        
        model = self._get_sentence_model()
        if not model:
            return None
        
        try:
            class_list = sorted(VALID_COCO_CLASSES)
            embeddings = model.encode(class_list, convert_to_numpy=True)
            self._class_embeddings_cache = {
                cls: emb for cls, emb in zip(class_list, embeddings)
            }
            logger.debug(f"Precomputed embeddings for {len(class_list)} COCO classes")
            return self._class_embeddings_cache
        except Exception as e:
            logger.warning(f"Failed to precompute class embeddings: {e}")
            return None
    
    def should_correct(
        self,
        yolo_class: str,
        description: str,
        confidence: float,
    ) -> bool:
        """
        Determine if YOLO classification should be corrected.
        
        **NEW Logic for Phase 1:**
        - Uses UNBIASED description (no YOLO hint)
        - Checks semantic mismatch between YOLO label and description
        - Lower confidence = more likely to need correction
        
        Args:
            yolo_class: Original YOLO classification
            description: UNBIASED FastVLM description
            confidence: YOLO confidence score (0-1)
            
        Returns:
            True if correction should be attempted
        """
        # High confidence detections are usually correct
        if confidence >= self.confidence_threshold:
            return False
        
        # If no description available, can't correct
        if not description or len(description) < 20:
            return False
        
        desc_lower = description.lower()
        class_lower = yolo_class.lower()
        
        # CASE 1: Class explicitly mentioned in description = probably correct
        if class_lower in desc_lower:
            return False
        
        # CASE 2: Synonym or related term mentioned = probably correct
        synonyms = self._get_synonyms(class_lower)
        if any(syn in desc_lower for syn in synonyms):
            return False
        
        # CASE 3: Description contains OTHER COCO class names = strong mismatch signal
        mentioned_classes = [cls for cls in VALID_COCO_CLASSES if cls in desc_lower and cls != class_lower]
        if mentioned_classes:
            logger.debug(f"Description mentions other classes: {mentioned_classes}, but YOLO detected '{yolo_class}'")
            return True
        
        # CASE 4: Low confidence + no class mention = correction candidate
        if confidence < 0.60:
            return True
        
        # CASE 5: Description has very specific terms that contradict YOLO class
        # E.g., description says "silver handle" but YOLO says "hair_drier"
        contradictory_terms = self._check_contradictory_terms(yolo_class, description)
        if contradictory_terms:
            logger.debug(f"Found contradictory terms for '{yolo_class}': {contradictory_terms}")
            return True
        
        return False
    
    def _get_synonyms(self, coco_class: str) -> List[str]:
        """Get common synonyms for a COCO class."""
        synonym_map = {
            'tv': ['television', 'monitor', 'screen', 'display'],
            'laptop': ['notebook', 'computer'],
            'couch': ['sofa', 'settee'],
            'cell phone': ['phone', 'smartphone', 'mobile'],
            'remote': ['controller', 'control'],
            'hair drier': ['hairdryer', 'blow dryer', 'dryer'],
            # Add more as needed
        }
        return synonym_map.get(coco_class, [])
    
    def _check_contradictory_terms(self, yolo_class: str, description: str) -> List[str]:
        """
        Check if description contains terms that contradict the YOLO class.
        
        Returns:
            List of contradictory terms found
        """
        desc_lower = description.lower()
        contradictions = []
        
        # Define contradiction patterns
        # E.g., if YOLO says "hair_drier" but description emphasizes "book"
        class_specific_contradictions = {
            'hair drier': ['book', 'notebook', 'magazine', 'text', 'pages', 'spiral', 'binding'],
            'remote': ['book', 'notebook', 'keyboard', 'laptop'],
            'cell phone': ['book', 'notebook', 'laptop screen'],
            # Add more patterns
        }
        
        if yolo_class.lower() in class_specific_contradictions:
            patterns = class_specific_contradictions[yolo_class.lower()]
            for pattern in patterns:
                if pattern in desc_lower:
                    contradictions.append(pattern)
        
        return contradictions
    
    def extract_corrected_class(
        self,
        yolo_class: str,
        description: str,
        confidence: float,
    ) -> Tuple[Optional[str], float]:
        """
        Extract corrected class from UNBIASED description using multi-stage matching.
        
        **Phase 1 Enhancement:** 
        - Strategy 1: Direct keyword extraction (highest confidence)
        - Strategy 2: Semantic similarity with all COCO classes
        - Strategy 3: Fuzzy matching for partial matches
        
        Args:
            yolo_class: Original YOLO class
            description: UNBIASED FastVLM description
            confidence: Original YOLO confidence
            
        Returns:
            (corrected_class, correction_confidence) or (None, 0.0) if no correction
        """
        if not self.should_correct(yolo_class, description, confidence):
            return None, 0.0
        
        self.corrections_attempted += 1
        
        # Strategy 1: Direct keyword extraction (90% confidence)
        canonical = self._extract_canonical_term(description)
        if canonical and canonical != yolo_class.lower():
            logger.info(f"✓ Keyword extraction: '{yolo_class}' → '{canonical}'")
            self.corrections_applied += 1
            return canonical, 0.90
        
        # Strategy 2: Semantic similarity matching (variable confidence)
        corrected, score = self._semantic_match(description, yolo_class)
        if corrected and score > self.semantic_threshold:
            logger.info(f"✓ Semantic match: '{yolo_class}' → '{corrected}' (score: {score:.2f})")
            self.corrections_applied += 1
            return corrected, score
        
        # Strategy 3: Fuzzy matching for partial word matches
        fuzzy_match = self._fuzzy_match(description, yolo_class)
        if fuzzy_match:
            logger.info(f"✓ Fuzzy match: '{yolo_class}' → '{fuzzy_match}'")
            self.corrections_applied += 1
            return fuzzy_match, 0.70
        
        logger.debug(f"No confident correction found for '{yolo_class}'")
        return None, 0.0
    
    def _fuzzy_match(self, description: str, yolo_class: str) -> Optional[str]:
        """
        Find COCO classes with partial word matches in description.
        
        E.g., description contains "notebook" → suggests "book" or "laptop"
        """
        desc_lower = description.lower()
        words = desc_lower.split()
        
        for coco_class in VALID_COCO_CLASSES:
            if coco_class == yolo_class.lower():
                continue
            
            # Check for partial matches
            class_words = coco_class.split()
            for class_word in class_words:
                for desc_word in words:
                    # At least 4 chars overlap and >60% match
                    if len(class_word) >= 4 and len(desc_word) >= 4:
                        overlap = sum(c1 == c2 for c1, c2 in zip(class_word, desc_word))
                        similarity = overlap / max(len(class_word), len(desc_word))
                        if similarity > 0.6:
                            return coco_class
        
        return None
    
    def _extract_canonical_term(self, description: str) -> Optional[str]:
        """
        Extract canonical COCO class from description keywords.
        
        Args:
            description: FastVLM description
            
        Returns:
            Canonical COCO class or None
        """
        desc_lower = description.lower()
        
        # Sort mappings by length (descending) to match "baseball bat" before "bat"
        sorted_mappings = sorted(CANONICAL_MAPPINGS.items(), key=lambda x: len(x[0]), reverse=True)
        
        # Check for direct canonical terms (using word boundaries)
        for term, coco_class in sorted_mappings:
            # Use regex to match whole words only
            if re.search(r'\b' + re.escape(term) + r'\b', desc_lower):
                return coco_class
        
        # Check for COCO classes directly in description
        # Also sort by length to match "sports ball" before "ball" (if ball was a class)
        sorted_coco = sorted(list(VALID_COCO_CLASSES), key=len, reverse=True)
        for coco_class in sorted_coco:
            if re.search(r'\b' + re.escape(coco_class) + r'\b', desc_lower):
                return coco_class
        
        return None
    
    def _semantic_match(
        self,
        description: str,
        yolo_class: str,
        top_k: int = 3,
    ) -> Tuple[Optional[str], float]:
        """
        Find best COCO class match using semantic similarity.
        
        Args:
            description: FastVLM description
            yolo_class: Original YOLO class (for exclusion)
            top_k: Number of top candidates to consider
            
        Returns:
            (best_match, similarity_score) or (None, 0.0)
        """
        model = self._get_sentence_model()
        class_embeddings = self._get_class_embeddings()
        
        if not model or not class_embeddings:
            return None, 0.0
        
        try:
            # Encode description
            desc_embedding = model.encode([description], convert_to_numpy=True)[0]
            
            # Compute similarities with all COCO classes
            similarities = []
            for coco_class, class_emb in class_embeddings.items():
                if coco_class == yolo_class.lower():
                    continue  # Skip original class
                
                sim = float(np.dot(desc_embedding, class_emb) / 
                           (np.linalg.norm(desc_embedding) * np.linalg.norm(class_emb)))
                similarities.append((coco_class, sim))
            
            # Sort by similarity
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            if similarities:
                best_match, best_score = similarities[0]
                return best_match, best_score
            
            return None, 0.0
            
        except Exception as e:
            logger.warning(f"Semantic matching failed: {e}")
            return None, 0.0
    
    def correct_entity_class(
        self,
        entity,
        description: str,
        confidence: float,
    ):
        """
        Correct entity's object class if needed using UNBIASED description.
        
        **Phase 1 Core Method:**
        This applies the multi-strategy correction:
        1. Checks if correction is needed (confidence, semantic mismatch)
        2. Attempts correction via keyword/semantic/fuzzy matching
        3. Updates entity with corrected class + metadata
        
        Args:
            entity: PerceptionEntity to potentially correct
            description: UNBIASED FastVLM description of entity
            confidence: Average confidence of entity
            
        Returns:
            Entity with potentially corrected object_class
        """
        if not hasattr(entity, 'object_class') or not entity.object_class:
            return entity
        
        original_class = entity.object_class.name if hasattr(entity.object_class, 'name') else str(entity.object_class)
        
        corrected_class, correction_confidence = self.extract_corrected_class(
            original_class,
            description,
            confidence
        )
        
        if corrected_class:
            logger.info(
                f"📝 Class correction applied: '{original_class}' → '{corrected_class}' "
                f"(correction_conf: {correction_confidence:.2f}, yolo_conf: {confidence:.2f})"
            )
            
            # Store correction metadata
            entity.original_class = original_class
            entity.corrected_class = corrected_class
            entity.correction_confidence = correction_confidence
            entity.correction_method = "unbiased_description_semantic_match"
            
            # Optionally update the actual object_class
            # (Depends on whether you want to replace or keep original + correction)
            # For now, keep both - downstream code can choose which to use
        else:
            # No correction needed - mark as validated
            entity.corrected_class = None
            entity.correction_confidence = confidence
        
        return entity
    
    def get_statistics(self) -> Dict[str, int]:
        """Get correction statistics for reporting."""
        return {
            "corrections_attempted": self.corrections_attempted,
            "corrections_applied": self.corrections_applied,
            "correction_rate": (
                self.corrections_applied / self.corrections_attempted 
                if self.corrections_attempted > 0 else 0.0
            )
        }
