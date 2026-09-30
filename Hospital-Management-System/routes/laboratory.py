from flask import Blueprint, redirect, render_template_string, request, url_for
from flask_login import login_required, current_user

from models import LabTestCatalog, LabTestRequest, LabTestResult, db
from routes.auth import role_required

laboratory_bp = Blueprint("laboratory", __name__, url_prefix="/lab", template_folder="../templates/laboratory")


@laboratory_bp.route("/dashboard")
@login_required
@role_required("Admin", "Doctor", "Laboratory Technician")
def dashboard():
    """Basic laboratory dashboard that matches the app's role navigation."""
    pending = LabTestRequest.query.filter_by(status="Pending").count()
    in_progress = LabTestRequest.query.filter_by(status="In Progress").count()
    completed = LabTestRequest.query.filter_by(status="Completed").count()
    recent = LabTestRequest.query.order_by(LabTestRequest.requested_at.desc()).limit(5).all()
    return render_template_string(
        """
        <h2>Laboratory Dashboard</h2>
        <p>Pending: {{ pending }}</p>
        <p>In Progress: {{ in_progress }}</p>
        <p>Completed: {{ completed }}</p>
        <h3>Recent requests</h3>
        {% if recent %}
          <ul>
          {% for item in recent %}
            <li>{{ item.accession_number }} - {{ item.status }}</li>
          {% endfor %}
          </ul>
        {% else %}
          <p>No laboratory requests yet.</p>
        {% endif %}
        """,
        pending=pending,
        in_progress=in_progress,
        completed=completed,
        recent=recent,
    )


@laboratory_bp.route("/catalog")
@login_required
@role_required("Admin", "Laboratory Technician")
def catalog():
    tests = LabTestCatalog.query.order_by(LabTestCatalog.category, LabTestCatalog.name).all()
    return render_template_string(
        """
        <h2>Laboratory Catalog</h2>
        {% if tests %}
          <ul>
          {% for test in tests %}
            <li>{{ test.name }} ({{ test.category }}) - {{ test.price }}</li>
          {% endfor %}
          </ul>
        {% else %}
          <p>No tests in the catalog yet.</p>
        {% endif %}
        """,
        tests=tests,
    )


@laboratory_bp.route("/requests")
@login_required
@role_required("Admin", "Doctor", "Laboratory Technician")
def requests():
    items = LabTestRequest.query.order_by(LabTestRequest.requested_at.desc()).all()
    return render_template_string(
        """
        <h2>Lab Requests</h2>
        {% if items %}
          <ul>
          {% for item in items %}
            <li>{{ item.accession_number }} - {{ item.status }}</li>
          {% endfor %}
          </ul>
        {% else %}
          <p>No lab requests yet.</p>
        {% endif %}
        """,
        items=items,
    )


@laboratory_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("Admin", "Doctor")
def create_request():
    if request.method == "POST":
        patient_id = request.form.get("patient_id")
        test_ids = request.form.getlist("test_ids")
        if not patient_id or not test_ids:
            return redirect(url_for("laboratory.create_request"))

        req = LabTestRequest(
            patient_id=int(patient_id),
            doctor_id=current_user.doctor.id,
            accession_number=f"LAB-{db.session.query(LabTestRequest).count() + 1:04d}",
            status="Pending",
            notes=request.form.get("notes", "")
        )
        db.session.add(req)
        db.session.flush()
        for test_id in test_ids:
            db.session.add(LabTestResult(request_id=req.id, test_catalog_id=int(test_id), value="", notes=""))
        db.session.commit()
        return redirect(url_for("laboratory.dashboard"))

    return render_template_string("<h2>New Lab Request</h2><p>Lab request form placeholder.</p>")


@laboratory_bp.route("/health")
def health():
    return "OK", 200
