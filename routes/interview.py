from flask import Blueprint, request, jsonify, session
from datetime import datetime, timezone, timedelta
import numpy as np
import base64
import cv2
import os
import re
from routes.session import  save_conversation_to_file
from utils.helpers import init_interview_data
from services.cohere_service  import generate_initial_questions, generate_dynamic_follow_up, generate_encouragement_prompt
from services.tts_service import text_to_speech
from services.visual_service import analyze_visual_response
from services.report_service    import generate_interview_report, save_admin_report_txt
from services.scoring_service import evaluate_response

import logging

interview_bp = Blueprint('interview', __name__)
logger = logging.getLogger(__name__)

# Configuration
MAX_FRAME_SIZE = 500
FRAME_CAPTURE_INTERVAL = 5
MAX_RECORDING_DURATION = 520
PAUSE_THRESHOLD = 40
FOLLOW_UP_PROBABILITY = 0.8
MIN_FOLLOW_UPS = 2
MAX_FOLLOW_UPS = 3  # Exactly 2 follow-ups per question
CONVERSATION_FILE = "interview_conversation.txt"


@interview_bp.route('/start_interview', methods=['POST'])
def start_interview():
    logger.info("Interview start request received")
    
    data = request.get_json()
    resume_text = data.get('resume_text', '')
    jd_text = data.get('jd_text', '')


    candidate_name = data.get('fileName', 'Candidate')  # match the key sent from JS
    candidate_name = candidate_name.split('.')[0].replace('_', ' ').replace('-', ' ')
    print("Candidate Name:----------------------------------------------------------", candidate_name)
    
    # Initialize interview session
    session['interview_data'] = init_interview_data()
    interview_data = session['interview_data']
    
    # Assign interview parameters
    interview_data['role'] = data.get('role', 'Software Engineer')
    interview_data['experience_level'] = data.get('experience_level', 'fresher')
    interview_data['years_experience'] = int(data.get('years_experience', 0))
    interview_data['resume'] = resume_text
    interview_data['jd'] = jd_text,
    interview_data['candidate_name'] = candidate_name  
    interview_data['start_time'] = datetime.now(timezone.utc)
    interview_data['last_activity_time'] = datetime.now(timezone.utc)

    logger.debug(f"Interview parameters set - Role: {interview_data['role']}, "
                 f"Experience: {interview_data['experience_level']}, "
                 f"Years: {interview_data['years_experience']}")

    try:
        questions, question_topics = generate_initial_questions(
            interview_data['role'],
            interview_data['experience_level'],
            interview_data['years_experience'],
            resume_text=resume_text,
            jd_text=jd_text
        )
        
        interview_data['questions'] = [q["main"] for q in questions]
        interview_data['follow_up_questions'] = []
        interview_data['question_topics'] = question_topics

        for q in questions:
            interview_data['conversation_history'].append({
                "question": q["main"],
                "prepared_follow_ups": q["follow_ups"]
            })
        
        interview_data['interview_started'] = True
        session['interview_data'] = interview_data
        logger.info("Interview started successfully")
        
        return jsonify({
            "status": "started",
            "total_questions": len(interview_data['questions']),
            "welcome_message": f"Welcome to the interview for {interview_data['role']} position."
        })

    except Exception as e:
        logger.error(f"Error starting interview: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@interview_bp.route('/get_question', methods=['GET'])
def get_question():
    logger.debug("Get question request received")

    interview_data = session.get('interview_data')
    if not interview_data:
        logger.warning("Interview data not found in session.")
        return jsonify({"status": "not_started"})

    if not interview_data.get('interview_started'):
        logger.warning("Attempt to get question before interview started")
        return jsonify({"status": "not_started"})

    elapsed_time = datetime.now(timezone.utc) - interview_data.get('start_time', datetime.now(timezone.utc))
    max_duration = timedelta(minutes=20)
    if elapsed_time > max_duration:
        logger.info("Interview duration exceeded.")
        return jsonify({"status": "time_exceeded", "message": "Interview time has ended."})

    interview_data.setdefault('used_questions', [])
    interview_data.setdefault('used_follow_ups', [])
    interview_data.setdefault('follow_up_questions', [])
    interview_data.setdefault('follow_up_count', 0)
    interview_data.setdefault('current_question', 0)
    interview_data.setdefault('conversation_history', [])

    is_follow_up = False
    current_q = None

    if (
        interview_data['follow_up_questions'] and
        interview_data['follow_up_count'] < MAX_FOLLOW_UPS and
        (interview_data['follow_up_count'] < MIN_FOLLOW_UPS or np.random.random() < FOLLOW_UP_PROBABILITY)
    ):
        for follow_up in interview_data['follow_up_questions']:
            if follow_up not in interview_data['used_follow_ups']:
                current_q = follow_up
                interview_data['used_follow_ups'].append(current_q)
                interview_data['follow_up_count'] += 1
                is_follow_up = True
                logger.debug(f"Selected follow-up question: {current_q}")
                break

    if not current_q:
        while interview_data['current_question'] < len(interview_data['questions']):
            idx = interview_data['current_question']
            q = interview_data['questions'][idx]
            if q not in interview_data['used_questions']:
                current_q = q
                interview_data['used_questions'].append(current_q)
                interview_data['current_topic'] = interview_data['question_topics'][idx]
                interview_data['follow_up_count'] = 0
                interview_data['current_question'] += 1
                is_follow_up = False
                logger.debug(f"Selected main question: {current_q}")
                break
            else:
                interview_data['current_question'] += 1

    if not current_q:
        logger.info("All questions exhausted, interview complete")
        return jsonify({"status": "completed"})

    interview_data['conversation_history'].append({"speaker": "bot", "text": current_q})
    save_conversation_to_file([{"speaker": "bot", "text": current_q}])
    interview_data['last_activity_time'] = datetime.now(timezone.utc)
    session['interview_data'] = interview_data

    logger.debug("Converting question to speech")
    try:
        audio_data = text_to_speech(current_q)
    except Exception as e:
        logger.error(f"Text-to-speech failed: {str(e)}")
        audio_data = None

    return jsonify({
        "status": "success",
        "question": current_q,
        "audio": audio_data,
        "question_number": interview_data['current_question'],
        "total_questions": len(interview_data['questions']),
        "is_follow_up": is_follow_up
    })


@interview_bp.route('/check_pause', methods=['GET'])
def check_pause():
    logger.debug("Check pause request received")
    interview_data = session.get('interview_data', init_interview_data())
    
    if not interview_data['interview_started']:
        logger.warning("Attempt to check pause before interview started")
        return jsonify({"status": "not_started"})
    
    current_time = datetime.now(timezone.utc)
    last_activity = interview_data['last_activity_time']
    seconds_since_activity = (current_time - last_activity).total_seconds() if last_activity else 0
    logger.debug(f"Seconds since last activity: {seconds_since_activity}")
    
    if seconds_since_activity > PAUSE_THRESHOLD:
        logger.info(f"Pause detected ({seconds_since_activity}s), generating encouragement")
        encouragement = generate_encouragement_prompt(interview_data['conversation_history'])
        audio_data = text_to_speech(encouragement)
        interview_data['last_activity_time'] = current_time
        session['interview_data'] = interview_data
        
        return jsonify({
            "status": "pause_detected",
            "prompt": encouragement,
            "audio": audio_data
        })
    
    return jsonify({"status": "active"})

@interview_bp.route('/process_answer', methods=['POST'])
def process_answer():
    logger.info("Process answer request received")
    interview_data = session.get('interview_data', init_interview_data())

    if not interview_data['interview_started']:
        logger.warning("Attempt to process answer before interview started")
        return jsonify({"status": "error", "message": "Interview not started"}), 400

    data = request.get_json()
    answer = data.get('answer', '').strip()
    frame_data = data.get('frame', None)
    logger.debug(f"Received answer length: {len(answer)} characters")

    if not answer:
        logger.warning("Empty answer received")
        return jsonify({"status": "error", "message": "Empty answer"}), 400

    last_entry = interview_data['conversation_history'][-1] if interview_data['conversation_history'] else {}
    current_question = last_entry.get('text') or last_entry.get('question') or ''

    interview_data['answers'].append(answer)
    interview_data['conversation_history'].append({"speaker": "user", "text": answer})
    save_conversation_to_file([{"speaker": "user", "text": answer}])
    interview_data['last_activity_time'] = datetime.now(timezone.utc)

    feedback_label = "Needs improvement"
    if len(answer) > 50:
        feedback_label = "Good answer"

    interview_data['conversation_history'].append({"speaker": "user", "text": answer, "feedback_label": feedback_label})
    save_conversation_to_file([{"speaker": "user", "text": answer, "feedback_label": feedback_label}])
    interview_data['last_activity_time'] = datetime.now(timezone.utc)

    try:
        logger.debug("Converting feedback to speech")
        feedback_audio = text_to_speech(feedback_label)
    except Exception as e:
        logger.error(f"Text-to-speech failed: {str(e)}")
        feedback_audio = None

    interview_data['conversation_history'][-1]['feedback_audio'] = feedback_audio
    session['interview_data'] = interview_data

    visual_feedback = None
    current_time = datetime.now().timestamp()
    if frame_data and (current_time - interview_data['last_frame_time']) > FRAME_CAPTURE_INTERVAL:
        try:
            logger.debug("Processing frame data")
            frame_bytes = base64.b64decode(frame_data.split(',')[1])
            frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

            if frame is not None:
                frame_base64 = process_frame_for_gpt4v(frame)
                visual_feedback = analyze_visual_response(
                    frame_base64,
                    interview_data['conversation_history'][-3:]
                )
                if visual_feedback:
                    interview_data['visual_feedback'].append(visual_feedback)
                    interview_data['last_frame_time'] = current_time
                    logger.debug("Visual feedback processed and stored")
        except Exception as e:
            logger.error(f"Error processing frame: {str(e)}", exc_info=True)

    logger.debug("Evaluating response quality")
    rating = evaluate_response(
        answer,
        current_question,
        interview_data['role'],
        interview_data['experience_level'],
        visual_feedback
    )
    interview_data['ratings'].append(rating)
    logger.debug(f"Response rated: {rating}/10")

    if (interview_data['current_topic'] and len(answer.split()) > 15 and
        interview_data['follow_up_count'] < MAX_FOLLOW_UPS):

        current_main_question_index = interview_data['current_question'] - 1
        if (current_main_question_index < len(interview_data['conversation_history']) and
            'prepared_follow_ups' in interview_data['conversation_history'][current_main_question_index]):

            prepared_follow_ups = interview_data['conversation_history'][current_main_question_index]['prepared_follow_ups']
            for follow_up in prepared_follow_ups:
                if follow_up not in interview_data['used_follow_ups'] and follow_up not in interview_data['follow_up_questions']:
                    interview_data['follow_up_questions'].append(follow_up)
                    logger.debug(f"Added prepared follow-up: {follow_up}")

        if len(interview_data['follow_up_questions']) < MAX_FOLLOW_UPS:
            logger.debug("Generating dynamic follow-up question")
            dynamic_follow_up = generate_dynamic_follow_up(
                interview_data['conversation_history'],
                interview_data['current_topic']
            )
            if dynamic_follow_up and dynamic_follow_up not in interview_data['used_follow_ups'] and dynamic_follow_up not in interview_data['follow_up_questions']:
                interview_data['follow_up_questions'].append(dynamic_follow_up)
                logger.debug(f"Added dynamic follow-up: {dynamic_follow_up}")

    interview_complete = interview_data['current_question'] >= len(interview_data['questions']) and not interview_data['follow_up_questions']

    if interview_complete:
        logger.info("Interview complete, generating report")
        user_report = generate_interview_report(interview_data)

        admin_filepath, admin_filename = save_admin_report_txt(interview_data)
        logger.info(f"Admin report saved: {admin_filepath}")

        return jsonify({
            "status": "interview_complete",
            "message": "Interview complete, report generated and saved.",
            "report_html": user_report.get('reports', ''),
            "admin_report_filename": admin_filename
        })

    session['interview_data'] = interview_data

    return jsonify({
        "status": "answer_processed",
        "current_question": interview_data['current_question'],
        "total_questions": len(interview_data['questions']),
        "interview_complete": False,
        "has_follow_up": len(interview_data['follow_up_questions']) > 0,
        "feedback_audio": feedback_audio
    })
    