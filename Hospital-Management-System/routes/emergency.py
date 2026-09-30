from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from models import db, Ambulance, EmergencyCall, PatientTransfer, Employee, Patient, HRDepartment
from routes.auth import role_required

emergency_bp = Blueprint("emergency", __name__, url_prefix="/emergency", template_folder="../templates/emergency")


@emergency_bp.route("/dashboard")
@login_required
@role_required("Admin", "Nurse", "Dispatcher") # Assuming a 'Dispatcher' role might be added
def dashboard():
    """Dashboard for the Emergency Management module."""
    
    active_emergencies = EmergencyCall.query.filter(
        EmergencyCall.status.in_(["Pending", "Dispatched", "Arrived"])
    ).options(
        joinedload(EmergencyCall.ambulance) # Eager load ambulance to prevent N+1 queries
    ).order_by(EmergencyCall.created_at.desc()).all()

    ambulances_available = Ambulance.query.filter_by(status="Available").count()
    ambulances_on_duty = Ambulance.query.filter_by(status="On Duty").count()

    # Calculate average response time (dispatch to arrival)
    avg_response_time_query = db.session.query(
        func.avg(func.julianday(EmergencyCall.arrival_time) - func.julianday(EmergencyCall.dispatch_time))
    ).filter(EmergencyCall.arrival_time != None, EmergencyCall.dispatch_time != None).scalar() or 0
    avg_response_minutes = avg_response_time_query * 24 * 60 # Convert days to minutes

    stats = {
        "active_emergencies": len(active_emergencies),
        "ambulances_available": ambulances_available,
        "ambulances_on_duty": ambulances_on_duty,
        "avg_response_time": f"{avg_response_minutes:.2f} mins"
    }

    return render_template("emergency_dashboard.html", title="Emergency Dashboard", stats=stats, active_emergencies=active_emergencies)


# --- Ambulance Management ---

@emergency_bp.route("/ambulances")
@login_required
@role_required("Admin", "Dispatcher")
def list_ambulances():
    ambulances = Ambulance.query.order_by(Ambulance.vehicle_number).all()
    return render_template("ambulances.html", title="Ambulance Fleet", ambulances=ambulances)

@emergency_bp.route("/ambulances/add", methods=["GET", "POST"])
@login_required
@role_required("Admin", "Dispatcher")
def add_ambulance():
    # Assuming 'Driver' is a position in the Employee model
    drivers = Employee.query.filter(Employee.position.ilike('%driver%')).all()
    if request.method == "POST":
        vehicle_number = request.form.get("vehicle_number")
        registration_number = request.form.get("registration_number")
        driver_id = request.form.get("driver_id", type=int)
        capacity = request.form.get("capacity", type=int)
        equipment = request.form.get("equipment")
        status = request.form.get("status")

        if Ambulance.query.filter_by(vehicle_number=vehicle_number).first():
            flash("An ambulance with this vehicle number already exists.", "danger")
            return redirect(request.url)

        new_ambulance = Ambulance(
            vehicle_number=vehicle_number,
            registration_number=registration_number,
            driver_id=driver_id if driver_id else None,
            capacity=capacity,
            equipment=equipment,
            status=status
        )
        db.session.add(new_ambulance)
        db.session.commit()
        flash("Ambulance added successfully.", "success")
        return redirect(url_for("emergency.list_ambulances"))

    return render_template("ambulance_form.html", title="Add Ambulance", drivers=drivers)

@emergency_bp.route("/ambulances/edit/<int:ambulance_id>", methods=["GET", "POST"])
@login_required
@role_required("Admin", "Dispatcher")
def edit_ambulance(ambulance_id):
    ambulance = Ambulance.query.get_or_404(ambulance_id)
    drivers = Employee.query.filter(Employee.position.ilike('%driver%')).all()
    if request.method == "POST":
        ambulance.vehicle_number = request.form.get("vehicle_number")
        ambulance.registration_number = request.form.get("registration_number")
        ambulance.driver_id = request.form.get("driver_id", type=int) or None
        ambulance.capacity = request.form.get("capacity", type=int)
        ambulance.equipment = request.form.get("equipment")
        ambulance.status = request.form.get("status")
        db.session.commit()
        flash("Ambulance details updated successfully.", "success")
        return redirect(url_for("emergency.list_ambulances"))

    return render_template("ambulance_form.html", title="Edit Ambulance", ambulance=ambulance, drivers=drivers)


