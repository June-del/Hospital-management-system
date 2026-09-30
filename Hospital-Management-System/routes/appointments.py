import os
from datetime import date, datetime, time
from typing import List, Optional, Tuple

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import or_

from config import BASE_DIR
from models import Appointment, Doctor, Patient, db

appointments_bp = Blueprint("appointments", __name__, template_folder="../templates/appointments")

TIME_SLOTS = [
    "08:00",
    "08:30",
    "09:00",
    "09:30",
    "10:00",
    "10:30",
    "11:00",
    "11:30",
    "12:00",
    "12:30",
    "13:00",
    "13:30",
    "14:00",
    "14:30",
    "15:00",
    "15:30",
    "16:00",
    "16:30",
    "17:00",
]

VISIT_TYPES = ["Consultation", "Follow-up", "Emergency"]
STATUSES = ["Pending", "Confirmed", "In Progress", "Completed", "Cancelled"]


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_time(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def _time_slots_for_doctor(doctor_id: Optional[int], appointment_date: Optional[date], appointment_id: Optional[int] = None) -> List[str]:
    active_slots = []
    if doctor_id and appointment_date:
        query = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == appointment_date,
            Appointment.status != "Cancelled",
        )
        if appointment_id is not None:
            query = query.filter(Appointment.id != appointment_id)
        taken_slots = {item.appointment_time for item in query.all()}
        active_slots = [slot for slot in TIME_SLOTS if slot not in taken_slots]
    else:
        active_slots = list(TIME_SLOTS)

    return active_slots


def _generate_queue_number(doctor_id: int, appointment_date: date, current_appointment: Optional[Appointment] = None) -> int:
    if current_appointment and current_appointment.queue_number:
        return current_appointment.queue_number

    existing = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == appointment_date,
        Appointment.status != "Cancelled",
    )
    if current_appointment is not None:
        existing = existing.filter(Appointment.id != current_appointment.id)
    return existing.count() + 1


def _validate_appointment_data(form_data, appointment_id: Optional[int] = None) -> Tuple[List[str], Optional[date], Optional[time]]:
    errors = []
    patient_id = form_data.get("patient_id", "").strip()
    doctor_id = form_data.get("doctor_id", "").strip()
    department = form_data.get("department", "").strip()
    appointment_date_raw = form_data.get("appointment_date", "").strip()
    appointment_time_raw = form_data.get("appointment_time", "").strip()
    symptoms = form_data.get("symptoms", "").strip()
    visit_type = form_data.get("visit_type", "Consultation").strip()
    status = form_data.get("status", "Pending").strip()

    if not patient_id:
        errors.append("Please select a patient.")
    if not doctor_id:
        errors.append("Please select a doctor.")
    if not department:
        errors.append("Department is required.")
    if not appointment_date_raw:
        errors.append("Appointment date is required.")
    if not appointment_time_raw:
        errors.append("Appointment time is required.")
    if not symptoms:
        errors.append("Symptoms or reason for visit is required.")
    if visit_type not in VISIT_TYPES:
        errors.append("Please choose a valid visit type.")
    if status not in STATUSES:
        errors.append("Please choose a valid appointment status.")

    appointment_date_value = None
    appointment_time_value = None
    if appointment_date_raw:
        try:
            appointment_date_value = _parse_date(appointment_date_raw)
        except ValueError:
            errors.append("Appointment date must be in YYYY-MM-DD format.")

    if appointment_time_raw:
        try:
            appointment_time_value = _parse_time(appointment_time_raw)
        except ValueError:
            errors.append("Appointment time must be in HH:MM format.")

    if appointment_date_value and appointment_time_value:
        today = date.today()
        if appointment_date_value < today:
            errors.append("Appointments cannot be booked for a past date.")
        elif appointment_date_value == today:
            current_time = datetime.now().time()
            if appointment_time_value <= current_time:
                errors.append("Appointments cannot be booked for a past time on today's date.")

    if patient_id and doctor_id and appointment_date_value and appointment_time_value:
        existing = Appointment.query.filter(
            Appointment.doctor_id == int(doctor_id),
            Appointment.appointment_date == appointment_date_value,
            Appointment.appointment_time == appointment_time_raw,
            Appointment.status != "Cancelled",
        )
        if appointment_id is not None:
            existing = existing.filter(Appointment.id != appointment_id)
        if existing.first():
            errors.append("This doctor is already booked at the selected time slot.")

    return errors, appointment_date_value, appointment_time_value


