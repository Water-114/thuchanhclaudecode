"""Admin dashboard blueprint: session-gated /admin area, separate from the public site."""
import functools
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from database import get_db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

STATUS_LABELS = {
    "pending": "Chờ xác nhận",
    "confirmed": "Đã xác nhận",
    "completed": "Hoàn thành",
    "cancelled": "Đã hủy",
}
STATUS_ORDER = ["pending", "confirmed", "completed", "cancelled"]


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("is_admin"):
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        password = request.form.get("password", "")
        if password and password == current_app.config["ADMIN_PASSWORD"]:
            session["is_admin"] = True
            next_url = request.args.get("next") or url_for("admin.dashboard")
            return redirect(next_url)
        flash("Mật khẩu không đúng.", "error")

    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@admin_required
def dashboard():
    db = get_db()

    total_orders = db.execute('SELECT COUNT(*) c FROM "order"').fetchone()["c"]
    revenue = db.execute(
        'SELECT COALESCE(SUM(total_amount), 0) r FROM "order" WHERE status = ?', ("completed",)
    ).fetchone()["r"]
    total_customers = db.execute("SELECT COUNT(*) c FROM user WHERE is_admin = 0").fetchone()["c"]
    total_products = db.execute("SELECT COUNT(*) c FROM product").fetchone()["c"]

    status_counts = {
        row["status"]: row["c"]
        for row in db.execute('SELECT status, COUNT(*) c FROM "order" GROUP BY status').fetchall()
    }

    recent_orders = db.execute(
        """SELECT o.id, o.status, o.total_amount, o.created_at, u.name AS customer_name
           FROM "order" o JOIN user u ON u.id = o.user_id
           ORDER BY o.created_at DESC LIMIT 8"""
    ).fetchall()

    top_products = db.execute(
        """SELECT p.name, SUM(oi.quantity) AS sold
           FROM order_item oi JOIN product p ON p.id = oi.product_id
           GROUP BY oi.product_id ORDER BY sold DESC LIMIT 5"""
    ).fetchall()

    return render_template(
        "admin/dashboard.html",
        active_page="dashboard",
        stats={
            "total_orders": total_orders,
            "revenue": revenue,
            "total_customers": total_customers,
            "total_products": total_products,
        },
        status_counts=status_counts,
        status_labels=STATUS_LABELS,
        recent_orders=recent_orders,
        top_products=top_products,
    )


# ---------- Products CRUD ----------

def normalize_product_form(form):
    return {
        "name": (form.get("name") or "").strip(),
        "price": (form.get("price") or "").strip(),
        "image": (form.get("image") or "").strip(),
        "description": (form.get("description") or "").strip(),
        "category_id": (form.get("category_id") or "").strip(),
    }


def validate_product(form):
    errors = []
    if not form["name"]:
        errors.append("Vui lòng nhập tên sản phẩm.")
    if not form["price"].isdigit() or int(form["price"]) <= 0:
        errors.append("Giá sản phẩm phải là số lớn hơn 0.")
    if not form["category_id"].isdigit():
        errors.append("Vui lòng chọn danh mục.")
    return errors


@admin_bp.route("/products")
@admin_required
def products_list():
    db = get_db()
    q = request.args.get("q", "").strip()
    category_id = request.args.get("category_id", "").strip()

    query = """SELECT p.*, c.name AS category_name FROM product p
               JOIN category c ON c.id = p.category_id WHERE 1 = 1"""
    params = []
    if q:
        query += " AND p.name LIKE ?"
        params.append(f"%{q}%")
    if category_id.isdigit():
        query += " AND p.category_id = ?"
        params.append(category_id)
    query += " ORDER BY p.id DESC"

    rows = db.execute(query, params).fetchall()
    categories = db.execute("SELECT * FROM category ORDER BY name").fetchall()
    return render_template(
        "admin/products.html", active_page="products", products=rows,
        q=q, category_id=category_id, categories=categories,
    )


