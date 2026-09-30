from app import app
from models import db, User, Patient, Doctor, Appointment, Invoice, InvoiceItem, Payment, Admission, Bed, Room, Ward, Building, HRDepartment
from datetime import date, datetime, timedelta
from decimal import Decimal

def seed_data():
    """Populates the database with sample data."""
    with app.app_context():
        # Clean up existing data
        db.reflect()
        db.drop_all()
        db.create_all()

        # --- Create Users ---
        admin_user = User(username="admin", role="Admin", full_name="Admin User")
        admin_user.set_password("admin123")

        doctor_user = User(username="dr.house@hospital.com", role="Doctor", full_name="Gregory House")
        doctor_user.set_password("doctor123")

        patient_user = User(username="john.doe@email.com", role="Patient", full_name="John Doe")
        patient_user.set_password("patient123")

        db.session.add_all([admin_user, doctor_user, patient_user])
        db.session.commit()

        # --- Create Staff/Patient Profiles ---
        doctor1 = Doctor(
            user_id=doctor_user.id, doctor_id="D202401010001", first_name="Gregory", last_name="House",
            specialization="Nephrology", department="Diagnostics", email="dr.house@hospital.com",
            gender="Male", date_of_birth=date(1959, 6, 11), national_id="12345", phone="555-0101",
            address="221B Baker St", qualification="MD, PhD", years_of_experience=20,
            license_number="LIC-GH-123", consultation_fee=250.00, working_days="Mon-Fri", working_hours="9am-5pm"
        )

        patient1 = Patient(
            user_id=patient_user.id, patient_id="P202401010001", full_name="John Doe",
            gender="Male", date_of_birth=date(1985, 5, 20), blood_group="O+",
            phone="555-0102", email="john.doe@email.com", address="123 Main St",
            emergency_contact="Jane Doe (555-0103)", next_of_kin="Jane Doe",
            insurance_provider="HealthFirst Insurance", allergies="Peanuts"
        )

        db.session.add_all([doctor1, patient1])
        db.session.commit()

        # --- Create Appointments ---
        appt1 = Appointment(
            patient_id=patient1.id, doctor_id=doctor1.id, appointment_date=date.today(),
            appointment_time="10:00 AM", department="Diagnostics", status="Confirmed",
            symptoms="Persistent cough and fatigue."
        )
        db.session.add(appt1)
        db.session.commit()

        # --- Create Billing ---
        invoice1 = Invoice(
            patient_id=patient1.id, appointment_id=appt1.id, invoice_date=date.today(),
            due_date=date.today() + timedelta(days=15), status="Pending"
        )
        db.session.add(invoice1)
        db.session.commit()

        item1 = InvoiceItem(invoice_id=invoice1.id, item_name="Consultation Fee", category="Consultation", quantity=1, unit_price=250.00, total=250.00)
        item2 = InvoiceItem(invoice_id=invoice1.id, item_name="Chest X-Ray", category="Radiology", quantity=1, unit_price=150.00, total=150.00)
        db.session.add_all([item1, item2])

        invoice1.total_amount = 400.00
        invoice1.final_amount = 400.00
        db.session.commit()

        print("Database seeded with sample data.")

if __name__ == "__main__":
    seed_data()