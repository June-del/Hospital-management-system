from datetime import date, datetime
from typing import Optional, Tuple

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from flask_login import current_user
from sqlalchemy import or_

from models import Doctor, MedicalRecord, Patient, db

emr_bp = Blueprint("emr", __name__, template_folder="../templates/emr")


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _validate_record_data(form_data, record_id: Optional[int] = None) -> Tuple[list[str], Optional[date], Optional[date]]:
    errors = []
    patient_id = form_data.get("patient_id", "").strip()
    doctor_id = form_data.get("doctor_id", "").strip()
    visit_date_raw = form_data.get("visit_date", "").strip()
    chief_complaint = form_data.get("chief_complaint", "").strip()
    follow_up_raw = form_data.get("follow_up_date", "").strip()

    if not patient_id:
        errors.append("Please select a patient.")
    if not doctor_id:
        errors.append("Please select a doctor.")
    if not chief_complaint:
        errors.append("Chief complaint is required.")

    visit_date_value = None
    follow_up_value = None
    if visit_date_raw:
        try:
            visit_date_value = _parse_date(visit_date_raw)
        except ValueError:
            errors.append("Visit date must be in YYYY-MM-DD format.")
    if follow_up_raw:
        try:
            follow_up_value = _parse_date(follow_up_raw)
        except ValueError:
            errors.append("Follow-up date must be in YYYY-MM-DD format.")

    return errors, visit_date_value, follow_up_value


