import logging
import re
import os
import cohere
from config import Config  # Import Config class



# Access the API key through the Config class
cohere_api_key = Config.COHERE_API_KEY

# Initialize Cohere client with the API key
co = cohere.Client(cohere_api_key)

logger = logging.getLogger(__name__)


def generate_initial_questions(role, experience_level, years_experience, jd_text, resume_text, load_conversation_fn=None):
    logger.debug("Starting question generation with resume and JD analysis")
    logger.debug(f"Role: {role}, Experience Level: {experience_level}, Years: {years_experience}")

    # Load previous conversation to avoid repetition
    previous_questions = []
    if load_conversation_fn:
        previous_conversation = load_conversation_fn()
        previous_questions = [item['text'] for item in previous_conversation if 'speaker' in item and item['speaker'] == 'bot']

    # Limit length to avoid token overload
    resume_excerpt = resume_text[:1500] if resume_text else "N/A"
    jd_excerpt = jd_text[:1500] if jd_text else "N/A"

    prompt = f"""
You are an intelligent AI interviewer conducting a real-time voice-based interview.

The candidate has applied for the position of *{role}*
Experience Level: *{experience_level}, Years of Experience: **{years_experience}*

---  
 *Resume Extract (Use this for 5 questions)*  
{resume_excerpt}

 *Job Description Extract (Use this for 5 questions)*  
{jd_excerpt}

 *Experience Info*  
Level: {experience_level}  
Years: {years_experience}

 *Target Role*  
{role}
---

 Your task is to generate *20 smart, unique, and personalized questions* broken down as follows:

1. *5 technical questions from Resume*
2. *5 technical questions from Job Description*
3. *5 questions based on Experience*
4. *5 questions based on Role responsibilities & expectations*

 Guidelines:
- Each main question must be followed by 2 intelligent follow-ups (use chain of thought)
- Do NOT repeat or overlap topics
- Avoid any questions from: {previous_questions}
- Each question must add unique value to the interview

 Format exactly like this:
Main Question: [question here]
Follow-ups: [follow-up 1] | [follow-up 2]
---

ONLY use the above format. Do NOT include labels like "Section", "Greeting".
"""

    try:
        logger.debug("Sending prompt to OpenAI for interview question generation")
        response = co.generate(
            model="command-r-plus",
            prompt=prompt,
            temperature=0.7,
            max_tokens=2000
        )
        script = response.generations[0].text
        logger.debug("Received response from OpenAI")

        if not script.strip():
            logger.error("Empty response from OpenAI")
            raise ValueError("AI returned no content")

        logger.debug("Raw script received from OpenAI:\n" + script)

        questions = []
        question_topics = []
        current_block = {}

        for line in script.split("\n"):
            line = line.strip()
            if line.startswith("Main Question:"):
                if current_block.get("main"):
                    questions.append(current_block)
                current_block = {
                    "main": line.replace("Main Question:", "").strip(),
                    "follow_ups": []
                }
            elif line.startswith("Follow-ups:"):
                follow_ups = line.replace("Follow-ups:", "").strip().split("|")
                current_block["follow_ups"] = [fq.strip() for fq in follow_ups if fq.strip()][:2]
                if "main" in current_block:
                    question_topics.append(extract_topic(current_block["main"]))
            elif line == "---":
                if current_block.get("main"):
                    questions.append(current_block)
                    current_block = {}

        if current_block.get("main"):
            questions.append(current_block)

        if experience_level == "fresher":
            questions = questions[:8]
        else:
            questions = questions[:8]

        logger.debug(f"Generated {len(questions)} questions with {len(question_topics)} topics")
        return questions, question_topics[:len(questions)]

    except Exception as e:
        logger.error(f"Error generating questions: {str(e)}", exc_info=True)
        logger.warning("Using fallback question set")

        if experience_level == "fresher":
            questions = [
                {
                    "main": "Welcome to the interview. Could you tell us about your educational background?",
                    "follow_ups": [
                        "What specific courses did you find most valuable?",
                        "How has your education prepared you for this role?"
                    ]
                },
                {
                    "main": "What programming languages are you most comfortable with?",
                    "follow_ups": [
                        "Can you describe a project where you used this language?",
                        "How did you learn it?"
                    ]
                },
                {
                    "main": "Can you explain a technical concept you learned recently?",
                    "follow_ups": [
                        "How have you applied this concept in practice?",
                        "What challenges did you face while learning it?"
                    ]
                },
                {
                    "main": "Describe a time you faced a challenge in a team project.",
                    "follow_ups": [
                        "What was your role in resolving it?",
                        "What did you learn from the experience?"
                    ]
                }
            ]
        else:
            questions = [
                {
                    "main": "Welcome to the interview. Can you summarize your professional experience?",
                    "follow_ups": [
                        "Which part of your experience is most relevant here?",
                        "What projects are you most proud of?"
                    ]
                },
                {
                    "main": "What technical challenges have you faced recently?",
                    "follow_ups": [
                        "How did you overcome them?",
                        "What tools did you use?"
                    ]
                },
                {
                    "main": "Describe a situation where you led a project or a team.",
                    "follow_ups": [
                        "What challenges did you face in leadership?",
                        "What did the team accomplish?"
                    ]
                },
                {
                    "main": "What's a major professional achievement you're proud of?",
                    "follow_ups": [
                        "What impact did it have?",
                        "What did you learn from it?"
                    ]
                }
            ]

        question_topics = [extract_topic(q["main"]) for q in questions]
        return questions, question_topics


