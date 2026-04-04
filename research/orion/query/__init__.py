"""
Visual Query System (Stage 5+6)
================================

Natural language queries over video memory.

Stage 5: Retrieval (Cypher → Evidence)
Stage 6: Reasoning (LLM → Natural Language)

Components:
- OrionRAG: Main query interface
- ReasoningModel: Ollama-based LLM reasoning
- QueryResult: Structured query response

Author: Orion Research Team
Date: January 2026
"""

from orion.query.rag_v2 import OrionRAG, QueryResult

try:
    from orion.query.reasoning import ReasoningModel, ReasoningConfig
    REASONING_AVAILABLE = True
except ImportError:
    ReasoningModel = None
    ReasoningConfig = None
    REASONING_AVAILABLE = False

__all__ = [
    "OrionRAG",
    "QueryResult",
    "ReasoningModel",
    "ReasoningConfig",
    "REASONING_AVAILABLE",
]
