
"""Language model processor using MLX Gemma."""
from typing import Dict, Any, List, Optional

from models import Detection, DetectionFrame
from services.model_manager import ModelManager
from utils.logger import get_logger

from utils.bbox import get_spatial_label

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
            "average_confidence": 0.0,
            "questions_answered": 0
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
            # Build prompt for scene analysis
            prompt = self._build_scene_analysis_prompt(frame, vision_analysis, context)
            
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
                    vlm_description=vision_analysis.get("description", ""),
                    llm_response=llm_result.get("response", "")
                ),
                "contextual_insights": self._extract_insights(
                    llm_result.get("response", ""),
                    context
                ),
                "enhanced_detections": self._enhance_detections(
                    frame.detections,
                    vision_analysis,
                    llm_result
                ),
                "confidence": llm_result.get("confidence", 0.0)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing scene: {e}")
            return {
                "scene_description": "Error analyzing scene",
                "contextual_insights": [],
                "enhanced_detections": [],
                "confidence": 0.0
            }
            
    async def answer_question(
        self,
        question: str,
        context: List[Dict[str, Any]]
    ) -> str:
        """
        Answer a user question based on provided context.
        
        Args:
            question: The user's question.
            context: Relevant historical context.
            
        Returns:
            The LLM's answer to the question.
        """
        try:
            prompt = self._build_question_answering_prompt(question, context)
            llm_result = await self.model_manager.process_text(prompt)
            self.stats["questions_answered"] += 1
            return llm_result["response"]
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            return "I am sorry, I could not process your question at this time."

    def _build_scene_analysis_prompt(
        self,
        frame: DetectionFrame,
        vision_analysis: Dict[str, Any],
        context: List[Dict[str, Any]]
    ) -> str:
        """Build concise prompt for LLM scene analysis, focusing on changes and key elements."""
        
        detections_for_prompt = [Detection(**d) for d in vision_analysis.get("detections", [])]
        current_vlm_desc = vision_analysis.get("description", "").replace("VLM model not loaded.", "").strip()

        prompt_parts = []

        # Start with a very direct instruction for the LLM
        prompt_parts.append("Analyze the current scene. Focus on key objects and any changes from the previous scene.\n")

        # Add concise historical context if available
        if context:
            # Get the most recent scene description from the context, filtering out placeholder
            last_context_entry = context[0]
            last_scene_desc = last_context_entry.get('vlm_description', '').replace("VLM model not loaded.", "").strip()
            if last_scene_desc:
                prompt_parts.append(f"Previous: {last_scene_desc}\n")

        # Add current VLM description if meaningful
        if current_vlm_desc:
            prompt_parts.append(f"Current: {current_vlm_desc}\n")

        # Add detected objects concisely
        if detections_for_prompt:
            obj_list = ", ".join([f"{d.label} ({get_spatial_label(d.bbox)})" for d in detections_for_prompt])
            prompt_parts.append(f"Objects: {obj_list}\n")

        prompt_parts.append("Provide a very brief summary (max 20 words) highlighting changes or main elements.")
        
        return "".join(prompt_parts)
        
    def _build_question_answering_prompt(
        self,
        question: str,
        context: List[Dict[str, Any]]
    ) -> str:
        """
        Build prompt for LLM question answering.
        """
        prompt_parts = [
            "You are an intelligent assistant. Answer the following question based on the provided context.\n\n",
            "Question: " + question + "\n\n"
        ]

        if context:
            prompt_parts.append("Context:\n")
            for entry in context:
                prompt_parts.append(f"- Frame ID: {entry.get('frame_id', 'N/A')}\n")
                prompt_parts.append(f"  Timestamp: {entry.get('timestamp', 'N/A')}\n")
                if entry.get('analysis') and entry['analysis'].get('scene_description'):
                    prompt_parts.append(f"  Scene Description: {entry['analysis']['scene_description']}\n")
                if entry.get('detections'):
                    prompt_parts.append(f"  Detections: {len(entry['detections'])} objects\n")
                prompt_parts.append("\n")
            prompt_parts.append("\n")

        prompt_parts.append("Answer:")
        return "".join(prompt_parts)
        
    def _enhance_description(
        self,
        ios_detections: List[Any],
        vlm_description: str,
        llm_response: str
    ) -> str:
        """Prioritize LLM response for scene description, filtering out VLM placeholder."""
        # If LLM provides a response, use it directly. Otherwise, fall back to VLM description.
        if llm_response and llm_response.strip():
            return llm_response.strip()
        elif vlm_description and "VLM model not loaded" not in vlm_description:
            return vlm_description.strip()
        else:
            return "No meaningful scene description available."
        
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
            "average_confidence": self.stats["average_confidence"],
            "questions_answered": self.stats["questions_answered"]
        }
        
    def is_healthy(self) -> bool:
        """Check if processor is healthy."""
        return self.model_manager.is_healthy()
        
    async def cleanup(self) -> None:
        """Cleanup processor resources."""
        self.stats = {
            "scenes_analyzed": 0,
            "average_confidence": 0.0,
            "questions_answered": 0
        }
        logger.info("LLM processor cleaned up")