def extract_topic(question):
    logger.debug(f"Extracting topic from question: {question}")
    question = question.lower()
    if 'tell me about' in question:
        return question.split('tell me about')[-1].strip(' ?')
    elif 'describe' in question:
        return question.split('describe')[-1].strip(' ?')
    elif 'explain' in question:
        return question.split('explain')[-1].strip(' ?')
    elif 'what' in question:
        return question.split('what')[-1].strip(' ?')
    elif 'how' in question:
        return question.split('how')[-1].strip(' ?')
    return question.split('?')[0].strip()


def generate_dynamic_follow_up(conversation_history, current_topic):
    logger.debug(f"Generating dynamic follow-up for topic: {current_topic}")
    try:
        prompt = f"""
        Based on the candidate's last response about '{current_topic}', generate a relevant, insightful follow-up question.
        The question should:
        1. Be directly related to specific details in their response
        2. Probe deeper into their experience, knowledge, or thought process
        3. Be professional and appropriate for a job interview
        4. Be concise (one sentence)
        
        Candidate's last response: "{conversation_history[-1]['text']}"
        
        Return ONLY the question, nothing else.
        """
        response = co.generate(
            model="command-r-plus",
            prompt=prompt,
            max_tokens=200,
            temperature=0.7
        )
        follow_up = response.generations[0].text.strip()
        logger.debug(f"Generated follow-up question: {follow_up}")
        return follow_up if follow_up.endswith('?') else follow_up + '?'
    except Exception as e:
        logger.error(f"Error generating dynamic follow-up: {str(e)}", exc_info=True)
        return None


def generate_encouragement_prompt(conversation_history):
    logger.debug("Generating encouragement prompt for paused candidate")
    try:
        prompt = f"""
        The candidate has paused during their response. Generate a brief, encouraging prompt to:
        - Help them continue their thought
        - Reference specific aspects of their previous answers
        - Be supportive and professional
        - Be concise (one short sentence)
        
        Current conversation context:
        {conversation_history[-2:]}
        
        Return ONLY the prompt, nothing else.
        """
        response = co.generate(
            model="command-r-plus",
            prompt=prompt,
            max_tokens=300,
            temperature=0.5
        )
        encouragement = response.generations[0].text.strip()
        logger.debug(f"Generated encouragement: {encouragement}")
        return encouragement
    except Exception as e:
        logger.error(f"Error generating encouragement prompt: {str(e)}", exc_info=True)
        return "Please continue with your thought."

def parse_questions(raw):
    questions = []
    topics = []

    question_blocks = re.split(r'\n\d+\.\s+Question:\s+', raw)
    for block in question_blocks[1:]:
        parts = block.strip().split("Follow-ups:")
        main_question = parts[0].strip()

        follow_ups = []
        if len(parts) > 1:
            follow_up_lines = parts[1].strip().split("\n")
            for line in follow_up_lines:
                line = line.strip()
                match = re.match(r'\d+\.\s*\|\s*(.+)', line)
                if match:
                    follow_ups.append(match.group(1))

        questions.append({
            "main": main_question,
            "follow_ups": follow_ups
        })
        topics.append("general")  # Or customize topic logic if needed

    return questions, topics

