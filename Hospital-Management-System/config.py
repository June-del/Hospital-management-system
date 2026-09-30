import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# --- Core Flask Settings ---
SECRET_KEY = os.environ.get("SECRET_KEY", "a-strong-dev-secret-key-that-should-be-changed")
DEBUG = os.environ.get("FLASK_DEBUG", "False").lower() in ("true", "1", "t")

# --- Database Settings ---
DB_USER = os.environ.get("POSTGRES_USER", "hospital_user")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "hospital_password")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("POSTGRES_DB", "hospital_db")

# Use PostgreSQL in production, but default to SQLite for local development when no
# database URL is configured so the app can boot without external services.
if os.environ.get("DATABASE_URL"):
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
else:
    sqlite_path = os.path.join(BASE_DIR, "database", "hospital.db")
    os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{sqlite_path}"

SQLALCHEMY_TRACK_MODIFICATIONS = False

# --- Session Management ---
PERMANENT_SESSION_LIFETIME = timedelta(minutes=int(os.environ.get("SESSION_LIFETIME_MINUTES", 30)))

# --- Default Admin ---
DEFAULT_ADMIN_USERNAME = os.environ.get("DEFAULT_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "admin123")

# --- User Roles (Static) ---
ROLES = ["Admin", "Doctor", "Nurse", "Patient", "Receptionist", "Pharmacist", "Laboratory Technician", "Cashier", "HR Manager", "Procurement Officer", "Executive", "Dispatcher", "Inventory Manager"]