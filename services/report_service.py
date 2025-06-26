# services/report_service.py

import logging
from datetime import datetime, timezone
from .tts_service import text_to_speech
from .cohere_service import co
from utils.file_utils import html_to_pdf
import os

logger = logging.getLogger(__name__)
def generate_interview_report(interview_data):
    try:
        # Calculate interview duration
        duration = "N/A"
        if interview_data['start_time'] and interview_data['end_time']:
            duration_seconds = (interview_data['end_time'] - interview_data['start_time']).total_seconds()
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            duration = f"{minutes}m {seconds}s"
        
        # Calculate average rating
        ratings = interview_data.get('ratings', [])
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        logger.debug(f"Average rating: {avg_rating:.1f}, based on {len(ratings)} ratings")
        
        # Determine status based on average rating
        if avg_rating >= 7:
            status_class = "selected"

        elif avg_rating >= 4 and avg_rating < 7:
            status_class = "onhold"
            
        else:
            status_class = "rejected"
        
        # Calculate skill distribution
        questions = interview_data.get('questions', [])
        question_topics = interview_data.get('question_topics', [])
        ratings = interview_data.get('ratings', [])
        
        technical_scores = []
        communication_scores = []
        behavioral_scores = []

        # Categorize ratings based on question types
        for i, (question, topic, rating) in enumerate(zip(questions, question_topics, ratings)):
            # More precise categorization using topic (assuming topics are descriptive)
            topic_lower = topic.lower() if topic else ""
            if "technical" in topic_lower or i < 10:  # Fallback to index-based for compatibility
                technical_scores.append(rating)
            elif "experience" in topic_lower or "role" in topic_lower or i < 15:
                behavioral_scores.append(rating)
            communication_scores.append(rating * 0.4)  # Proxy for communication (clarity/professionalism)

        # Calculate average scores with fallback
        technical_avg = sum(technical_scores) / len(technical_scores) if technical_scores else 5
        behavioral_avg = sum(behavioral_scores) / len(behavioral_scores) if behavioral_scores else 5
        communication_avg = sum(communication_scores) / len(communication_scores) if communication_scores else 5
        logger.debug(f"Skill averages - Technical: {technical_avg:.1f}, Communication: {communication_avg:.1f}, Behavioral: {behavioral_avg:.1f}")

        # Normalize to percentages with safeguard
        total = max(technical_avg + communication_avg + behavioral_avg, 0.01)  # Avoid division by zero
        technical_pct = (technical_avg / total) * 100 if total > 0 else 33.33
        communication_pct = (communication_avg / total) * 100 if total > 0 else 33.33
        behavioral_pct = 100 - technical_pct - communication_pct  # Ensure sum is 100%
        logger.debug(f"Skill percentages - Technical: {technical_pct:.1f}%, Communication: {communication_pct:.1f}%, Behavioral: {behavioral_pct:.1f}%")

        # Generate bar chart HTML
        bar_chart_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 400px; margin: 20px auto;">
            <h4 style="text-align: center;">Skill Distribution</h4>
            <div style="margin-bottom: 15px;">
                <span style="display: inline-block; width: 120px; font-weight: bold;">Technical 🛠</span>
                <div style="display: inline-block; width: 200px; background-color: #e0e0e0; border-radius: 5px; overflow: hidden;">
                    <div style="width: {min(technical_pct, 100)}%; background-color: #4CAF50; height: 20px;"></div>
                </div>
                <span style="margin-left: 10px;">{technical_pct:.1f}%</span>
            </div>
            <div style="margin-bottom: 15px;">
                <span style="display: inline-block; width: 120px; font-weight: bold;">Communication 🗣</span>
                <div style="display: inline-block; width: 200px; background-color: #e0e0e0; border-radius: 5px; overflow: hidden;">
                    <div style="width: {min(communication_pct, 100)}%; background-color: #2196F3; height: 20px;"></div>
                </div>
                <span style="margin-left: 10px;">{communication_pct:.1f}%</span>
            </div>
            <div style="margin-bottom: 15px;">
                <span style="display: inline-block; width: 120px; font-weight: bold;">Behavioral 🤝</span>
                <div style="display: inline-block; width: 200px; background-color: #e0e0e0; border-radius: 5px; overflow: hidden;">
                    <div style="width: {min(behavioral_pct, 100)}%; background-color: #FFC107; height: 20px;"></div>
                </div>
                <span style="margin-left: 10px;">{behavioral_pct:.1f}%</span>
            </div>
        </div>
        """

        # Prepare conversation history
        conversation_history_text = "\n".join([f"{item['speaker']}: {item['text']}" for item in interview_data['conversation_history'] if 'speaker' in item])
        
        report_prompt = f"""
