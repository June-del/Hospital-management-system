import unittest
from pathlib import Path

from app import app
from models import db, Doctor, Patient, User, create_default_admin


class CSRFFormTest(unittest.TestCase):
    def test_patient_and_doctor_forms_include_csrf_token(self):
        root = Path(__file__).resolve().parents[1]
        patient_form = (root / "Hospital-Management-System" / "templates" / "patients" / "patient_form.html").read_text(encoding="utf-8")
        doctor_form = (root / "Hospital-Management-System" / "templates" / "doctors" / "doctor_form.html").read_text(encoding="utf-8")

        self.assertIn("csrf_token", patient_form)
        self.assertIn("csrf_token", doctor_form)

    def test_patient_and_doctor_save_routes_persist_records(self):
        with app.app_context():
            db.drop_all()
            db.create_all()
            create_default_admin()

        with app.test_client() as client:
            login = client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=False)
            self.assertEqual(login.status_code, 302)

            patient_response = client.post(
                '/patients/add',
                data={
                    'full_name': 'Alice Patient',
                    'gender': 'Female',
                    'date_of_birth': '1990-05-15',
                    'blood_group': 'O+',
                    'phone': '1234567890',
                    'email': 'alice@example.com',
                    'address': '123 Main St',
                    'emergency_contact': '999',
                    'next_of_kin': 'Bob',
                    'insurance_provider': 'Acme',
                    'allergies': 'Peanuts',
                    'medical_conditions': 'None',
                },
                follow_redirects=False,
            )
            self.assertEqual(patient_response.status_code, 302)
            self.assertEqual(Patient.query.count(), 1)

            doctor_response = client.post(
                '/doctors/add',
                data={
                    'first_name': 'Dr Alicia',
                    'last_name': 'Ng',
                    'gender': 'Female',
                    'date_of_birth': '1985-04-20',
                    'national_id': 'N123',
                    'phone': '5551112222',
                    'email': 'doc@example.com',
                    'address': '42 Health Ave',
                    'specialization': 'Cardiology',
                    'department': 'Cardiology',
                    'qualification': 'MD',
                    'years_of_experience': '10',
                    'license_number': 'LIC-123',
                    'consultation_fee': '150',
                    'working_days': 'Mon-Fri',
                    'working_hours': '9-5',
                    'status': 'Available',
                },
                follow_redirects=False,
            )
            self.assertEqual(doctor_response.status_code, 302)
            self.assertEqual(Doctor.query.count(), 1)
            self.assertEqual(User.query.filter_by(username='doc@example.com').count(), 1)


if __name__ == "__main__":
    unittest.main()
