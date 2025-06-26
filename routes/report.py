# routes/report.py

import os
import base64
import logging
import requests
import pdfkit
from flask import Blueprint, session, jsonify, send_from_directory
from datetime import datetime, timezone

from services.report_service import generate_interview_report, save_admin_report_txt
from utils.file_utils import html_to_pdf
from utils.helpers import init_interview_data

logger = logging.getLogger(__name__)
report_bp = Blueprint('report', __name__)
CONVERSATION_FILE = "interview_conversation.txt"
PDF_OUTPUT_DIR = os.path.join(os.getcwd(), "reports")
os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)

@report_bp.route('/generate_report', methods=['GET'])
def generate_report():
    logger.info("Generate report request received")
    interview_data = session.get('interview_data', init_interview_data())

    if not interview_data['interview_started']:
        logger.warning("Attempt to generate report before interview started")
        return jsonify({"status": "error", "message": "Interview not started"}), 400

    if not interview_data['end_time']:
        interview_data['end_time'] = datetime.now(timezone.utc)
        session['interview_data'] = interview_data
        logger.debug("Set end time for interview")

    # ✅ Set additional session details
    interview_data["candidate_name"] = session.get("candidate_name", "Anonymous")
    interview_data["organization_name"] = session.get("organization_name", "N/A")
    interview_data["email"] = session.get("email", "Not Provided")
    interview_data["job_title"] = session.get("job_title", "Unknown")
    interview_data["resume_text"] = session.get("resume_text", "")
    interview_data["jd_text"] = session.get("jd_text", "")

    session['interview_data'] = interview_data

    # ✅ Generate HTML report
    report = generate_interview_report(interview_data)
    logger.info("Interview report generated")

    html_report = report.get("report", "")
    if report["status"] == "error":
        return jsonify(report), 500

    try:
        pdf_binary = html_to_pdf(html_report)
        if not pdf_binary:
            raise Exception("Empty PDF data")
        logger.info("PDF generated successfully")
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        return jsonify({"status": "error", "message": "PDF generation failed"}), 500

    # ✅ Save admin report locally
    admin_filepath, admin_filename = save_admin_report_txt(interview_data)
    logger.info(f"Admin report saved: {admin_filepath}")

    # ✅ Prepare Django payload
    django_payload = {
        "candidate_name": interview_data["candidate_name"],
        "role": interview_data["job_title"],
        "organization_name": interview_data["organization_name"],
        "years_experience": interview_data["years_experience"],
        "start_time": interview_data["start_time"].isoformat(),
        "end_time": interview_data["end_time"].isoformat(),
        "average_rating": report["avg_rating"],
        "status": report["status_class"].capitalize(),
        "report_text": html_report,
        "pdf_file": base64.b64encode(pdf_binary).decode("utf-8")
    }

    # ✅ Send to Django backend
    try:
        django_url = "https://ibot-backend.onrender.com/jobs/store-interview-report/"
        django_response = requests.post(django_url, json=django_payload, headers={"Content-Type": "application/json"})

        if django_response.status_code == 201:
            logger.info("Report successfully sent to Django backend")
        else:
            logger.warning(f"Failed to save report in Django: {django_response.text}")
    except Exception as e:
        logger.error(f"Failed to send data to Django: {e}")

    return jsonify({
        **report,
        "admin_report_filename": admin_filename
    })

@report_bp.route('/download_report/<filename>')
def download_report(filename):
    folder = 'reports'
    return send_from_directory(folder, filename, as_attachment=True)
