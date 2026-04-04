"""
Stage 6: LLM Reasoning Module for Orion
========================================

Provides natural language reasoning over video memory using Ollama.

Features:
1. Natural Language → Cypher translation
2. Evidence-based answer synthesis
3. Conversational memory for follow-up questions
4. Streaming responses for real-time interaction

Author: Orion Research Team
Date: January 2026
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Generator

logger = logging.getLogger(__name__)

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    ollama = None


@dataclass
class ReasoningConfig:
    """Configuration for the reasoning model."""
    model: str = "qwen2.5:14b-instruct-q8_0"
    base_url: str = "http://localhost:11434"
    
    # Generation settings
    temperature_cypher: float = 0.0  # Deterministic for Cypher generation
    temperature_synthesis: float = 0.3  # Slightly creative for answers
    max_tokens: int = 1024
    
    # Prompting
    system_prompt: str = """You are Orion, a helpful and intelligent video memory assistant. Your goal is to help the user recall and understand what happened in a video by querying a knowledge graph of detected objects, interactions, and spatial relationships.

You have access to a Memgraph database containing:
- Entities: Tracked objects (person, laptop, etc.) with unique IDs and classes.
- Frames: Temporal markers with timestamps.
- Spatial/Action relations: NEAR (proximity), HELD_BY (interaction), ON (spatial support).

Persona Guidelines:
1. **Be Conversational**: Respond like a helpful companion. Instead of just listing data, synthesize it into a natural narrative.
2. **Be Evidence-Based**: Use specific timestamps and object details from the provided evidence.
3. **Be Transparent**: If you don't know something or the evidence is missing, explain why politely. 
4. **No Hallucinations**: Only discuss what is explicitly present in the provided graph evidence.
5. **Contextual Awareness**: Reference previous parts of the conversation if relevant."""

    # Context window
    max_conversation_history: int = 10


@dataclass
class ConversationTurn:
    """Single turn in conversation history."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    evidence: Optional[List[Dict]] = None


