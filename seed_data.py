"""Seed coffeeshop.db from the original data/category.csv and data/product.csv files,
plus demo customers/orders for the admin dashboard."""
import csv
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "coffeeshop.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"
CATEGORY_CSV = BASE_DIR / "data" / "category.csv"
PRODUCT_CSV = BASE_DIR / "data" / "product.csv"

CUSTOMER_NAMES = [
    "Nguyễn Văn An", "Trần Thị Bình", "Lê Hoàng Cường", "Phạm Thị Dung",
    "Hoàng Văn Em", "Vũ Thị Phương", "Đặng Minh Giang", "Bùi Thị Hoa",
    "Ngô Văn Khánh", "Đỗ Thị Lan", "Phan Văn Minh", "Trịnh Thị Nga",
    "Lý Văn Phúc", "Dương Thị Quỳnh", "Huỳnh Văn Sơn", "Mai Thị Thu",
    "Đinh Văn Tài", "Lâm Thị Uyên", "Tô Văn Việt", "Chu Thị Yến",
]

SAMPLE_NOTES = [
    "Giao trước 17h giúp mình nhé.",
    "Không dùng đá, ít đường.",
    "Gọi trước khi giao 10 phút.",
    "Giao tại quầy lễ tân, không cần gọi.",
    "Mang thêm ống hút giấy.",
    "Cho xin thêm đường riêng.",
    "Giao vào giờ nghỉ trưa.",
]

ADMIN_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    username TEXT,
    password_hash TEXT,
    phone TEXT,
    created_at TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS "order" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'confirmed', 'completed', 'cancelled')),
    total_amount INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user (id)
);

CREATE TABLE IF NOT EXISTS order_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    price INTEGER NOT NULL,
    FOREIGN KEY (order_id) REFERENCES "order" (id),
    FOREIGN KEY (product_id) REFERENCES product (id)
);
"""


def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    with open(CATEGORY_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        conn.executemany(
            "INSERT INTO category (id, name, description) VALUES (:id, :name, :description)",
            rows,
        )

    with open(PRODUCT_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        conn.executemany(
            """INSERT INTO product
               (id, name, price, image, description, published_date, category_id)
               VALUES (:id, :name, :price, :image, :description, :published_date, :category_id)""",
            rows,
        )

    conn.commit()
    seed_admin_data(conn)
    conn.close()
    print(f"Seeded {DB_PATH} with {len(rows)} products.")


def ensure_admin_tables(conn):
    """Create user/order/order_item if missing, without touching existing tables/data."""
    conn.executescript(ADMIN_TABLES_SQL)
    conn.commit()


def migrate_order_schema(conn):
    """Recreate the order table so status allows 'confirmed' and it has a note column,
    without losing existing rows. Returns True if a migration actually ran."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'order'"
    ).fetchone()
    if row is None:
        return False  # table doesn't exist yet; ensure_admin_tables() will create the current version

    current_sql = row[0]
    if "confirmed" in current_sql and "note" in current_sql:
        return False  # already up to date

    conn.executescript(
        """
        CREATE TABLE "order_new" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'confirmed', 'completed', 'cancelled')),
            total_amount INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user (id)
        );
        INSERT INTO "order_new" (id, user_id, status, total_amount, created_at)
            SELECT id, user_id, status, total_amount, created_at FROM "order";
        DROP TABLE "order";
        ALTER TABLE "order_new" RENAME TO "order";
        """
    )
    conn.commit()
    return True


def migrate_user_schema(conn):
    """Add any missing columns to an already-existing user table (username,
    password_hash), backfilling username from the email prefix. Returns True
    if a migration ran."""
    columns = [row[1] for row in conn.execute("PRAGMA table_info(user)").fetchall()]
    if not columns:
        return False  # table doesn't exist yet; ensure_admin_tables() will create the current version

    migrated = False

    if "username" not in columns:
        conn.execute("ALTER TABLE user ADD COLUMN username TEXT")
        for user_id, email in conn.execute("SELECT id, email FROM user").fetchall():
            conn.execute(
                "UPDATE user SET username = ? WHERE id = ?", (email.split("@")[0], user_id)
            )
        migrated = True

    if "password_hash" not in columns:
        conn.execute("ALTER TABLE user ADD COLUMN password_hash TEXT")
        migrated = True

    if migrated:
        conn.commit()
    return migrated


