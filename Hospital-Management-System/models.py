from typing import Optional
from datetime import datetime, date
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from config import DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USERNAME, ROLES

db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    full_name = db.Column(db.String(120), nullable=False, default="")
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    is_locked = db.Column(db.Boolean, default=False, nullable=False)
    last_password_change = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    patient = db.relationship("Patient", backref="user", uselist=False, cascade="all, delete-orphan")
    doctor = db.relationship("Doctor", backref="user", uselist=False, cascade="all, delete-orphan")
    nurse = db.relationship("Nurse", backref="user", uselist=False, cascade="all, delete-orphan")
    employee = db.relationship("Employee", backref=db.backref("user", uselist=False))

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Patient(db.Model):
    __tablename__ = "patients"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    patient_id = db.Column(db.String(50), unique=True, nullable=False, default="")
    full_name = db.Column(db.String(120), nullable=False, default="")
    gender = db.Column(db.String(20), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    blood_group = db.Column(db.String(10), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.Text, nullable=True)
    emergency_contact = db.Column(db.String(120), nullable=True)
    next_of_kin = db.Column(db.String(120), nullable=True)
    insurance_provider = db.Column(db.String(120), nullable=True)
    allergies = db.Column(db.Text, nullable=True)
    medical_conditions = db.Column(db.Text, nullable=True)
    photo_filename = db.Column(db.String(255), nullable=True)
    registration_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    @staticmethod
    def generate_patient_id():
        from random import randint
        return f"P{date.today().strftime('%Y%m%d')}{randint(1000, 9999)}"


class Doctor(db.Model):
    __tablename__ = "doctors"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    doctor_id = db.Column(db.String(50), unique=True, nullable=False, default="")
    first_name = db.Column(db.String(80), nullable=False, default="")
    last_name = db.Column(db.String(80), nullable=False, default="")
    gender = db.Column(db.String(20), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    national_id = db.Column(db.String(50), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.Text, nullable=True)
    specialization = db.Column(db.String(120), nullable=True)
    department = db.Column(db.String(120), nullable=True)
    qualification = db.Column(db.String(200), nullable=True)
    years_of_experience = db.Column(db.Integer, default=0)
    license_number = db.Column(db.String(80), nullable=True)
    consultation_fee = db.Column(db.Numeric(10, 2), default=0)
    working_days = db.Column(db.String(120), nullable=True)
    working_hours = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(50), default="Available")
    profile_photo = db.Column(db.String(255), nullable=True)
    date_joined = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @staticmethod
    def save_photo(file_storage):
        from config import BASE_DIR
        from utils import save_uploaded_file

        upload_folder = os.path.join(BASE_DIR, "static", "uploads", "doctors")
        allowed_extensions = {"png", "jpg", "jpeg", "gif"}
        return save_uploaded_file(file_storage, upload_folder, allowed_extensions)


class Nurse(db.Model):
    __tablename__ = "nurses"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    first_name = db.Column(db.String(80), nullable=False, default="")
    last_name = db.Column(db.String(80), nullable=False, default="")
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    department = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(50), default="Available")


class HRDepartment(db.Model):
    __tablename__ = "hr_departments"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    head_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=True)
    head = db.relationship(
        "Employee",
        foreign_keys=[head_id],
        backref=db.backref("managed_department", uselist=False, foreign_keys="[HRDepartment.head_id]"),
    )


class Employee(db.Model):
    __tablename__ = "employees"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    employee_number = db.Column(db.String(80), unique=True, nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("hr_departments.id"), nullable=True)
    department = db.relationship(
        "HRDepartment",
        foreign_keys=[department_id],
        backref=db.backref("employees", foreign_keys="[Employee.department_id]"),
    )
    employment_date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(50), default="Active")


class Attendance(db.Model):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    date = db.Column(db.Date, default=date.today)
    check_in = db.Column(db.DateTime, nullable=True)
    check_out = db.Column(db.DateTime, nullable=True)


class Leave(db.Model):
    __tablename__ = "leaves"
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    start_date = db.Column(db.Date, default=date.today)
    end_date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(50), default="Pending")


