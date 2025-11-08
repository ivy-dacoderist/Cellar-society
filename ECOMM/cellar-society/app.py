# ============================================
# IMPORTS
# ============================================
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from auth_backend import authenticate_admin, authenticate_customer, register_customer
from user_backend import get_all_products, add_to_cart
from functools import wraps
from datetime import datetime
import sqlite3
import hashlib
import os

# ============================================
# APP CONFIGURATION
# ============================================
app = Flask(__name__)
app.secret_key = 'cellar_society_secret_2025'


# ============================================
# DATABASE PATH (POINT TO PARENT FOLDER)
# ============================================
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'cellar_society.db'))


# ============================================
# DATABASE SETUP
# ============================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Admins table
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Products
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        region TEXT NOT NULL,
        vintage INTEGER NOT NULL,
        price REAL NOT NULL,
        alcohol REAL NOT NULL,
        stock INTEGER NOT NULL,
        description TEXT,
        image_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Customers
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        phone TEXT,
        address TEXT,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Orders
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        total_price REAL NOT NULL,
        status TEXT DEFAULT 'Pending',
        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )''')

    # Default admin
    c.execute("SELECT * FROM admins WHERE username='admin'")
    admin = c.fetchone()
    hashed_pw = hashlib.sha256('admin123'.encode()).hexdigest()

    if not admin:
        c.execute("INSERT INTO admins (username, password) VALUES (?, ?)", ('admin', hashed_pw))
    else:
        if admin[2] != hashed_pw:
            c.execute("UPDATE admins SET password=? WHERE username='admin'", (hashed_pw,))

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============================================
# HASH TABLE CACHE
# ============================================
class ProductHashTable:
    def __init__(self):
        self.table = {}

    def insert(self, product_id, product_data):
        self.table[product_id] = product_data

    def get(self, product_id):
        return self.table.get(product_id, None)

    def delete(self, product_id):
        if product_id in self.table:
            del self.table[product_id]
            return True
        return False

    def get_all(self):
        return list(self.table.values())

product_cache = ProductHashTable()

def load_products_to_cache():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM products")
    products = c.fetchall()
    conn.close()

    product_cache.table.clear()
    for p in products:
        product_cache.insert(p[0], {
            'id': p[0],
            'name': p[1],
            'type': p[2],
            'region': p[3],
            'vintage': p[4],
            'price': p[5],
            'alcohol': p[6],
            'stock': p[7],
            'description': p[8],
            'image_url': p[9]
        })

# ============================================
# DECORATORS
# ============================================
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Please log in as admin.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def customer_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'customer_id' not in session:
            flash('Please log in as customer.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ============================================
# AUTH ROUTES
# ============================================
@app.route('/')
def index():
    if 'admin_id' in session:
        return redirect(url_for('dashboard'))
    elif 'customer_id' in session:
        return redirect(url_for('user_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form['username']
        password = request.form['password']

        admin = authenticate_admin(username_or_email, password)
        if admin:
            session.clear()
            session['admin_id'] = admin['id']
            session['admin_username'] = admin['username']
            flash(f"Welcome back, {admin['username']}!", 'success')
            return redirect(url_for('dashboard'))

        customer = authenticate_customer(username_or_email, password)
        if customer:
            session.clear()
            session['customer_id'] = customer['id']
            session['customer_name'] = customer['name']
            flash(f"Welcome, {customer['name']}!", 'success')
            return redirect(url_for('user_dashboard'))

        flash('Invalid username or password.', 'error')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm = request.form['confirm']

        if register_customer(name, email, password, confirm):
            return redirect(url_for('login'))
        else:
            return render_template('user/register.html')

    return render_template('user/register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

# ============================================
# ADMIN ROUTES
# ============================================
@app.route('/dashboard')
@admin_required
def dashboard():
    conn = get_db_connection()
    total_products = conn.execute('SELECT COUNT(*) AS c FROM products').fetchone()['c']
    total_customers = conn.execute('SELECT COUNT(*) AS c FROM customers').fetchone()['c']
    total_orders = conn.execute('SELECT COUNT(*) AS c FROM orders').fetchone()['c']
    pending_orders = conn.execute('SELECT COUNT(*) AS c FROM orders WHERE status="Pending"').fetchone()['c']
    recent_orders = conn.execute('''
        SELECT o.id, c.name AS customer_name, p.name AS product_name,
               o.quantity, o.total_price, o.status, o.order_date
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        JOIN products p ON o.product_id = p.id
        ORDER BY o.order_date DESC
        LIMIT 5
    ''').fetchall()
    conn.close()

    return render_template('admin/dashboard.html',
                           stats={
                               'total_products': total_products,
                               'total_customers': total_customers,
                               'total_orders': total_orders,
                               'pending_orders': pending_orders
                           },
                           recent_orders=recent_orders)

@app.route('/products')
@admin_required
def products():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('admin/products.html', products=products)

@app.route('/products/add', methods=['GET', 'POST'])
@admin_required
def add_product():
    if request.method == 'POST':
        data = (
            request.form['name'],
            request.form['type'],
            request.form['region'],
            int(request.form['vintage']),
            float(request.form['price']),
            float(request.form['alcohol']),
            int(request.form['stock']),
            request.form.get('description', ''),
            request.form.get('image_url', '')
        )
        conn = get_db_connection()
        conn.execute('''INSERT INTO products 
                        (name, type, region, vintage, price, alcohol, stock, description, image_url)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', data)
        conn.commit()
        conn.close()
        flash('Product added successfully!', 'success')
        return redirect(url_for('products'))
    return render_template('admin/add_product.html')

