import functools
import os
from datetime import datetime

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from admin import STATUS_LABELS, admin_bp
from database import DB_PATH, close_db, get_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-coffeeshop-secret-change-me")
app.config["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD", "admin123")

app.teardown_appcontext(close_db)


@app.template_filter("currency")
def currency_filter(value):
    try:
        return f"{int(value):,}".replace(",", ".") + "đ"
    except (TypeError, ValueError):
        return value


def init_db_if_needed():
    from seed_data import ensure_admin_data, seed

    if not DB_PATH.exists():
        seed()
    ensure_admin_data()


@app.before_request
def load_current_customer():
    g.customer = None
    customer_id = session.get("customer_id")
    if customer_id:
        g.customer = get_db().execute(
            "SELECT * FROM user WHERE id = ?", (customer_id,)
        ).fetchone()


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.customer is None:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.route("/")
def home():
    return render_template("index.html", active_page="home")


@app.route("/products")
def products_page():
    return render_template("products.html", active_page="products")


@app.route("/contact")
def contact_page():
    return render_template("contact.html", active_page="contact")


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.customer:
        return redirect(url_for("home"))

    form = {"name": "", "email": "", "phone": ""}
    if request.method == "POST":
        form["name"] = (request.form.get("name") or "").strip()
        form["email"] = (request.form.get("email") or "").strip().lower()
        form["phone"] = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        errors = []
        if not form["name"]:
            errors.append("Vui lòng nhập họ tên.")
        if not form["email"] or "@" not in form["email"]:
            errors.append("Vui lòng nhập email hợp lệ.")
        if len(password) < 6:
            errors.append("Mật khẩu cần ít nhất 6 ký tự.")
        if password != confirm_password:
            errors.append("Mật khẩu xác nhận không khớp.")

        db = get_db()
        if not errors and db.execute(
            "SELECT id FROM user WHERE email = ?", (form["email"],)
        ).fetchone():
            errors.append("Email này đã được đăng ký.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", form=form)

        username = form["email"].split("@")[0]
        db.execute(
            """INSERT INTO user (name, email, username, password_hash, phone, created_at, is_admin)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (form["name"], form["email"], username, generate_password_hash(password),
             form["phone"], datetime.now().isoformat()),
        )
        db.commit()
        flash("Đăng ký thành công! Vui lòng đăng nhập.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.customer:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        user = get_db().execute(
            "SELECT * FROM user WHERE email = ? AND is_admin = 0", (email,)
        ).fetchone()

        if user and user["password_hash"] and check_password_hash(user["password_hash"], password):
            session["customer_id"] = user["id"]
            next_url = request.args.get("next") or url_for("home")
            return redirect(next_url)

        flash("Email hoặc mật khẩu không đúng.", "error")

    return render_template("login.html", active_page="login")


@app.route("/logout")
def logout():
    session.pop("customer_id", None)
    return redirect(url_for("home"))


@app.route("/cart")
def cart_page():
    return render_template("cart.html", active_page="cart")


@app.route("/checkout")
@login_required
def checkout_page():
    return render_template("checkout.html")


@app.route("/api/checkout", methods=["POST"])
@login_required
def api_checkout():
    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    note = (data.get("note") or "").strip()

    if not items:
        return jsonify({"error": "Giỏ hàng đang trống."}), 400

    db = get_db()
    order_items = []
    total = 0
    for item in items:
        product_id = item.get("product_id")
        quantity = item.get("quantity")
        if not isinstance(product_id, int) or not isinstance(quantity, int) or quantity < 1:
            return jsonify({"error": "Dữ liệu giỏ hàng không hợp lệ."}), 400

        product = db.execute(
            "SELECT id, price FROM product WHERE id = ?", (product_id,)
        ).fetchone()
        if product is None:
            return jsonify({"error": "Một sản phẩm trong giỏ không còn tồn tại."}), 400

        order_items.append((product["id"], quantity, product["price"]))
        total += product["price"] * quantity

    cur = db.execute(
        'INSERT INTO "order" (user_id, status, total_amount, note, created_at) VALUES (?, ?, ?, ?, ?)',
        (g.customer["id"], "pending", total, note or None, datetime.now().isoformat()),
    )
    order_id = cur.lastrowid
    db.executemany(
        "INSERT INTO order_item (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
        [(order_id, pid, qty, price) for pid, qty, price in order_items],
    )
    db.commit()

    return jsonify({"order_id": order_id})


@app.route("/orders")
@login_required
def my_orders():
    orders = get_db().execute(
        'SELECT * FROM "order" WHERE user_id = ? ORDER BY created_at DESC', (g.customer["id"],)
    ).fetchall()
    return render_template(
        "my_orders.html", orders=orders, status_labels=STATUS_LABELS, active_page="orders"
    )


@app.route("/orders/<int:order_id>")
@login_required
def order_detail_page(order_id):
    db = get_db()
    order = db.execute(
        'SELECT * FROM "order" WHERE id = ? AND user_id = ?', (order_id, g.customer["id"])
    ).fetchone()
    if order is None:
        flash("Không tìm thấy đơn hàng.", "error")
        return redirect(url_for("my_orders"))

    items = db.execute(
        """SELECT oi.*, p.name AS product_name, p.image AS product_image
           FROM order_item oi JOIN product p ON p.id = oi.product_id
           WHERE oi.order_id = ? ORDER BY oi.id""",
        (order_id,),
    ).fetchall()

    return render_template(
        "order_detail.html", order=order, items=items, status_labels=STATUS_LABELS
    )


@app.route("/api/categories")
def api_categories():
    db = get_db()
    rows = db.execute("SELECT id, name, description FROM category ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/products")
def api_products():
    db = get_db()
    category_id = request.args.get("category_id")
    if category_id and category_id != "all":
        rows = db.execute(
            "SELECT * FROM product WHERE category_id = ? ORDER BY published_date DESC",
            (category_id,),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM product ORDER BY published_date DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/contact", methods=["POST"])
def api_contact():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    message = (data.get("message") or "").strip()

    if not name or not email or len(message) < 10:
        return jsonify({"error": "Dữ liệu không hợp lệ."}), 400

    db = get_db()
    db.execute(
        "INSERT INTO feedback (name, email, message, created_at) VALUES (?, ?, ?, ?)",
        (name, email, message, datetime.now().isoformat()),
    )
    db.commit()
    return jsonify({"message": f"Cảm ơn {name}, chúng tôi đã nhận được góp ý của bạn!"})


app.register_blueprint(admin_bp)

init_db_if_needed()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