class Building(db.Model):
    __tablename__ = "buildings"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.Text, nullable=True)


class Floor(db.Model):
    __tablename__ = "floors"
    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), nullable=False)
    floor_number = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(120), nullable=False)


class Ward(db.Model):
    __tablename__ = "wards"
    id = db.Column(db.Integer, primary_key=True)
    floor_id = db.Column(db.Integer, db.ForeignKey("floors.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    ward_type = db.Column(db.String(80), nullable=False)
    occupied_beds = db.Column(db.Integer, default=0)


class Room(db.Model):
    __tablename__ = "rooms"
    id = db.Column(db.Integer, primary_key=True)
    ward_id = db.Column(db.Integer, db.ForeignKey("wards.id"), nullable=False)
    room_number = db.Column(db.String(50), nullable=False)
    room_type = db.Column(db.String(50), nullable=False)


class Bed(db.Model):
    __tablename__ = "beds"
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("rooms.id"), nullable=False)
    bed_number = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), default="Available")
    room = db.relationship("Room", backref="beds")


class Admission(db.Model):
    __tablename__ = "admissions"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    bed_id = db.Column(db.Integer, db.ForeignKey("beds.id"), nullable=False)
    admitting_doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    admission_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    discharge_date = db.Column(db.DateTime, nullable=True)
    reason = db.Column(db.Text, nullable=True)
    patient = db.relationship("Patient", backref=db.backref("admissions", lazy=True))
    bed = db.relationship("Bed", backref=db.backref("admissions", lazy=True))
    admitting_doctor = db.relationship("Doctor", backref=db.backref("admissions", lazy=True))


class Appointment(db.Model):
    __tablename__ = "appointments"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    department = db.Column(db.String(120), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.String(10), nullable=False)
    queue_number = db.Column(db.Integer, default=0)
    visit_type = db.Column(db.String(30), default="Consultation")
    status = db.Column(db.String(30), default="Pending")
    symptoms = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    patient = db.relationship("Patient", backref=db.backref("appointments", lazy=True))
    doctor = db.relationship("Doctor", backref=db.backref("appointments", lazy=True))


class Invoice(db.Model):
    __tablename__ = "invoices"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointments.id"), nullable=True)
    invoice_date = db.Column(db.Date, default=date.today)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), default="Pending")
    total_amount = db.Column(db.Numeric(10, 2), default=0)
    discount = db.Column(db.Numeric(10, 2), default=0)
    tax = db.Column(db.Numeric(10, 2), default=0)
    final_amount = db.Column(db.Numeric(10, 2), default=0)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship("Patient", backref=db.backref("invoices", lazy=True))
    appointment = db.relationship("Appointment", backref=db.backref("invoices", lazy=True))
    items = db.relationship("InvoiceItem", backref="invoice", lazy=True, cascade="all, delete-orphan")
    payments = db.relationship("Payment", backref="invoice", lazy=True, cascade="all, delete-orphan")


class InvoiceItem(db.Model):
    __tablename__ = "invoice_items"
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    item_name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(40), default="Other")
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), default=0)


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    payment_date = db.Column(db.Date, default=date.today)
    amount_paid = db.Column(db.Numeric(10, 2), default=0)
    payment_method = db.Column(db.String(40), default="Cash")
    transaction_reference = db.Column(db.String(120), nullable=True)
    received_by = db.Column(db.String(120), nullable=True)
    remarks = db.Column(db.Text, nullable=True)


