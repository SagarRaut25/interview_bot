import os
import logging
from io import BytesIO
from datetime import datetime, timezone
from xhtml2pdf import pisa

logger = logging.getLogger(__name__)

CONVERSATION_FILE = "interview_conversation.txt"


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


def html_to_pdf(html_content: str) -> bytes:
    """
    Converts HTML string to PDF bytes using xhtml2pdf (pisa).
    """
    result = BytesIO()
    pisa_status = pisa.CreatePDF(html_content, dest=result)
    if pisa_status.err:
        logger.error("xhtml2pdf failed to convert HTML to PDF")
        return None
    return result.getvalue()