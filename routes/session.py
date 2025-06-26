# routes/session.py

import os
import logging
from flask import Blueprint, request, session
from datetime import datetime, timezone
from utils.helpers import init_interview_data
logger = logging.getLogger(__name__)
session_bp = Blueprint('session', __name__)
CONVERSATION_FILE = "interview_conversation.txt"
from utils.helpers import init_interview_data

@session_bp.before_request
def before_request():
    logger.debug(f"Before request - path: {request.path}, method: {request.method}")
    if 'interview_data' not in session:
        logger.debug("No interview data in session, initializing new data")
        session['interview_data'] = init_interview_data()
    session.permanent = True  # Keeps session alive across browser restarts if configured

@session_bp.route('/logout')
def logout():
    logger.info("Logout requested - clearing session")
    session.clear()
    return "Session cleared, user logged out."


def save_conversation_to_file(conversation_data):
    try:
        with open(CONVERSATION_FILE, "a") as f:
            for item in conversation_data:
                if 'speaker' in item:
                    f.write(f"{item['speaker']}: {item['text']}\n")
                elif 'question' in item:
                    f.write(f"Question: {item['question']}\n")
        logger.debug("Conversation saved to file")
    except Exception as e:
        logger.error(f"Error saving conversation to file: {str(e)}", exc_info=True)

def load_conversation_from_file():
    try:
        if not os.path.exists(CONVERSATION_FILE):
            return []
        
        with open(CONVERSATION_FILE, "r") as f:
            lines = f.readlines()
        
        conversation = []
        for line in lines:
            if line.startswith("bot:") or line.startswith("user:"):
                speaker, text = line.split(":", 1)
                conversation.append({"speaker": speaker.strip(), "text": text.strip()})
            elif line.startswith("Question:"):
                question = line.split(":", 1)[1].strip()
                conversation.append({"question": question})
        
        return conversation
    except Exception as e:
        logger.error(f"Error loading conversation from file: {str(e)}", exc_info=True)
        return []
