from datetime import date, datetime, timedelta
from decimal import Decimal
from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from sqlalchemy import func, extract

from models import db, Patient, Admission, Bed, Doctor, MedicalRecord
from routes.auth import role_required
from routes.billing import Invoice, InvoiceItem, Payment
from routes.radiology import RadiologyRequest
# from routes.laboratory import LaboratoryRequest # Assuming this model will exist

executive_bp = Blueprint("executive", __name__, url_prefix="/executive", template_folder="../templates/executive")


@executive_bp.route("/dashboard")
@login_required
@role_required("Admin")
def dashboard():
    """Main dashboard for executive analytics."""
    today = date.today()
    
    # --- KPIs ---
    total_revenue = db.session.query(func.sum(Payment.amount_paid)).scalar() or Decimal('0.00')
    total_patients = Patient.query.count()
    total_doctors = Doctor.query.count()
    
    # Bed Occupancy
    total_beds = Bed.query.count()
    occupied_beds = Bed.query.filter_by(status="Occupied").count()
    bed_occupancy_rate = (occupied_beds / total_beds * 100) if total_beds > 0 else 0

    # Average Length of Stay (ALOS)
    alos_query = db.session.query(
        func.avg(func.julianday(Admission.discharge_date) - func.julianday(Admission.admission_date))
    ).filter(Admission.discharge_date != None).scalar() or 0

    # Top Performing Doctors (by number of patients seen)
    top_doctors = db.session.query(
        Doctor.first_name,
        Doctor.last_name,
        func.count(MedicalRecord.id).label('patient_count')
    ).join(MedicalRecord, Doctor.id == MedicalRecord.doctor_id)\
     .group_by(Doctor.id)\
     .order_by(func.count(MedicalRecord.id).desc())\
     .limit(5).all()

    # Top Departments (by revenue)
    top_departments = db.session.query(
        InvoiceItem.category,
        func.sum(InvoiceItem.total).label('total_revenue')
    ).group_by(InvoiceItem.category)\
     .order_by(func.sum(InvoiceItem.total).desc())\
     .limit(5).all()

    # Top Diseases (by diagnosis count)
    top_diseases = db.session.query(
        MedicalRecord.diagnosis,
        func.count(MedicalRecord.id).label('diagnosis_count')
    ).filter(MedicalRecord.diagnosis != None, MedicalRecord.diagnosis != '')\
     .group_by(MedicalRecord.diagnosis)\
     .order_by(func.count(MedicalRecord.id).desc())\
     .limit(5).all()

    kpis = {
        "total_revenue": f"${total_revenue:,.2f}",
        "total_patients": f"{total_patients:,}",
        "bed_occupancy_rate": f"{bed_occupancy_rate:.2f}%",
        "average_length_of_stay": f"{alos_query:.2f} days",
        "average_wait_time": "N/A", # Placeholder
        "top_doctors": [f"Dr. {d.first_name} {d.last_name} ({d.patient_count} patients)" for d in top_doctors],
        "top_departments": [f"{d.category} (${d.total_revenue:,.2f})" for d in top_departments],
        "top_diseases": [f"{d.diagnosis} ({d.diagnosis_count} cases)" for d in top_diseases]
    }

    return render_template("executive_dashboard.html", title="Executive Analytics", kpis=kpis)


