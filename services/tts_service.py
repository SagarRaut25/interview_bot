# services/tts_service.py

import base64
import tempfile
import os
import logging
from gtts import gTTS

logger = logging.getLogger(__name__)

def text_to_speech(text: str) -> str:
    """
    Converts input text to speech using Google Text-to-Speech (gTTS)
    and returns the MP3 audio as a base64-encoded string.
    """
    logger.debug(f"Converting text to speech: {text[:50]}...")  # Log preview of text
    try:
        # Generate audio using gTTS
        tts = gTTS(text=text, lang='en', slow=False)

        # Write to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
            temp_filename = temp_file.name
            tts.save(temp_filename)

        # Read and encode the MP3 file
        with open(temp_filename, 'rb') as f:
            audio_data = f.read()

        # Cleanup
        os.unlink(temp_filename)

        # Return base64-encoded audio
        logger.debug("Successfully converted text to base64 audio")
        return base64.b64encode(audio_data).decode('utf-8')

    except Exception as e:
        logger.error(f"Text-to-speech error: {str(e)}", exc_info=True)
        return None
