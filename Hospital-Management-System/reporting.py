import io
from datetime import date, datetime, timedelta
from decimal import Decimal
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, make_response
from flask_login import current_user, login_required
from sqlalchemy import func, extract, case
from sqlalchemy.orm import joinedload
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

try:
    import pandas as pd
except Exception:  # pragma: no cover - optional dependency
    pd = None

from models import (
    db, Patient, Doctor, Appointment, Admission, Payment, Invoice, InvoiceItem,
    MedicalRecord, ProductCatalog, Employee, HRDepartment, Bed, RadiologyRequest,
    User
)
from routes.auth import role_required

reporting_bp = Blueprint("reporting", __name__, url_prefix="/reporting", template_folder="../templates/reporting")


def _pdf_cell(value):
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return str(float(value))
    return str(value)


def _safe_date(value, fmt="%Y-%m-%d"):
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime(fmt)
    return str(value)


def _safe_datetime(value, fmt="%Y-%m-%d %H:%M"):
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime(fmt)
    return str(value)


def _build_pdf_response(title, subtitle, columns, rows, filename_prefix):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 0.2 * inch))
    if subtitle:
        story.append(Paragraph(subtitle, styles["BodyText"]))
    story.append(Spacer(1, 0.15 * inch))

    if not rows:
        story.append(Paragraph("No data available for the selected criteria.", styles["BodyText"]))
        doc.build(story)
        pdf_bytes = buffer.getvalue()
    else:
        table_data = [list(columns)] + [[_pdf_cell(cell) for cell in row] for row in rows]
        table = Table(table_data, repeatRows=1)
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(table)
        doc.build(story)
        pdf_bytes = buffer.getvalue()

    response = make_response(pdf_bytes)
    response.headers["Content-Disposition"] = f"attachment; filename={filename_prefix}_{date.today().isoformat()}.pdf"
    response.headers["Content-Type"] = "application/pdf"
    return response


@reporting_bp.route("/dashboard")
@login_required
@role_required("Admin") # Restrict to Admin for now
def dashboard():
    """Main dashboard for the Reporting Center."""
    today = date.today()
    first_day_of_month = today.replace(day=1)

    # KPIs for the current month
    monthly_admissions = Admission.query.filter(Admission.admission_date >= first_day_of_month).count()
    monthly_discharges = Admission.query.filter(Admission.discharge_date >= first_day_of_month).count()
    monthly_revenue = db.session.query(func.sum(Payment.amount_paid)).filter(Payment.payment_date >= first_day_of_month).scalar() or Decimal('0.00')
    monthly_appointments = Appointment.query.filter(Appointment.appointment_date >= first_day_of_month).count()

    kpis = {
        "monthly_admissions": monthly_admissions,
        "monthly_discharges": monthly_discharges,
        "monthly_revenue": f"${monthly_revenue:,.2f}",
        "monthly_appointments": monthly_appointments
    }

    return render_template("reporting_dashboard.html", title="Reporting Center Dashboard", kpis=kpis)


