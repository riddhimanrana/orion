"""
Persistent Spatial Memory System

This module implements a continuously learning spatial intelligence system that:
- Builds semantic memory over time (remembers everything)
- Maintains spatial reconstruction (3D scene understanding)
- Enables interactive queries with context awareness
- Provides long-term memory across sessions

Think of this as the "historian" for robotics models - constant understanding
over hours, days, with perfect spatial and temporal context.
"""

from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import json
import numpy as np
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class SpatialEntity:
    """Represents an entity with full spatial and semantic understanding"""
    entity_id: int
    class_name: str
    semantic_label: Optional[str] = None  # e.g., "the red book on the desk"
    first_seen: float = 0.0
    last_seen: float = 0.0
    observations_count: int = 0
    
    # Spatial understanding
    primary_zone: Optional[int] = None
    all_zones: List[int] = None
    avg_position_3d: Optional[Tuple[float, float, float]] = None  # (x, y, z) in mm
    movement_history: List[Tuple[float, Tuple[float, float, float]]] = None  # [(timestamp, pos), ...]
    
    # Semantic understanding
    captions: List[str] = None  # All captions generated for this entity
    activities: List[str] = None  # Detected activities involving this entity
    relationships: List[Dict] = None  # Spatial/temporal relationships with other entities
    
    # Visual features
    dominant_colors: List[str] = None
    appearance_features: Optional[np.ndarray] = None  # CLIP embedding
    
    def __post_init__(self):
        if self.all_zones is None:
            self.all_zones = []
        if self.movement_history is None:
            self.movement_history = []
        if self.captions is None:
            self.captions = []
        if self.activities is None:
            self.activities = []
        if self.relationships is None:
            self.relationships = []
        if self.dominant_colors is None:
            self.dominant_colors = []


@dataclass
class SpatialZone:
    """Represents a spatial zone with semantic understanding"""
    zone_id: int
    zone_type: Optional[str] = None  # e.g., "desk area", "doorway", "shelf"
    center_3d: Optional[Tuple[float, float, float]] = None
    radius_mm: Optional[float] = None
    
    # Entities in this zone
    entity_ids: List[int] = None
    permanent_entities: List[int] = None  # Entities that rarely move (furniture, etc.)
    transient_entities: List[int] = None  # Entities that move frequently
    
    # Semantic understanding
    typical_activities: List[str] = None  # What typically happens here
    scene_context: Optional[str] = None  # e.g., "kitchen counter with cooking items"
    
    def __post_init__(self):
        if self.entity_ids is None:
            self.entity_ids = []
        if self.permanent_entities is None:
            self.permanent_entities = []
        if self.transient_entities is None:
            self.transient_entities = []
        if self.typical_activities is None:
            self.typical_activities = []


@dataclass
class ConversationContext:
    """Maintains conversation context for intelligent queries"""
    last_query: Optional[str] = None
    last_entity_ids: List[int] = None  # Entities mentioned in last query
    last_zone_id: Optional[int] = None
    query_history: List[Dict] = None  # Full conversation history
    
    def __post_init__(self):
        if self.last_entity_ids is None:
            self.last_entity_ids = []
        if self.query_history is None:
            self.query_history = []


