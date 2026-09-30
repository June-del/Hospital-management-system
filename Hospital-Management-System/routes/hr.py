from datetime import date
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required

from models import db, Employee, HRDepartment, User, Leave
from routes.auth import role_required

hr_bp = Blueprint("hr", __name__, url_prefix="/hr", template_folder="../templates/hr")


@hr_bp.route("/")
@login_required
@role_required("Admin", "HR Manager")
def index():
    """Main dashboard for the HR module."""
    stats = {
        "total_employees": User.query.filter(User.role != 'Patient').count(),
        "doctors": User.query.filter_by(role='Doctor').count(),
        "nurses": User.query.filter_by(role='Nurse').count(),
        "pharmacists": User.query.filter_by(role='Pharmacist').count(),
        "lab_staff": User.query.filter_by(role='Laboratory Technician').count(),
        "receptionists": User.query.filter_by(role='Receptionist').count(),
        "staff_on_leave": Leave.query.filter(
            Leave.status == 'Approved',
            Leave.start_date <= date.today(),
            Leave.end_date >= date.today()
        ).count(),
        "attendance_today": 0 # Placeholder for attendance feature
    }
    
    recent_hires = Employee.query.order_by(Employee.employment_date.desc()).limit(5).all()

    return render_template("hr_dashboard.html", title="Human Resources", stats=stats, recent_hires=recent_hires)


@hr_bp.route("/employees")
@login_required
@role_required("Admin", "HR Manager")
def list_employees():
    """List all employees with search and filtering."""
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "", type=str).strip()
    
    query = Employee.query
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Employee.first_name + " " + Employee.last_name).like(search_pattern) |
            Employee.employee_number.like(search_pattern) |
            Employee.email.like(search_pattern)
        )

    pagination = query.order_by(Employee.first_name, Employee.last_name).paginate(page=page, per_page=15, error_out=False)
    return render_template("employees_list.html", title="All Employees", employees=pagination.items, pagination=pagination, search=search)


@hr_bp.route("/departments")
@login_required
@role_required("Admin", "HR Manager")
def list_departments():
    """List all departments."""
    departments = HRDepartment.query.order_by(HRDepartment.name).all()
    return render_template("departments_list.html", title="Departments", departments=departments)