You are an expert AI HR assistant responsible for generating professional interview evaluation reports.

The following interview was conducted for the role of {interview_data['role']}.

### Candidate Overview:
- 🎓 Experience Level: {interview_data['experience_level']}
- 🕒 Years of Experience: {interview_data['years_experience']}
- ⏱ Interview Duration: {duration}
- ⭐ Average Interviewer Rating: {avg_rating:.1f}/10

### 📜 Interview Transcript:
{conversation_history_text}

---

## 🎯 Your Task:
Generate a detailed interview evaluation report using the transcript and rating context.

Format the output in clean HTML with semantic structure, using <h2>, <table>, and <div>.

✅ Include the following 5 sections:

---

### 1. <h2>Interview Summary</h2>
- Provide a concise overview of how the interview went.
- Mention how well the candidate communicated, handled technical questions, and overall impression.

---

### 2. <h2>Key Strengths</h2>
- Show a table with exactly 2 columns: 'Aspect' and 'Evidence from Responses'.
- Include 2-4 rows, each identifying a strength (e.g., Problem Solving, Communication, Domain Expertise) and quoting or summarizing a relevant answer from the transcript.
- Use the following HTML table structure:
  <table style="width: 100%; border-collapse: collapse;">
    <tr style="border: 1px solid #000;">
      <th style="border: 1px solid #000; padding: 8px;">Aspect</th>
      <th style="border: 1px solid #000; padding: 8px;">Evidence from Responses</th>
    </tr>
    <tr style="border: 1px solid #000;">
      <td style="border: 1px solid #000; padding: 8px;">[Strength Aspect]</td>
      <td style="border: 1px solid #000; padding: 8px;">[Quote or Summary]</td>
    </tr>
    <!-- Additional rows as needed -->
  </table>

---

### 3. <h2>Areas for Improvement</h2>
- Show a table with exactly 2 columns: 'Aspect to Improve' and 'Suggestion or Evidence'.
- Include 2-4 rows, each identifying an area for improvement (e.g., Confidence, Project Depth) and providing actionable feedback or evidence from the transcript.
- Use the following HTML table structure:
  <table style="width: 100%; border-collapse: collapse;">
    <tr style="border: 1px solid #000;">
      <th style="border: 1px solid #000; padding: 8px;">Aspect to Improve</th>
      <th style="border: 1px solid #000; padding: 8px;">Suggestion or Evidence</th>
    </tr>
    <tr style="border: 1px solid #000;">
      <td style="border: 1px solid #000; padding: 8px;">[Improvement Aspect]</td>
      <td style="border: 1px solid #000; padding: 8px;">[Feedback or Evidence]</td>
    </tr>
    <!-- Additional rows as needed -->
  </table>

---

