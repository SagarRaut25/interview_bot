# utils/helpers.py

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
CONVERSATION_FILE = "interview_conversation.txt"

def init_interview_data():
    """
    Initializes a new interview data structure and clears previous conversation history.
    """
    logger.debug("Initializing new interview data structure")
    # Clear previous conversation file
    if os.path.exists(CONVERSATION_FILE):
        os.remove(CONVERSATION_FILE)
        
    return {
        "questions": [],
        "answers": [],
        "ratings": [],
        "current_question": 0,
        "interview_started": False,
        "conversation_history": [],
        "role": "",
        "experience_level": "",
        "years_experience": 0,
        "start_time": None,
        "end_time": None,
        "visual_feedback": [],
        "last_frame_time": 0,
        "last_activity_time": None,
        "follow_up_questions": [],
        "current_topic": None,
        "follow_up_count": 0,
        "current_context": "",
        "question_topics": [],
        "used_questions": [],
        "used_follow_ups": []
    }
