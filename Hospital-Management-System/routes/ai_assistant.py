from flask import Blueprint, render_template, request, jsonify, flash
from flask_login import login_required

from models import db, Patient, MedicalRecord
from routes.auth import role_required

ai_assistant_bp = Blueprint("ai_assistant", __name__, url_prefix="/ai", template_folder="../templates/ai")


def _get_ai_suggestion(task: str, context: dict) -> str:
    """
    Simulates a response from an AI model based on the task and context.
    In a real application, this would make an API call to a service like Gemini.
    """
    patient_id = context.get("patient_id")
    patient = Patient.query.get(patient_id) if patient_id else None
    patient_name = patient.full_name if patient else "the patient"

    # Safety Disclaimer
    disclaimer = (
        "<hr><small class='text-muted'><em><strong>Disclaimer:</strong> This content is AI-generated for decision support only. "
        "It is not a diagnosis. All information must be verified by a qualified healthcare professional before being used for clinical care.</em></small>"
    )

    # Pre-defined responses based on the task
    responses = {
        "summarize_history": (
            f"<h5>Summary for {patient_name}</h5>"
            f"<p>The patient has a history of hypertension and was last seen for a routine follow-up. "
            f"Key diagnoses include Essential Hypertension (I10) and Type 2 Diabetes Mellitus without complications (E11.9). "
            f"No known drug allergies. The last recorded BP was 135/85 mmHg.</p>"
        ),
        "generate_discharge_summary": (
            f"<h5>Draft Discharge Summary for {patient_name}</h5>"
            f"<p><strong>Admission Date:</strong> [Date]<br>"
            f"<strong>Discharge Date:</strong> [Date]<br>"
            f"<strong>Principal Diagnosis:</strong> Community-Acquired Pneumonia (J18.9)<br>"
            f"<strong>Hospital Course:</strong> The patient was admitted with fever and cough. Treated with intravenous antibiotics and responded well. "
            f"Condition stable upon discharge.<br>"
            f"<strong>Discharge Medications:</strong> Amoxicillin 500mg three times daily for 5 days.<br>"
            f"<strong>Follow-up:</strong> Please see your primary care physician in 7 days.</p>"
        ),
        "explain_lab_results": (
            f"<h5>Simplified Explanation of Lab Results</h5>"
            f"<p>The patient's recent blood test shows slightly elevated white blood cell count, which can be a sign that the body is fighting an infection. "
            f"Hemoglobin and platelet levels are within the normal range, indicating no signs of anemia or bleeding issues. "
            f"Kidney and liver function tests appear normal.</p>"
        ),
        "explain_radiology_report": (
            f"<h5>Simplified Explanation of Radiology Report</h5>"
            f"<p>The chest X-ray shows an opacity in the lower lobe of the right lung, which is consistent with pneumonia. "
            f"There are no signs of fluid around the lungs (pleural effusion) or a collapsed lung (pneumothorax). The heart size is normal.</p>"
        ),
        "draft_referral_letter": (
            f"<h5>Draft Referral Letter</h5>"
            f"<p>Dear [Cardiologist Name],</p>"
            f"<p>I am referring {patient_name} for further evaluation of persistent chest pain. "
            f"The patient is a [Age]-year-old with a history of [History, e.g., hypertension]. "
            f"An initial ECG showed non-specific changes. Your expert opinion would be greatly appreciated.</p>"
            f"<p>Sincerely,<br>[Your Name]</p>"
        ),
        "generate_medical_certificate": (
            f"<h5>Draft Medical Certificate</h5>"
            f"<p>This is to certify that <strong>{patient_name}</strong> was seen and treated at our facility from [Start Date] to [End Date]. "
            f"The patient was diagnosed with [Diagnosis] and is advised to rest for a period of [Number] days. "
            f"The patient is fit to resume duties on [Resume Date].</p>"
        ),
        "draft_clinical_notes": (
            f"<h5>Draft Clinical Notes (SOAP Format)</h5>"
            f"<p><strong>S:</strong> Patient complains of a headache and dizziness for the past 2 days.<br>"
            f"<strong>O:</strong> BP 150/90 mmHg, Pulse 88 bpm. No focal neurological deficits observed.<br>"
            f"<strong>A:</strong> Uncontrolled Hypertension.<br>"
            f"<strong>P:</strong> Adjust medication to include Amlodipine 5mg daily. Advise on low-salt diet. Follow up in 1 week for BP check.</p>"
        )
    }

    return responses.get(task, "I am sorry, I cannot help with that task.") + disclaimer


@ai_assistant_bp.route("/")
@login_required
@role_required("Admin", "Doctor", "Nurse")
def index():
    """A standalone page for the AI assistant (optional)."""
    return render_template("ai_assistant.html", title="AI Clinical Assistant")


@ai_assistant_bp.route("/ask", methods=["POST"])
@login_required
@role_required("Admin", "Doctor", "Nurse")
def ask_ai():
    """Endpoint to handle AI requests from the chat interface."""
    data = request.get_json()
    if not data or "task" not in data:
        return jsonify({"error": "Invalid request. 'task' is required."}), 400

    task = data.get("task")
    context = {
        "patient_id": data.get("patient_id"),
        "record_id": data.get("record_id")
    }

    # Simulate getting a response from an AI model
    suggestion = _get_ai_suggestion(task, context)

    return jsonify({"response": suggestion})