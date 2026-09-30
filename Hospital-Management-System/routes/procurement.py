from datetime import date, datetime
from decimal import Decimal
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from models import AuditLog
from models import db, User, HRDepartment, Supplier, ProductCatalog, PurchaseRequest, PurchaseRequestItem, PurchaseOrder, PurchaseOrderItem, GoodsReceivedNote, GoodsReceivedItem
from routes.auth import role_required

procurement_bp = Blueprint("procurement", __name__, url_prefix="/procurement", template_folder="../templates/procurement")

# Helper functions for generating IDs
def generate_supplier_id() -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    count = Supplier.query.count() + 1
    return f"SUP-{today}-{count:04d}"

def generate_request_number() -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    count = PurchaseRequest.query.count() + 1
    return f"PR-{today}-{count:04d}"

def generate_po_number() -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    count = PurchaseOrder.query.count() + 1
    return f"PO-{today}-{count:04d}"

def generate_grn_number() -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    count = GoodsReceivedNote.query.count() + 1
    return f"GRN-{today}-{count:04d}"


@procurement_bp.route("/dashboard")
@login_required
@role_required("Admin", "Procurement Officer") # Assuming a 'Procurement Officer' role
def dashboard():
    """Procurement Dashboard displaying key metrics."""
    today = date.today()
    
    pending_requests = PurchaseRequest.query.filter(
        or_(
            PurchaseRequest.status == "Pending Department Approval",
            PurchaseRequest.status == "Pending Proc Approval"
        )
    ).count()

    pending_pos = PurchaseOrder.query.filter(
        or_(
            PurchaseOrder.status == "Draft",
            PurchaseOrder.status == "Sent",
            PurchaseOrder.status == "Partially Received"
        )
    ).count()

    deliveries_today = PurchaseOrder.query.filter(
        PurchaseOrder.expected_delivery_date == today,
        PurchaseOrder.status.in_(["Sent", "Partially Received"])
    ).count()

    # Monthly Procurement Cost (last 6 months)
    six_months_ago = today - timedelta(days=180)
    monthly_costs = db.session.query(
        func.strftime('%Y-%m', PurchaseOrder.order_date).label('month'),
        func.sum(PurchaseOrder.total_amount).label('total')
    ).filter(PurchaseOrder.order_date >= six_months_ago, PurchaseOrder.status.in_(['Received', 'Partially Received']))\
     .group_by('month').order_by('month').all()

    # Top Suppliers (by total spend)
    top_suppliers = db.session.query(
        Supplier.company_name,
        func.sum(PurchaseOrder.total_amount).label('total_spend')
    ).join(PurchaseOrder).filter(PurchaseOrder.status.in_(['Received', 'Partially Received']))\
     .group_by(Supplier.company_name).order_by(func.sum(PurchaseOrder.total_amount).desc()).limit(5).all()

    stats = {
        "pending_requests": pending_requests,
        "pending_pos": pending_pos,
        "deliveries_today": deliveries_today,
        "monthly_costs": {m.month: float(m.total) for m in monthly_costs},
        "top_suppliers": [{"name": s.company_name, "spend": float(s.total_spend)} for s in top_suppliers]
    }

    return render_template("procurement_dashboard.html", title="Procurement Dashboard", stats=stats)


# --- Supplier Management ---
@procurement_bp.route("/suppliers")
@login_required
@role_required("Admin", "Procurement Officer")
def list_suppliers():
    suppliers = Supplier.query.order_by(Supplier.company_name).all()
    return render_template("suppliers.html", title="Suppliers", suppliers=suppliers)