@reporting_bp.route("/data/monthly_trends")
@login_required
@role_required("Admin")
def monthly_trends_data():
    """Provides data for monthly trends charts (Admissions, Discharges, Revenue, Appointments)."""
    twelve_months_ago = date.today() - timedelta(days=365)

    # Helper to fetch monthly counts/sums
    def fetch_monthly_data(model, date_col, value_col=None, filter_cond=None):
        query = db.session.query(
            extract('year', date_col).label('year'),
            extract('month', date_col).label('month'),
            func.sum(value_col) if value_col else func.count(model.id)
        ).filter(date_col >= twelve_months_ago)
        if filter_cond is not None:
            query = query.filter(filter_cond)
        return query.group_by('year', 'month').order_by('year', 'month').all()

    monthly_admissions = fetch_monthly_data(Admission, Admission.admission_date)
    monthly_discharges = fetch_monthly_data(Admission, Admission.discharge_date, filter_cond=Admission.discharge_date != None)
    monthly_revenue = fetch_monthly_data(Payment, Payment.payment_date, Payment.amount_paid)
    monthly_appointments = fetch_monthly_data(Appointment, Appointment.appointment_date)

    # Generate labels for the last 12 months
    chart_labels = []
    month_keys = []
    for i in range(12):
        month_date = (date.today().replace(day=1) - timedelta(days=i*30)).replace(day=1)
        chart_labels.append(month_date.strftime("%b %Y"))
        month_keys.append(month_date.strftime("%Y-%m"))
    chart_labels.reverse()
    month_keys.reverse()

    def format_chart_data(query_result):
        data_map = {f"{int(r.year)}-{int(r.month):02d}": float(r[2] or 0) for r in query_result}
        return [data_map.get(key, 0) for key in month_keys]

    return jsonify({
        "labels": chart_labels,
        "admissions": format_chart_data(monthly_admissions),
        "discharges": format_chart_data(monthly_discharges),
        "revenue": format_chart_data(monthly_revenue),
        "appointments": format_chart_data(monthly_appointments)
    })