@executive_bp.route("/data/charts")
@login_required
@role_required("Admin")
def chart_data():
    """Provides data for the Chart.js charts."""
    twelve_months_ago = date.today() - timedelta(days=365)

    # 1. Patient Growth (Monthly)
    patient_growth = db.session.query(
        extract('year', Patient.registration_date).label('year'),
        extract('month', Patient.registration_date).label('month'),
        func.count(Patient.id)
    ).filter(Patient.registration_date >= twelve_months_ago)\
     .group_by('year', 'month')\
     .order_by('year', 'month').all()

    # 2. Revenue (Monthly)
    monthly_revenue = db.session.query(
        extract('year', Payment.payment_date).label('year'),
        extract('month', Payment.payment_date).label('month'),
        func.sum(Payment.amount_paid)
    ).filter(Payment.payment_date >= twelve_months_ago)\
     .group_by('year', 'month')\
     .order_by('year', 'month').all()

    # 3. Occupancy Rate (Monthly) - This is a simplified calculation
    monthly_admissions = db.session.query(
        extract('year', Admission.admission_date).label('year'),
        extract('month', Admission.admission_date).label('month'),
        func.count(Admission.id)
    ).filter(Admission.admission_date >= twelve_months_ago)\
     .group_by('year', 'month')\
     .order_by('year', 'month').all()

    monthly_discharges = db.session.query(
        extract('year', Admission.discharge_date).label('year'),
        extract('month', Admission.discharge_date).label('month'),
        func.count(Admission.id)
    ).filter(Admission.discharge_date != None, Admission.discharge_date >= twelve_months_ago)\
     .group_by('year', 'month')\
     .order_by('year', 'month').all()

    # 4. Departmental Performance (Lab, Radiology, Pharmacy)
    lab_requests = db.session.query(
        extract('year', Invoice.invoice_date).label('year'),
        extract('month', Invoice.invoice_date).label('month'),
        func.count(InvoiceItem.id)
    ).join(Invoice).filter(InvoiceItem.category == 'Laboratory', Invoice.invoice_date >= twelve_months_ago)\
     .group_by('year', 'month')\
     .order_by('year', 'month').all()

    imaging_requests = db.session.query(
        extract('year', RadiologyRequest.requested_date).label('year'),
        extract('month', RadiologyRequest.requested_date).label('month'),
        func.count(RadiologyRequest.id)
    ).filter(RadiologyRequest.requested_date >= twelve_months_ago)\
     .group_by('year', 'month')\
     .order_by('year', 'month').all()

    pharmacy_sales = db.session.query(
        extract('year', Invoice.invoice_date).label('year'),
        extract('month', Invoice.invoice_date).label('month'),
        func.sum(InvoiceItem.total)
    ).join(Invoice).filter(InvoiceItem.category == 'Pharmacy', Invoice.invoice_date >= twelve_months_ago)\
     .group_by('year', 'month')\
     .order_by('year', 'month').all()

    # Helper to format monthly data
    def format_monthly_data(query_result):
        data = {}
        for r in query_result:
            month_key = f"{int(r.year)}-{int(r.month):02d}"
            data[month_key] = float(r[2])
        return data

    # Generate labels for the last 12 months
    chart_labels = []
    for i in range(12):
        month = date.today().replace(day=1) - timedelta(days=i*30)
        chart_labels.append(month.strftime("%b %Y"))
    chart_labels.reverse()

    month_keys = []
    for i in range(12):
        month = date.today().replace(day=1) - timedelta(days=i*30)
        month_keys.append(month.strftime("%Y-%m"))
    month_keys.reverse()

    def get_chart_data(data_dict):
        return [data_dict.get(key, 0) for key in month_keys]

    return jsonify({
        "labels": chart_labels,
        "patientGrowth": get_chart_data(format_monthly_data(patient_growth)),
        "monthlyRevenue": get_chart_data(format_monthly_data(monthly_revenue)),
        "monthlyAdmissions": get_chart_data(format_monthly_data(monthly_admissions)),
        "monthlyDischarges": get_chart_data(format_monthly_data(monthly_discharges)),
        "labRequests": get_chart_data(format_monthly_data(lab_requests)),
        "imagingRequests": get_chart_data(format_monthly_data(imaging_requests)),
        "pharmacySales": get_chart_data(format_monthly_data(pharmacy_sales)),
    })


@executive_bp.route("/export/pdf")
@login_required
@role_required("Admin")
def export_pdf():
    # This uses ReportLab to generate a PDF from dashboard data.
    # 1. Gather dashboard summary values.
    # 2. Generate a PDF in memory.
    # 3. Return the PDF as a downloadable response.
    flash("PDF export functionality is under development.", "info")
    return redirect(url_for("executive.dashboard"))


@executive_bp.route("/export/excel")
@login_required
@role_required("Admin")
def export_excel():
    # This would require a library like openpyxl or pandas.
    # 1. Gather data into a pandas DataFrame.
    # 2. Use df.to_excel() to create an in-memory Excel file.
    # 3. Return the file as a Flask response.
    flash("Excel export functionality is under development.", "info")
    return redirect(url_for("executive.dashboard"))


@executive_bp.route("/export/csv")
@login_required
@role_required("Admin")
def export_csv():
    # This can be done with Python's built-in csv module.
    # 1. Gather data.
    # 2. Use io.StringIO and csv.writer to create a CSV string.
    # 3. Return as a Flask response with mimetype 'text/csv'.
    flash("CSV export functionality is under development.", "info")
    return redirect(url_for("executive.dashboard"))