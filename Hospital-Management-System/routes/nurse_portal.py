import os
from datetime import date, datetime, timedelta
from functools import wraps
from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from config import BASE_DIR
from models import db, Nurse, Patient, Appointment, Admission, VitalSign, MedicationAdministration, NursingNote, Bed, Ward, Room
from routes.wards import BED_STATUSES # Reusing constants from wards module

nurse_portal_bp = Blueprint("nurse_portal", __name__, url_prefix="/nurse", template_folder="../templates/nurse_portal")

UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "nurses")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def nurse_required(view):
    """Decorator to ensure the logged-in user is a nurse."""
    @wraps(view)
    @login_required
    def wrapped_view(*args, **kwargs):
        if current_user.role != "Nurse":
            flash("This area is for nurses only.", "danger")
            return redirect(url_for("auth.dashboard"))
        if not current_user.nurse:
            flash("Your nurse profile is not fully set up. Please contact administration.", "danger")
            return redirect(url_for("auth.logout"))
        return view(*args, **kwargs)
    return wrapped_view


def generate_nurse_id() -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    count = Nurse.query.count() + 1
    return f"N{today}{count:04d}"


@nurse_portal_bp.route("/dashboard")
@nurse_required
def dashboard():
    """Nurse's main dashboard."""
    nurse_id = current_user.nurse.id
    today = date.today()

    # Assigned Patients (e.g., patients in wards where this nurse is on duty, or patients they've recently interacted with)
    # For simplicity, let's assume assigned patients are those currently admitted to a ward this nurse is associated with
    # or patients for whom this nurse has recorded vitals/meds today.
    # A more robust system would have a nurse-ward assignment or nurse-patient assignment.
    # For now, let's get patients admitted today or with recent activity by this nurse.
    assigned_patients_query = Patient.query.join(Admission).filter(
        Admission.discharge_date == None, # Currently admitted
        # Further filter by ward/department if nurse has a specific ward assignment
        # For now, we'll show all admitted patients for demonstration
    ).distinct()
    assigned_patients = assigned_patients_query.all()

    # Today's Admissions (for wards this nurse might be working in)
    today_admissions = Admission.query.filter(
        db.func.date(Admission.admission_date) == today
    ).order_by(Admission.admission_date.desc()).all()

    # Today's Discharges (for wards this nurse might be working in)
    today_discharges = Admission.query.filter(
        db.func.date(Admission.discharge_date) == today
    ).order_by(Admission.discharge_date.desc()).all()

    # Today's Tasks (e.g., patients needing vitals, meds) - simplified for now
    # This would typically come from a care plan or scheduled tasks
    today_tasks = [] # Placeholder

    return render_template(
        "nurse_dashboard.html",
        title="Nurse Portal Dashboard",
        assigned_patients=assigned_patients,
        today_admissions=today_admissions,
        today_discharges=today_discharges,
        today_tasks=today_tasks
    )


@nurse_portal_bp.route("/patients")
@nurse_required
def assigned_patients():
    """List all patients currently admitted to the hospital (simplified for now)."""
    # In a real system, this would be filtered by patients assigned to the current nurse's ward/shift
    page = request.args.get("page", 1, type=int)
    search_term = request.args.get("search", "").strip()

    query = Patient.query.join(Admission).filter(Admission.discharge_date == None)

    if search_term:
        search_pattern = f"%{search_term}%"
        query = query.filter(
            or_(
                Patient.full_name.like(search_pattern),
                Patient.patient_id.like(search_pattern)
            )
        )
    
    pagination = query.distinct().order_by(Patient.full_name).paginate(page=page, per_page=10, error_out=False)

    return render_template("assigned_patients.html", title="Assigned Patients", patients=pagination.items, pagination=pagination, search_term=search_term)


@nurse_portal_bp.route("/patient/<int:patient_id>/record_vitals", methods=["GET", "POST"])
@nurse_required
def record_vitals(patient_id):
    """Record vital signs for a specific patient."""
    patient = Patient.query.get_or_404(patient_id)
    nurse = current_user.nurse

    if request.method == "POST":
        temperature = request.form.get("temperature", type=float)
        pulse_rate = request.form.get("pulse_rate", type=int)
        bp_systolic = request.form.get("bp_systolic", type=int)
        bp_diastolic = request.form.get("bp_diastolic", type=int)
        respiratory_rate = request.form.get("respiratory_rate", type=int)
        oxygen_saturation = request.form.get("oxygen_saturation", type=int)
        notes = request.form.get("notes", "").strip()

        new_vitals = VitalSign(
            patient_id=patient.id,
            nurse_id=nurse.id,
            temperature=temperature,
            pulse_rate=pulse_rate,
            blood_pressure_systolic=bp_systolic,
            blood_pressure_diastolic=bp_diastolic,
            respiratory_rate=respiratory_rate,
            oxygen_saturation=oxygen_saturation,
            notes=notes
        )
        db.session.add(new_vitals)
        db.session.commit()
        flash("Vital signs recorded successfully.", "success")
        return redirect(url_for("nurse_portal.view_patient_details", patient_id=patient.id))

    return render_template("record_vitals.html", title=f"Record Vitals for {patient.full_name}", patient=patient)


