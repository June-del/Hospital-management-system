from datetime import date, datetime
from functools import wraps
from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from sqlalchemy import or_

from models import db, Doctor, Patient, Appointment, MedicalRecord
from routes.emr import MedicalRecord # Re-import to ensure MedicalRecord is available
from routes.appointments import Appointment # Re-import to ensure Appointment is available
from routes.radiology import RadiologyRequest, ImagingService # Assuming these exist
# from routes.laboratory import LabTestRequest, LabTestCatalog # Assuming these exist

doctor_portal_bp = Blueprint("doctor_portal", __name__, url_prefix="/doctor", template_folder="../templates/doctor_portal")


def doctor_required(view):
    """Decorator to ensure the logged-in user is a doctor."""
    @wraps(view)
    @login_required
    def wrapped_view(*args, **kwargs):
        if current_user.role != "Doctor":
            flash("This area is for doctors only.", "danger")
            return redirect(url_for("auth.dashboard"))
        if not current_user.doctor:
            flash("Your doctor profile is not fully set up. Please contact administration.", "danger")
            return redirect(url_for("auth.logout"))
        return view(*args, **kwargs)
    return wrapped_view


@doctor_portal_bp.route("/dashboard")
@doctor_required
def dashboard():
    """Doctor's main dashboard."""
    doctor_id = current_user.doctor.id
    today = date.today()

    # Today's Patients (based on appointments)
    today_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == today,
        Appointment.status.in_(["Pending", "Confirmed", "In Progress"])
    ).order_by(Appointment.appointment_time).all()

    # Upcoming Appointments (next 7 days)
    upcoming_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date > today,
        Appointment.appointment_date <= today + datetime.timedelta(days=7),
        Appointment.status.in_(["Pending", "Confirmed"])
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).limit(5).all()

    # Pending Lab Results (for patients seen by this doctor)
    # This requires LabTestRequest and LabTestResult models to be implemented
    pending_lab_results = [] # Placeholder
    # if 'LabTestRequest' in globals(): # Check if Lab module is integrated
    #     pending_lab_results = LabTestRequest.query.join(Patient).filter(
    #         LabTestRequest.doctor_id == doctor_id,
    #         LabTestRequest.status.in_(['Processing', 'Sample Collected'])
    #     ).order_by(LabTestRequest.request_date.desc()).limit(5).all()

    # Pending Imaging Reports (for patients seen by this doctor)
    # This requires RadiologyRequest and RadiologyReport models to be implemented
    pending_imaging_reports = [] # Placeholder
    if 'RadiologyRequest' in globals(): # Check if Radiology module is integrated
        pending_imaging_reports = RadiologyRequest.query.join(Patient).filter(
            RadiologyRequest.doctor_id == doctor_id,
            RadiologyRequest.status.in_(['Scheduled', 'In Progress', 'Awaiting Report'])
        ).order_by(RadiologyRequest.requested_date.desc()).limit(5).all()

    return render_template(
        "doctor_dashboard.html",
        title="Doctor Portal Dashboard",
        today_appointments=today_appointments,
        upcoming_appointments=upcoming_appointments,
        pending_lab_results=pending_lab_results,
        pending_imaging_reports=pending_imaging_reports
    )


@doctor_portal_bp.route("/patients")
@doctor_required
def patient_search():
    """Allows doctors to search for patients assigned to them."""
    doctor_id = current_user.doctor.id
    search_term = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)

    # Filter patients by those who have appointments with this doctor
    # This is a simplified approach; a more robust solution might involve a direct patient-doctor assignment table
    query = Patient.query.join(Appointment).filter(Appointment.doctor_id == doctor_id)

    if search_term:
        search_pattern = f"%{search_term}%"
        query = query.filter(
            or_(
                Patient.full_name.like(search_pattern),
                Patient.patient_id.like(search_pattern),
                Patient.email.like(search_pattern),
                Patient.phone.like(search_pattern)
            )
        )
    
    # Ensure distinct patients are returned
    pagination = query.distinct().order_by(Patient.full_name).paginate(page=page, per_page=10, error_out=False)

    return render_template("patient_search.html", title="My Patients", patients=pagination.items, pagination=pagination, search_term=search_term)