@appointments_bp.route("/appointments")
@login_required
def appointments_index():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "", type=str).strip()
    appointment_date = request.args.get("date", "", type=str).strip()
    doctor_id = request.args.get("doctor", "", type=str).strip()
    department = request.args.get("department", "", type=str).strip()
    status = request.args.get("status", "", type=str).strip()

    query = Appointment.query
    if search:
        search_pattern = f"%{search}%"
        query = query.join(Patient).join(Doctor).filter(
            or_(
                Patient.full_name.like(search_pattern),
                Doctor.first_name.like(search_pattern),
                Doctor.last_name.like(search_pattern),
                Appointment.department.like(search_pattern),
                Appointment.symptoms.like(search_pattern),
            )
        )
    if appointment_date:
        query = query.filter(Appointment.appointment_date == appointment_date)
    if doctor_id:
        query = query.filter(Appointment.doctor_id == int(doctor_id))
    if department:
        query = query.filter(Appointment.department == department)
    if status:
        query = query.filter(Appointment.status == status)

    pagination = query.order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc()).paginate(page=page, per_page=10, error_out=False)
    return render_template(
        "appointments.html",
        appointments=pagination.items,
        pagination=pagination,
        search=search,
        appointment_date=appointment_date,
        doctor_id=doctor_id,
        department=department,
        status=status,
        doctors=Doctor.query.order_by(Doctor.last_name).all(),
        departments=[row[0] for row in db.session.query(Appointment.department).distinct().order_by(Appointment.department).all()],
        statuses=STATUSES,
        title="Appointments",
    )


@appointments_bp.route("/appointments/book", methods=["GET", "POST"])
@login_required
def book_appointment():
    if request.method == "POST":
        errors, appointment_date_value, appointment_time_value = _validate_appointment_data(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "appointment_form.html",
                appointment=None,
                patients=Patient.query.order_by(Patient.full_name).all(),
                doctors=Doctor.query.order_by(Doctor.last_name).all(),
                visit_types=VISIT_TYPES,
                statuses=STATUSES,
                available_slots=_time_slots_for_doctor(request.form.get("doctor_id", type=int), appointment_date_value),
                title="Book Appointment",
            )

        doctor = Doctor.query.get_or_404(int(request.form.get("doctor_id")))
        department = request.form.get("department", "").strip() or doctor.department
        appointment = Appointment(
            patient_id=int(request.form.get("patient_id")),
            doctor_id=doctor.id,
            department=department,
            appointment_date=appointment_date_value,
            appointment_time=request.form.get("appointment_time", "").strip(),
            queue_number=_generate_queue_number(doctor.id, appointment_date_value),
            visit_type=request.form.get("visit_type", "Consultation").strip(),
            status=request.form.get("status", "Pending").strip() or "Pending",
            symptoms=request.form.get("symptoms", "").strip(),
            notes=request.form.get("notes", "").strip(),
        )
        db.session.add(appointment)
        db.session.commit()
        flash("Appointment booked successfully.", "success")
        return redirect(url_for("appointments.appointments_index"))

    return render_template(
        "appointment_form.html",
        appointment=None,
        patients=Patient.query.order_by(Patient.full_name).all(),
        doctors=Doctor.query.order_by(Doctor.last_name).all(),
        visit_types=VISIT_TYPES,
        statuses=STATUSES,
        available_slots=TIME_SLOTS,
        title="Book Appointment",
    )


