import logging
import os
from flask import Flask, flash, redirect, request, url_for
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate

from models import SystemSetting, create_default_admin, db, get_user_by_id, init_db
from flask import g

app = Flask(__name__)
app.config.from_object("config")

# --- Production-Ready Initializations ---
# CSRF Protection
csrf = CSRFProtect(app)

# Database and Migrations
db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager(app)
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id: str):
    return get_user_by_id(int(user_id))


@app.before_request
def protect_pages():
    if request.endpoint in {None, "static"}:
        return None

    # Session timeout check (more robust implementation needed for strict enforcement)
    # For now, Flask-Login's PERMANENT_SESSION_LIFETIME combined with login_required is sufficient.
    # A more explicit check would involve storing last activity time in session.

    if request.endpoint in {"auth.login", "auth.logout", "auth.register"}:
        return None

    if current_user.is_authenticated:
        return None

    flash("Please log in to continue.", "warning")
    return redirect(url_for("auth.login"))

@app.context_processor
def inject_settings():
    """Injects system settings into all templates."""
    if 'settings' not in g:
        try:
            if db.inspect(db.engine).has_table('system_settings'):
                g.settings = {s.key: s.value for s in SystemSetting.query.all()}
            else:
                g.settings = {}
        except Exception:
            g.settings = {}
    return dict(settings=g.settings)

def register_blueprints(flask_app):
    """Dynamically register all blueprints."""
    from routes.appointments import appointments_bp
    from routes.auth import auth_bp
    from routes.billing import billing_bp
    from routes.doctors import doctors_bp
    from routes.emr import emr_bp
    from routes.wards import wards_bp
    from routes.hr import hr_bp
    from routes.system_admin import system_admin_bp
    from routes.security_audit import security_audit_bp
    from routes.emergency import emergency_bp
    from routes.laboratory import laboratory_bp
    from routes.procurement import procurement_bp
    from routes.ai_assistant import ai_assistant_bp
    from routes.executive import executive_bp
    from routes.nurse_portal import nurse_portal_bp
    from routes.doctor_portal import doctor_portal_bp
    from routes.portal import portal_bp
    from routes.patients import patients_bp

    try:
        from reporting import reporting_bp
    except Exception as exc:  # pragma: no cover - optional feature may be unavailable
        logging.warning("Reporting module unavailable: %s", exc)
        reporting_bp = None

    flask_app.register_blueprint(auth_bp)
    flask_app.register_blueprint(doctors_bp)
    flask_app.register_blueprint(patients_bp)
    flask_app.register_blueprint(appointments_bp)
    flask_app.register_blueprint(emr_bp)
    flask_app.register_blueprint(billing_bp)
    flask_app.register_blueprint(wards_bp)
    flask_app.register_blueprint(hr_bp)
    flask_app.register_blueprint(system_admin_bp)
    flask_app.register_blueprint(security_audit_bp)
    flask_app.register_blueprint(laboratory_bp)
    flask_app.register_blueprint(emergency_bp)
    flask_app.register_blueprint(procurement_bp)
    flask_app.register_blueprint(ai_assistant_bp)
    flask_app.register_blueprint(executive_bp)
    flask_app.register_blueprint(nurse_portal_bp)
    flask_app.register_blueprint(doctor_portal_bp)
    flask_app.register_blueprint(portal_bp)
    if reporting_bp is not None:
        flask_app.register_blueprint(reporting_bp)

def reset_local_sqlite_database_if_needed(flask_app):
    """Safely reset a local SQLite DB only when explicitly requested.

    Removing the file on every startup is unsafe because a live connection or a
    previously running process may still hold the database open, especially on
    Windows. We therefore keep the reset opt-in and skip the removal if the file
    is locked or if the app is running normally.
    """
    database_uri = flask_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not database_uri.startswith("sqlite"):
        return

    if os.environ.get("RESET_LOCAL_SQLITE_DB", "").lower() not in {"1", "true", "yes"}:
        return

    sqlite_path = database_uri.replace("sqlite:///", "", 1)
    if sqlite_path.startswith("/"):
        db_file = sqlite_path
    else:
        db_file = os.path.join(os.path.dirname(__file__), sqlite_path)

    if not os.path.exists(db_file):
        return

    try:
        os.remove(db_file)
    except PermissionError:
        logging.warning(
            "Skipping SQLite reset because the database is already in use: %s",
            db_file,
        )
    except OSError as exc:
        logging.warning("Could not reset SQLite DB %s: %s", db_file, exc)


with app.app_context():
    reset_local_sqlite_database_if_needed(app)
    init_db()
    create_default_admin()
    register_blueprints(app)


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("auth.dashboard"))
    return redirect(url_for("auth.login"))


@app.route("/health")
def health_check():
    """Health check endpoint for load balancers and monitoring."""
    # In a real scenario, you might also check DB connection.
    return "OK", 200


# Configure logging for production
if not app.debug:
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
    app.logger.info('Hospital Management System starting up...')