@nurse_portal_bp.route("/patient/<int:patient_id>/administer_medication", methods=["GET", "POST"])
@nurse_required
def administer_medication(patient_id):
    """Record medication administration for a specific patient."""
    patient = Patient.query.get_or_404(patient_id)
    nurse = current_user.nurse

    if request.method == "POST":
        medication_name = request.form.get("medication_name", "").strip()
        dosage = request.form.get("dosage", "").strip()
        route = request.form.get("route", "").strip()
        notes = request.form.get("notes", "").strip()

        if not all([medication_name, dosage, route]):
            flash("Medication name, dosage, and route are required.", "danger")
            return redirect(request.url)

        new_med_admin = MedicationAdministration(
            patient_id=patient.id,
            nurse_id=nurse.id,
            medication_name=medication_name,
            dosage=dosage,
            route=route,
            notes=notes
        )
        db.session.add(new_med_admin)
        db.session.commit()
        flash("Medication administration recorded successfully.", "success")
        return redirect(url_for("nurse_portal.view_patient_details", patient_id=patient.id))

    return render_template("medication_admin.html", title=f"Administer Medication to {patient.full_name}", patient=patient)


@nurse_portal_bp.route("/patient/<int:patient_id>/add_nursing_note", methods=["GET", "POST"])
@nurse_required
def add_nursing_note(patient_id):
    """Add a nursing note for a specific patient."""
    patient = Patient.query.get_or_404(patient_id)
    nurse = current_user.nurse

    if request.method == "POST":
        note_text = request.form.get("note_text", "").strip()

        if not note_text:
            flash("Nursing note cannot be empty.", "danger")
            return redirect(request.url)

        new_note = NursingNote(
            patient_id=patient.id,
            nurse_id=nurse.id,
            note_text=note_text
        )
        db.session.add(new_note)
        db.session.commit()
        flash("Nursing note added successfully.", "success")
        return redirect(url_for("nurse_portal.view_patient_details", patient_id=patient.id))

    return render_template("nursing_notes.html", title=f"Add Nursing Note for {patient.full_name}", patient=patient)


@nurse_portal_bp.route("/patient/<int:patient_id>/details")
@nurse_required
def view_patient_details(patient_id):
    """View a patient's details, vitals, meds, and notes."""
    patient = Patient.query.get_or_404(patient_id)
    
    # Fetch recent vitals, meds, notes for this patient
    recent_vitals = VitalSign.query.filter_by(patient_id=patient.id).order_by(VitalSign.timestamp.desc()).limit(5).all()
    recent_meds = MedicationAdministration.query.filter_by(patient_id=patient.id).order_by(MedicationAdministration.administration_datetime.desc()).limit(5).all()
    recent_notes = NursingNote.query.filter_by(patient_id=patient.id).order_by(NursingNote.timestamp.desc()).limit(5).all()

    return render_template(
        "patient_details.html",
        title=f"Patient Details: {patient.full_name}",
        patient=patient,
        recent_vitals=recent_vitals,
        recent_meds=recent_meds,
        recent_notes=recent_notes
    )


@nurse_portal_bp.route("/shift_handover", methods=["GET", "POST"])
@nurse_required
def shift_handover():
    """Manage shift handovers."""
    # This would involve selecting patients, summarizing their status, and assigning to another nurse
    flash("Shift Handover feature is under development.", "info")
    return render_template("shift_handover.html", title="Shift Handover")


@nurse_portal_bp.route("/bed_assignment/<int:patient_id>", methods=["GET", "POST"])
@nurse_required
def bed_assignment(patient_id):
    """Assign a bed to a patient (or transfer)."""
    patient = Patient.query.get_or_404(patient_id)
    current_admission = Admission.query.filter_by(patient_id=patient.id, discharge_date=None).first()

    if request.method == "POST":
        new_bed_id = request.form.get("new_bed_id", type=int)
        if not new_bed_id:
            flash("Please select a new bed.", "danger")
            return redirect(request.url)

        new_bed = Bed.query.get(new_bed_id)
        if not new_bed or new_bed.status != "Available":
            flash("The selected new bed is not available.", "danger")
            return redirect(request.url)

        if current_admission:
            # Transfer patient
            old_bed = current_admission.bed
            old_bed.status = "Available"
            current_admission.bed_id = new_bed_id
            new_bed.status = "Occupied"
            db.session.commit()
            flash(f"Patient {patient.full_name} transferred successfully to Bed {new_bed.bed_number}.", "success")
        else:
            # Admit patient to this bed (simplified, full admission process is in wards.py)
            flash("Full admission process should be used for new admissions.", "warning")
            return redirect(url_for("wards.admit_patient", patient_id=patient.id, bed_id=new_bed.id))

        return redirect(url_for("nurse_portal.view_patient_details", patient_id=patient.id))

    available_beds = Bed.query.filter(Bed.status == "Available").join(Room).join(Ward).order_by(Ward.name, Room.room_number, Bed.bed_number).all()
    
    return render_template("bed_assignment.html", title=f"Assign Bed to {patient.full_name}", patient=patient, current_admission=current_admission, available_beds=available_beds)


@nurse_portal_bp.route("/patient/<int:patient_id>/transfer_out", methods=["GET", "POST"])
@nurse_required
def patient_transfer_out(patient_id):
    """Initiate transfer of a patient to another ward/facility."""
    patient = Patient.query.get_or_404(patient_id)
    current_admission = Admission.query.filter_by(patient_id=patient.id, discharge_date=None).first()

    if not current_admission:
        flash("Patient is not currently admitted.", "danger")
        return redirect(url_for("nurse_portal.view_patient_details", patient_id=patient.id))

    if request.method == "POST":
        # Logic for transferring out (e.g., to another ward, or discharge)
        # This would typically involve updating the admission record, freeing the bed, etc.
        # For simplicity, we'll just mark the current admission as discharged.
        current_admission.discharge_date = datetime.utcnow()
        current_admission.bed.status = "Available"
        db.session.commit()
        flash(f"Patient {patient.full_name} has been transferred/discharged.", "success")
        return redirect(url_for("nurse_portal.dashboard"))

    return render_template("patient_transfer_out.html", title=f"Transfer/Discharge {patient.full_name}", patient=patient, admission=current_admission)