@doctor_portal_bp.route("/patient/<int:patient_id>/history")
@doctor_required
def view_patient_history(patient_id):
    """View comprehensive medical history for a specific patient."""
    doctor_id = current_user.doctor.id
    patient = Patient.query.get_or_404(patient_id)

    # Verify that the patient is assigned to the current doctor (e.g., has had an appointment)
    if not Appointment.query.filter_by(patient_id=patient_id, doctor_id=doctor_id).first():
        flash("You do not have access to this patient's records.", "danger")
        return redirect(url_for("doctor_portal.dashboard"))

    medical_records = MedicalRecord.query.filter_by(patient_id=patient_id).order_by(MedicalRecord.visit_date.desc()).all()
    appointments = Appointment.query.filter_by(patient_id=patient_id, doctor_id=doctor_id).order_by(Appointment.appointment_date.desc()).all()
    
    # Placeholder for Lab and Radiology results
    lab_results = []
    radiology_reports = []
    # if 'LabTestRequest' in globals():
    #     lab_results = LabTestRequest.query.filter_by(patient_id=patient_id, doctor_id=doctor_id, status='Completed').order_by(LabTestRequest.request_date.desc()).all()
    if 'RadiologyRequest' in globals():
        radiology_reports = RadiologyRequest.query.filter_by(patient_id=patient_id, doctor_id=doctor_id, status='Completed').order_by(RadiologyRequest.requested_date.desc()).all()

    return render_template(
        "patient_history.html",
        title=f"Patient History: {patient.full_name}",
        patient=patient,
        medical_records=medical_records,
        appointments=appointments,
        lab_results=lab_results,
        radiology_reports=radiology_reports
    )


@doctor_portal_bp.route("/patient/<int:patient_id>/create_medical_record", methods=["GET", "POST"])
@doctor_required
def create_medical_record(patient_id):
    """Create a new medical record for a patient."""
    doctor_id = current_user.doctor.id
    patient = Patient.query.get_or_404(patient_id)

    # Verify doctor-patient relationship
    if not Appointment.query.filter_by(patient_id=patient_id, doctor_id=doctor_id).first():
        flash("You do not have access to create records for this patient.", "danger")
        return redirect(url_for("doctor_portal.dashboard"))

    # Reuse the EMR form, pre-filling doctor and patient
    # This will require modifications to emr_form.html to handle pre-filled values
    # and potentially to emr.py's create_emr to accept doctor_id from current_user
    return redirect(url_for("emr.create_emr", patient_id=patient.id, doctor_id=current_user.doctor.id))


@doctor_portal_bp.route("/patient/<int:patient_id>/request_radiology", methods=["GET", "POST"])
@doctor_required
def request_radiology(patient_id):
    """Request radiology tests for a patient."""
    doctor_id = current_user.doctor.id
    patient = Patient.query.get_or_404(patient_id)

    if not Appointment.query.filter_by(patient_id=patient_id, doctor_id=doctor_id).first():
        flash("You do not have access to request tests for this patient.", "danger")
        return redirect(url_for("doctor_portal.dashboard"))
    
    # Reuse the radiology request form, pre-filling patient and doctor
    # This will require modifications to radiology/request_form.html and radiology.py's create_request
    return redirect(url_for("radiology.create_request", patient_id=patient.id, doctor_id=current_user.doctor.id))


# Placeholder for other features
@doctor_portal_bp.route("/reports/patients_seen_today")
@doctor_required
def patients_seen_today_report():
    doctor_id = current_user.doctor.id
    today = date.today()
    patients_seen = MedicalRecord.query.filter_by(doctor_id=doctor_id, visit_date=today).distinct(MedicalRecord.patient_id).all()
    return render_template("reports/patients_seen_today.html", title="Patients Seen Today", patients=patients_seen, today=today)


@doctor_portal_bp.route("/complete_consultation/<int:appointment_id>", methods=["POST"])
@doctor_required
def complete_consultation(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.doctor_id != current_user.doctor.id:
        flash("You are not authorized to complete this appointment.", "danger")
        return redirect(url_for("doctor_portal.dashboard"))
    
    appointment.status = "Completed"
    db.session.commit()
    flash(f"Consultation for {appointment.patient.full_name} completed.", "success")
    return redirect(url_for("doctor_portal.dashboard"))