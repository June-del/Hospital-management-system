from datetime import date, datetime, timedelta
from functools import wraps
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user, AnonymousUserMixin
from sqlalchemy import func, case
from werkzeug.utils import secure_filename
from models import (
    db, authenticate_user, create_user, get_user_by_username,
    Patient, Doctor, Appointment, Payment, AuditLog, SecurityEvent
)

auth_bp = Blueprint("auth", __name__, template_folder="../templates")

RATE_LIMIT_STORAGE = {}

def limit_requests(limit=10, per=60):
    """A simple rate limiting decorator."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Use IP address for anonymous users, user ID for authenticated users
            key = request.remote_addr
            if current_user and not isinstance(current_user, AnonymousUserMixin):
                key = f"{current_user.id}-{request.remote_addr}"

            now = datetime.utcnow()
            requests = RATE_LIMIT_STORAGE.get(key, [])
            # Filter out requests older than the 'per' window
            requests = [req_time for req_time in requests if (now - req_time).total_seconds() < per]
            if len(requests) >= limit:
                return "Too many requests. Please try again later.", 429
            requests.append(now)
            RATE_LIMIT_STORAGE[key] = requests
            return f(*args, **kwargs)
        return wrapped
    return decorator


def role_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("auth.login"))

            if current_user.role not in allowed_roles:
                flash("You do not have permission to view this page.", "danger")
                return redirect(url_for("auth.dashboard"))
            return view(*args, **kwargs)

        return wrapped

    return decorator

PANEL_CONFIG = {
    "admin": {"title": "Admin Panel", "description": "Administrative tools and system controls.", "roles": ["Admin"]},
    "doctor": {"title": "Doctor Panel", "description": "Patient care and clinical management workspace.", "roles": ["Admin", "Doctor"]},
    "nurse": {"title": "Nurse Panel", "description": "Care coordination and ward activity overview.", "roles": ["Admin", "Nurse"]},
    "receptionist": {"title": "Receptionist Panel", "description": "Appointments and patient front-desk operations.", "roles": ["Admin", "Receptionist"]},
    "pharmacist": {"title": "Pharmacist Panel", "description": "Medication dispensing and inventory control.", "roles": ["Admin", "Pharmacist"]},
    "lab": {"title": "Laboratory Panel", "description": "Test requests, results, and specimen tracking.", "roles": ["Admin", "Laboratory Technician"]},
    "cashier": {"title": "Cashier Panel", "description": "Payments, billing, and daily settlement tasks.", "roles": ["Admin", "Cashier"]},
}

def get_panel_name_from_role(role: str) -> str:
    role_map = {
        "Doctor": "doctor", "Nurse": "nurse", "Receptionist": "receptionist",
        "Pharmacist": "pharmacist", "Laboratory Technician": "lab", "Cashier": "cashier",
        "Admin": "admin"
    }
    return role_map.get(role, "dashboard")

def get_accessible_pages(role: str):
    pages = {
        "Admin": [
            ("auth.panel", {"panel_name": "admin"}, "Admin Panel"),
            ("auth.panel", {"panel_name": "doctor"}, "Doctor Panel"),
            ("auth.panel", {"panel_name": "nurse"}, "Nurse Panel"),
            ("auth.panel", {"panel_name": "receptionist"}, "Receptionist Panel"),
            ("executive.dashboard", "Executive Dashboard"),
            ("procurement.dashboard", "Procurement"),
            ("hr.index", "Human Resources"),
            ("wards.index", "Ward Management"),
            ("appointments.appointments_index", "Appointments"),
            ("laboratory.dashboard", "Laboratory"),
            ("emr.emr_index", "Electronic Medical Records"),
            ("billing.billing_index", "Billing & Payments"),
            ("auth.panel", {"panel_name": "cashier"}, "Cashier Panel"),
            ("emergency.dashboard", "Emergency"),
            ("security_audit.dashboard", "Security & Audit"),
            ("system_admin.dashboard", "System Admin"),
            ("reporting.dashboard", "Reporting Center"),
            ("ai_assistant.index", "AI Assistant"),
        ],
        "Doctor": [("doctor_portal.dashboard", "Doctor Portal"), ("appointments.appointments_index", "Appointments"), ("emr.emr_index", "Electronic Medical Records")],
        "Pharmacist": [("auth.panel", {"panel_name": "pharmacist"}, "Pharmacist Panel")],
        "Nurse": [("nurse_portal.dashboard", "Nurse Portal"), ("wards.index", "Ward Management"), ("appointments.appointments_index", "Appointments"), ("ai_assistant.index", "AI Assistant"), ("emergency.dashboard", "Emergency")],
        "Receptionist": [("auth.panel", {"panel_name": "receptionist"}, "Receptionist Panel"), ("appointments.appointments_index", "Appointments")],
        "Laboratory Technician": [("auth.panel", {"panel_name": "lab"}, "Laboratory Panel")],
        "Cashier": [("auth.panel", {"panel_name": "cashier"}, "Cashier Panel")],
    }
    return pages.get(role, [])


@auth_bp.route("/login", methods=["GET", "POST"])
@limit_requests(limit=10, per=60) # Limit to 10 login attempts per minute per IP/user
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = authenticate_user(username, password)
        ip_address = request.remote_addr

        if user:
            if user.is_locked:
                flash("Your account is locked. Please contact an administrator.", "danger")
                # Log security event for attempted login on locked account
                security_event = SecurityEvent(user_id=user.id, event_type="Attempted Login (Locked)", ip_address=ip_address, details=f"User '{username}' attempted to log in while account was locked.")
                db.session.add(security_event)
                db.session.commit()
                return render_template("login.html")

            # Reset failed login attempts on successful login
            if user.failed_login_attempts > 0:
                user.failed_login_attempts = 0
                db.session.commit()

            login_user(user, remember=True)
            flash(f"Welcome back, {user.username}!", "success")
            
            # Log successful login
            audit_log = AuditLog(user_id=user.id, action="Login", entity_type="User", entity_id=user.id, details=f"User '{username}' logged in successfully.")
            db.session.add(audit_log)
            db.session.commit()

            # Password expiration check (placeholder)
            if (datetime.utcnow() - user.last_password_change).days > 90: # Example: 90 days
                flash("Your password has expired. Please change it.", "warning")
                # return redirect(url_for("auth.change_password")) # Implement this route

            if user.role == "Patient":
                return redirect(url_for("portal.dashboard"))
            elif user.role == "Nurse":
                return redirect(url_for("nurse_portal.dashboard"))
            elif user.role == "Doctor":
                return redirect(url_for("doctor_portal.dashboard"))
            elif user.role == "Admin":
                return redirect(url_for("auth.dashboard")) # Admin dashboard
            else:
                return redirect(url_for("auth.dashboard")) # Default dashboard for other roles

        # Handle failed login attempts
        user_attempt = get_user_by_username(username)
        if user_attempt:
            user_attempt.failed_login_attempts += 1
            if user_attempt.failed_login_attempts >= 5: # Lock after 5 failed attempts
                user_attempt.is_locked = True
                security_event = SecurityEvent(user_id=user_attempt.id, event_type="Account Locked", ip_address=ip_address, details=f"Account for '{username}' locked after 5 failed login attempts.")
                db.session.add(security_event)
                flash("Too many failed login attempts. Your account has been locked.", "danger")
            else:
                security_event = SecurityEvent(user_id=user_attempt.id, event_type="Failed Login", ip_address=ip_address, details=f"Failed login attempt for '{username}'. Attempts: {user_attempt.failed_login_attempts}")
                db.session.add(security_event)
            db.session.commit()
        else:
            # Log failed login for unknown user
            security_event = SecurityEvent(user_id=None, event_type="Failed Login (Unknown User)", ip_address=ip_address, details=f"Failed login attempt for unknown username '{username}'.")
            db.session.add(security_event)
            db.session.commit()

        flash("Invalid username or password.", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    logout_user()
    # Log logout
    if current_user.is_authenticated: # Check if user was authenticated before logging out
        audit_log = AuditLog(user_id=current_user.id, action="Logout", entity_type="User", entity_id=current_user.id, details=f"User '{current_user.username}' logged out.")
        db.session.add(audit_log)
        db.session.commit()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("auth.dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not all([full_name, email, password, confirm_password]):
            flash("All fields are required.", "danger")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")

        if get_user_by_username(email):
            flash("An account with this email already exists.", "danger")
            return render_template("register.html")

        # Create User and Patient records
        try:
            user = create_user(username=email, password=password, role="Patient", full_name=full_name)
            patient = Patient(
                user_id=user.id,
                patient_id=Patient.generate_patient_id(),
                full_name=full_name,
                email=email,
            )
            db.session.add(patient)
            db.session.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred during registration: {e}", "danger")

    return render_template("register.html")


@auth_bp.route("/dashboard")
@login_required
def dashboard():
    today = date.today()
    
    # --- Statistics ---
    total_patients = Patient.query.count()
    total_doctors = Doctor.query.count()
    today_appointments_count = Appointment.query.filter(Appointment.appointment_date == today).count()
    today_revenue = db.session.query(func.sum(Payment.amount_paid)).filter(Payment.payment_date == today).scalar() or Decimal('0.00')

    # --- Chart Data ---
    # 1. Monthly Patient Registrations (Bar Chart)
    six_months_ago = today.replace(day=1) - timedelta(days=150) # Approx 5 months before current month
    six_months_ago = six_months_ago.replace(day=1)

    monthly_regs = db.session.query(
        func.strftime('%Y-%m', Patient.registration_date),
        func.count(Patient.id)
    ).filter(
        Patient.registration_date >= six_months_ago
    ).group_by(
        func.strftime('%Y-%m', Patient.registration_date)
    ).order_by(
        func.strftime('%Y-%m', Patient.registration_date)
    ).all()
    
    chart_labels = [datetime.strptime(r[0], '%Y-%m').strftime('%b %Y') for r in monthly_regs]
    chart_data = [r[1] for r in monthly_regs]

    # 2. Appointment Status Distribution (Doughnut Chart)
    # Optimized from 4 queries to 1
    status_counts = db.session.query(
        Appointment.status, func.count(Appointment.id)
    ).group_by(Appointment.status).all()
    appointment_summary = {status: count for status, count in status_counts}
    appointment_summary.setdefault("Pending", 0)
    appointment_summary.setdefault("Completed", 0)
    appointment_summary.setdefault("Cancelled", 0)
    appointment_summary.setdefault("Confirmed", 0)

    # --- Recent Activity & Today's Appointments ---
    # Eager load patient and doctor to prevent N+1 queries in template
    from sqlalchemy.orm import joinedload
    today_appointments = Appointment.query.options(joinedload(Appointment.patient), joinedload(Appointment.doctor)).filter(Appointment.appointment_date == today).order_by(Appointment.appointment_time.asc()).limit(5).all()
    recent_patients = Patient.query.order_by(Patient.registration_date.desc()).limit(3).all()
    
    return render_template(
        "dashboard.html",
        user=current_user,
        page_title="Dashboard",
        page_description="Manage your daily tasks from a single place.",
        allowed_pages=get_accessible_pages(current_user.role),
        stats={'patients': total_patients, 'doctors': total_doctors, 'today_appts': today_appointments_count, 'today_revenue': today_revenue},
        monthly_registration_chart={'labels': chart_labels, 'data': chart_data},
        appointment_summary=appointment_summary, # Now uses the optimized dictionary
        today_appointments=today_appointments,
        recent_patients=recent_patients,
    )


@auth_bp.route("/panel/<panel_name>")
@login_required
def panel(panel_name: str):
    config = PANEL_CONFIG.get(panel_name)
    if not config:
        flash("The requested panel does not exist.", "danger")
        return redirect(url_for("auth.dashboard"))

    if current_user.role not in config["roles"]:
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("auth.dashboard"))

    return render_template(
        "dashboard.html",
        user=current_user,
        page_title=config["title"],
        page_description=config["description"],
        allowed_pages=get_accessible_pages(current_user.role),
    )
