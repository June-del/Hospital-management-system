from datetime import date
from functools import wraps
from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required, current_user

from models import db
from routes.appointments import Appointment
from routes.billing import Invoice
from routes.emr import MedicalRecord

portal_bp = Blueprint("portal", __name__, url_prefix="/portal", template_folder="../templates/portal")


def patient_required(view):
    """Decorator to ensure the logged-in user is a patient."""
    @wraps(view)
    @login_required
    def wrapped_view(*args, **kwargs):
        if current_user.role != "Patient":
            flash("This area is for patients only.", "danger")
            return redirect(url_for("auth.dashboard"))
        if not current_user.patient:
            flash("Your patient profile is not fully set up. Please contact support.", "danger")
            return redirect(url_for("auth.logout"))
        return view(*args, **kwargs)
    return wrapped_view


@portal_bp.route("/dashboard")
@patient_required
def dashboard():
    """The main dashboard for the patient portal."""
    patient_id = current_user.patient.id
    today = date.today()

    # Fetch data specific to the logged-in patient
    upcoming_appointments = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.appointment_date >= today,
        Appointment.status.in_(["Pending", "Confirmed"])
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).limit(5).all()

    recent_records = MedicalRecord.query.filter_by(patient_id=patient_id).order_by(MedicalRecord.visit_date.desc()).limit(3).all()

    outstanding_invoices = Invoice.query.filter(
        Invoice.patient_id == patient_id,
        Invoice.status.in_(["Pending", "Partially Paid"])
    ).order_by(Invoice.invoice_date.desc()).limit(5).all()

    # In a real app, you'd also fetch lab results, prescriptions, etc.
    
    return render_template(
        "portal_dashboard.html",
        title="My Dashboard",
        upcoming_appointments=upcoming_appointments,
        recent_records=recent_records,
        outstanding_invoices=outstanding_invoices
    )