@reporting_bp.route("/reports/<string:report_name>")
@login_required
@role_required("Admin")
def view_report(report_name):
    """Generic route to view various reports."""
    page = request.args.get("page", 1, type=int)
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else None
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else None

    report_data = []
    report_title = report_name.replace('_', ' ').title() + " Report"
    template_name = f"{report_name}_report.html"
    
    query = None

    if report_name == "admissions":
        query = Admission.query.options(joinedload(Admission.patient), joinedload(Admission.admitting_doctor), joinedload(Admission.bed).joinedload(Bed.room).joinedload(Room.ward))
        if start_date: query = query.filter(Admission.admission_date >= start_date)
        if end_date: query = query.filter(Admission.admission_date <= end_date)
        report_data = query.order_by(Admission.admission_date.desc()).paginate(page=page, per_page=20, error_out=False)
    
    elif report_name == "discharges":
        query = Admission.query.options(joinedload(Admission.patient), joinedload(Admission.admitting_doctor), joinedload(Admission.bed).joinedload(Bed.room).joinedload(Room.ward))
        query = query.filter(Admission.discharge_date != None)
        if start_date: query = query.filter(Admission.discharge_date >= start_date)
        if end_date: query = query.filter(Admission.discharge_date <= end_date)
        report_data = query.order_by(Admission.discharge_date.desc()).paginate(page=page, per_page=20, error_out=False)

    elif report_name == "revenue":
        query = Payment.query.options(joinedload(Payment.invoice).joinedload(Invoice.patient))
        if start_date: query = query.filter(Payment.payment_date >= start_date)
        if end_date: query = query.filter(Payment.payment_date <= end_date)
        report_data = query.order_by(Payment.payment_date.desc()).paginate(page=page, per_page=20, error_out=False)
        
    elif report_name == "appointments":
        query = Appointment.query.options(joinedload(Appointment.patient), joinedload(Appointment.doctor))
        if start_date: query = query.filter(Appointment.appointment_date >= start_date)
        if end_date: query = query.filter(Appointment.appointment_date <= end_date)
        report_data = query.order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).paginate(page=page, per_page=20, error_out=False)

    elif report_name == "patients":
        query = Patient.query
        if start_date: query = query.filter(Patient.registration_date >= start_date)
        if end_date: query = query.filter(Patient.registration_date <= end_date)
        report_data = query.order_by(Patient.registration_date.desc()).paginate(page=page, per_page=20, error_out=False)

    elif report_name == "doctors":
        report_data = Doctor.query.order_by(Doctor.last_name).all() # No pagination for simplicity here
        template_name = "doctors_report.html" # Specific template

    elif report_name == "pharmacy":
        query = InvoiceItem.query.options(joinedload(InvoiceItem.invoice).joinedload(Invoice.patient)).filter(InvoiceItem.category == 'Pharmacy')
        if start_date: query = query.join(Invoice).filter(Invoice.invoice_date >= start_date)
        if end_date: query = query.join(Invoice).filter(Invoice.invoice_date <= end_date)
        report_data = query.order_by(InvoiceItem.id.desc()).paginate(page=page, per_page=20, error_out=False)

    elif report_name == "laboratory":
        query = InvoiceItem.query.options(joinedload(InvoiceItem.invoice).joinedload(Invoice.patient)).filter(InvoiceItem.category == 'Laboratory')
        if start_date: query = query.join(Invoice).filter(Invoice.invoice_date >= start_date)
        if end_date: query = query.filter(Invoice.invoice_date <= end_date)
        report_data = query.order_by(InvoiceItem.id.desc()).paginate(page=page, per_page=20, error_out=False)

    elif report_name == "radiology":
        query = RadiologyRequest.query.options(joinedload(RadiologyRequest.patient), joinedload(RadiologyRequest.doctor), joinedload(RadiologyRequest.service))
        if start_date: query = query.filter(RadiologyRequest.requested_date >= start_date)
        if end_date: query = query.filter(RadiologyRequest.requested_date <= end_date)
        report_data = query.order_by(RadiologyRequest.requested_date.desc()).paginate(page=page, per_page=20, error_out=False)

    elif report_name == "inventory":
        report_data = ProductCatalog.query.order_by(ProductCatalog.name).all()
        template_name = "inventory_report.html"

    elif report_name == "bed_occupancy":
        total_beds = Bed.query.count()
        occupied_beds = Bed.query.filter_by(status="Occupied").count()
        available_beds = Bed.query.filter_by(status="Available").count()
        occupancy_rate = (occupied_beds / total_beds * 100) if total_beds > 0 else 0
        
        admissions_in_beds = db.session.query(Admission).filter(Admission.discharge_date == None).options(joinedload(Admission.patient), joinedload(Admission.bed).joinedload(Bed.room).joinedload(Room.ward)).all()
        
        report_data = {
            "total_beds": total_beds,
            "occupied_beds": occupied_beds,
            "available_beds": available_beds,
            "occupancy_rate": occupancy_rate,
            "admissions_in_beds": admissions_in_beds
        }
        template_name = "bed_occupancy_report.html"

    elif report_name == "top_diseases":
        report_data = db.session.query(
            MedicalRecord.diagnosis,
            func.count(MedicalRecord.id).label('diagnosis_count')
        ).filter(MedicalRecord.diagnosis != None, MedicalRecord.diagnosis != '')\
         .group_by(MedicalRecord.diagnosis)\
         .order_by(func.count(MedicalRecord.id).desc())\
         .limit(10).all()
        template_name = "top_diseases_report.html"

    elif report_name == "medicine_consumption":
        report_data = db.session.query(
            InvoiceItem.item_name,
            func.sum(InvoiceItem.quantity).label('total_quantity'),
            func.sum(InvoiceItem.total).label('total_revenue')
        ).filter(InvoiceItem.category == 'Pharmacy')
        if start_date: report_data = report_data.join(Invoice).filter(Invoice.invoice_date >= start_date)
        if end_date: report_data = report_data.join(Invoice).filter(Invoice.invoice_date <= end_date)
        report_data = report_data.group_by(InvoiceItem.item_name).order_by(func.sum(InvoiceItem.quantity).desc()).limit(10).all()
        template_name = "medicine_consumption_report.html"

    elif report_name == "payroll":
        flash("Payroll report is a complex feature and is under development.", "info")
        return render_template("report_placeholder.html", title="Payroll Report")

    elif report_name == "financial_summary":
        flash("Financial Summary report is a complex feature and is under development.", "info")
        return render_template("report_placeholder.html", title="Financial Summary Report")

    else:
        flash("Report not found.", "danger")
        return redirect(url_for("reporting.dashboard"))

    return render_template(
        template_name,
        title=report_title,
        report_data=report_data,
        pagination=report_data if hasattr(report_data, 'items') else None, # Pass pagination object if it exists
        start_date=start_date_str,
        end_date=end_date_str,
        report_name=report_name
    )