class MedicalRecord(db.Model):
    __tablename__ = "medical_records"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    visit_date = db.Column(db.Date, default=date.today)
    chief_complaint = db.Column(db.Text, nullable=False)
    symptoms = db.Column(db.Text, nullable=True)
    medical_history = db.Column(db.Text, nullable=True)
    allergies = db.Column(db.Text, nullable=True)
    physical_examination = db.Column(db.Text, nullable=True)
    diagnosis = db.Column(db.Text, nullable=True)
    treatment_plan = db.Column(db.Text, nullable=True)
    prescription = db.Column(db.Text, nullable=True)
    lab_tests_requested = db.Column(db.Text, nullable=True)
    imaging_requested = db.Column(db.Text, nullable=True)
    follow_up_date = db.Column(db.Date, nullable=True)
    clinical_notes = db.Column(db.Text, nullable=True)
    temperature = db.Column(db.String(20), nullable=True)
    blood_pressure = db.Column(db.String(20), nullable=True)
    pulse_rate = db.Column(db.String(20), nullable=True)
    respiratory_rate = db.Column(db.String(20), nullable=True)
    weight = db.Column(db.String(20), nullable=True)
    height = db.Column(db.String(20), nullable=True)
    bmi = db.Column(db.String(20), nullable=True)
    oxygen_saturation = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship("Patient", backref=db.backref("medical_records", lazy=True))
    doctor = db.relationship("Doctor", backref=db.backref("medical_records", lazy=True))


class LabTestCatalog(db.Model):
    __tablename__ = "lab_test_catalog"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    reference_range = db.Column(db.String(100), nullable=True)
    unit = db.Column(db.String(50), nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    is_active = db.Column(db.Boolean, default=True)


class LabTestRequest(db.Model):
    __tablename__ = "lab_test_requests"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    accession_number = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(50), default="Pending")
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    patient = db.relationship("Patient", backref=db.backref("lab_requests", lazy="dynamic"))
    doctor = db.relationship("Doctor", backref=db.backref("lab_requests_ordered", lazy="dynamic"))
    results = db.relationship("LabTestResult", backref="request", cascade="all, delete-orphan")


class LabTestResult(db.Model):
    __tablename__ = "lab_test_results"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("lab_test_requests.id"), nullable=False)
    test_catalog_id = db.Column(db.Integer, db.ForeignKey("lab_test_catalog.id"), nullable=False)
    value = db.Column(db.String(100), nullable=True)
    is_abnormal = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, nullable=True)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    recorded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    test_catalog = db.relationship("LabTestCatalog")
    recorded_by = db.relationship("User")


class ImagingService(db.Model):
    __tablename__ = "imaging_services"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    category = db.Column(db.String(80), nullable=True)
    price = db.Column(db.Numeric(10, 2), default=0)


class RadiologyRequest(db.Model):
    __tablename__ = "radiology_requests"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("imaging_services.id"), nullable=True)
    requested_date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(50), default="Scheduled")
    notes = db.Column(db.Text, nullable=True)
    patient = db.relationship("Patient", backref=db.backref("radiology_requests", lazy=True))
    doctor = db.relationship("Doctor", backref=db.backref("radiology_requests", lazy=True))
    service = db.relationship("ImagingService", backref="requests")


class Ambulance(db.Model):
    __tablename__ = "ambulances"
    id = db.Column(db.Integer, primary_key=True)
    vehicle_number = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(50), default="Available")


class EmergencyCall(db.Model):
    __tablename__ = "emergency_calls"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=True)
    ambulance_id = db.Column(db.Integer, db.ForeignKey("ambulances.id"), nullable=True)
    caller_name = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    incident_type = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(50), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PatientTransfer(db.Model):
    __tablename__ = "patient_transfers"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    from_ward_id = db.Column(db.Integer, db.ForeignKey("wards.id"), nullable=True)
    to_ward_id = db.Column(db.Integer, db.ForeignKey("wards.id"), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    transfer_date = db.Column(db.DateTime, default=datetime.utcnow)


class Supplier(db.Model):
    __tablename__ = "suppliers"
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.String(80), unique=True, nullable=False)
    company_name = db.Column(db.String(180), nullable=False)
    contact_person = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.Text, nullable=True)
    tax_number = db.Column(db.String(80), nullable=True)
    status = db.Column(db.String(50), default="Active")


class ProductCatalog(db.Model):
    __tablename__ = "product_catalog"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(80), nullable=True)
    unit_of_measure = db.Column(db.String(40), nullable=True)
    sku = db.Column(db.String(60), nullable=True)
    reorder_level = db.Column(db.Integer, default=0)
    preferred_supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)


