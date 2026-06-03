"""Populate the database with realistic fake e-commerce data.

Deterministic (seeded) so everyone gets the same dataset. Generates:
    ~500 customers, 1000 products, 10000 orders (each 1-5 line items),
    and a payment per non-cancelled order.

Uses psycopg's fast COPY path so seeding takes a couple of seconds.

Usage:
    python scripts/init_db.py     # first, to (re)create tables
    python scripts/seed_data.py
"""

from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import psycopg  # noqa: E402

from insightforge_mcp.config import get_settings  # noqa: E402

random.seed(42)

N_CUSTOMERS = 500
N_PRODUCTS = 1000
N_ORDERS = 10_000
TODAY = date(2026, 6, 3)

FIRST = ["Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie",
         "Avery", "Quinn", "Drew", "Cameron", "Reese", "Skyler", "Devin", "Harper"]
LAST = ["Smith", "Johnson", "Lee", "Garcia", "Patel", "Kim", "Brown", "Nguyen",
        "Müller", "Rossi", "Silva", "Khan", "Anders", "Walsh", "Owens", "Fox"]
CITIES = [("London", "UK"), ("Berlin", "DE"), ("Paris", "FR"), ("Madrid", "ES"),
          ("New York", "US"), ("Toronto", "CA"), ("Mumbai", "IN"), ("Tokyo", "JP"),
          ("Sydney", "AU"), ("São Paulo", "BR")]
CATEGORIES = ["Electronics", "Home & Kitchen", "Books", "Toys", "Sports",
              "Beauty", "Garden", "Office", "Grocery", "Fashion"]
ADJ = ["Pro", "Max", "Eco", "Ultra", "Smart", "Classic", "Mini", "Deluxe", "Prime", "Lite"]
NOUN = ["Blender", "Headphones", "Notebook", "Lamp", "Backpack", "Bottle", "Charger",
        "Keyboard", "Sneakers", "Mug", "Chair", "Drone", "Camera", "Speaker", "Watch"]
STATUSES = ["completed", "completed", "completed", "completed", "pending", "cancelled", "refunded"]
METHODS = ["card", "card", "card", "paypal", "bank_transfer", "cash"]


def main() -> None:
    settings = get_settings()
    print("Generating data ...")

    customers = []
    for _ in range(N_CUSTOMERS):
        fn, ln = random.choice(FIRST), random.choice(LAST)
        city, country = random.choice(CITIES)
        email = f"{fn}.{ln}.{random.randint(1, 99999)}@example.com".lower()
        created = TODAY - timedelta(days=random.randint(30, 1095))
        customers.append((fn + " " + ln, email, city, country, created))

    products = []
    for _ in range(N_PRODUCTS):
        name = f"{random.choice(ADJ)} {random.choice(NOUN)} {random.randint(100, 999)}"
        cost = round(random.uniform(2, 400), 2)
        price = round(cost * random.uniform(1.2, 2.5), 2)
        stock = random.randint(0, 500)
        created = TODAY - timedelta(days=random.randint(30, 1095))
        products.append((name, random.choice(CATEGORIES), price, cost, stock, created))

    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            print("Loading customers ...")
            with cur.copy(
                "COPY customers (name, email, city, country, created_at) FROM STDIN"
            ) as cp:
                for row in customers:
                    cp.write_row(row)

            print("Loading products ...")
            with cur.copy(
                "COPY products (name, category, price, cost, stock, created_at) FROM STDIN"
            ) as cp:
                for row in products:
                    cp.write_row(row)

            # Fetch generated ids + prices for FK references.
            cur.execute("SELECT id FROM customers ORDER BY id")
            customer_ids = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT id, price FROM products ORDER BY id")
            product_rows = cur.fetchall()
            product_ids = [r[0] for r in product_rows]
            price_by_id = {r[0]: float(r[1]) for r in product_rows}

            print("Loading orders ...")
            orders = []
            for _ in range(N_ORDERS):
                cust = random.choice(customer_ids)
                odate = TODAY - timedelta(days=random.randint(0, 730))
                orders.append((cust, odate, random.choice(STATUSES)))
            with cur.copy(
                "COPY orders (customer_id, order_date, status) FROM STDIN"
            ) as cp:
                for row in orders:
                    cp.write_row(row)

            cur.execute("SELECT id, status FROM orders ORDER BY id")
            order_rows = cur.fetchall()

            print("Loading order_items ...")
            order_totals: dict[int, float] = {}
            with cur.copy(
                "COPY order_items (order_id, product_id, quantity, unit_price) FROM STDIN"
            ) as cp:
                for oid, _status in order_rows:
                    for _ in range(random.randint(1, 5)):
                        pid = random.choice(product_ids)
                        qty = random.randint(1, 4)
                        unit = price_by_id[pid]
                        cp.write_row((oid, pid, qty, unit))
                        order_totals[oid] = order_totals.get(oid, 0.0) + unit * qty

            print("Loading payments ...")
            with cur.copy(
                "COPY payments (order_id, amount, method, status) FROM STDIN"
            ) as cp:
                for oid, status in order_rows:
                    if status == "cancelled":
                        continue
                    amount = round(order_totals.get(oid, 0.0), 2)
                    pay_status = "refunded" if status == "refunded" else "paid"
                    cp.write_row((oid, amount, random.choice(METHODS), pay_status))

    print(
        f"Seed complete: {N_CUSTOMERS} customers, {N_PRODUCTS} products, "
        f"{N_ORDERS} orders + line items and payments."
    )


if __name__ == "__main__":
    main()
