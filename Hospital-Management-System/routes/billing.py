import io
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from flask import Blueprint, flash, redirect, render_template, request, url_for, make_response
from flask_login import login_required
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import or_
from models import AuditLog, Appointment, Doctor, Invoice, InvoiceItem, MedicalRecord, Patient, Payment, db

billing_bp = Blueprint("billing", __name__, template_folder="../templates/billing")

INVOICE_STATUSES = ["Pending", "Paid", "Partially Paid", "Cancelled"]
INVOICE_CATEGORIES = ["Consultation", "Laboratory", "Pharmacy", "Admission", "Procedure", "Other"]
PAYMENT_METHODS = ["Cash", "M-Pesa", "Card", "Bank Transfer", "Insurance"]


def _money(value) -> Decimal:
    return Decimal(str(value or 0))


def _calculate_invoice_totals(invoice: Invoice) -> None:
    total = sum(_money(item.total) for item in invoice.items)
    discount = _money(invoice.discount)
    tax = _money(invoice.tax)
    invoice.total_amount = total
    invoice.final_amount = total - discount + tax


def _invoice_balance(invoice: Invoice) -> Decimal:
    paid = sum(_money(payment.amount_paid) for payment in invoice.payments)
    return _money(invoice.final_amount) - paid


def _update_invoice_status(invoice: Invoice) -> None:
    balance = _invoice_balance(invoice)
    if balance <= 0:
        invoice.status = "Paid"
    elif any(payment.amount_paid for payment in invoice.payments):
        invoice.status = "Partially Paid"
    else:
        invoice.status = "Pending"


