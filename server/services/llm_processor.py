"""Language model processor using MLX Gemma."""
from typing import Dict, Any, List, Optional

from models import DetectionFrame
from services.model_manager import ModelManager
from utils.logger import get_logger

logger = get_logger(__name__)

class LLMProcessor:
    """Handles text generation and scene understanding."""
    
    def __init__(self, model_manager: ModelManager):
        """
        Initialize LLM processor.
        
        Args:
            model_manager: MLX model manager instance
        """
        self.model_manager = model_manager
        self.stats = {
            "scenes_analyzed": 0,
            "average_confidence": 0.0
        }
        logger.info("LLMProcessor initialized")
        
    async def initialize(self) -> None:
        """Initialize LLM processing."""
        logger.info("LLM processor ready")
        
    async def analyze_scene(
        self,
        frame: DetectionFrame,
        vision_analysis: Dict[str, Any],
        context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze a scene using vision results and context.
        
        Args:
            frame: Current frame with iOS detections
            vision_analysis: Results from MLX vision processing
            context: Recent historical context
            
        Returns:
            Enhanced scene understanding
        """
        try:
            # Build prompt from all available information
            prompt = self._build_prompt(frame, vision_analysis, context)
            
            # Get enhanced understanding from Gemma
            llm_result = await self.model_manager.process_text(prompt, vision_analysis)
            
            # Update stats
            self.stats["scenes_analyzed"] += 1
            self.stats["average_confidence"] = (
                (self.stats["average_confidence"] * (self.stats["scenes_analyzed"] - 1) +
                llm_result["confidence"]) / self.stats["scenes_analyzed"]
            )
            
            # Return enhanced analysis
            return {
                "scene_description": self._enhance_description(
                    ios_detections=frame.detections,
                    vlm_description=vision_analysis["description"],
                    llm_response=llm_result["response"]
                ),
                "contextual_insights": self._extract_insights(
                    llm_result["response"],
                    context
                ),
                "enhanced_detections": self._enhance_detections(
                    frame.detections,
                    vision_analysis,
                    llm_result
                ),
                "confidence": llm_result["confidence"]
            }
            
        except Exception as e:
            logger.error(f"Error analyzing scene: {e}")
            return {
                "scene_description": "Error analyzing scene",
                "contextual_insights": [],
                "enhanced_detections": [],
                "confidence": 0.0
            }
            
    def _build_prompt(
        self,
        frame: DetectionFrame,
        vision_analysis: Dict[str, Any],
        context: List[Dict[str, Any]]
    ) -> str:
        """Build comprehensive prompt for LLM."""
        prompt_parts = [
            "Analyze this scene using all available information:\n\n",
            
            "iOS Detections:\n",
            *[f"- {d.label} (confidence: {d.confidence:.2f})\n" for d in frame.detections],
            "\n",
            
            "MLX Vision Analysis:\n",
            f"- Description: {vision_analysis.get('description', 'No description')}\n",
            f"- Confidence: {vision_analysis.get('confidence', 0.0):.2f}\n\n"
        ]
        
        if context:
            prompt_parts.extend([
                "Recent Context:\n",
                *[f"- Previous Scene: {c.get('description', 'No description')}\n" 
                  for c in context[-3:]],
                "\n"
            ])
            
        prompt_parts.extend([
            "Please provide:\n",
            "1. A comprehensive scene description\n",
            "2. Key insights about object relationships and interactions\n",
            "3. Any notable changes from previous scenes\n",
            "4. Potential actions or events occurring\n"
        ])
        
        return "".join(prompt_parts)
        
    def _enhance_description(
        self,
        ios_detections: List[Any],
        vlm_description: str,
        llm_response: str
    ) -> str:
        """Combine all sources to create enhanced description."""
        # Start with VLM's understanding
        description = vlm_description.strip()
        
        # Add LLM's insights
        if llm_response:
            description += f"\n\nEnhanced understanding: {llm_response}"
            
        return description
        
    def _extract_insights(
        self,
        llm_response: str,
        context: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract key insights from LLM response."""
        insights = []
        
        # Split response into lines
        lines = llm_response.split('\n')
        
        # Extract insights (lines starting with specific markers)
        markers = ['- ', '• ', '* ', 'Insight:', 'Note:']
        for line in lines:
            line = line.strip()
            if any(line.startswith(m) for m in markers):
                insights.append(line.lstrip('- •*').strip())
                
        return insights
        
    def _enhance_detections(
        self,
        ios_detections: List[Any],
        vision_analysis: Dict[str, Any],
        llm_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Enhance detection information."""
        enhanced = []
        
        for det in ios_detections:
            enhanced.append({
                "label": det.label,
                "confidence": det.confidence,
                "bbox": det.bbox,
                "track_id": det.track_id,
                "mlx_features": vision_analysis.get("features", []),
                "context": llm_result.get("response", "")
            })
            
        return enhanced
        
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            "scenes_analyzed": self.stats["scenes_analyzed"],
            "average_confidence": self.stats["average_confidence"]
        }
        
    def is_healthy(self) -> bool:
        """Check if processor is healthy."""
        return self.model_manager.is_healthy()
        
    async def cleanup(self) -> None:
        """Cleanup processor resources."""
        self.stats = {
            "scenes_analyzed": 0,
            "average_confidence": 0.0
        }
        logger.info("LLM processor cleaned up")