class PurchaseRequest(db.Model):
    __tablename__ = "purchase_requests"
    id = db.Column(db.Integer, primary_key=True)
    request_number = db.Column(db.String(80), unique=True, nullable=False)
    requested_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    department = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(100), default="Pending Department Approval")
    order_date = db.Column(db.DateTime, default=datetime.utcnow)


class PurchaseRequestItem(db.Model):
    __tablename__ = "purchase_request_items"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("purchase_requests.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product_catalog.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Numeric(10, 2), default=0)


class PurchaseOrder(db.Model):
    __tablename__ = "purchase_orders"
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(80), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    status = db.Column(db.String(80), default="Draft")
    order_date = db.Column(db.Date, default=date.today)
    expected_delivery_date = db.Column(db.Date, nullable=True)
    total_amount = db.Column(db.Numeric(10, 2), default=0)


class PurchaseOrderItem(db.Model):
    __tablename__ = "purchase_order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product_catalog.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Numeric(10, 2), default=0)


class GoodsReceivedNote(db.Model):
    __tablename__ = "goods_received_notes"
    id = db.Column(db.Integer, primary_key=True)
    grn_number = db.Column(db.String(80), unique=True, nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    received_date = db.Column(db.Date, default=date.today)


class GoodsReceivedItem(db.Model):
    __tablename__ = "goods_received_items"
    id = db.Column(db.Integer, primary_key=True)
    grn_id = db.Column(db.Integer, db.ForeignKey("goods_received_notes.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product_catalog.id"), nullable=False)
    quantity = db.Column(db.Integer, default=0)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(150), nullable=False)
    entity_type = db.Column(db.String(120), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class SecurityEvent(db.Model):
    __tablename__ = "security_events"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    event_type = db.Column(db.String(150), nullable=False)
    ip_address = db.Column(db.String(80), nullable=True)
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class SystemSetting(db.Model):
    __tablename__ = "system_settings"
    key = db.Column(db.String(120), primary_key=True)
    value = db.Column(db.String(255), nullable=True)


class VitalSign(db.Model):
    __tablename__ = "vital_signs"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    blood_pressure = db.Column(db.String(20), nullable=True)
    heart_rate = db.Column(db.String(20), nullable=True)


class MedicationAdministration(db.Model):
    __tablename__ = "medication_administrations"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    medication_name = db.Column(db.String(150), nullable=False)
    administered_at = db.Column(db.DateTime, default=datetime.utcnow)


class NursingNote(db.Model):
    __tablename__ = "nursing_notes"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def init_db() -> None:
    if current_app:
        db.create_all()
        return

    from app import app as flask_app

    with flask_app.app_context():
        db.create_all()


def create_user(username: str, password: str, role: str, full_name: str = "") -> User:
    if role not in ROLES:
        raise ValueError(f"Unsupported role: {role}")

    if current_app:
        user = User(username=username, role=role, full_name=full_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    from app import app as flask_app

    with flask_app.app_context():
        user = User(username=username, role=role, full_name=full_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user


def get_user_by_username(username: str) -> Optional[User]:
    if current_app:
        return User.query.filter_by(username=username).first()

    from app import app as flask_app

    with flask_app.app_context():
        return User.query.filter_by(username=username).first()


def get_user_by_id(user_id: int) -> Optional[User]:
    if current_app:
        return User.query.get(user_id)

    from app import app as flask_app

    with flask_app.app_context():
        return User.query.get(user_id)


def authenticate_user(username: str, password: str) -> Optional[User]:
    user = get_user_by_username(username)
    if user and user.check_password(password):
        return user
    return None


def create_default_admin() -> User:
    existing = get_user_by_username(DEFAULT_ADMIN_USERNAME)
    if existing:
        if not existing.check_password(DEFAULT_ADMIN_PASSWORD):
            existing.set_password(DEFAULT_ADMIN_PASSWORD)
            existing.role = "Admin"
            existing.full_name = "System Administrator"
            db.session.commit()
        return existing

    return create_user(
        username=DEFAULT_ADMIN_USERNAME,
        password=DEFAULT_ADMIN_PASSWORD,
        role="Admin",
        full_name="System Administrator",
    )