@procurement_bp.route("/suppliers/add", methods=["GET", "POST"])
@login_required
@role_required("Admin", "Procurement Officer")
def add_supplier():
    if request.method == "POST":
        company_name = request.form.get("company_name")
        contact_person = request.form.get("contact_person")
        phone = request.form.get("phone")
        email = request.form.get("email")
        address = request.form.get("address")
        tax_number = request.form.get("tax_number")
        status = request.form.get("status", "Active")

        if Supplier.query.filter_by(company_name=company_name).first():
            flash("Supplier with this company name already exists.", "danger")
            return redirect(request.url)
        if email and Supplier.query.filter_by(email=email).first():
            flash("Supplier with this email already exists.", "danger")
            return redirect(request.url)
        if tax_number and Supplier.query.filter_by(tax_number=tax_number).first():
            flash("Supplier with this tax number already exists.", "danger")
            return redirect(request.url)

        new_supplier = Supplier(
            supplier_id=generate_supplier_id(),
            company_name=company_name,
            contact_person=contact_person,
            phone=phone,
            email=email,
            address=address,
            tax_number=tax_number,
            status=status
        )
        db.session.add(new_supplier)
        db.session.commit()
        audit_log = AuditLog(user_id=current_user.id, action="Supplier Created", entity_type="Supplier", entity_id=new_supplier.id, details=f"Supplier '{new_supplier.company_name}' added.")
        db.session.add(audit_log)
        flash("Supplier added successfully.", "success")
        return redirect(url_for("procurement.list_suppliers"))
    return render_template("supplier_form.html", title="Add Supplier")

@procurement_bp.route("/suppliers/edit/<int:supplier_id>", methods=["GET", "POST"])
@login_required
@role_required("Admin", "Procurement Officer")
def edit_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    if request.method == "POST":
        supplier.company_name = request.form.get("company_name")
        supplier.contact_person = request.form.get("contact_person")
        supplier.phone = request.form.get("phone")
        supplier.email = request.form.get("email")
        supplier.address = request.form.get("address")
        supplier.tax_number = request.form.get("tax_number")
        supplier.status = request.form.get("status", "Active")
        db.session.commit()
        audit_log = AuditLog(user_id=current_user.id, action="Supplier Updated", entity_type="Supplier", entity_id=supplier.id, details=f"Supplier '{supplier.company_name}' updated.")
        db.session.add(audit_log)
        flash("Supplier updated successfully.", "success")
        return redirect(url_for("procurement.list_suppliers"))
    return render_template("supplier_form.html", title="Edit Supplier", supplier=supplier)

@procurement_bp.route("/suppliers/delete/<int:supplier_id>", methods=["POST"])
@login_required
@role_required("Admin", "Procurement Officer")
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    audit_log = AuditLog(user_id=current_user.id, action="Supplier Deleted", entity_type="Supplier", entity_id=supplier.id, details=f"Supplier '{supplier.company_name}' deleted.")
    db.session.add(audit_log)
    db.session.delete(supplier)
    db.session.commit()
    flash("Supplier deleted successfully.", "success")
    return redirect(url_for("procurement.list_suppliers"))


# --- Product Catalog Management ---
@procurement_bp.route("/products")
@login_required
@role_required("Admin", "Procurement Officer", "Inventory Manager") # Assuming 'Inventory Manager' role
def list_products():
    products = ProductCatalog.query.order_by(ProductCatalog.name).all()
    return render_template("products.html", title="Product Catalog", products=products)

@procurement_bp.route("/products/add", methods=["GET", "POST"])
@login_required
@role_required("Admin", "Procurement Officer", "Inventory Manager")
def add_product():
    suppliers = Supplier.query.filter_by(status="Active").all()
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        category = request.form.get("category")
        unit_of_measure = request.form.get("unit_of_measure")
        sku = request.form.get("sku")
        reorder_level = request.form.get("reorder_level", type=int)
        preferred_supplier_id = request.form.get("preferred_supplier_id", type=int)

        if ProductCatalog.query.filter_by(name=name).first():
            flash("Product with this name already exists.", "danger")
            return redirect(request.url)
        if sku and ProductCatalog.query.filter_by(sku=sku).first():
            flash("Product with this SKU already exists.", "danger")
            return redirect(request.url)

        new_product = ProductCatalog(
            name=name,
            description=description,
            category=category,
            unit_of_measure=unit_of_measure,
            sku=sku,
            reorder_level=reorder_level,
            preferred_supplier_id=preferred_supplier_id if preferred_supplier_id else None
        )
        db.session.add(new_product)
        db.session.commit()
        audit_log = AuditLog(user_id=current_user.id, action="Product Added", entity_type="ProductCatalog", entity_id=new_product.id, details=f"Product '{new_product.name}' added to catalog.")
        db.session.add(audit_log)
        flash("Product added to catalog successfully.", "success")
        return redirect(url_for("procurement.list_products"))
    return render_template("product_form.html", title="Add Product", suppliers=suppliers)