@emr_bp.route("/emr")
@login_required
def emr_index():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "", type=str).strip()
    doctor_id = request.args.get("doctor", "", type=str).strip()
    patient_id = request.args.get("patient", "", type=str).strip()

    query = MedicalRecord.query
    if search:
        search_pattern = f"%{search}%"
        query = query.join(Patient).join(Doctor).filter(
            or_(
                Patient.full_name.like(search_pattern),
                Doctor.first_name.like(search_pattern),
                Doctor.last_name.like(search_pattern),
                MedicalRecord.chief_complaint.like(search_pattern),
                MedicalRecord.diagnosis.like(search_pattern),
            )
        )
    if doctor_id:
        query = query.filter(MedicalRecord.doctor_id == int(doctor_id))
    if patient_id:
        query = query.filter(MedicalRecord.patient_id == int(patient_id))

    pagination = query.order_by(MedicalRecord.visit_date.desc(), MedicalRecord.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template(
        "emr_list.html",
        records=pagination.items,
        pagination=pagination,
        search=search,
        doctor_id=doctor_id,
        patient_id=patient_id,
        doctors=Doctor.query.order_by(Doctor.last_name).all(),
        patients=Patient.query.order_by(Patient.full_name).all(),
        title="Electronic Medical Records",
    )


@emr_bp.route("/emr/create", methods=["GET", "POST"])
@login_required
def create_emr():
    if request.method == "POST":
        errors, visit_date_value, follow_up_value = _validate_record_data(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "emr_form.html",
                record=None,
                patients=Patient.query.order_by(Patient.full_name).all(),
                doctors=Doctor.query.order_by(Doctor.last_name).all(),
                title="Create Medical Record",
            )

        record = MedicalRecord(
            patient_id=int(request.form.get("patient_id")),
            doctor_id=int(request.form.get("doctor_id")),
            visit_date=visit_date_value or date.today(),
            chief_complaint=request.form.get("chief_complaint", "").strip(),
            symptoms=request.form.get("symptoms", "").strip(),
            medical_history=request.form.get("medical_history", "").strip(),
            allergies=request.form.get("allergies", "").strip(),
            physical_examination=request.form.get("physical_examination", "").strip(),
            diagnosis=request.form.get("diagnosis", "").strip(),
            treatment_plan=request.form.get("treatment_plan", "").strip(),
            prescription=request.form.get("prescription", "").strip(),
            lab_tests_requested=request.form.get("lab_tests_requested", "").strip(),
            imaging_requested=request.form.get("imaging_requested", "").strip(),
            follow_up_date=follow_up_value,
            clinical_notes=request.form.get("clinical_notes", "").strip(),
            temperature=request.form.get("temperature", "").strip(),
            blood_pressure=request.form.get("blood_pressure", "").strip(),
            pulse_rate=request.form.get("pulse_rate", "").strip(),
            respiratory_rate=request.form.get("respiratory_rate", "").strip(),
            weight=request.form.get("weight", "").strip(),
            height=request.form.get("height", "").strip(),
            bmi=request.form.get("bmi", "").strip(),
            oxygen_saturation=request.form.get("oxygen_saturation", "").strip(),
        )
        db.session.add(record)
        db.session.commit()
        audit_log = AuditLog(user_id=current_user.id, action="Medical Record Created", entity_type="MedicalRecord", entity_id=record.id, details=f"New EMR for patient '{record.patient.full_name}' by Dr. {record.doctor.last_name}.")
        db.session.add(audit_log)
        flash("Medical record created successfully.", "success")
        return redirect(url_for("emr.emr_index"))

    return render_template(
        "emr_form.html",
        record=None,
        patients=Patient.query.order_by(Patient.full_name).all(),
        doctors=Doctor.query.order_by(Doctor.last_name).all(),
        title="Create Medical Record",
    )


@emr_bp.route("/emr/edit/<int:record_id>", methods=["GET", "POST"])
@login_required
def edit_emr(record_id):
    record = MedicalRecord.query.get_or_404(record_id)
    if request.method == "POST":
        errors, visit_date_value, follow_up_value = _validate_record_data(request.form, record_id)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "emr_form.html",
                record=record,
                patients=Patient.query.order_by(Patient.full_name).all(),
                doctors=Doctor.query.order_by(Doctor.last_name).all(),
                title="Edit Medical Record",
            )

        record.patient_id = int(request.form.get("patient_id"))
        record.doctor_id = int(request.form.get("doctor_id"))
        record.visit_date = visit_date_value or record.visit_date
        record.chief_complaint = request.form.get("chief_complaint", "").strip()
        record.symptoms = request.form.get("symptoms", "").strip()
        record.medical_history = request.form.get("medical_history", "").strip()
        record.allergies = request.form.get("allergies", "").strip()
        record.physical_examination = request.form.get("physical_examination", "").strip()
        record.diagnosis = request.form.get("diagnosis", "").strip()
        record.treatment_plan = request.form.get("treatment_plan", "").strip()
        record.prescription = request.form.get("prescription", "").strip()
        record.lab_tests_requested = request.form.get("lab_tests_requested", "").strip()
        record.imaging_requested = request.form.get("imaging_requested", "").strip()
        record.follow_up_date = follow_up_value
        record.clinical_notes = request.form.get("clinical_notes", "").strip()
        record.temperature = request.form.get("temperature", "").strip()
        record.blood_pressure = request.form.get("blood_pressure", "").strip()
        record.pulse_rate = request.form.get("pulse_rate", "").strip()
        record.respiratory_rate = request.form.get("respiratory_rate", "").strip()
        record.weight = request.form.get("weight", "").strip()
        record.height = request.form.get("height", "").strip()
        record.bmi = request.form.get("bmi", "").strip()
        record.oxygen_saturation = request.form.get("oxygen_saturation", "").strip()
        db.session.commit()
        audit_log = AuditLog(user_id=current_user.id, action="Medical Record Updated", entity_type="MedicalRecord", entity_id=record.id, details=f"EMR for patient '{record.patient.full_name}' updated by Dr. {record.doctor.last_name}.")
        db.session.add(audit_log)
        flash("Medical record updated successfully.", "success")
        return redirect(url_for("emr.emr_index"))

    return render_template(
        "emr_form.html",
        record=record,
        patients=Patient.query.order_by(Patient.full_name).all(),
        doctors=Doctor.query.order_by(Doctor.last_name).all(),
        title="Edit Medical Record",
    )


@emr_bp.route("/emr/<int:record_id>")
@login_required
def view_emr(record_id):
    record = MedicalRecord.query.get_or_404(record_id)
    previous_visits = MedicalRecord.query.filter(
        MedicalRecord.patient_id == record.patient_id,
        MedicalRecord.id != record.id,
    ).order_by(MedicalRecord.visit_date.desc()).all()
    return render_template(
        "emr_detail.html",
        record=record,
        previous_visits=previous_visits,
        title="Medical Record Details",
    )


@emr_bp.route("/emr/print/<int:record_id>")
@login_required
def print_emr(record_id):
    record = MedicalRecord.query.get_or_404(record_id)
    return render_template("emr_print.html", record=record, title="Print Medical Record")


@emr_bp.route("/dashboard/emr")
@login_required
def emr_dashboard():
    today = date.today()
    total_records = MedicalRecord.query.count()
    records_created_today = MedicalRecord.query.filter(MedicalRecord.visit_date == today).count()
    patients_seen_today = MedicalRecord.query.filter(MedicalRecord.visit_date == today).distinct(MedicalRecord.patient_id).count()

    return render_template(
        "emr_dashboard.html",
        total_records=total_records,
        records_created_today=records_created_today,
        patients_seen_today=patients_seen_today,
        title="EMR Dashboard",
    )