def _validate_invoice_data(form_data) -> Tuple[list[str], Optional[date], Optional[date]]:
    errors = []
    patient_id = form_data.get("patient_id", "").strip()
    invoice_date_raw = form_data.get("invoice_date", "").strip()
    due_date_raw = form_data.get("due_date", "").strip()
    if not patient_id:
        errors.append("Please select a patient.")
    invoice_date_value = None
    due_date_value = None
    if invoice_date_raw:
        try:
            invoice_date_value = datetime.strptime(invoice_date_raw, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Invoice date must be in YYYY-MM-DD format.")
    if due_date_raw:
        try:
            due_date_value = datetime.strptime(due_date_raw, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Due date must be in YYYY-MM-DD format.")
    return errors, invoice_date_value, due_date_value


def _build_pdf_response(title, summary_rows, table_data, filename_prefix):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 0.2 * inch))
    for key, value in summary_rows:
        story.append(Paragraph(f"<b>{key}</b>: {value}", styles["BodyText"]))
    story.append(Spacer(1, 0.15 * inch))

    if table_data:
        table = Table(table_data, repeatRows=1)
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(table)

    doc.build(story)
    response = make_response(buffer.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={filename_prefix}_{date.today().isoformat()}.pdf"
    response.headers["Content-Type"] = "application/pdf"
    return response


@billing_bp.route("/billing")
@login_required
def billing_index():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "", type=str).strip()
    status = request.args.get("status", "", type=str).strip()
    start_date = request.args.get("start_date", "", type=str).strip()
    end_date = request.args.get("end_date", "", type=str).strip()

    query = Invoice.query
    if search:
        search_pattern = f"%{search}%"
        query = query.join(Patient).filter(or_(Patient.full_name.like(search_pattern), Invoice.notes.like(search_pattern)))
    if status:
        query = query.filter(Invoice.status == status)
    if start_date:
        query = query.filter(Invoice.invoice_date >= datetime.strptime(start_date, "%Y-%m-%d").date())
    if end_date:
        query = query.filter(Invoice.invoice_date <= datetime.strptime(end_date, "%Y-%m-%d").date())

    pagination = query.order_by(Invoice.invoice_date.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template(
        "invoices.html",
        invoices=pagination.items,
        pagination=pagination,
        search=search,
        status=status,
        start_date=start_date,
        end_date=end_date,
        statuses=INVOICE_STATUSES,
        title="Billing & Payments",
    )


@billing_bp.route("/billing/create", methods=["GET", "POST"])
@login_required
def create_invoice():
    if request.method == "POST":
        errors, invoice_date_value, due_date_value = _validate_invoice_data(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "invoice_form.html",
                invoice=None,
                patients=Patient.query.order_by(Patient.full_name).all(),
                appointments=Appointment.query.order_by(Appointment.appointment_date.desc()).all(),
                categories=INVOICE_CATEGORIES,
                statuses=INVOICE_STATUSES,
                title="Create Invoice",
            )

        invoice = Invoice(
            patient_id=int(request.form.get("patient_id")),
            appointment_id=(request.form.get("appointment_id") or None),
            invoice_date=invoice_date_value or date.today(),
            due_date=due_date_value,
            status=request.form.get("status", "Pending").strip() or "Pending",
            discount=request.form.get("discount", 0),
            tax=request.form.get("tax", 0),
            notes=request.form.get("notes", "").strip(),
        )
        db.session.add(invoice)
        db.session.flush()

        item_names = request.form.getlist("item_name")
        item_categories = request.form.getlist("category")
        item_quantities = request.form.getlist("quantity")
        item_prices = request.form.getlist("unit_price")
        for name, category, quantity, price in zip(item_names, item_categories, item_quantities, item_prices):
            if not name:
                continue
            item = InvoiceItem(
                invoice_id=invoice.id,
                item_name=name,
                category=category,
                quantity=int(quantity or 1),
                unit_price=price,
                total=int(quantity or 1) * Decimal(str(price or 0)),
            )
            db.session.add(item)

        _calculate_invoice_totals(invoice)
        _update_invoice_status(invoice)
        db.session.commit()
        flash("Invoice created successfully.", "success")
        audit_log = AuditLog(user_id=current_user.id, action="Invoice Created", entity_type="Invoice", entity_id=invoice.id, details=f"Invoice #{invoice.id} created for patient '{invoice.patient.full_name}'.")
        db.session.add(audit_log)
        return redirect(url_for("billing.billing_index"))

    return render_template(
        "invoice_form.html",
        invoice=None,
        patients=Patient.query.order_by(Patient.full_name).all(),
        appointments=Appointment.query.order_by(Appointment.appointment_date.desc()).all(),
        categories=INVOICE_CATEGORIES,
        statuses=INVOICE_STATUSES,
        title="Create Invoice",
    )


@billing_bp.route("/billing/edit/<int:invoice_id>", methods=["GET", "POST"])
@login_required
def edit_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    if request.method == "POST":
        errors, invoice_date_value, due_date_value = _validate_invoice_data(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "invoice_form.html",
                invoice=invoice,
                patients=Patient.query.order_by(Patient.full_name).all(),
                appointments=Appointment.query.order_by(Appointment.appointment_date.desc()).all(),
                categories=INVOICE_CATEGORIES,
                statuses=INVOICE_STATUSES,
                title="Edit Invoice",
            )

        invoice.patient_id = int(request.form.get("patient_id"))
        invoice.appointment_id = request.form.get("appointment_id") or None
        invoice.invoice_date = invoice_date_value or invoice.invoice_date
        invoice.due_date = due_date_value
        invoice.status = request.form.get("status", "Pending").strip() or "Pending"
        invoice.discount = request.form.get("discount", 0)
        invoice.tax = request.form.get("tax", 0)
        invoice.notes = request.form.get("notes", "").strip()

        invoice.items = []
        item_names = request.form.getlist("item_name")
        item_categories = request.form.getlist("category")
        item_quantities = request.form.getlist("quantity")
        item_prices = request.form.getlist("unit_price")
        for name, category, quantity, price in zip(item_names, item_categories, item_quantities, item_prices):
            if not name:
                continue
            invoice.items.append(
                InvoiceItem(
                    item_name=name,
                    category=category,
                    quantity=int(quantity or 1),
                    unit_price=price,
                    total=int(quantity or 1) * Decimal(str(price or 0)),
                )
            )

        _calculate_invoice_totals(invoice)
        _update_invoice_status(invoice)
        db.session.commit()
        flash("Invoice updated successfully.", "success")
        audit_log = AuditLog(user_id=current_user.id, action="Invoice Updated", entity_type="Invoice", entity_id=invoice.id, details=f"Invoice #{invoice.id} updated for patient '{invoice.patient.full_name}'.")
        db.session.add(audit_log)
        return redirect(url_for("billing.billing_index"))

    return render_template(
        "invoice_form.html",
        invoice=invoice,
        patients=Patient.query.order_by(Patient.full_name).all(),
        appointments=Appointment.query.order_by(Appointment.appointment_date.desc()).all(),
        categories=INVOICE_CATEGORIES,
        statuses=INVOICE_STATUSES,
        title="Edit Invoice",
    )


@billing_bp.route("/billing/delete/<int:invoice_id>", methods=["POST"])
@login_required
def delete_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    db.session.delete(invoice)
    db.session.commit()
    flash("Invoice deleted successfully.", "success")
    return redirect(url_for("billing.billing_index"))


@billing_bp.route("/billing/<int:invoice_id>")
@login_required
def view_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template("invoice_detail.html", invoice=invoice, title="Invoice Details")


@billing_bp.route("/billing/print/<int:invoice_id>")
@login_required
def print_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template("invoice_print.html", invoice=invoice, title="Print Invoice")


@billing_bp.route("/billing/pdf/<int:invoice_id>")
@login_required
def download_invoice_pdf(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    summary_rows = [
        ("Invoice #", str(invoice.id)),
        ("Patient", invoice.patient.full_name),
        ("Patient ID", invoice.patient.patient_id),
        ("Invoice Date", invoice.invoice_date.strftime("%Y-%m-%d") if invoice.invoice_date else "N/A"),
        ("Due Date", invoice.due_date.strftime("%Y-%m-%d") if invoice.due_date else "N/A"),
        ("Status", invoice.status),
        ("Final Amount", str(invoice.final_amount)),
    ]
    item_rows = [["Item", "Category", "Qty", "Unit Price", "Total"]]
    for item in invoice.items:
        item_rows.append([
            item.item_name,
            item.category,
            str(item.quantity),
            str(item.unit_price),
            str(item.total),
        ])
    return _build_pdf_response(
        "Invoice PDF",
        summary_rows,
        item_rows,
        f"invoice_{invoice.id}",
    )


@billing_bp.route("/billing/payment/<int:invoice_id>", methods=["GET", "POST"])
@login_required
def record_payment(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    if request.method == "POST":
        amount = Decimal(str(request.form.get("amount_paid", 0)))
        existing_paid = sum(_money(payment.amount_paid) for payment in invoice.payments)
        if amount <= 0:
            flash("Payment amount must be greater than zero.", "danger")
            return redirect(url_for("billing.record_payment", invoice_id=invoice.id))
        if amount > _invoice_balance(invoice):
            flash("Payment cannot exceed the invoice balance.", "danger")
            return redirect(url_for("billing.record_payment", invoice_id=invoice.id))

        reference = request.form.get("transaction_reference", "").strip()
        if reference and Payment.query.filter(Payment.invoice_id == invoice.id, Payment.transaction_reference == reference).first():
            flash("A payment with this transaction reference already exists.", "danger")
            return redirect(url_for("billing.record_payment", invoice_id=invoice.id))

        payment = Payment(
            invoice_id=invoice.id,
            payment_date=datetime.strptime(request.form.get("payment_date", ""), "%Y-%m-%d").date() if request.form.get("payment_date") else date.today(),
            amount_paid=amount,
            payment_method=request.form.get("payment_method", "Cash").strip(),
            transaction_reference=reference,
            received_by=request.form.get("received_by", "").strip(),
            remarks=request.form.get("remarks", "").strip(),
        )
        db.session.add(payment)
        _update_invoice_status(invoice)
        db.session.commit()
        flash("Payment recorded successfully.", "success")
        audit_log = AuditLog(user_id=current_user.id, action="Payment Recorded", entity_type="Payment", entity_id=payment.id, details=f"Payment of ${amount} recorded for Invoice #{invoice.id} by '{current_user.username}'.")
        db.session.add(audit_log)
        return redirect(url_for("billing.view_invoice", invoice_id=invoice.id))

    return render_template(
        "payment_form.html",
        invoice=invoice,
        methods=PAYMENT_METHODS,
        title="Record Payment",
    )


@billing_bp.route("/billing/receipt/<int:payment_id>")
@login_required
def print_receipt(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    return render_template("receipt_print.html", payment=payment, title="Receipt")


@billing_bp.route("/billing/receipt/pdf/<int:payment_id>")
@login_required
def download_receipt_pdf(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    summary_rows = [
        ("Payment #", str(payment.id)),
        ("Invoice #", str(payment.invoice_id)),
        ("Patient", payment.invoice.patient.full_name),
        ("Date", payment.payment_date.strftime("%Y-%m-%d") if payment.payment_date else "N/A"),
        ("Amount Paid", str(payment.amount_paid)),
        ("Method", payment.payment_method),
        ("Reference", payment.transaction_reference or "N/A"),
        ("Received By", payment.received_by or "N/A"),
    ]
    table_data = [["Field", "Value"]]
    for key, value in summary_rows:
        table_data.append([key, value])
    return _build_pdf_response(
        "Receipt PDF",
        [],
        table_data,
        f"receipt_{payment.id}",
    )


@billing_bp.route("/billing/insurance")
def insurance_placeholder():
    return render_template("insurance_placeholder.html", title="M-Pesa / Insurance Placeholder")


@billing_bp.route("/billing/dashboard")
@login_required
def billing_dashboard():
    today = date.today()
    monthly_start = date(today.year, today.month, 1)
    today_revenue = sum(_money(payment.amount_paid) for payment in Payment.query.filter(Payment.payment_date == today).all())
    monthly_revenue = sum(_money(payment.amount_paid) for payment in Payment.query.filter(Payment.payment_date >= monthly_start).all())
    outstanding_bills = sum(_money(invoice.final_amount) for invoice in Invoice.query.filter(Invoice.status != "Paid").all())
    paid_bills = Invoice.query.filter(Invoice.status == "Paid").count()
    pending_bills = Invoice.query.filter(Invoice.status == "Pending").count()
    recent_payments = Payment.query.order_by(Payment.payment_date.desc()).limit(5).all()

    return render_template(
        "billing_dashboard.html",
        today_revenue=today_revenue,
        monthly_revenue=monthly_revenue,
        outstanding_bills=outstanding_bills,
        paid_bills=paid_bills,
        pending_bills=pending_bills,
        recent_payments=recent_payments,
        title="Billing Dashboard",
    )


@billing_bp.route("/billing/reports")
@login_required
def billing_reports():
    daily = []
    weekly = []
    monthly = []
    department = []
    doctor = []

    for payment in Payment.query.order_by(Payment.payment_date.asc()).all():
        daily.append((payment.payment_date.strftime("%Y-%m-%d"), float(payment.amount_paid)))

    return render_template(
        "reports.html",
        daily=daily,
        weekly=weekly,
        monthly=monthly,
        department=department,
        doctor=doctor,
        title="Billing Reports",
    )