@admin_bp.route("/products/add", methods=["GET", "POST"])
@admin_required
def product_add():
    db = get_db()
    categories = db.execute("SELECT * FROM category ORDER BY name").fetchall()

    if request.method == "POST":
        form = normalize_product_form(request.form)
        errors = validate_product(form)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/product_form.html", active_page="products", mode="add",
                product=form, categories=categories,
            )
        db.execute(
            """INSERT INTO product (name, price, image, description, published_date, category_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (form["name"], int(form["price"]), form["image"], form["description"],
             datetime.now().isoformat(), int(form["category_id"])),
        )
        db.commit()
        flash(f"Đã thêm sản phẩm \"{form['name']}\".", "success")
        return redirect(url_for("admin.products_list"))

    return render_template(
        "admin/product_form.html", active_page="products", mode="add",
        product={}, categories=categories,
    )


@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def product_edit(product_id):
    db = get_db()
    categories = db.execute("SELECT * FROM category ORDER BY name").fetchall()
    existing = db.execute("SELECT * FROM product WHERE id = ?", (product_id,)).fetchone()
    if existing is None:
        flash("Không tìm thấy sản phẩm.", "error")
        return redirect(url_for("admin.products_list"))

    if request.method == "POST":
        form = normalize_product_form(request.form)
        errors = validate_product(form)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/product_form.html", active_page="products", mode="edit",
                product=form, categories=categories, product_id=product_id,
            )
        db.execute(
            """UPDATE product SET name = ?, price = ?, image = ?, description = ?, category_id = ?
               WHERE id = ?""",
            (form["name"], int(form["price"]), form["image"], form["description"],
             int(form["category_id"]), product_id),
        )
        db.commit()
        flash(f"Đã cập nhật sản phẩm \"{form['name']}\".", "success")
        return redirect(url_for("admin.products_list"))

    return render_template(
        "admin/product_form.html", active_page="products", mode="edit",
        product=dict(existing), categories=categories, product_id=product_id,
    )


@admin_bp.route("/products/<int:product_id>/delete", methods=["POST"])
@admin_required
def product_delete(product_id):
    db = get_db()
    in_use = db.execute(
        "SELECT COUNT(*) c FROM order_item WHERE product_id = ?", (product_id,)
    ).fetchone()["c"]
    if in_use > 0:
        flash("Không thể xóa: sản phẩm này đã có trong đơn hàng.", "error")
        return redirect(url_for("admin.products_list"))

    db.execute("DELETE FROM product WHERE id = ?", (product_id,))
    db.commit()
    flash("Đã xóa sản phẩm.", "success")
    return redirect(url_for("admin.products_list"))


# ---------- Categories CRUD ----------

def normalize_category_form(form):
    return {
        "name": (form.get("name") or "").strip(),
        "description": (form.get("description") or "").strip(),
    }


def validate_category(form):
    errors = []
    if not form["name"]:
        errors.append("Vui lòng nhập tên danh mục.")
    return errors


@admin_bp.route("/categories")
@admin_required
def categories_list():
    db = get_db()
    rows = db.execute(
        """SELECT c.*, (SELECT COUNT(*) FROM product p WHERE p.category_id = c.id) AS product_count
           FROM category c ORDER BY c.id"""
    ).fetchall()
    return render_template("admin/categories.html", active_page="categories", categories=rows)


@admin_bp.route("/categories/add", methods=["GET", "POST"])
@admin_required
def category_add():
    if request.method == "POST":
        form = normalize_category_form(request.form)
        errors = validate_category(form)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/category_form.html", active_page="categories", mode="add", category=form,
            )
        db = get_db()
        db.execute(
            "INSERT INTO category (name, description) VALUES (?, ?)",
            (form["name"], form["description"]),
        )
        db.commit()
        flash(f"Đã thêm danh mục \"{form['name']}\".", "success")
        return redirect(url_for("admin.categories_list"))

    return render_template(
        "admin/category_form.html", active_page="categories", mode="add", category={},
    )


@admin_bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@admin_required
def category_edit(category_id):
    db = get_db()
    existing = db.execute("SELECT * FROM category WHERE id = ?", (category_id,)).fetchone()
    if existing is None:
        flash("Không tìm thấy danh mục.", "error")
        return redirect(url_for("admin.categories_list"))

    if request.method == "POST":
        form = normalize_category_form(request.form)
        errors = validate_category(form)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/category_form.html", active_page="categories", mode="edit",
                category=form, category_id=category_id,
            )
        db.execute(
            "UPDATE category SET name = ?, description = ? WHERE id = ?",
            (form["name"], form["description"], category_id),
        )
        db.commit()
        flash(f"Đã cập nhật danh mục \"{form['name']}\".", "success")
        return redirect(url_for("admin.categories_list"))

    return render_template(
        "admin/category_form.html", active_page="categories", mode="edit",
        category=dict(existing), category_id=category_id,
    )


@admin_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def category_delete(category_id):
    db = get_db()
    in_use = db.execute(
        "SELECT COUNT(*) c FROM product WHERE category_id = ?", (category_id,)
    ).fetchone()["c"]
    if in_use > 0:
        flash("Không thể xóa: vẫn còn sản phẩm thuộc danh mục này.", "error")
        return redirect(url_for("admin.categories_list"))

    db.execute("DELETE FROM category WHERE id = ?", (category_id,))
    db.commit()
    flash("Đã xóa danh mục.", "success")
    return redirect(url_for("admin.categories_list"))


# ---------- Orders ----------

@admin_bp.route("/orders")
@admin_required
def orders_list():
    db = get_db()
    status = request.args.get("status", "").strip()

    query = """SELECT o.*, u.name AS customer_name FROM "order" o
               JOIN user u ON u.id = o.user_id WHERE 1 = 1"""
    params = []
    if status in STATUS_LABELS:
        query += " AND o.status = ?"
        params.append(status)
    query += " ORDER BY o.created_at DESC"

    orders = db.execute(query, params).fetchall()
    return render_template(
        "admin/orders.html", active_page="orders", orders=orders,
        status=status, status_labels=STATUS_LABELS, status_order=STATUS_ORDER,
    )


@admin_bp.route("/orders/<int:order_id>")
@admin_required
def order_detail(order_id):
    db = get_db()
    order = db.execute(
        """SELECT o.*, u.name AS customer_name, u.email AS customer_email, u.phone AS customer_phone
           FROM "order" o JOIN user u ON u.id = o.user_id WHERE o.id = ?""",
        (order_id,),
    ).fetchone()
    if order is None:
        flash("Không tìm thấy đơn hàng.", "error")
        return redirect(url_for("admin.orders_list"))

    items = db.execute(
        """SELECT oi.*, p.name AS product_name, p.image AS product_image
           FROM order_item oi JOIN product p ON p.id = oi.product_id
           WHERE oi.order_id = ? ORDER BY oi.id""",
        (order_id,),
    ).fetchall()

    return render_template(
        "admin/order_detail.html", active_page="orders", order=order, items=items,
        status_labels=STATUS_LABELS, status_order=STATUS_ORDER,
    )


@admin_bp.route("/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def order_update_status(order_id):
    db = get_db()
    existing = db.execute('SELECT id FROM "order" WHERE id = ?', (order_id,)).fetchone()
    if existing is None:
        flash("Không tìm thấy đơn hàng.", "error")
        return redirect(url_for("admin.orders_list"))

    new_status = request.form.get("status", "")
    if new_status not in STATUS_LABELS:
        flash("Trạng thái không hợp lệ.", "error")
    else:
        db.execute('UPDATE "order" SET status = ? WHERE id = ?', (new_status, order_id))
        db.commit()
        flash(f"Đã cập nhật đơn #{order_id} sang \"{STATUS_LABELS[new_status]}\".", "success")

    next_url = request.form.get("next") or url_for("admin.order_detail", order_id=order_id)
    return redirect(next_url)


# ---------- Customers ----------

@admin_bp.route("/customers")
@admin_required
def customers_list():
    db = get_db()
    q = request.args.get("q", "").strip()

    query = """SELECT u.*, COUNT(o.id) AS order_count
               FROM user u LEFT JOIN "order" o ON o.user_id = u.id
               WHERE u.is_admin = 0"""
    params = []
    if q:
        query += " AND (u.name LIKE ? OR u.email LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    query += " GROUP BY u.id ORDER BY u.created_at DESC"

    customers = db.execute(query, params).fetchall()
    return render_template(
        "admin/customers.html", active_page="customers", customers=customers, q=q,
    )


@admin_bp.route("/customers/<int:customer_id>")
@admin_required
def customer_detail(customer_id):
    db = get_db()
    customer = db.execute(
        "SELECT * FROM user WHERE id = ? AND is_admin = 0", (customer_id,)
    ).fetchone()
    if customer is None:
        flash("Không tìm thấy khách hàng.", "error")
        return redirect(url_for("admin.customers_list"))

    orders = db.execute(
        'SELECT * FROM "order" WHERE user_id = ? ORDER BY created_at DESC', (customer_id,)
    ).fetchall()

    total_spent = db.execute(
        'SELECT COALESCE(SUM(total_amount), 0) s FROM "order" WHERE user_id = ? AND status = ?',
        (customer_id, "completed"),
    ).fetchone()["s"]

    return render_template(
        "admin/customer_detail.html", active_page="customers", customer=customer,
        orders=orders, total_spent=total_spent, status_labels=STATUS_LABELS,
    )
