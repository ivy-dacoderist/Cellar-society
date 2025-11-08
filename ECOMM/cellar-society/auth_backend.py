# auth_backend.py

import sqlite3
import os
import hashlib
from flask import flash
from werkzeug.security import generate_password_hash, check_password_hash

# Point to the DB in the parent folder
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'cellar_society.db'))


# ------------------------------------------------------
# DATABASE CONNECTION
# ------------------------------------------------------

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_all_products():
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
    conn.close()
    return products

def add_to_cart(customer_id, product_id, quantity=1):
    conn = get_db_connection()
    cursor = conn.cursor()

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

# ------------------------------------------------------
# PASSWORD HASHING HELPERS
# ------------------------------------------------------

def hash_admin_password(password):
    """SHA256 hashing for admin passwords."""
    return hashlib.sha256(password.encode()).hexdigest()


# ------------------------------------------------------
# ADMIN AUTHENTICATION
# ------------------------------------------------------

def authenticate_admin(username, password):
    """Verify admin login credentials."""
    conn = get_db_connection()
    hashed_pw = hash_admin_password(password)
    admin = conn.execute(
        'SELECT * FROM admins WHERE username = ? AND password = ?',
        (username, hashed_pw)
    ).fetchone()
    conn.close()
    return admin


def register_admin(username, password, confirm_password):
    """Register a new admin."""
    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return False

    conn = get_db_connection()
    existing = conn.execute('SELECT * FROM admins WHERE username = ?', (username,)).fetchone()

    if existing:
        flash("Username already exists. Try another.", "error")
        conn.close()
        return False

    hashed_pw = hash_admin_password(password)
    conn.execute('INSERT INTO admins (username, password) VALUES (?, ?)', (username, hashed_pw))
    conn.commit()
    conn.close()

    flash("Admin account created successfully! You can now log in.", "success")
    return True


# ------------------------------------------------------
# CUSTOMER AUTHENTICATION
# ------------------------------------------------------

def authenticate_customer(identifier, password):
    """
    Verify customer credentials.
    Can log in using either email or name.
    """
    conn = get_db_connection()
    customer = conn.execute(
        'SELECT * FROM customers WHERE email = ? OR name = ?',
        (identifier, identifier)
    ).fetchone()
    conn.close()

    if customer and check_password_hash(customer['password'], password):
        return customer
    return None


def register_customer(name, email, password, confirm):
    """Register a new customer."""
    if password != confirm:
        flash("Passwords do not match.", "error")
        return False

    hashed_pw = generate_password_hash(password)
    conn = get_db_connection()

    existing = conn.execute('SELECT * FROM customers WHERE email = ?', (email,)).fetchone()
    if existing:
        flash("Email already exists. Please use another one.", "error")
        conn.close()
        return False

    conn.execute(
        'INSERT INTO customers (name, email, password) VALUES (?, ?, ?)',
        (name, email, hashed_pw)
    )
    conn.commit()
    conn.close()

    flash("Account created successfully! You can now log in.", "success")
    return True
