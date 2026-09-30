import os
from datetime import datetime
from typing import Optional

from flask import Blueprint, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from models import db, Doctor, User, create_user, get_user_by_username # Doctor.save_photo is now in models.py
from config import BASE_DIR # Keep BASE_DIR for UPLOAD_FOLDER

doctors_bp = Blueprint("doctors", __name__, template_folder="../templates/doctors")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "doctors")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def generate_doctor_id() -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    count = Doctor.query.count() + 1
    return f"D{today}{count:04d}"


def validate_doctor_data(form_data):
    errors = []
    email = form_data.get("email", "").strip() # type: ignore
    phone = form_data.get("phone", "").strip()
    license_number = form_data.get("license_number", "").strip()

    if not form_data.get("first_name", "").strip():
        errors.append("First name is required.")
    if not form_data.get("last_name", "").strip():
        errors.append("Last name is required.")
    if not email:
        errors.append("Email is required.")
    elif "@" not in email or "." not in email:
        errors.append("Please enter a valid email address.")
    if not phone:
        errors.append("Phone number is required.")
    elif len(phone) < 7:
        errors.append("Phone number must be at least 7 characters.")
    if not license_number:
        errors.append("License number is required.")
    
    # Check for existing doctor email or license number (excluding current doctor if editing)
    # This logic needs to be aware if it's an edit or add operation
    # For now, assuming add operation or general check
    if Doctor.query.filter(Doctor.email == email).first(): # type: ignore
        errors.append("A doctor with this email already exists.")
    if Doctor.query.filter(Doctor.license_number == license_number).first(): # type: ignore
        errors.append("A doctor with this license number already exists.")

    if get_user_by_username(email): # type: ignore
        errors.append("A doctor with this license number already exists.")

    return errors


@doctors_bp.route("/doctors")
@login_required
def doctors_index():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "", type=str).strip()
    department = request.args.get("department", "", type=str).strip()
    specialization = request.args.get("specialization", "", type=str).strip()
    availability = request.args.get("availability", "", type=str).strip()

    query = Doctor.query
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Doctor.first_name.like(search_pattern),
                Doctor.last_name.like(search_pattern),
                Doctor.doctor_id.like(search_pattern),
                Doctor.email.like(search_pattern),
                Doctor.specialization.like(search_pattern),
            )
        )
    if department:
        query = query.filter(Doctor.department == department)
    if specialization:
        query = query.filter(Doctor.specialization == specialization)
    if availability:
        query = query.filter(Doctor.status == availability)

    pagination = query.order_by(Doctor.date_joined.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template(
        "doctors.html",
        doctors=pagination.items,
        pagination=pagination,
        search=search,
        department=department,
        specialization=specialization,
        availability=availability,
        title="Doctors",
    )


@doctors_bp.route("/doctors/add", methods=["GET", "POST"])
@login_required
def add_doctor():
    if request.method == "POST":
        errors = validate_doctor_data(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("doctor_form.html", doctor=None, title="Add Doctor")

        # Create a User account for the doctor
        user = create_user(
            username=request.form.get("email", "").strip(),
            password="password", # Default password, should be changed on first login
            role="Doctor",
            full_name=f"{request.form.get('first_name', '').strip()} {request.form.get('last_name', '').strip()}"
        )
        photo_filename = None
        if "photo" in request.files:
            photo_filename = Doctor.save_photo(request.files["photo"])

        doctor = Doctor(
            doctor_id=generate_doctor_id(),
            first_name=request.form.get("first_name", "").strip(),
            last_name=request.form.get("last_name", "").strip(),
            gender=request.form.get("gender", "").strip(),
            date_of_birth=datetime.strptime(request.form.get("date_of_birth", ""), "%Y-%m-%d").date(),
            national_id=request.form.get("national_id", "").strip(),
            phone=request.form.get("phone", "").strip(),
            email=request.form.get("email", "").strip(),
            address=request.form.get("address", "").strip(),
            specialization=request.form.get("specialization", "").strip(),
            department=request.form.get("department", "").strip(),
            qualification=request.form.get("qualification", "").strip(),
            years_of_experience=int(request.form.get("years_of_experience", 0)),
            license_number=request.form.get("license_number", "").strip(),
            consultation_fee=request.form.get("consultation_fee", 0),
            working_days=request.form.get("working_days", "").strip(),
            working_hours=request.form.get("working_hours", "").strip(),
            status=request.form.get("status", "Available").strip(),
            user_id=user.id, # Link to the newly created user
            profile_photo=photo_filename,
        )
        db.session.add(doctor)
        db.session.commit()
        flash("Doctor added successfully.", "success")
        return redirect(url_for("doctors.doctors_index"))

    return render_template("doctor_form.html", doctor=None, title="Add Doctor")


@doctors_bp.route("/doctors/edit/<int:doctor_id>", methods=["GET", "POST"])
@login_required
def edit_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    if request.method == "POST":
        errors = validate_doctor_data(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("doctor_form.html", doctor=doctor, title="Edit Doctor")

        doctor.first_name = request.form.get("first_name", "").strip()
        doctor.last_name = request.form.get("last_name", "").strip()
        doctor.gender = request.form.get("gender", "").strip()
        doctor.date_of_birth = datetime.strptime(request.form.get("date_of_birth", ""), "%Y-%m-%d").date()
        doctor.national_id = request.form.get("national_id", "").strip()
        doctor.phone = request.form.get("phone", "").strip()
        doctor.email = request.form.get("email", "").strip()
        doctor.address = request.form.get("address", "").strip()
        doctor.specialization = request.form.get("specialization", "").strip()
        doctor.department = request.form.get("department", "").strip()
        doctor.qualification = request.form.get("qualification", "").strip()
        doctor.years_of_experience = int(request.form.get("years_of_experience", 0))
        doctor.license_number = request.form.get("license_number", "").strip()
        doctor.consultation_fee = request.form.get("consultation_fee", 0)
        doctor.working_days = request.form.get("working_days", "").strip()
        doctor.working_hours = request.form.get("working_hours", "").strip()
        doctor.status = request.form.get("status", "Available").strip()

        if "photo" in request.files and request.files["photo"].filename:
            doctor.profile_photo = Doctor.save_photo(request.files["photo"])

        db.session.commit()
        flash("Doctor updated successfully.", "success")
        return redirect(url_for("doctors.doctors_index"))

    return render_template("doctor_form.html", doctor=doctor, title="Edit Doctor")


@doctors_bp.route("/doctors/delete/<int:doctor_id>", methods=["POST"])
@login_required
def delete_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    db.session.delete(doctor)
    db.session.commit()
    flash("Doctor deleted successfully.", "success")
    return redirect(url_for("doctors.doctors_index"))


@doctors_bp.route("/doctors/profile/<int:doctor_id>")
@login_required
def doctor_profile(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    return render_template("doctor_profile.html", doctor=doctor, title="Doctor Profile")


@doctors_bp.route("/uploads/doctors/<filename>")
def uploaded_doctor_photo(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@doctors_bp.route("/dashboard/doctors")
@login_required
def dashboard_doctors():
    total_doctors = Doctor.query.count()
    available_doctors = Doctor.query.filter(Doctor.status == "Available").count()
    on_leave_doctors = Doctor.query.filter(Doctor.status == "On Leave").count()
    return render_template(
        "dashboard_doctors.html",
        total_doctors=total_doctors,
        available_doctors=available_doctors,
        on_leave_doctors=on_leave_doctors,
        title="Doctor Dashboard",
    )
