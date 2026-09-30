from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from sqlalchemy import or_

from models import db, Building, Floor, Ward, Room, Bed, Admission, Patient, Doctor
from routes.auth import role_required

wards_bp = Blueprint("wards", __name__, url_prefix="/wards", template_folder="../templates/wards")

WARD_TYPES = ["General", "ICU", "Maternity", "Pediatric", "Surgical", "Isolation"]
ROOM_TYPES = ["Private", "Semi-Private", "General"]
BED_STATUSES = ["Available", "Occupied", "Maintenance"]


@wards_bp.route("/")
@login_required
@role_required("Admin", "Nurse")
def index():
    # Dashboard Stats
    stats = {
        "total_wards": Ward.query.count(),
        "total_rooms": Room.query.count(),
        "total_beds": Bed.query.count(),
        "available_beds": Bed.query.filter_by(status="Available").count(),
        "occupied_beds": Bed.query.filter_by(status="Occupied").count(),
        "icu_occupancy": Ward.query.filter_by(ward_type="ICU").first().occupied_beds if Ward.query.filter_by(ward_type="ICU").count() > 0 else 0,
        "isolation_occupancy": Ward.query.filter_by(ward_type="Isolation").first().occupied_beds if Ward.query.filter_by(ward_type="Isolation").count() > 0 else 0,
    }

    wards = Ward.query.order_by(Ward.name).all()
    return render_template("wards_dashboard.html", title="Ward Management", stats=stats, wards=wards)


# --- Ward Management ---
@wards_bp.route("/list")
@login_required
@role_required("Admin")
def list_wards():
    wards = Ward.query.join(Floor).join(Building).order_by(Building.name, Floor.floor_number, Ward.name).all()
    return render_template("wards_list.html", title="All Wards", wards=wards)


@wards_bp.route("/add", methods=["GET", "POST"])
@login_required
@role_required("Admin")
def add_ward():
    if request.method == "POST":
        name = request.form.get("name")
        ward_type = request.form.get("ward_type")
        floor_id = request.form.get("floor_id")

        if not all([name, ward_type, floor_id]):
            flash("All fields are required.", "danger")
        else:
            new_ward = Ward(name=name, ward_type=ward_type, floor_id=int(floor_id))
            db.session.add(new_ward)
            db.session.commit()
            flash("Ward added successfully.", "success")
            return redirect(url_for("wards.index"))

    floors = Floor.query.join(Building).order_by(Building.name, Floor.floor_number).all()
    return render_template("ward_form.html", title="Add Ward", floors=floors, ward_types=WARD_TYPES)


# --- Bed Management ---
@wards_bp.route("/beds")
@login_required
@role_required("Admin", "Nurse")
def list_beds():
    beds = Bed.query.join(Room).join(Ward).order_by(Ward.name, Room.room_number, Bed.bed_number).all()
    return render_template("beds_list.html", title="Bed Management", beds=beds)


# --- Admission, Discharge, Transfer (ADT) ---
@wards_bp.route("/admit", methods=["GET", "POST"])
@login_required
@role_required("Admin", "Receptionist", "Nurse")
def admit_patient():
    if request.method == "POST":
        patient_id = request.form.get("patient_id", type=int)
        bed_id = request.form.get("bed_id", type=int)
        doctor_id = request.form.get("doctor_id", type=int)
        reason = request.form.get("reason")

        if not all([patient_id, bed_id, doctor_id]):
            flash("Patient, Bed, and Admitting Doctor are required.", "danger")
            return redirect(request.url)

        # Validation: Check if patient is already admitted
        active_admission = Admission.query.filter_by(patient_id=patient_id, discharge_date=None).first()
        if active_admission:
            flash("This patient is already admitted to a bed.", "danger")
            return redirect(url_for("wards.index"))

        # Validation: Check if bed is available
        bed = Bed.query.get(bed_id)
        if not bed or bed.status != "Available":
            flash("The selected bed is not available.", "danger")
            return redirect(request.url)

        # Process Admission
        admission = Admission(
            patient_id=patient_id,
            bed_id=bed_id,
            admitting_doctor_id=doctor_id,
            reason=reason
        )
        bed.status = "Occupied"
        db.session.add(admission)
        db.session.commit()

        flash("Patient admitted successfully.", "success")
        return redirect(url_for("wards.view_admission", admission_id=admission.id))

    patients = Patient.query.order_by(Patient.full_name).all()
    available_beds = Bed.query.filter_by(status="Available").join(Room).join(Ward).order_by(Ward.name, Room.room_number, Bed.bed_number).all()
    doctors = Doctor.query.order_by(Doctor.last_name).all()
    return render_template("admission_form.html", title="Admit Patient", patients=patients, beds=available_beds, doctors=doctors)


@wards_bp.route("/admission/<int:admission_id>")
@login_required
@role_required("Admin", "Doctor", "Nurse")
def view_admission(admission_id):
    admission = Admission.query.get_or_404(admission_id)
    return render_template("admission_detail.html", title="Admission Details", admission=admission)


@wards_bp.route("/discharge/<int:admission_id>", methods=["POST"])
@login_required
@role_required("Admin", "Doctor", "Nurse")
def discharge_patient(admission_id):
    admission = Admission.query.get_or_404(admission_id)
    if admission.discharge_date:
        flash("Patient has already been discharged.", "warning")
        return redirect(url_for("wards.view_admission", admission_id=admission.id))

    # Check for outstanding balance before allowing discharge (future enhancement)

    admission.discharge_date = db.func.now()
    admission.bed.status = "Available"
    db.session.commit()

    flash("Patient discharged successfully.", "success")
    return redirect(url_for("wards.index"))


@wards_bp.route("/transfer/<int:admission_id>", methods=["GET", "POST"])
@login_required
@role_required("Admin", "Nurse")
def transfer_patient(admission_id):
    admission = Admission.query.get_or_404(admission_id)
    if admission.discharge_date:
        flash("Cannot transfer a discharged patient.", "danger")
        return redirect(url_for("wards.view_admission", admission_id=admission.id))

    if request.method == "POST":
        new_bed_id = request.form.get("new_bed_id", type=int)
        if not new_bed_id:
            flash("Please select a new bed.", "danger")
            return redirect(request.url)

        new_bed = Bed.query.get(new_bed_id)
        if not new_bed or new_bed.status != "Available":
            flash("The selected new bed is not available.", "danger")
            return redirect(request.url)

        # Free up old bed
        old_bed = admission.bed
        old_bed.status = "Available"

        # Assign new bed
        admission.bed_id = new_bed_id
        new_bed.status = "Occupied"

        db.session.commit()
        flash(f"Patient transferred successfully from Bed {old_bed.bed_number} to Bed {new_bed.bed_number}.", "success")
        return redirect(url_for("wards.view_admission", admission_id=admission.id))

    current_bed = admission.bed
    available_beds = Bed.query.filter(
        Bed.status == "Available",
        Bed.id != current_bed.id
    ).join(Room).join(Ward).order_by(Ward.name, Room.room_number, Bed.bed_number).all()

    return render_template("transfer_form.html", title="Transfer Patient", admission=admission, beds=available_beds)


# --- Reports ---
@wards_bp.route("/reports")
@login_required
@role_required("Admin")
def reports():
    admissions = Admission.query.order_by(Admission.admission_date.desc()).all()
    wards = Ward.query.order_by(Ward.name).all()
    return render_template("reports.html", title="Ward Reports", admissions=admissions, wards=wards)