# ✅ FIXED: Edit Product Route
@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('products'))

    if request.method == 'POST':
        data = (
            request.form['name'],
            request.form['type'],
            request.form['region'],
            int(request.form['vintage']),
            float(request.form['price']),
            float(request.form['alcohol']),
            int(request.form['stock']),
            request.form.get('description', ''),
            request.form.get('image_url', ''),
            product_id
        )
        conn.execute('''UPDATE products 
                        SET name=?, type=?, region=?, vintage=?, price=?, alcohol=?, stock=?, description=?, image_url=?
                        WHERE id=?''', data)
        conn.commit()
        conn.close()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('products'))

    conn.close()
    return render_template('admin/edit_product.html', product=product)

@app.route('/customers')
@admin_required
def customers():
    search = request.args.get('search', '')
    conn = get_db_connection()
    query = 'SELECT * FROM customers WHERE 1=1'
    params = []
    if search:
        query += ' AND (name LIKE ? OR email LIKE ?)'
        params += [f'%{search}%', f'%{search}%']
    customers = conn.execute(query + ' ORDER BY joined_at DESC', params).fetchall()
    conn.close()
    return render_template('admin/customers.html', customers=customers, search=search)

# ✅ FIXED: Delete Product Route
@app.route('/products/delete/<int:product_id>', methods=['POST', 'GET'])
@admin_required
def delete_product(product_id):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()
    if not product:
        flash('Product not found.', 'error')
        conn.close()
        return redirect(url_for('products'))

    conn.execute('DELETE FROM products WHERE id=?', (product_id,))
    conn.commit()
    conn.close()

    flash(f'Product "{product["name"]}" deleted successfully!', 'success')
    return redirect(url_for('products'))

# ✅ FIXED: Customer Detail Route
@app.route('/customers/<int:customer_id>')
@admin_required
def customer_detail(customer_id):
    conn = get_db_connection()
    customer = conn.execute('SELECT * FROM customers WHERE id=?', (customer_id,)).fetchone()
    orders = conn.execute('''
        SELECT o.*, p.name AS product_name
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.customer_id=?
    ''', (customer_id,)).fetchall()
    conn.close()
    if not customer:
        flash('Customer not found.', 'error')
        return redirect(url_for('customers'))
    return render_template('admin/customer_detail.html', customer=customer, orders=orders)

@app.route('/orders')
@admin_required
def orders():
    status_filter = request.args.get('status', '')
    conn = get_db_connection()
    query = '''
        SELECT o.*, c.name AS customer_name, p.name AS product_name
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        JOIN products p ON o.product_id = p.id
        WHERE 1=1
    '''
    params = []
    if status_filter:
        query += ' AND o.status=?'
        params.append(status_filter)
    orders = conn.execute(query + ' ORDER BY o.order_date DESC', params).fetchall()
    conn.close()
    return render_template('admin/orders.html', orders=orders, status_filter=status_filter)

# ============================================
# USER ROUTES
# ============================================
@app.route('/user/dashboard')
@customer_required
def user_dashboard():
    products = get_all_products()  # fetch all products
    return render_template(
        'user/dashboard.html',
        customer_name=session.get('customer_name'),
        products=products  # pass products to the template
    )

@app.route('/user/orders')
@customer_required
def user_orders():
    conn = get_db_connection()
    orders = conn.execute('''
        SELECT o.*, p.name AS product_name, p.price
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.customer_id=?
        ORDER BY o.order_date DESC
    ''', (session['customer_id'],)).fetchall()
    conn.close()
    return render_template('user/orders.html', orders=orders)


# Add to Cart route
@app.route('/user/add_to_cart/<int:product_id>', methods=['POST'])
@customer_required
def add_to_cart_route(product_id):
    customer_id = session.get('customer_id')
    if not customer_id:
        flash("You must be logged in to add items to your cart.", "error")
        return redirect(url_for('login'))

    add_to_cart(customer_id, product_id)
    flash("Product added to your cart!", "success")
    return redirect(url_for('user_dashboard'))

# Buy Now route (redirects to checkout later)
@app.route('/user/buy_now/<int:product_id>', methods=['POST'])
@customer_required
def buy_now_route(product_id):
    customer_id = session.get('customer_id')
    if not customer_id:
        flash("You must be logged in to buy items.", "error")
        return redirect(url_for('login'))

    # For now, just add to cart then redirect (can later go to checkout)
    add_to_cart(customer_id, product_id)
    flash("Product added! Proceed to checkout.", "info")
    return redirect(url_for('user_dashboard'))

@app.route('/user/profile')
@customer_required
def user_profile():
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM customers WHERE id=?', (session['customer_id'],)).fetchone()
    conn.close()
    return render_template('user/profile.html', user=user)

# ============================================
# RUN APP
# ============================================
if __name__ == '__main__':
    init_db()
    load_products_to_cache()
    print("=" * 60)
    print(" Cellar Society Admin & User Panel Starting...")
    print("=" * 60)
    print(" Access at: http://localhost:5000")
    print(" Default Admin Login: admin / admin123")
    print("=" * 60)
    app.run(debug=True, port=5000)