@appointments_bp.route("/appointments/edit/<int:appointment_id>", methods=["GET", "POST"])
@login_required
def edit_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    if request.method == "POST":
        errors, appointment_date_value, appointment_time_value = _validate_appointment_data(request.form, appointment_id=appointment_id)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "appointment_form.html",
                appointment=appointment,
                patients=Patient.query.order_by(Patient.full_name).all(),
                doctors=Doctor.query.order_by(Doctor.last_name).all(),
                visit_types=VISIT_TYPES,
                statuses=STATUSES,
                available_slots=_time_slots_for_doctor(request.form.get("doctor_id", type=int), appointment_date_value, appointment_id),
                title="Edit Appointment",
            )

        doctor = Doctor.query.get_or_404(int(request.form.get("doctor_id")))
        appointment.patient_id = int(request.form.get("patient_id"))
        appointment.doctor_id = doctor.id
        appointment.department = request.form.get("department", "").strip() or doctor.department
        appointment.appointment_date = appointment_date_value
        appointment.appointment_time = request.form.get("appointment_time", "").strip()
        appointment.queue_number = _generate_queue_number(doctor.id, appointment_date_value, appointment)
        appointment.visit_type = request.form.get("visit_type", "Consultation").strip()
        appointment.status = request.form.get("status", "Pending").strip() or "Pending"
        appointment.symptoms = request.form.get("symptoms", "").strip()
        appointment.notes = request.form.get("notes", "").strip()
        db.session.commit()
        flash("Appointment updated successfully.", "success")
        return redirect(url_for("appointments.appointments_index"))

    return render_template(
        "appointment_form.html",
        appointment=appointment,
        patients=Patient.query.order_by(Patient.full_name).all(),
        doctors=Doctor.query.order_by(Doctor.last_name).all(),
        visit_types=VISIT_TYPES,
        statuses=STATUSES,
        available_slots=_time_slots_for_doctor(appointment.doctor_id, appointment.appointment_date, appointment.id),
        title="Edit Appointment",
    )


@appointments_bp.route("/appointments/cancel/<int:appointment_id>", methods=["POST"])
@login_required
def cancel_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    appointment.status = "Cancelled"
    db.session.commit()
    flash("Appointment cancelled successfully.", "warning")
    return redirect(url_for("appointments.appointments_index"))


@appointments_bp.route("/appointments/complete/<int:appointment_id>", methods=["POST"])
@login_required
def complete_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    appointment.status = "Completed"
    db.session.commit()
    flash("Appointment marked as completed.", "success")
    return redirect(url_for("appointments.appointments_index"))


@appointments_bp.route("/appointments/<int:appointment_id>")
@login_required
def appointment_details(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    return render_template("appointment_details.html", appointment=appointment, title="Appointment Details")


@appointments_bp.route("/appointments/calendar")
@login_required
def appointment_calendar():
    selected_month = request.args.get("month", datetime.now().strftime("%Y-%m"), type=str)
    try:
        selected_date = datetime.strptime(selected_month, "%Y-%m")
    except ValueError:
        selected_date = datetime.now()

    year = selected_date.year
    month = selected_date.month
    prev_month = (month - 2) % 12 + 1
    prev_year = year if month > 1 else year - 1
    next_month = month % 12 + 1
    next_year = year if month < 12 else year + 1
    first_day = datetime(year, month, 1)
    total_days = (first_day.replace(year=year + (month // 12), month=(month % 12) + 1, day=1) - datetime(year, month, 1)).days
    days = [datetime(year, month, day) for day in range(1, total_days + 1)]
    appointments_by_day = {}
    for appointment in Appointment.query.filter(
        Appointment.appointment_date >= date(year, month, 1),
        Appointment.appointment_date <= date(year, month, total_days),
    ).order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc()).all():
        appointments_by_day.setdefault(appointment.appointment_date, []).append(appointment)

    return render_template(
        "calendar.html",
        year=year,
        month=month,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
        days=days,
        appointments_by_day=appointments_by_day,
        selected_month=selected_month,
        title="Appointment Calendar",
    )


@appointments_bp.route("/dashboard/appointments")
@login_required
def appointment_dashboard():
    today = date.today()
    today_appointments = Appointment.query.filter(Appointment.appointment_date == today).order_by(Appointment.appointment_time.asc()).all()
    pending_appointments = Appointment.query.filter(Appointment.status == "Pending").order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc()).all()
    completed_appointments = Appointment.query.filter(Appointment.status == "Completed").order_by(Appointment.appointment_date.desc()).limit(5).all()
    cancelled_appointments = Appointment.query.filter(Appointment.status == "Cancelled").order_by(Appointment.appointment_date.desc()).limit(5).all()
    upcoming_appointments = Appointment.query.filter(Appointment.appointment_date >= today, Appointment.status != "Cancelled").order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc()).limit(8).all()

    return render_template(
        "dashboard.html",
        today_appointments=today_appointments,
        pending_appointments=pending_appointments,
        completed_appointments=completed_appointments,
        cancelled_appointments=cancelled_appointments,
        upcoming_appointments=upcoming_appointments,
        summary={
            "today": len(today_appointments),
            "pending": len(pending_appointments),
            "completed": len(completed_appointments),
            "cancelled": len(cancelled_appointments),
            "upcoming": len(upcoming_appointments),
        },
        title="Appointment Dashboard",
    )
