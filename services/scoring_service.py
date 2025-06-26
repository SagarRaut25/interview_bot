# services/scoring_service.py

import logging
from services.cohere_service import co

logger = logging.getLogger(__name__)

def evaluate_response(answer: str, question: str, role: str, experience_level: str, visual_feedback: str = None) -> float:
    """
    Evaluates a candidate's answer to an interview question using Cohere.
    Returns a score between 1 and 10 based on relevance, clarity, and professionalism.
    """

    logger.debug(f"Evaluating response for question: {question[:50]}...")

    answer = answer.strip()

    if len(answer) < 20:
        logger.debug("Answer too short, returning 2")
        return 2.0
    elif len(answer) < 50:
        logger.debug("Short but acceptable answer, returning 4")
        return 4.0

    # Compose prompt
    rating_prompt = f"""
You are assessing an interview response for a {role} position from a {experience_level} candidate.

Question: "{question}"
Answer: "{answer}"

Evaluate the answer based on the following *five criteria*, each rated from 1 to 10:
1. Relevance
2. Knowledge depth
3. Clarity
4. Use of examples
5. Professionalism

Also consider the candidate's visual feedback (if available): "{visual_feedback or 'N/A'}"

Only return the output in the following strict *JSON format*:

{{
  "relevance": <score>,
  "knowledge_depth": <score>,
  "clarity": <score>,
  "examples": <score>,
  "professionalism": <score>,
  "final_rating": <weighted_average_score>,
  "answer_quality": "<classification_text>"
}}
"""

    try:
        response = co.generate(
            model="command-r-plus",
            prompt=rating_prompt,
            max_tokens=150,
            temperature=0.3
        )
        rating_text = response.generations[0].text.strip()

        # Attempt to extract the final rating score
        import re
        import json

        try:
            rating_json = json.loads(rating_text)
            final_rating = float(rating_json.get("final_rating", 5))
            final_rating = max(1.0, min(10.0, final_rating))
            logger.debug(f"Extracted structured rating: {final_rating}")
            return final_rating
        except Exception as parse_err:
            logger.warning(f"Failed to parse JSON rating, fallback attempt. Raw text: {rating_text}")
            match = re.search(r'"final_rating"\s*:\s*(\d+(\.\d+)?)', rating_text)
            if match:
                fallback_rating = float(match.group(1))
                return max(1.0, min(10.0, fallback_rating))

            logger.warning("Could not extract rating value. Returning default: 5.0")
            return 5.0

    except Exception as e:
        logger.error(f"Error evaluating response: {str(e)}", exc_info=True)
        return 5.0
