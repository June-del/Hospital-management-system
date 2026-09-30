import logging
import os
from datetime import datetime
from typing import Optional

from flask import Blueprint, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, DateField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional as WtformsOptional
from sqlalchemy import or_

from config import BASE_DIR
from models import db, AuditLog, Patient
from utils import generate_id, save_uploaded_file

patients_bp = Blueprint("patients", __name__, template_folder="../templates/patients")
logger = logging.getLogger(__name__)

UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "patients")
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

class PatientForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=120)])
    gender = SelectField('Gender', choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], validators=[DataRequired()])
    date_of_birth = DateField('Date of Birth', format='%Y-%m-%d', validators=[DataRequired()])
    blood_group = SelectField('Blood Group', choices=[('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'), ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-')], validators=[DataRequired()])
    phone = StringField('Phone', validators=[DataRequired(), Length(min=7, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    address = TextAreaField('Address', validators=[DataRequired()])
    emergency_contact = StringField('Emergency Contact', validators=[DataRequired(), Length(max=120)])
    next_of_kin = StringField('Next of Kin', validators=[DataRequired(), Length(max=120)])
    insurance_provider = StringField('Insurance Provider', validators=[DataRequired(), Length(max=120)])
    allergies = TextAreaField('Allergies', validators=[WtformsOptional()])
    medical_conditions = TextAreaField('Medical Conditions', validators=[WtformsOptional()])
    photo = FileField('Profile Photo', validators=[FileAllowed(ALLOWED_EXTENSIONS, 'Images only!')])
    submit = SubmitField('Save Patient')



@patients_bp.route("/patients")
@login_required
def patients_index():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "", type=str).strip()
    query = Patient.query

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Patient.full_name.like(search_pattern),
                Patient.patient_id.like(search_pattern),
                Patient.email.like(search_pattern),
                Patient.phone.like(search_pattern),
            )
        )

    ordered_query = query.order_by(Patient.registration_date.desc())
    pagination = ordered_query.paginate(page=page, per_page=10, error_out=False)
    return render_template(
        "patients.html",
        patients=pagination.items,
        pagination=pagination,
        search=search,
        title="Patients",
    )


@patients_bp.route("/patients/add", methods=["GET", "POST"])
@login_required
def add_patient():
    form = PatientForm()
    if form.validate_on_submit():
        if Patient.query.filter_by(email=form.email.data).first():
            form.email.errors.append("This email address is already registered.")
        if Patient.query.filter_by(phone=form.phone.data).first():
            form.phone.errors.append("This phone number is already registered.")

        if form.email.errors or form.phone.errors:
            return render_template("patient_form.html", form=form, title="Add Patient")

        photo_filename = None
        if form.photo.data:
            photo_filename = save_uploaded_file(form.photo.data, UPLOAD_FOLDER, ALLOWED_EXTENSIONS)

        patient = Patient(patient_id=generate_id("P", Patient))
        form.populate_obj(patient)
        patient.photo_filename = photo_filename

        try:
            db.session.add(patient)
            db.session.flush()
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.exception("PATIENT SAVE FAILED: %s", exc)
            flash("Unable to save patient. The database transaction failed.", "danger")
            return render_template("patient_form.html", form=form, title="Add Patient")

        flash("Patient added successfully.", "success")
        audit_log = AuditLog(user_id=current_user.id, action="Patient Created", entity_type="Patient", entity_id=patient.id, details=f"Patient '{patient.full_name}' added.")
        db.session.add(audit_log)
        db.session.commit()
        return redirect(url_for("patients.patients_index"))

    return render_template("patient_form.html", form=form, title="Add Patient")


@patients_bp.route("/patients/edit/<int:patient_id>", methods=["GET", "POST"])
@login_required
def edit_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    form = PatientForm(obj=patient) # Pre-populate form with patient data
    if form.validate_on_submit():
        # Check for uniqueness, excluding the current patient
        if Patient.query.filter(Patient.email == form.email.data, Patient.id != patient_id).first():
            form.email.errors.append("This email address is already registered to another patient.")
        if Patient.query.filter(Patient.phone == form.phone.data, Patient.id != patient_id).first():
            form.phone.errors.append("This phone number is already registered to another patient.")
        
        if form.email.errors or form.phone.errors:
            return render_template("patient_form.html", form=form, title="Edit Patient")

        form.populate_obj(patient)

        if form.photo.data:
            patient.photo_filename = save_uploaded_file(form.photo.data, UPLOAD_FOLDER, ALLOWED_EXTENSIONS)

        db.session.commit()
        flash("Patient updated successfully.", "success")
        # Add audit log for edit
        audit_log = AuditLog(user_id=current_user.id, action="Patient Updated", entity_type="Patient", entity_id=patient.id, details=f"Patient '{patient.full_name}' details updated.")
        db.session.add(audit_log)
        db.session.commit()
        return redirect(url_for("patients.patients_index"))

    return render_template("patient_form.html", form=form, title="Edit Patient")


@patients_bp.route("/patients/delete/<int:patient_id>", methods=["POST"])
@login_required
def delete_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    db.session.delete(patient)
    audit_log = AuditLog(user_id=current_user.id, action="Patient Deleted", entity_type="Patient", entity_id=patient.id, details=f"Patient '{patient.full_name}' deleted.")
    db.session.add(audit_log)
    db.session.commit()
    flash("Patient deleted successfully.", "success")
    return redirect(url_for("patients.patients_index"))


@patients_bp.route("/patients/profile/<int:patient_id>")
@login_required
def patient_profile(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    return render_template("patient_profile.html", patient=patient, title="Patient Profile")


@patients_bp.route("/uploads/patients/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@patients_bp.route("/dashboard/patients")
@login_required
def dashboard_patients():
    total_patients = Patient.query.count()
    recent_patients = Patient.query.order_by(Patient.registration_date.desc()).limit(5).all()
    return render_template(
        "dashboard_patients.html",
        total_patients=total_patients,
        recent_patients=recent_patients,
        title="Patient Dashboard",
    )