def backfill_order_demo_fields(conn):
    """One-time cosmetic backfill right after migrate_order_schema: split some
    pending orders into confirmed, and attach sample notes to a subset of orders."""
    random.seed(43)

    pending_ids = [
        row[0]
        for row in conn.execute('SELECT id FROM "order" WHERE status = ?', ("pending",)).fetchall()
    ]
    for order_id in pending_ids:
        if random.random() < 0.5:
            conn.execute('UPDATE "order" SET status = ? WHERE id = ?', ("confirmed", order_id))

    all_ids = [row[0] for row in conn.execute('SELECT id FROM "order"').fetchall()]
    for order_id in all_ids:
        if random.random() < 0.35:
            conn.execute(
                'UPDATE "order" SET note = ? WHERE id = ?', (random.choice(SAMPLE_NOTES), order_id)
            )

    conn.commit()


def seed_admin_data(conn):
    """Fill user/order/order_item with demo data, only if the user table is empty."""
    already_seeded = conn.execute("SELECT COUNT(*) FROM user").fetchone()[0] > 0
    if already_seeded:
        return

    random.seed(42)
    now = datetime.now()

    users = [
        (
            name,
            f"khachhang{i}@gmail.com",
            f"khachhang{i}",
            None,
            f"09{random.randint(10000000, 99999999)}",
            (now - timedelta(days=random.randint(30, 400))).isoformat(),
            0,
        )
        for i, name in enumerate(CUSTOMER_NAMES, start=1)
    ]
    users.append(
        ("Quản trị viên", "admin@coffeeshop.vn", "admin", None, "0900000000", now.isoformat(), 1)
    )

    conn.executemany(
        """INSERT INTO user (name, email, username, password_hash, phone, created_at, is_admin)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        users,
    )
    conn.commit()

    customer_ids = [
        row[0] for row in conn.execute("SELECT id FROM user WHERE is_admin = 0").fetchall()
    ]
    products = conn.execute("SELECT id, price FROM product").fetchall()
    if not products or not customer_ids:
        return

    statuses = ["completed"] * 5 + ["confirmed"] * 2 + ["pending"] * 1 + ["cancelled"] * 2

    for _ in range(70):
        user_id = random.choice(customer_ids)
        created_at = now - timedelta(days=random.randint(0, 90), hours=random.randint(0, 23))
        status = random.choice(statuses)
        note = random.choice(SAMPLE_NOTES) if random.random() < 0.35 else None
        chosen = random.sample(products, k=min(random.randint(1, 4), len(products)))

        total = 0
        order_items = []
        for prod_id, price in chosen:
            qty = random.randint(1, 3)
            order_items.append((prod_id, qty, price))
            total += qty * price

        cur = conn.execute(
            'INSERT INTO "order" (user_id, status, total_amount, note, created_at) VALUES (?, ?, ?, ?, ?)',
            (user_id, status, total, note, created_at.isoformat()),
        )
        order_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO order_item (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
            [(order_id, pid, qty, price) for pid, qty, price in order_items],
        )

    conn.commit()


def ensure_admin_data():
    """Migration-safe entry point: creates/upgrades admin tables and seeds demo data
    on an already-existing coffeeshop.db, without touching category/product/feedback."""
    conn = sqlite3.connect(DB_PATH)
    ensure_admin_tables(conn)
    migrate_user_schema(conn)
    migrated = migrate_order_schema(conn)
    if migrated:
        backfill_order_demo_fields(conn)
    seed_admin_data(conn)
    conn.close()


if __name__ == "__main__":
    seed()