# --- Emergency Call Management ---

@emergency_bp.route("/calls")
@login_required
@role_required("Admin", "Nurse", "Dispatcher")
def list_emergency_calls():
    """Displays the emergency queue."""
    calls = EmergencyCall.query.order_by(EmergencyCall.created_at.desc()).all()
    return render_template("emergency_calls.html", title="Emergency Call Queue", calls=calls)

@emergency_bp.route("/calls/new", methods=["GET", "POST"])
@login_required
@role_required("Admin", "Nurse", "Dispatcher")
def new_emergency_call():
    if request.method == "POST":
        caller_name = request.form.get("caller_name")
        phone = request.form.get("phone")
        location = request.form.get("location")
        emergency_type = request.form.get("emergency_type")
        priority = request.form.get("priority")

        if not all([caller_name, phone, location, emergency_type, priority]):
            flash("All fields are required.", "danger")
            return redirect(request.url)

        new_call = EmergencyCall(
            caller_name=caller_name,
            phone=phone,
            location=location,
            emergency_type=emergency_type,
            priority=priority,
            status="Pending"
        )
        db.session.add(new_call)
        db.session.commit()
        flash("New emergency call logged successfully.", "success")
        return redirect(url_for("emergency.list_emergency_calls"))

    return render_template("emergency_call_form.html", title="Log New Emergency Call")

@emergency_bp.route("/calls/dispatch/<int:call_id>", methods=["GET", "POST"])
@login_required
@role_required("Admin", "Dispatcher")
def dispatch_ambulance(call_id):
    call = EmergencyCall.query.get_or_404(call_id)
    if call.status != "Pending":
        flash("This call has already been actioned.", "info")
        return redirect(url_for("emergency.list_emergency_calls"))

    available_ambulances = Ambulance.query.filter_by(status="Available").all()

    if request.method == "POST":
        ambulance_id = request.form.get("ambulance_id", type=int)
        if not ambulance_id:
            flash("Please select an ambulance to dispatch.", "danger")
            return redirect(request.url)

        ambulance = Ambulance.query.get(ambulance_id)
        if not ambulance or ambulance.status != "Available":
            flash("The selected ambulance is not available.", "danger")
            return redirect(request.url)

        # Update call status
        call.status = "Dispatched"
        call.ambulance_id = ambulance.id
        call.dispatch_time = datetime.utcnow()

        # Update ambulance status
        ambulance.status = "On Duty"

        db.session.commit()
        flash(f"Ambulance {ambulance.vehicle_number} dispatched successfully.", "success")
        return redirect(url_for("emergency.list_emergency_calls"))

    return render_template("dispatch_form.html", title="Dispatch Ambulance", call=call, ambulances=available_ambulances)


@emergency_bp.route("/calls/update_status/<int:call_id>/<string:new_status>", methods=["POST"])
@login_required
@role_required("Admin", "Dispatcher", "Nurse")
def update_call_status(call_id, new_status):
    call = EmergencyCall.query.get_or_404(call_id)
    valid_statuses = ["Arrived", "Completed", "Cancelled"]
    if new_status not in valid_statuses:
        flash("Invalid status update.", "danger")
        return redirect(url_for("emergency.list_emergency_calls"))

    call.status = new_status
    if new_status == "Arrived":
        call.arrival_time = datetime.utcnow()
    elif new_status == "Completed" or new_status == "Cancelled":
        call.completion_time = datetime.utcnow()
        # Make the ambulance available again
        if call.ambulance:
            call.ambulance.status = "Available"
    
    db.session.commit()
    flash(f"Call status updated to '{new_status}'.", "success")
    return redirect(url_for("emergency.list_emergency_calls"))


# --- Patient Transfer ---

@emergency_bp.route("/transfers")
@login_required
@role_required("Admin", "Nurse", "Dispatcher")
def list_patient_transfers():
    """Displays the history of patient transfers."""
    transfers = PatientTransfer.query.order_by(PatientTransfer.request_time.desc()).all()
    return render_template("patient_transfers.html", title="Patient Transfer History", transfers=transfers)