"""
The Historian Module
====================

The "brain" of Orion. It answers user queries about the video history by:
1. Embedding the user query (CLIP).
2. Retrieving relevant entities from Memgraph (Vector Search).
3. Retrieving structural context (Spatial/Temporal Graph Search).
4. Generating an answer using an LLM (Gemma 3 4B via Ollama).

Author: Orion Research Team
Date: November 2025
"""

import logging
from typing import List, Dict, Any, Optional
import json

from orion.managers.model_manager import ModelManager
from orion.graph.backends.memgraph import MemgraphBackend

logger = logging.getLogger(__name__)

class HistorianAgent:
    """
    RAG Agent for Video Understanding.
    """
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.model_manager = ModelManager.get_instance()
        
        # Connect to Memgraph
        try:
            self.memgraph = MemgraphBackend()
            logger.info("Historian connected to Memgraph")
        except Exception as e:
            logger.error(f"Historian failed to connect to Memgraph: {e}")
            self.memgraph = None
            
        # Ensure models are loaded
        # We need CLIP for query embedding and Ollama for generation
        self.clip = self.model_manager.clip
        
    def answer_query(self, query: str) -> str:
        """
        Answer a natural language query about the video history.
        """
        if not self.memgraph:
            return "Error: Memory database not available."
            
        logger.info(f"Historian processing query: '{query}'")
        
        # 1. Embed Query
        query_emb = self.clip.encode_text(query, normalize=True)
        
        # 2. Vector Search (Find relevant entities)
        # We search for entities that semantically match the query
        relevant_entities = self.memgraph.search_similar_entities(
            query_embedding=query_emb.tolist(),
            limit=5,
            min_score=0.25 # CLIP text-image similarity can be lower than image-image
        )
        
        if not relevant_entities:
            return "I couldn't find any relevant objects in my memory to answer that."
            
        # 3. Build Context
        context_str = self._build_context(relevant_entities)
        
        if self.verbose:
            logger.info(f"Retrieved Context:\n{context_str}")
            
        # 4. Generate Answer with LLM
        prompt = self._construct_prompt(query, context_str)
        
        try:
            response = self.model_manager.generate_with_ollama(
                prompt=prompt,
                model="gemma3:4b", # Or configurable
                temperature=0.3 # Low temp for factual answers
            )
            return response
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return "I encountered an error while thinking about the answer."

    def _build_context(self, entities: List[Dict[str, Any]]) -> str:
        """
        Construct a text context from retrieved entities and their graph relationships.
        """
        context_parts = []
        
        for i, entity in enumerate(entities):
            e_id = entity['entity_id']
            cls = entity['class_name']
            score = entity['score']
            
            # Get detailed observations (time, location)
            # We can query the graph for more info about this entity
            # For now, we'll use a simple query to get its timeline
            # TODO: Add a method in MemgraphBackend to get "Entity Summary"
            
            # Let's fetch the last known location and time
            # We can use `query_spatial_relationships` or just assume we have some info
            # Since `search_similar_entities` returns minimal info, we might want to fetch more.
            # But for MVP, let's assume we can get some basic info if we had it.
            
            # Let's try to get spatial relationships for this entity
            spatial_rels = self.memgraph.query_spatial_relationships(e_id)
            spatial_desc = ", ".join([f"{r['relationship']} {r['related_class']}" for r in spatial_rels])
            
            part = f"Entity #{e_id} ({cls}):\n"
            part += f"  - Relevance Score: {score:.2f}\n"
            if spatial_desc:
                part += f"  - Spatial Context: {spatial_desc}\n"
            
            context_parts.append(part)
            
        return "\n".join(context_parts)

    def _construct_prompt(self, query: str, context: str) -> str:
        return f"""You are Orion, an intelligent video historian assistant.
You have access to a memory of events and objects from a video.

User Query: "{query}"

Relevant Memory Context:
{context}

Instructions:
1. Answer the user's query based ONLY on the provided context.
2. If the context doesn't contain the answer, say "I don't have enough information to answer that."
3. Be concise and direct.
4. Refer to objects by their class name and ID if helpful (e.g., "The cup (Entity #42)").

Answer:"""
