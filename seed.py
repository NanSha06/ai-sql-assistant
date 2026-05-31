"""
seed.py — Create and populate the sample database for AI SQL Assistant.

Tables created:
  - customers
  - products
  - employees
  - orders
  - order_items

Run with:
    python seed.py
"""

import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values

load_dotenv()

# ── Connection ─────────────────────────────────────────────────────────────────

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "sql_assist"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS", "")
    )


# ── Schema ─────────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
-- Drop tables if they exist (clean slate)
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS employees CASCADE;

-- Customers
CREATE TABLE customers (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(150) UNIQUE NOT NULL,
    city        VARCHAR(100),
    country     VARCHAR(100),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Products
CREATE TABLE products (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    category    VARCHAR(100),
    price       DECIMAL(10, 2) NOT NULL,
    stock_qty   INT DEFAULT 0,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Employees
CREATE TABLE employees (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    department  VARCHAR(100),
    salary      DECIMAL(10, 2),
    hire_date   DATE,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Orders
CREATE TABLE orders (
    id              SERIAL PRIMARY KEY,
    customer_id     INT REFERENCES customers(id),
    employee_id     INT REFERENCES employees(id),
    status          VARCHAR(50) DEFAULT 'pending',
    total_amount    DECIMAL(10, 2) DEFAULT 0.00,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Order Items
CREATE TABLE order_items (
    id          SERIAL PRIMARY KEY,
    order_id    INT REFERENCES orders(id),
    product_id  INT REFERENCES products(id),
    quantity    INT NOT NULL,
    unit_price  DECIMAL(10, 2) NOT NULL
);
"""

# ── Sample Data ────────────────────────────────────────────────────────────────

CUSTOMERS = [
    ("Alice Johnson",    "alice@example.com",    "New York",     "USA"),
    ("Bob Smith",        "bob@example.com",      "London",       "UK"),
    ("Carlos Rivera",    "carlos@example.com",   "Madrid",       "Spain"),
    ("Diana Chen",       "diana@example.com",    "Shanghai",     "China"),
    ("Ethan Brown",      "ethan@example.com",    "Toronto",      "Canada"),
    ("Fatima Al-Sayed",  "fatima@example.com",   "Dubai",        "UAE"),
    ("George Müller",    "george@example.com",   "Berlin",       "Germany"),
    ("Hana Yamamoto",    "hana@example.com",     "Tokyo",        "Japan"),
    ("Ivan Petrov",      "ivan@example.com",     "Moscow",       "Russia"),
    ("Julia Santos",     "julia@example.com",    "São Paulo",    "Brazil"),
    ("Kevin O'Brien",    "kevin@example.com",    "Dublin",       "Ireland"),
    ("Laura Mancini",    "laura@example.com",    "Rome",         "Italy"),
    ("Mohammed Hassan",  "mohammed@example.com", "Cairo",        "Egypt"),
    ("Nina Eriksson",    "nina@example.com",     "Stockholm",    "Sweden"),
    ("Oliver Wright",    "oliver@example.com",   "Sydney",       "Australia"),
    ("Priya Sharma",     "priya@example.com",    "Mumbai",       "India"),
    ("Quinn Adams",      "quinn@example.com",    "Chicago",      "USA"),
    ("Rosa Fernandez",   "rosa@example.com",     "Buenos Aires", "Argentina"),
    ("Samuel Lee",       "samuel@example.com",   "Seoul",        "South Korea"),
    ("Tara Nguyen",      "tara@example.com",     "Hanoi",        "Vietnam"),
]

PRODUCTS = [
    ("Wireless Mouse",          "Electronics",      29.99,  150),
    ("Mechanical Keyboard",     "Electronics",      89.99,  80),
    ("USB-C Hub",               "Electronics",      49.99,  200),
    ("Laptop Stand",            "Accessories",      39.99,  120),
    ("Noise Cancelling Headphones", "Electronics", 199.99, 60),
    ("Webcam HD 1080p",         "Electronics",      79.99,  90),
    ("Desk Lamp LED",           "Home Office",      34.99,  175),
    ("Ergonomic Chair",         "Furniture",        349.99, 25),
    ("Standing Desk",           "Furniture",        499.99, 15),
    ("Monitor 27-inch 4K",      "Electronics",      599.99, 40),
    ("Notebook A5",             "Stationery",        4.99,  500),
    ("Ballpoint Pens (10-pack)","Stationery",        7.99,  400),
    ("Sticky Notes (5-pack)",   "Stationery",        3.49,  600),
    ("Cable Management Box",    "Accessories",      19.99,  220),
    ("Phone Stand",             "Accessories",      14.99,  300),
    ("Screen Cleaner Kit",      "Accessories",       9.99,  350),
    ("External SSD 1TB",        "Electronics",      109.99, 70),
    ("Bluetooth Speaker",       "Electronics",      59.99,  100),
    ("Smart Plug",              "Smart Home",       24.99,  180),
    ("LED Strip Lights",        "Smart Home",       29.99,  160),
]

EMPLOYEES = [
    ("James Carter",    "Sales",        55000.00, "2019-03-15"),
    ("Sophie Turner",   "Sales",        58000.00, "2020-06-01"),
    ("David Kim",       "Engineering",  95000.00, "2018-11-20"),
    ("Emma Wilson",     "Engineering",  98000.00, "2017-07-10"),
    ("Liam Thompson",   "Marketing",    62000.00, "2021-01-25"),
    ("Olivia Harris",   "Marketing",    60000.00, "2021-08-14"),
    ("Noah Martinez",   "Support",      48000.00, "2022-03-01"),
    ("Ava Robinson",    "Support",      47000.00, "2022-09-18"),
    ("William Clark",   "HR",           65000.00, "2016-05-30"),
    ("Isabella Lewis",  "Finance",      72000.00, "2019-12-05"),
]

STATUSES = ["pending", "processing", "completed", "completed", "completed", "cancelled"]


def random_date(days_back: int = 365) -> datetime:
    return datetime.now() - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59)
    )


# ── Seed Functions ─────────────────────────────────────────────────────────────

def create_schema(cur):
    print("📦 Creating schema...")
    cur.execute(SCHEMA_SQL)
    print("   ✅ Tables created.")


def seed_customers(cur):
    print("👤 Seeding customers...")
    rows = [
        (name, email, city, country, random_date(730))
        for name, email, city, country in CUSTOMERS
    ]
    execute_values(cur, """
        INSERT INTO customers (name, email, city, country, created_at)
        VALUES %s
    """, rows)
    print(f"   ✅ {len(rows)} customers inserted.")


def seed_products(cur):
    print("📦 Seeding products...")
    rows = [
        (name, category, price, stock, random_date(730))
        for name, category, price, stock in PRODUCTS
    ]
    execute_values(cur, """
        INSERT INTO products (name, category, price, stock_qty, created_at)
        VALUES %s
    """, rows)
    print(f"   ✅ {len(rows)} products inserted.")


def seed_employees(cur):
    print("👔 Seeding employees...")
    rows = [
        (name, dept, salary, hire_date, random_date(730))
        for name, dept, salary, hire_date in EMPLOYEES
    ]
    execute_values(cur, """
        INSERT INTO employees (name, department, salary, hire_date, created_at)
        VALUES %s
    """, rows)
    print(f"   ✅ {len(rows)} employees inserted.")


def seed_orders(cur, num_orders: int = 120):
    print(f"🛒 Seeding {num_orders} orders...")

    # Fetch valid IDs
    cur.execute("SELECT id FROM customers")
    customer_ids = [r[0] for r in cur.fetchall()]

    cur.execute("SELECT id FROM employees")
    employee_ids = [r[0] for r in cur.fetchall()]

    cur.execute("SELECT id, price FROM products")
    products = cur.fetchall()  # [(id, price), ...]

    orders_inserted = 0
    items_inserted = 0

    for _ in range(num_orders):
        customer_id = random.choice(customer_ids)
        employee_id = random.choice(employee_ids)
        status = random.choice(STATUSES)
        order_date = random_date(365)

        # Insert order (total_amount updated after items)
        cur.execute("""
            INSERT INTO orders (customer_id, employee_id, status, total_amount, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (customer_id, employee_id, status, 0.00, order_date))
        order_id = cur.fetchone()[0]

        # Add 1–4 items per order
        num_items = random.randint(1, 4)
        selected_products = random.sample(products, min(num_items, len(products)))

        order_total = 0.00
        item_rows = []
        for product_id, unit_price in selected_products:
            qty = random.randint(1, 5)
            item_rows.append((order_id, product_id, qty, unit_price))
            order_total += qty * float(unit_price)

        execute_values(cur, """
            INSERT INTO order_items (order_id, product_id, quantity, unit_price)
            VALUES %s
        """, item_rows)

        # Update order total
        cur.execute("""
            UPDATE orders SET total_amount = %s WHERE id = %s
        """, (round(order_total, 2), order_id))

        orders_inserted += 1
        items_inserted += len(item_rows)

    print(f"   ✅ {orders_inserted} orders inserted.")
    print(f"   ✅ {items_inserted} order items inserted.")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("\n🚀 Starting database seed...\n")

    try:
        conn = get_connection()
        conn.autocommit = False
        cur = conn.cursor()

        create_schema(cur)
        seed_customers(cur)
        seed_products(cur)
        seed_employees(cur)
        seed_orders(cur, num_orders=120)

        conn.commit()

        print("\n✅ Database seeded successfully!")
        print("\n📊 Summary:")
        for table in ["customers", "products", "employees", "orders", "order_items"]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"   {table:<15} → {count} rows")

        print("\n🎉 You can now run: streamlit run app.py\n")

    except Exception as e:
        print(f"\n❌ Seeding failed: {e}")
        if conn:
            conn.rollback()
        raise

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    main()