# --- Purchase Requests ---
@procurement_bp.route("/requests")
@login_required
@role_required("Admin", "Procurement Officer", "HR Manager") # HR Manager for department approval
def list_purchase_requests():
    requests = PurchaseRequest.query.order_by(PurchaseRequest.request_date.desc()).all()
    return render_template("purchase_requests.html", title="Purchase Requests", requests=requests)

@procurement_bp.route("/requests/create", methods=["GET", "POST"])
@login_required
@role_required("Admin", "Doctor", "Nurse", "Pharmacist", "Laboratory Technician", "HR Manager") # Any staff can create a request
def create_purchase_request():
    departments = HRDepartment.query.all()
    products = ProductCatalog.query.order_by(ProductCatalog.name).all()
    if request.method == "POST":
        department_id = request.form.get("department_id", type=int)
        priority = request.form.get("priority")
        items_data = request.form.getlist("item_id") # List of product IDs
        quantities_data = request.form.getlist("quantity") # List of quantities

        if not department_id or not priority or not items_data or not quantities_data:
            flash("Missing required fields.", "danger")
            return redirect(request.url)
        if len(items_data) != len(quantities_data):
            flash("Mismatch in item and quantity data.", "danger")
            return redirect(request.url)

        new_request = PurchaseRequest(
            request_number=generate_request_number(),
            department_id=department_id,
            requested_by_id=current_user.id,
            priority=priority,
            status="Pending Department Approval" # Initial status
        )
        db.session.add(new_request)
        db.session.flush() # To get new_request.id

        for i in range(len(items_data)):
            product_id = int(items_data[i])
            quantity = int(quantities_data[i])
            if quantity <= 0:
                flash("Quantity must be positive for all items.", "danger")
                db.session.rollback()
                return redirect(request.url)
            
            item = PurchaseRequestItem(
                request_id=new_request.id,
                product_id=product_id,
                quantity=quantity
            )
            db.session.add(item)
        
        db.session.commit()
        flash("Purchase request created successfully.", "success")
        audit_log = AuditLog(user_id=current_user.id, action="Purchase Request Created", entity_type="PurchaseRequest", entity_id=new_request.id, details=f"PR #{new_request.request_number} created by '{current_user.username}'.")
        db.session.add(audit_log)
        return redirect(url_for("procurement.list_purchase_requests"))

    return render_template("purchase_request_form.html", title="Create Purchase Request", departments=departments, products=products)


# --- Purchase Orders ---
@procurement_bp.route("/orders")
@login_required
@role_required("Admin", "Procurement Officer")
def list_purchase_orders():
    orders = PurchaseOrder.query.order_by(PurchaseOrder.order_date.desc()).all()
    return render_template("purchase_orders.html", title="Purchase Orders", orders=orders)

@procurement_bp.route("/orders/generate", methods=["GET", "POST"])
@login_required
@role_required("Admin", "Procurement Officer")
def generate_po():
    suppliers = Supplier.query.filter_by(status="Active").all()
    products = ProductCatalog.query.order_by(ProductCatalog.name).all()
    purchase_requests = PurchaseRequest.query.filter_by(status="Approved").all()

    if request.method == "POST":
        supplier_id = request.form.get("supplier_id", type=int)
        expected_delivery_date_str = request.form.get("expected_delivery_date")
        requisition_id = request.form.get("requisition_id", type=int)
        
        item_ids = request.form.getlist("item_id")
        quantities = request.form.getlist("quantity")
        unit_prices = request.form.getlist("unit_price")

        if not supplier_id or not item_ids or not quantities or not unit_prices:
            flash("Missing required fields for PO.", "danger")
            return redirect(request.url)

        expected_delivery_date = datetime.strptime(expected_delivery_date_str, "%Y-%m-%d").date() if expected_delivery_date_str else None

        new_po = PurchaseOrder(
            po_number=generate_po_number(),
            supplier_id=supplier_id,
            expected_delivery_date=expected_delivery_date,
            requisition_id=requisition_id if requisition_id else None,
            status="Draft"
        )
        db.session.add(new_po)
        db.session.flush()

        total_amount = Decimal('0.00')
        for i in range(len(item_ids)):
            product_id = int(item_ids[i])
            quantity = int(quantities[i])
            unit_price = Decimal(unit_prices[i])

            if quantity <= 0 or unit_price <= 0:
                flash("Quantity and Unit Price must be positive for all items.", "danger")
                db.session.rollback()
                return redirect(request.url)

            po_item = PurchaseOrderItem(
                po_id=new_po.id,
                product_id=product_id,
                quantity_ordered=quantity,
                unit_price=unit_price
            )
            db.session.add(po_item)
            total_amount += (unit_price * quantity)
        
        new_po.total_amount = total_amount
        db.session.commit()
        flash(f"Purchase Order {new_po.po_number} generated successfully.", "success")
        audit_log = AuditLog(user_id=current_user.id, action="Purchase Order Generated", entity_type="PurchaseOrder", entity_id=new_po.id, details=f"PO #{new_po.po_number} generated for supplier '{new_po.supplier.company_name}'.")
        db.session.add(audit_log)
        return redirect(url_for("procurement.list_purchase_orders"))

    return render_template("purchase_order_form.html", title="Generate Purchase Order", suppliers=suppliers, products=products, purchase_requests=purchase_requests)