@reporting_bp.route("/export/<string:report_name>/<string:format>")
@login_required
@role_required("Admin")
def export_report(report_name, format):
    """Generic route to export various reports to CSV, Excel, or PDF."""
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else None
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else None

    # Re-fetch data without pagination for export
    query = None
    columns = []
    
    if report_name == "admissions":
        query = Admission.query.options(joinedload(Admission.patient), joinedload(Admission.admitting_doctor), joinedload(Admission.bed).joinedload(Bed.room).joinedload(Room.ward))
        if start_date: query = query.filter(Admission.admission_date >= start_date)
        if end_date: query = query.filter(Admission.admission_date <= end_date)
        data = query.order_by(Admission.admission_date.desc()).all()
        columns = ["Admission ID", "Patient Name", "Patient ID", "Admitting Doctor", "Ward", "Room", "Bed", "Admission Date", "Reason"]
        rows = [[a.id, a.patient.full_name if a.patient else "", a.patient.patient_id if a.patient else "", f"Dr. {a.admitting_doctor.first_name} {a.admitting_doctor.last_name}" if a.admitting_doctor else "", a.bed.room.ward.name if a.bed and a.bed.room and a.bed.room.ward else "", a.bed.room.room_number if a.bed and a.bed.room else "", a.bed.bed_number if a.bed else "", _safe_datetime(a.admission_date), a.reason or ""] for a in data]

    elif report_name == "discharges":
        query = Admission.query.options(joinedload(Admission.patient), joinedload(Admission.admitting_doctor), joinedload(Admission.bed).joinedload(Bed.room).joinedload(Room.ward))
        query = query.filter(Admission.discharge_date != None)
        if start_date: query = query.filter(Admission.discharge_date >= start_date)
        if end_date: query = query.filter(Admission.discharge_date <= end_date)
        data = query.order_by(Admission.discharge_date.desc()).all()
        columns = ["Admission ID", "Patient Name", "Patient ID", "Admitting Doctor", "Ward", "Room", "Bed", "Admission Date", "Discharge Date", "Reason"]
        rows = [[a.id, a.patient.full_name if a.patient else "", a.patient.patient_id if a.patient else "", f"Dr. {a.admitting_doctor.first_name} {a.admitting_doctor.last_name}" if a.admitting_doctor else "", a.bed.room.ward.name if a.bed and a.bed.room and a.bed.room.ward else "", a.bed.room.room_number if a.bed and a.bed.room else "", a.bed.bed_number if a.bed else "", _safe_datetime(a.admission_date), _safe_datetime(a.discharge_date) if a.discharge_date else 'N/A', a.reason or ""] for a in data]

    elif report_name == "revenue":
        query = Payment.query.options(joinedload(Payment.invoice).joinedload(Invoice.patient))
        if start_date: query = query.filter(Payment.payment_date >= start_date)
        if end_date: query = query.filter(Payment.payment_date <= end_date)
        data = query.order_by(Payment.payment_date.desc()).all()
        columns = ["Payment ID", "Invoice ID", "Patient Name", "Payment Date", "Amount Paid", "Method", "Reference"]
        rows = [[p.id, p.invoice_id, p.invoice.patient.full_name if p.invoice and p.invoice.patient else "", _safe_date(p.payment_date), float(p.amount_paid), p.payment_method or "", p.transaction_reference or ""] for p in data]

    elif report_name == "appointments":
        query = Appointment.query.options(joinedload(Appointment.patient), joinedload(Appointment.doctor))
        if start_date: query = query.filter(Appointment.appointment_date >= start_date)
        if end_date: query = query.filter(Appointment.appointment_date <= end_date)
        data = query.order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).all()
        columns = ["Appointment ID", "Patient Name", "Doctor Name", "Date", "Time", "Department", "Status", "Symptoms"]
        rows = [[a.id, a.patient.full_name if a.patient else "", f"Dr. {a.doctor.first_name} {a.doctor.last_name}" if a.doctor else "", _safe_date(a.appointment_date), a.appointment_time or "", a.department or "", a.status or "", a.symptoms or ""] for a in data]

    elif report_name == "patients":
        query = Patient.query
        if start_date: query = query.filter(Patient.registration_date >= start_date)
        if end_date: query = query.filter(Patient.registration_date <= end_date)
        data = query.order_by(Patient.registration_date.desc()).all()
        columns = ["Patient ID", "Full Name", "Gender", "DOB", "Phone", "Email", "Registration Date"]
        rows = [[p.patient_id, p.full_name, p.gender or "", _safe_date(p.date_of_birth), p.phone or "", p.email or "", _safe_date(p.registration_date)] for p in data]

    elif report_name == "doctors":
        data = Doctor.query.order_by(Doctor.last_name).all()
        columns = ["Doctor ID", "Full Name", "Specialization", "Department", "Email", "Phone", "Status"]
        rows = [[d.doctor_id, f"Dr. {d.first_name} {d.last_name}", d.specialization or "", d.department or "", d.email or "", d.phone or "", d.status or ""] for d in data]

    elif report_name == "pharmacy":
        query = InvoiceItem.query.options(joinedload(InvoiceItem.invoice).joinedload(Invoice.patient)).filter(InvoiceItem.category == 'Pharmacy')
        if start_date: query = query.join(Invoice).filter(Invoice.invoice_date >= start_date)
        if end_date: query = query.join(Invoice).filter(Invoice.invoice_date <= end_date)
        data = query.order_by(InvoiceItem.id.desc()).all()
        columns = ["Item Name", "Quantity", "Unit Price", "Total", "Invoice ID", "Patient Name", "Invoice Date"]
        rows = [[i.item_name, i.quantity, float(i.unit_price), float(i.total), i.invoice_id, i.invoice.patient.full_name if i.invoice and i.invoice.patient else "", _safe_date(i.invoice.invoice_date) if i.invoice else ""] for i in data]

    elif report_name == "laboratory":
        query = InvoiceItem.query.options(joinedload(InvoiceItem.invoice).joinedload(Invoice.patient)).filter(InvoiceItem.category == 'Laboratory')
        if start_date: query = query.join(Invoice).filter(Invoice.invoice_date >= start_date)
        if end_date: query = query.join(Invoice).filter(Invoice.invoice_date <= end_date)
        data = query.order_by(InvoiceItem.id.desc()).all()
        columns = ["Test Name", "Quantity", "Unit Price", "Total", "Invoice ID", "Patient Name", "Invoice Date"]
        rows = [[i.item_name, i.quantity, float(i.unit_price), float(i.total), i.invoice_id, i.invoice.patient.full_name if i.invoice and i.invoice.patient else "", _safe_date(i.invoice.invoice_date) if i.invoice else ""] for i in data]

    elif report_name == "radiology":
        query = RadiologyRequest.query.options(joinedload(RadiologyRequest.patient), joinedload(RadiologyRequest.doctor), joinedload(RadiologyRequest.service))
        if start_date: query = query.filter(RadiologyRequest.requested_date >= start_date)
        if end_date: query = query.filter(RadiologyRequest.requested_date <= end_date)
        data = query.order_by(RadiologyRequest.requested_date.desc()).all()
        columns = ["Request ID", "Patient Name", "Doctor Name", "Service", "Requested Date", "Status"]
        rows = [[r.id, r.patient.full_name if r.patient else "", f"Dr. {r.doctor.first_name} {r.doctor.last_name}" if r.doctor else "", r.service.name if r.service else "", _safe_date(r.requested_date), r.status or ""] for r in data]

    elif report_name == "inventory":
        data = ProductCatalog.query.options(joinedload(ProductCatalog.preferred_supplier)).order_by(ProductCatalog.name).all()
        columns = ["Product Name", "Category", "Unit", "SKU", "Current Stock", "Reorder Level", "Preferred Supplier"]
        rows = [[p.name, p.category or "", p.unit_of_measure or "", p.sku or "", p.current_stock, p.reorder_level, p.preferred_supplier.company_name if p.preferred_supplier else 'N/A'] for p in data]

    elif report_name == "bed_occupancy":
        total_beds = Bed.query.count()
        occupied_beds = Bed.query.filter_by(status="Occupied").count()
        available_beds = Bed.query.filter_by(status="Available").count()
        occupancy_rate = (occupied_beds / total_beds * 100) if total_beds > 0 else 0
        
        admissions_in_beds = db.session.query(Admission).filter(Admission.discharge_date == None).options(joinedload(Admission.patient), joinedload(Admission.bed).joinedload(Bed.room).joinedload(Room.ward)).all()
        
        # For export, we'll just export the current admissions in beds
        data = admissions_in_beds
        columns = ["Patient Name", "Patient ID", "Ward", "Room", "Bed Number", "Admission Date"]
        rows = [[a.patient.full_name if a.patient else "", a.patient.patient_id if a.patient else "", a.bed.room.ward.name if a.bed and a.bed.room and a.bed.room.ward else "", a.bed.room.room_number if a.bed and a.bed.room else "", a.bed.bed_number if a.bed else "", _safe_datetime(a.admission_date)] for a in data]

    elif report_name == "top_diseases":
        data = db.session.query(
            MedicalRecord.diagnosis,
            func.count(MedicalRecord.id).label('diagnosis_count')
        ).filter(MedicalRecord.diagnosis != None, MedicalRecord.diagnosis != '')\
         .group_by(MedicalRecord.diagnosis)\
         .order_by(func.count(MedicalRecord.id).desc()).all()
        columns = ["Diagnosis", "Count"]
        rows = [[d.diagnosis or "", d.diagnosis_count] for d in data]

    elif report_name == "medicine_consumption":
        data = db.session.query(
            InvoiceItem.item_name,
            func.sum(InvoiceItem.quantity).label('total_quantity'),
            func.sum(InvoiceItem.total).label('total_revenue')
        ).filter(InvoiceItem.category == 'Pharmacy')
        if start_date: data = data.join(Invoice).filter(Invoice.invoice_date >= start_date)
        if end_date: data = data.join(Invoice).filter(Invoice.invoice_date <= end_date)
        data = data.group_by(InvoiceItem.item_name).order_by(func.sum(InvoiceItem.quantity).desc()).all()
        columns = ["Medicine Name", "Total Quantity Consumed", "Total Revenue"]
        rows = [[d.item_name or "", d.total_quantity, float(d.total_revenue)] for d in data]

    elif report_name in ["payroll", "financial_summary"]:
        flash(f"{report_name.replace('_', ' ').title()} export functionality is under development.", "info")
        return redirect(url_for("reporting.dashboard"))

    else:
        flash("Report not found for export.", "danger")
        return redirect(url_for("reporting.dashboard"))

    if not data:
        flash("No data to export for the selected criteria.", "warning")
        return redirect(url_for("reporting.view_report", report_name=report_name, start_date=start_date_str, end_date=end_date_str))

    df = pd.DataFrame(rows, columns=columns)
    report_title = report_name.replace('_', ' ').title()

    if format == "csv":
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        response = make_response(csv_buffer.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename={report_title}_{date.today().isoformat()}.csv"
        response.headers["Content-type"] = "text/csv"
        return response

    elif format == "excel":
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)
        response = make_response(excel_buffer.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename={report_title}_{date.today().isoformat()}.xlsx"
        response.headers["Content-type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return response

    elif format == "pdf":
        generated_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        subtitle = (
            f"Generated by: {current_user.full_name if current_user.is_authenticated else 'System'} | "
            f"Date range: {start_date_str or 'All Time'} to {end_date_str or 'All Time'} | "
            f"Generated on: {generated_at}"
        )
        return _build_pdf_response(
            f"{report_title} Report",
            subtitle,
            columns,
            rows,
            report_title.replace(" ", "_").lower(),
        )

    else:
        flash("Invalid export format.", "danger")
        return redirect(url_for("reporting.dashboard"))