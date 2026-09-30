from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from sqlalchemy import or_

from models import db, AuditLog, SecurityEvent, User
from routes.auth import role_required

security_audit_bp = Blueprint("security_audit", __name__, url_prefix="/security_audit", template_folder="../templates/security_audit")


@security_audit_bp.route("/dashboard")
@login_required
@role_required("Admin")
def dashboard():
    """Security & Audit Dashboard."""
    
    recent_audit_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()
    recent_security_events = SecurityEvent.query.order_by(SecurityEvent.timestamp.desc()).limit(10).all()
    
    locked_accounts = User.query.filter_by(is_locked=True).count()
    failed_logins_24h = SecurityEvent.query.filter(
        SecurityEvent.event_type == "Failed Login",
        SecurityEvent.timestamp >= datetime.utcnow() - timedelta(hours=24)
    ).count()

    stats = {
        "locked_accounts": locked_accounts,
        "failed_logins_24h": failed_logins_24h,
        "total_audit_logs": AuditLog.query.count(),
        "total_security_events": SecurityEvent.query.count()
    }

    return render_template(
        "security_audit_dashboard.html",
        title="Security & Audit Dashboard",
        stats=stats,
        recent_audit_logs=recent_audit_logs,
        recent_security_events=recent_security_events
    )


@security_audit_bp.route("/audit_logs")
@login_required
@role_required("Admin")
def list_audit_logs():
    """List all audit logs with search and filtering."""
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()
    user_id = request.args.get("user_id", type=int)
    action = request.args.get("action", "").strip()

    query = AuditLog.query.join(User, isouter=True)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                User.username.like(search_pattern),
                AuditLog.action.like(search_pattern),
                AuditLog.entity_type.like(search_pattern),
                AuditLog.details.like(search_pattern)
            )
        )
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)

    pagination = query.order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=20, error_out=False)
    
    users = User.query.order_by(User.username).all()
    actions = db.session.query(AuditLog.action).distinct().all()

    return render_template(
        "audit_logs.html",
        title="Audit Logs",
        logs=pagination.items,
        pagination=pagination,
        search=search,
        user_id=user_id,
        action=action,
        users=users,
        actions=[a[0] for a in actions]
    )


@security_audit_bp.route("/security_events")
@login_required
@role_required("Admin")
def list_security_events():
    """List all security events with search and filtering."""
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()
    event_type = request.args.get("event_type", "").strip()

    query = SecurityEvent.query.join(User, isouter=True)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                User.username.like(search_pattern),
                SecurityEvent.event_type.like(search_pattern),
                SecurityEvent.ip_address.like(search_pattern),
                SecurityEvent.details.like(search_pattern)
            )
        )
    if event_type:
        query = query.filter(SecurityEvent.event_type == event_type)

    pagination = query.order_by(SecurityEvent.timestamp.desc()).paginate(page=page, per_page=20, error_out=False)
    
    event_types = db.session.query(SecurityEvent.event_type).distinct().all()

    return render_template(
        "security_events.html",
        title="Security Events",
        events=pagination.items,
        pagination=pagination,
        search=search,
        event_type=event_type,
        event_types=[e[0] for e in event_types]
    )


@security_audit_bp.route("/accounts/unlock/<int:user_id>", methods=["POST"])
@login_required
@role_required("Admin")
def unlock_account(user_id):
    user = User.query.get_or_404(user_id)
    user.is_locked = False
    user.failed_login_attempts = 0
    db.session.commit()
    flash(f"Account for '{user.username}' unlocked successfully.", "success")
    # Log this action
    audit_log = AuditLog(user_id=current_user.id, action="Account Unlocked", entity_type="User", entity_id=user.id, details=f"Admin '{current_user.username}' unlocked account for '{user.username}'.")
    db.session.add(audit_log)
    db.session.commit()
    return redirect(url_for("security_audit.dashboard"))

# Placeholder for other reports and settings
@security_audit_bp.route("/reports/user_activity")
@login_required
@role_required("Admin")
def user_activity_report():
    flash("User Activity Report functionality is under development.", "info")
    return render_template("reports_placeholder.html", title="User Activity Report")

@security_audit_bp.route("/settings/password_policy", methods=["GET", "POST"])
@login_required
@role_required("Admin")
def set_password_policy():
    flash("Password Policy settings are under development.", "info")
    return render_template("settings_placeholder.html", title="Password Policy")