class SpatialMemorySystem:
    """
    Persistent spatial intelligence system
    
    This is the "brain" that remembers everything about the video/space:
    - All entities ever seen, with full semantic labels
    - Spatial reconstruction and zone understanding
    - Temporal relationships and activities
    - Conversation context for intelligent queries
    """
    
    def __init__(self, memory_dir: Path = Path("memory")):
        self.memory_dir = Path(memory_dir) if isinstance(memory_dir, str) else memory_dir
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Core memory structures
        self.entities: Dict[int, SpatialEntity] = {}
        self.zones: Dict[int, SpatialZone] = {}
        self.conversation_context = ConversationContext()
        
        # Semantic understanding
        self.scene_type: Optional[str] = None  # e.g., "kitchen", "office", "living room"
        self.scene_description: Optional[str] = None  # Rich description
        self.spatial_layout: Optional[Dict] = None  # 3D reconstruction info
        self.current_scene: Optional[Any] = None  # SceneContext from scene_understanding module
        
        # Session tracking
        self.session_start: datetime = datetime.now()
        self.total_frames_processed: int = 0
        self.total_captions_generated: int = 0
        
        # Load from disk if exists
        self._load_from_disk()
    
    def add_entity_observation(
        self,
        entity_id: int,
        class_name: str,
        timestamp: float,
        position_3d: Optional[Tuple[float, float, float]] = None,
        zone_id: Optional[int] = None,
        caption: Optional[str] = None,
        confidence: float = 1.0
    ):
        """
        Add an entity observation and update spatial memory
        
        This continuously builds understanding of the entity over time
        """
        if entity_id not in self.entities:
            # New entity - create memory
            self.entities[entity_id] = SpatialEntity(
                entity_id=entity_id,
                class_name=class_name,
                first_seen=timestamp,
                last_seen=timestamp,
                observations_count=1
            )
            logger.info(f"New entity in memory: {class_name} (ID: {entity_id})")
        else:
            # Update existing entity
            entity = self.entities[entity_id]
            entity.last_seen = timestamp
            entity.observations_count += 1
        
        entity = self.entities[entity_id]
        
        # Update spatial understanding
        if position_3d is not None:
            entity.movement_history.append((timestamp, position_3d))
            
            # Update average position
            if len(entity.movement_history) > 0:
                positions = [pos for _, pos in entity.movement_history]
                entity.avg_position_3d = tuple(np.mean(positions, axis=0))
        
        # Update zone membership
        if zone_id is not None and zone_id not in entity.all_zones:
            entity.all_zones.append(zone_id)
            if entity.primary_zone is None:
                entity.primary_zone = zone_id
        
        # Add semantic caption
        if caption is not None and caption not in entity.captions:
            entity.captions.append(caption)
            self.total_captions_generated += 1
            logger.info(f"Caption added for {class_name}: {caption[:50]}...")
    
    def update_zone(
        self,
        zone_id: int,
        zone_type: Optional[str] = None,
        center_3d: Optional[Tuple[float, float, float]] = None,
        radius_mm: Optional[float] = None,
        scene_context: Optional[str] = None
    ):
        """Update spatial zone understanding"""
        if zone_id not in self.zones:
            self.zones[zone_id] = SpatialZone(zone_id=zone_id)
        
        zone = self.zones[zone_id]
        if zone_type:
            zone.zone_type = zone_type
        if center_3d:
            zone.center_3d = center_3d
        if radius_mm:
            zone.radius_mm = radius_mm
        if scene_context:
            zone.scene_context = scene_context
    
    def add_relationship(
        self,
        entity1_id: int,
        entity2_id: int,
        relationship_type: str,
        confidence: float = 1.0,
        timestamp: Optional[float] = None
    ):
        """
        Add spatial/semantic relationship between entities
        
        Examples:
        - "book NEAR laptop" (spatial)
        - "person HOLDING phone" (interaction)
        - "cup ON_TOP_OF desk" (spatial+semantic)
        """
        if entity1_id in self.entities:
            self.entities[entity1_id].relationships.append({
                'related_entity': entity2_id,
                'type': relationship_type,
                'confidence': confidence,
                'timestamp': timestamp
            })
    
    def generate_semantic_label(self, entity_id: int) -> str:
        """
        Generate rich semantic label for entity based on all observations
        
        Example: "the red book on the desk near the laptop"
        """
        if entity_id not in self.entities:
            return f"unknown_{entity_id}"
        
        entity = self.entities[entity_id]
        
        # Start with class
        label = entity.class_name
        
        # Add color if known
        if entity.dominant_colors:
            label = f"{entity.dominant_colors[0]} {label}"
        
        # Add location context
        if entity.primary_zone and entity.primary_zone in self.zones:
            zone = self.zones[entity.primary_zone]
            if zone.zone_type:
                label += f" in {zone.zone_type}"
        
        # Add relationships
        if entity.relationships:
            # Find most common relationship
            rel_types = [r['type'] for r in entity.relationships]
            if rel_types:
                common_rel = max(set(rel_types), key=rel_types.count)
                label += f" ({common_rel})"
        
        return label
    
    def query_with_context(
        self,
        query: str,
        use_conversation_context: bool = True
    ) -> Dict[str, Any]:
        """
        Intelligent query that understands context and asks clarifying questions
        
        Returns:
            {
                'answer': str,
                'clarification_needed': bool,
                'clarification_question': Optional[str],
                'entities_mentioned': List[int],
                'confidence': float
            }
        """
        # Parse query and extract intent
        query_lower = query.lower()
        
        # Check if query references previous context
        context_refs = ['it', 'that', 'this', 'the same', 'there']
        uses_context = any(ref in query_lower for ref in context_refs)
        
        if uses_context and use_conversation_context:
            # Use conversation context
            if self.conversation_context.last_entity_ids:
                relevant_entities = self.conversation_context.last_entity_ids
            else:
                return {
                    'answer': None,
                    'clarification_needed': True,
                    'clarification_question': "What object are you referring to? Could you be more specific?",
                    'entities_mentioned': [],
                    'confidence': 0.0
                }
        else:
            # Search for entities matching query
            relevant_entities = self._search_entities(query)
        
        # Update conversation context
        self.conversation_context.last_query = query
        self.conversation_context.last_entity_ids = relevant_entities
        self.conversation_context.query_history.append({
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'entity_ids': relevant_entities
        })
        
        # Generate answer based on memory
        if not relevant_entities:
            return {
                'answer': f"I don't have any memory of that in this space.",
                'clarification_needed': False,
                'clarification_question': None,
                'entities_mentioned': [],
                'confidence': 0.0
            }
        
        # Build rich answer from memory
        entity_id = relevant_entities[0]
        entity = self.entities[entity_id]
        
        answer = self._generate_contextual_answer(entity, query)
        
        return {
            'answer': answer,
            'clarification_needed': False,
            'clarification_question': None,
            'entities_mentioned': relevant_entities,
            'confidence': 0.9 if entity.captions else 0.5
        }
    
    def _search_entities(self, query: str) -> List[int]:
        """Search for entities matching query terms"""
        query_lower = query.lower()
        matches = []
        
        for entity_id, entity in self.entities.items():
            # Check class name
            if entity.class_name.lower() in query_lower:
                matches.append(entity_id)
                continue
            
            # Check captions
            for caption in entity.captions:
                if any(word in caption.lower() for word in query_lower.split()):
                    matches.append(entity_id)
                    break
        
        return matches
    
    def _generate_contextual_answer(self, entity: SpatialEntity, query: str) -> str:
        """Generate rich contextual answer from entity memory"""
        query_lower = query.lower()
        
        # Color query
        if 'color' in query_lower:
            if entity.dominant_colors:
                return f"The {entity.class_name} was {entity.dominant_colors[0]}."
            elif entity.captions:
                return f"Based on what I saw: {entity.captions[0]}"
            else:
                return f"I saw a {entity.class_name}, but I don't have color information yet."
        
        # Location query
        if 'where' in query_lower or 'location' in query_lower:
            if entity.primary_zone and entity.primary_zone in self.zones:
                zone = self.zones[entity.primary_zone]
                answer = f"The {entity.class_name} was in zone {entity.primary_zone}"
                if zone.zone_type:
                    answer += f" ({zone.zone_type})"
                return answer + "."
            else:
                return f"The {entity.class_name} was in the space, but I don't have specific zone info."
        
        # General query - return rich description
        semantic_label = self.generate_semantic_label(entity.entity_id)
        answer = f"I remember {semantic_label}. "
        
        if entity.captions:
            answer += f"Specifically: {entity.captions[0]} "
        
        answer += f"I saw it {entity.observations_count} times"
        if entity.first_seen and entity.last_seen:
            duration = entity.last_seen - entity.first_seen
            answer += f" over {duration:.1f} seconds"
        
        answer += "."
        return answer
    
    def _save_to_disk(self):
        """Persist memory to disk for long-term storage"""
        try:
            # Save entities
            entities_file = self.memory_dir / "entities.json"
            entities_data = {}
            for eid, entity in self.entities.items():
                entity_dict = asdict(entity)
                # Convert numpy arrays to lists
                if entity.appearance_features is not None:
                    entity_dict['appearance_features'] = entity.appearance_features.tolist()
                # Handle any other potential numpy arrays in nested structures
                entity_dict = self._convert_numpy_to_list(entity_dict)
                entities_data[str(eid)] = entity_dict
            
            with open(entities_file, 'w') as f:
                json.dump(entities_data, f, indent=2)
            
            # Save zones
            zones_file = self.memory_dir / "zones.json"
            zones_data = {}
            for zid, zone in self.zones.items():
                zone_dict = asdict(zone)
                # Handle any numpy arrays in zone data
                zone_dict = self._convert_numpy_to_list(zone_dict)
                zones_data[str(zid)] = zone_dict
            
            with open(zones_file, 'w') as f:
                json.dump(zones_data, f, indent=2)
            
            # Save metadata
            metadata_file = self.memory_dir / "metadata.json"
            metadata = {
                'session_start': self.session_start.isoformat(),
                'total_frames_processed': self.total_frames_processed,
                'total_captions_generated': self.total_captions_generated,
                'scene_type': self.scene_type,
                'scene_description': self.scene_description,
                'last_saved': datetime.now().isoformat()
            }
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Memory saved to {self.memory_dir}")
        
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
    
    def _convert_numpy_to_list(self, obj):
        """Recursively convert numpy arrays to lists for JSON serialization"""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: self._convert_numpy_to_list(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_to_list(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._convert_numpy_to_list(item) for item in obj)
        else:
            return obj
    
    def _load_from_disk(self):
        """Load persistent memory from disk"""
        try:
            entities_file = self.memory_dir / "entities.json"
            if entities_file.exists():
                with open(entities_file, 'r') as f:
                    entities_data = json.load(f)
                
                for eid_str, data in entities_data.items():
                    eid = int(eid_str)
                    # Convert appearance_features back to numpy
                    if data['appearance_features'] is not None:
                        data['appearance_features'] = np.array(data['appearance_features'])
                    self.entities[eid] = SpatialEntity(**data)
                
                logger.info(f"Loaded {len(self.entities)} entities from memory")
            
            zones_file = self.memory_dir / "zones.json"
            if zones_file.exists():
                with open(zones_file, 'r') as f:
                    zones_data = json.load(f)
                
                for zid_str, data in zones_data.items():
                    zid = int(zid_str)
                    self.zones[zid] = SpatialZone(**data)
                
                logger.info(f"Loaded {len(self.zones)} zones from memory")
            
            # Load metadata
            metadata_file = self.memory_dir / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                # Restore metadata
                if 'total_frames_processed' in metadata:
                    self.total_frames_processed = metadata['total_frames_processed']
                if 'total_captions_generated' in metadata:
                    self.total_captions_generated = metadata['total_captions_generated']
                if 'scene_type' in metadata:
                    self.scene_type = metadata['scene_type']
                if 'scene_description' in metadata:
                    self.scene_description = metadata['scene_description']
                
                logger.info(f"Loaded metadata (captions: {self.total_captions_generated}, frames: {self.total_frames_processed})")
        
        except Exception as e:
            logger.warning(f"Could not load memory: {e}")
    
    def save(self):
        """Explicitly save memory to disk"""
        self._save_to_disk()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics"""
        return {
            'total_entities': len(self.entities),
            'total_zones': len(self.zones),
            'total_captions': self.total_captions_generated,
            'frames_processed': self.total_frames_processed,
            'session_duration_seconds': (datetime.now() - self.session_start).total_seconds(),
            'conversation_turns': len(self.conversation_context.query_history)
        }