# --- Goods Receiving ---
@procurement_bp.route("/grn/receive/<int:po_id>", methods=["GET", "POST"])
@login_required
@role_required("Admin", "Procurement Officer", "Inventory Manager")
def receive_goods(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    if po.status == "Received":
        flash("This Purchase Order has already been fully received.", "info")
        return redirect(url_for("procurement.list_purchase_orders"))

    if request.method == "POST":
        received_by_id = current_user.id
        remarks = request.form.get("remarks")
        
        received_quantities = {}
        for item in po.items:
            received_qty = request.form.get(f"received_qty_{item.id}", type=int)
            if received_qty is not None:
                received_quantities[item.id] = received_qty
        
        if not received_quantities:
            flash("No items selected for receiving.", "danger")
            return redirect(request.url)

        new_grn = GoodsReceivedNote(
            grn_number=generate_grn_number(),
            po_id=po.id,
            received_by_id=received_by_id,
            remarks=remarks
        )
        db.session.add(new_grn)
        db.session.flush()

        all_items_received = True
        for po_item in po.items:
            qty_to_receive = received_quantities.get(po_item.id, 0)
            if qty_to_receive > 0:
                if qty_to_receive > (po_item.quantity_ordered - po_item.quantity_received):
                    flash(f"Cannot receive more than ordered for {po_item.product.name}.", "danger")
                    db.session.rollback()
                    return redirect(request.url)
                
                grn_item = GoodsReceivedItem(
                    grn_id=new_grn.id,
                    po_item_id=po_item.id,
                    product_id=po_item.product_id,
                    quantity_received=qty_to_receive
                )
                db.session.add(grn_item)

                # Update PurchaseOrderItem's received quantity
                po_item.quantity_received += qty_to_receive

                # Update ProductCatalog's current stock (Inventory Integration)
                product = ProductCatalog.query.get(po_item.product_id)
                if product:
                    product.current_stock += qty_to_receive
                
            if po_item.quantity_received < po_item.quantity_ordered:
                all_items_received = False
        
        po.status = "Received" if all_items_received else "Partially Received"
        db.session.commit()
        flash(f"Goods Received Note {new_grn.grn_number} created successfully. PO status updated.", "success")
        audit_log = AuditLog(user_id=current_user.id, action="Goods Received", entity_type="GoodsReceivedNote", entity_id=new_grn.id, details=f"GRN #{new_grn.grn_number} created for PO #{po.po_number}.")
        db.session.add(audit_log)
        return redirect(url_for("procurement.list_purchase_orders"))

    return render_template("receive_goods.html", title=f"Receive Goods for PO {po.po_number}", po=po)


# --- Reports (Placeholders) ---
@procurement_bp.route("/reports/purchase_report")
@login_required
@role_required("Admin", "Procurement Officer")
def purchase_report():
    flash("Purchase Report functionality is under development.", "info")
    return render_template("reports.html", title="Purchase Report")

@procurement_bp.route("/reports/supplier_performance")
@login_required
@role_required("Admin", "Procurement Officer")
def supplier_performance_report():
    flash("Supplier Performance Report functionality is under development.", "info")
    return render_template("reports.html", title="Supplier Performance Report")