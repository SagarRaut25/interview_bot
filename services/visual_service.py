# services/visual_service.py

import logging
from services.cohere_service import co

logger = logging.getLogger(__name__)

def analyze_visual_response(frame_base64: str, conversation_context: list) -> str:
    """
    Analyzes the candidate's visual frame (as base64 string) along with recent conversation context,
    and returns a short professional visual feedback using Cohere.
    """
    logger.debug("Analyzing visual response with Cohere")

    try:
        recent_context = conversation_context[-3:] if len(conversation_context) > 3 else conversation_context

        prompt = f"""
Analyze this interview candidate's appearance and environment.

Context from conversation:
{recent_context}

Please provide a brief professional feedback on:
1. Professional appearance (if visible)
2. Body language and posture
3. Environment appropriateness
4. Any visual distractions

Keep the response under 50 words. Return only the comment, no titles or extra labels.
"""
        response = co.generate(
            model="command-r-plus",
            prompt=prompt,
            max_tokens=200,
            temperature=0.2
        )
        feedback = response.generations[0].text.strip()
        logger.debug(f"Visual feedback received: {feedback}")
        return feedback

    except Exception as e:
        logger.error(f"Error in visual analysis: {str(e)}", exc_info=True)
        return None