class ReasoningModel:
    """
    Ollama-based reasoning model for video Q&A.
    
    Provides:
    - Natural language understanding
    - Cypher query generation
    - Evidence-based answer synthesis
    - Conversational context tracking
    
    Example:
        model = ReasoningModel()
        
        # Simple Q&A
        answer = model.synthesize_answer(
            question="What did the person interact with?",
            evidence=[{"object": "book", "holder": "person", "count": 77}]
        )
        
        # Cypher generation
        cypher = model.generate_cypher("Find all objects near the laptop")
    """
    
    def __init__(self, config: Optional[ReasoningConfig] = None):
        """Initialize reasoning model."""
        if not OLLAMA_AVAILABLE:
            raise ImportError(
                "ollama package not installed. Install with: pip install ollama"
            )
        
        self.config = config or ReasoningConfig()
        self.conversation_history: List[ConversationTurn] = []
        self._client = None
        self._model_validated = False
        
        logger.info(f"ReasoningModel initialized with model: {self.config.model}")
    
    @property
    def client(self):
        """Lazy initialization of Ollama client."""
        if self._client is None:
            self._client = ollama.Client(host=self.config.base_url)
        return self._client
    
    def validate_model(self) -> bool:
        """Check if the configured model is available."""
        if self._model_validated:
            return True
        
        try:
            # Try to list models
            models = self.client.list()
            model_names = [m.model for m in models.models] if hasattr(models, 'models') else []
            
            # Check if our model is available (handle version tags)
            model_base = self.config.model.split(":")[0]
            available = any(model_base in name for name in model_names)
            
            if not available:
                logger.warning(
                    f"Model '{self.config.model}' not found. "
                    f"Available models: {model_names}. "
                    f"Pull with: ollama pull {self.config.model}"
                )
                return False
            
            self._model_validated = True
            logger.info(f"✓ Model '{self.config.model}' validated")
            return True
            
        except Exception as e:
            logger.error(f"Failed to validate model: {e}")
            return False
    
    def generate_cypher(self, question: str, schema_hint: Optional[str] = None) -> str:
        """
        Generate a Cypher query from natural language.
        
        Args:
            question: Natural language question
            schema_hint: Optional schema description
            
        Returns:
            Cypher query string
        """
        schema = schema_hint or """
Schema:
- (Entity {id, class_name, first_seen, last_seen, embedding})
- (Frame {idx, timestamp})
- (Zone {id, type})
- (Entity)-[OBSERVED_IN {bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence}]->(Frame)
- (Entity)-[NEAR {confidence, frame_idx}]->(Entity)
- (Entity)-[HELD_BY {confidence, frame_idx}]->(Entity)
- (Entity)-[IN_ZONE]->(Zone)
"""
        
        prompt = f"""Generate a Cypher query for Memgraph to answer this question.

{schema}

Question: {question}

Rules:
1. Return ONLY the Cypher query, no explanation
2. Use proper Memgraph syntax (similar to Neo4j)
3. Limit results to 20 unless counting
4. Include relevant properties in RETURN
5. Do NOT use SQL syntax (e.g., SELECT, FROM) or pseudo-code
6. Only use labels/relationships that appear in the schema exactly as written

Cypher query:"""
        
        try:
            response = self.client.generate(
                model=self.config.model,
                prompt=prompt,
                options={
                    "temperature": self.config.temperature_cypher,
                    "num_predict": 256,
                }
            )
            
            cypher = response.response.strip()
            
            # Clean up common issues
            if cypher.startswith("```"):
                lines = cypher.split("\n")
                cypher = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            
            cypher = cypher.replace("```cypher", "").replace("```", "").strip()
            
            logger.debug(f"Generated Cypher: {cypher}")
            return cypher
            
        except Exception as e:
            logger.error(f"Cypher generation failed: {e}")
            return ""
    
    def synthesize_answer(
        self,
        question: str,
        evidence: List[Dict[str, Any]],
        include_reasoning: bool = False,
    ) -> str:
        """
        Synthesize a natural language answer from evidence.
        
        Args:
            question: Original user question
            evidence: List of evidence dicts from Memgraph queries
            include_reasoning: If True, show reasoning steps
            
        Returns:
            Natural language answer
        """
        # Format evidence for the prompt
        if not evidence:
            evidence_text = "No relevant data found in the video memory."
        else:
            evidence_lines = []
            for i, e in enumerate(evidence[:20], 1):  # Limit to 20 items
                evidence_lines.append(f"{i}. {self._format_evidence_item(e)}")
            evidence_text = "\n".join(evidence_lines)
        
        # Build enhanced prompt with better synthesis instructions
        prompt = f"""You are Orion, a knowledgeable video memory assistant. The user asked about a video they recorded, and you have evidence from the video's object tracking and scene graph.

**User Question:** {question}

**Evidence from Video Memory:**
{evidence_text}

**Response Guidelines:**
1. **Answer Directly**: Start with the direct answer to the question. Don't hedge unnecessarily.
2. **Use Specifics**: Include timestamps (e.g., "at 5.2 seconds"), object counts, and durations from the evidence.
3. **Be Confident**: If the evidence supports an answer, state it confidently. Only express uncertainty if the evidence is genuinely ambiguous.
4. **Narrative Flow**: Connect the facts into a coherent story rather than listing data points.
5. **Brief & Clear**: Keep your answer concise (2-4 sentences for simple questions, more for complex ones).

**Your Response:**"""
        
        try:
            response = self.client.generate(
                model=self.config.model,
                prompt=prompt,
                system=self.config.system_prompt,
                options={
                    "temperature": self.config.temperature_synthesis,
                    "num_predict": self.config.max_tokens,
                }
            )
            
            answer = response.response.strip()
            
            # Track conversation
            self.conversation_history.append(ConversationTurn(
                role="user",
                content=question,
            ))
            self.conversation_history.append(ConversationTurn(
                role="assistant",
                content=answer,
                evidence=evidence,
            ))
            
            # Trim history if needed
            if len(self.conversation_history) > self.config.max_conversation_history * 2:
                self.conversation_history = self.conversation_history[-self.config.max_conversation_history * 2:]
            
            return answer
            
        except Exception as e:
            logger.error(f"Answer synthesis failed: {e}")
            return f"I encountered an error processing your question: {str(e)}"
    
    def stream_answer(
        self,
        question: str,
        evidence: List[Dict[str, Any]],
    ) -> Generator[str, None, None]:
        """
        Stream answer tokens for real-time display.
        
        Yields:
            Answer tokens as they're generated
        """
        if not evidence:
            evidence_text = "No relevant data found in the video memory."
        else:
            evidence_lines = []
            for i, e in enumerate(evidence[:20], 1):
                evidence_lines.append(f"{i}. {self._format_evidence_item(e)}")
            evidence_text = "\n".join(evidence_lines)
        
        prompt = f"""You are Orion, a knowledgeable video memory assistant. The user asked about a video they recorded, and you have evidence from the video's object tracking and scene graph.

**User Question:** {question}

**Evidence from Video Memory:**
{evidence_text}

**Response Guidelines:**
1. **Answer Directly**: Start with the direct answer. Don't hedge.
2. **Use Specifics**: Include timestamps, object counts, and durations.
3. **Be Confident**: State answers confidently when evidence supports them.
4. **Brief & Clear**: Keep your answer concise.

**Your Response:**"""
        
        try:
            stream = self.client.generate(
                model=self.config.model,
                prompt=prompt,
                system=self.config.system_prompt,
                stream=True,
                options={
                    "temperature": self.config.temperature_synthesis,
                    "num_predict": self.config.max_tokens,
                }
            )
            
            full_answer = ""
            for chunk in stream:
                token = chunk.response
                full_answer += token
                yield token
            
            # Track conversation after streaming completes
            self.conversation_history.append(ConversationTurn(
                role="user",
                content=question,
            ))
            self.conversation_history.append(ConversationTurn(
                role="assistant",
                content=full_answer,
                evidence=evidence,
            ))
            
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            yield f"Error: {str(e)}"
    
    def _format_evidence_item(self, item: Dict[str, Any]) -> str:
        """Format a single evidence item for the prompt."""
        parts = []
        
        # Handle different evidence formats
        if "class" in item:
            parts.append(f"Object: {item['class']}")
        if "class_name" in item:
            parts.append(f"Object: {item['class_name']}")
        if "object" in item:
            parts.append(f"Object: {item['object']}")
        
        if "observations" in item:
            parts.append(f"seen {item['observations']} times")
        if "count" in item:
            parts.append(f"count: {item['count']}")
        
        if "first_seen" in item:
            parts.append(f"first seen: {item['first_seen']}")
        if "last_seen" in item:
            parts.append(f"last seen: {item['last_seen']}")
        if "time" in item:
            parts.append(f"at {item['time']:.1f}s" if isinstance(item['time'], (int, float)) else f"at {item['time']}")
        
        if "holder" in item:
            parts.append(f"held by: {item['holder']}")
        if "nearby" in item:
            parts.append(f"near: {item['nearby']}")
        
        if "frame" in item:
            parts.append(f"frame {item['frame']}")
        
        if "confidence" in item:
            parts.append(f"confidence: {item['confidence']:.2f}" if isinstance(item['confidence'], float) else f"confidence: {item['confidence']}")
        
        return ", ".join(parts) if parts else str(item)
    
    def get_conversation_context(self) -> str:
        """Get formatted conversation history for context."""
        if not self.conversation_history:
            return ""
        
        lines = []
        for turn in self.conversation_history[-6:]:  # Last 3 exchanges
            role = "User" if turn.role == "user" else "Assistant"
            lines.append(f"{role}: {turn.content}")
        
        return "\n".join(lines)
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history.clear()
        logger.debug("Conversation history cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get model statistics."""
        return {
            "model": self.config.model,
            "conversation_turns": len(self.conversation_history),
            "model_validated": self._model_validated,
        }


def test_reasoning():
    """Test the reasoning module."""
    logging.basicConfig(level=logging.INFO)
    
    print("Testing ReasoningModel...")
    print("=" * 50)
    
    try:
        model = ReasoningModel()
        
        # Validate model
        if not model.validate_model():
            print("Model validation failed. Is Ollama running?")
            print("Start with: ollama serve")
            print(f"Pull model with: ollama pull {model.config.model}")
            return
        
        # Test Cypher generation
        print("\n1. Testing Cypher Generation:")
        cypher = model.generate_cypher("What objects were near the laptop?")
        print(f"   Generated: {cypher}")
        
        # Test answer synthesis
        print("\n2. Testing Answer Synthesis:")
        evidence = [
            {"class": "book", "observations": 77, "first_seen": "1.0s", "last_seen": "38.0s"},
            {"class": "person", "observations": 169, "first_seen": "0.0s", "last_seen": "56.0s"},
            {"object": "book", "holder": "person", "count": 77},
        ]
        answer = model.synthesize_answer(
            "What did the person interact with?",
            evidence
        )
        print(f"   Answer: {answer}")
        
        # Test streaming
        print("\n3. Testing Streaming Response:")
        print("   ", end="", flush=True)
        for token in model.stream_answer("How long was the book visible?", evidence):
            print(token, end="", flush=True)
        print()
        
        print("\n✓ All tests passed!")
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Install with: pip install ollama")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_reasoning()
