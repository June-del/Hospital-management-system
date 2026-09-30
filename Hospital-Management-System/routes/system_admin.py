import os
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from sqlalchemy import func

from models import db, SystemSetting, User
from routes.auth import role_required
from config import ROLES

system_admin_bp = Blueprint("system_admin", __name__, url_prefix="/admin", template_folder="../templates/system_admin")


def _get_settings():
    """Helper function to retrieve all system settings as a dictionary."""
    settings_query = SystemSetting.query.all()
    settings = {s.key: s.value for s in settings_query}
    return settings


@system_admin_bp.route("/dashboard")
@login_required
@role_required("Admin")
def dashboard():
    """System Administration Dashboard."""
    
    # System Health Placeholders
    db_size = "N/A"
    try:
        # This is a SQLite-specific way to get DB size.
        # For other DBs like PostgreSQL or MySQL, a different query would be needed.
        db_path = db.get_engine().url.database
        if db_path and os.path.exists(db_path):
            size_in_bytes = os.path.getsize(db_path)
            db_size = f"{size_in_bytes / (1024*1024):.2f} MB"
    except Exception:
        pass # Fails gracefully if DB path is not on local filesystem

    system_health = {
        "database_status": "Online",
        "database_size": db_size,
        "server_load": "Normal", # Placeholder
        "last_backup": "Never" # Placeholder
    }

    return render_template("admin_dashboard.html", title="System Administration", system_health=system_health)


@system_admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@role_required("Admin")
def settings():
    """Manage all system settings."""
    if request.method == "POST":
        # Get all keys from the form
        form_keys = request.form.keys()
        for key in form_keys:
            setting = SystemSetting.query.get(key)
            if setting:
                setting.value = request.form[key]
            else:
                # Create new setting if it doesn't exist
                new_setting = SystemSetting(key=key, value=request.form[key])
                db.session.add(new_setting)
        
        # Handle file upload for logo
        if 'hospital_logo' in request.files:
            logo_file = request.files['hospital_logo']
            if logo_file.filename != '':
                # In a real app, save this file securely and store the path
                # For now, we just store the filename as a placeholder
                logo_setting = SystemSetting.query.get('hospital_logo')
                if logo_setting:
                    logo_setting.value = logo_file.filename
                else:
                    db.session.add(SystemSetting(key='hospital_logo', value=logo_file.filename))

        db.session.commit()
        flash("Settings updated successfully.", "success")
        return redirect(url_for("system_admin.settings"))

    settings = _get_settings()
    return render_template("settings.html", title="System Settings", settings=settings)


@system_admin_bp.route("/roles")
@login_required
@role_required("Admin")
def list_roles():
    """List user roles and count users in each role."""
    # Optimized from N+1 query in template to a single query here.
    role_counts_query = db.session.query(User.role, func.count(User.id)).group_by(User.role).all()
    role_counts = {role: count for role, count in role_counts_query}
    
    all_roles = {role: role_counts.get(role, 0) for role in ROLES}
    return render_template("roles.html", title="User Roles & Permissions", roles_with_counts=all_roles)


@system_admin_bp.route("/maintenance/backup", methods=["POST"])
@login_required
@role_required("Admin")
def backup_system():
    """Placeholder for system backup functionality."""
    # This is a complex feature that depends on the deployment environment.
    # It would involve running `sqlite3 .backup` or `pg_dump`.
    flash("System backup functionality is under development.", "info")
    return redirect(url_for("system_admin.dashboard"))


@system_admin_bp.route("/maintenance/restore", methods=["POST"])
@login_required
@role_required("Admin")
def restore_system():
    """Placeholder for system restore functionality."""
    flash("System restore is a critical operation and is under development.", "warning")
    return redirect(url_for("system_admin.dashboard"))


@system_admin_bp.route("/maintenance/db")
@login_required
@role_required("Admin")
def database_maintenance():
    """Placeholder for database maintenance tasks."""
    flash("Database maintenance tasks (e.g., VACUUM) are under development.", "info")
    return redirect(url_for("system_admin.dashboard"))