### 4. <h2>Visual Analysis</h2>
Include the following:
- Interview Round Ratings (list each question's rating, e.g., Question 1: 8/10)
- Skill Balance Bar Chart:
  - Technical Skills  — {technical_pct:.1f}%
  - Communication  — {communication_pct:.1f}%
  - Behavioral Fit  — {behavioral_pct:.1f}

Use the provided HTML for the bar chart:
{bar_chart_html}

---

### 5. <h2>Overall Recommendation</h2>
- Clearly state whether the candidate is:
  - ✅ Selected
  - ⏳ On Hold
  - ❌ Rejected
- Explain why using 2-3 crisp bullet points in a <ul> list.

---

## Requirements:
- Return the entire content as pure HTML.
- Do not add external CSS or scripts.
- Ensure tables for 'Key Strengths' and 'Areas for Improvement' strictly follow the provided HTML structure with inline CSS.
- Use <p> tags for text content outside tables.
- Do not use markdown or other formats; output must be valid HTML.
"""
        logger.debug("Sending report generation request to Cohere")

        # Send the report prompt to Cohere
        response = co.generate(
            model="command-r-plus",
            prompt=report_prompt,
            max_tokens=2000,
            temperature=0.5
        )
        
        report_content = response.generations[0].text
        logger.debug("Received report content from Cohere")
        
        # Generate voice feedback
        voice_feedback_prompt = f"""
Extract or create a concise 5-6 line voice feedback summary from this interview report:
{report_content}

The feedback should:
- Be spoken in a natural, conversational tone
- Highlight the key conclusions
- Be encouraging but honest
- Be exactly 5-6 lines long
"""
        logger.debug("Sending voice feedback generation request to Cohere")
        voice_response = co.generate(
            model="command-r-plus",
            prompt=voice_feedback_prompt,
            max_tokens=300,
            temperature=0.5
        )
        
        voice_feedback = voice_response.generations[0].text.strip()
        logger.debug(f"Generated voice feedback: {voice_feedback}")
        
        # Convert voice feedback to audio
        logger.debug("Converting voice feedback to audio")
        voice_audio = text_to_speech(voice_feedback)
        
        return {
            "status": "success",
            "report": report_content,
            "voice_feedback": voice_feedback,
            "voice_audio": voice_audio,
            "status_class": status_class,
            "avg_rating": avg_rating,
            "duration": duration
        }
    
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "report": "<p>Error generating report. Please try again.</p>",
            "voice_feedback": "We encountered an error generating your feedback.",
            "voice_audio": None
        }


def create_text_report_from_interview_data(interview_data):
    candidate = interview_data.get('candidate_name', 'Unknown Candidate')
    role = interview_data.get('role', 'Unknown Role')
    exp_level = interview_data.get('experience_level', 'Unknown')
    years = interview_data.get('years_experience', 0)

    conv_history = interview_data.get("conversation_history", [])

    # We expect pairs: question (bot), answer (user)
    conversation_lines = []
    i = 0
    n = len(conv_history)
    question_counter = 1
    while i < n:
        # Question from bot
        q_item = conv_history[i]
        if q_item.get("speaker", "").lower() == "bot":
            question_text = q_item.get("text", "")
            conversation_lines.append(f"Q{question_counter}: {question_text}")
        else:
            i += 1
            continue

        # Answer from user (should be next)
        if i + 1 < n:
            a_item = conv_history[i + 1]
            if a_item.get("speaker", "").lower() == "user":
                answer_text = a_item.get("text", "")
                conversation_lines.append(f"Response: {answer_text}")

                # Add feedback label if present
                feedback_label = a_item.get("feedback_label")
                if feedback_label:
                    conversation_lines.append(f"  → Feedback: {feedback_label}")

        question_counter += 1
        i += 2  # Move to next Q&A pair

    conversation_text = "\n".join(conversation_lines)
    # Calculate average rating
    ratings = interview_data.get('ratings', [])
    avg_rating = sum(ratings) / len(ratings) if ratings else 0

    # Determine performance level
    if avg_rating >= 8:
        performance = "High"
    elif avg_rating >= 6:
        performance = "Moderate"
    elif avg_rating >= 4:
        performance = "Low"
    else:
        performance = "Poor"

    # Calculate duration
    duration = "N/A"
    if interview_data.get('start_time') and interview_data.get('end_time'):
        duration_seconds = (interview_data['end_time'] - interview_data['start_time']).total_seconds()
        minutes = int(duration_seconds // 60)
        seconds = int(duration_seconds % 60)
        duration = f"{minutes}m {seconds}s"

    report_txt = f"""
Interview Report for {candidate}
Role: {role}
Experience Level: {exp_level}
Years of Experience: {years}

Interview Duration: {duration}
Average Rating: {avg_rating:.1f}/10
Overall Performance: {performance}

Conversation Transcript with Feedback:
{conversation_text}

End of Report
"""
    return report_txt

def save_admin_report_txt(interview_data):
    report_txt = create_text_report_from_interview_data(interview_data)
    
    candidate = interview_data.get("candidate_name", "unknown").replace(" ", "_")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{candidate}interview_report{timestamp}.txt"

    reports_folder = os.path.join(os.getcwd(), "reports")
    if not os.path.exists(reports_folder):
        os.makedirs(reports_folder)

    filepath = os.path.join(reports_folder, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report_txt)

    return filepath, filename
