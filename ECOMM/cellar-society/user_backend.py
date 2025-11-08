# user_backend.py
import sqlite3
import os

# Absolute path to the real DB
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', 'cellar_society.db'))

def get_db_connection():
    """
    Returns a SQLite connection with Row factory
    so that rows behave like dictionaries.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_all_products():
    """
    Fetch all products from the database.
    Returns a list of sqlite3.Row objects.
    """
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
    conn.close()
    return products


def add_to_cart(customer_id, product_id, quantity=1):
    """
    Adds a product to the customer's cart.
    If the product already exists in the cart, increases the quantity.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Make sure the 'cart' table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    # Check if the product is already in the cart
    existing = cursor.execute(
        "SELECT * FROM cart WHERE customer_id = ? AND product_id = ?",
        (customer_id, product_id)
    ).fetchone()

    if existing:
        cursor.execute(
            "UPDATE cart SET quantity = quantity + ? WHERE customer_id = ? AND product_id = ?",
            (quantity, customer_id, product_id)
        )
    else:
        cursor.execute(
            "INSERT INTO cart (customer_id, product_id, quantity) VALUES (?, ?, ?)",
            (customer_id, product_id, quantity)
        )

    conn.commit()
    conn.close()
    return True
