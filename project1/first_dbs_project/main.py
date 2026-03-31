from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_cors import CORS
import mysql.connector

app = Flask(__name__)
app.secret_key = "dev-secret-key"
CORS(app)

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Pooja@1998",
    database="shopping_db"
)

cursor = db.cursor(dictionary=True)

# ---------------- AUTH (combined login/register) ----------------
@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'GET':
        # optional ?tab=register to show register tab
        return render_template('auth.html')

    data = request.get_json(silent=True) or request.form
    action = (data.get('action') or '').lower()

    if action == 'register':
        try:
            cursor.execute(
                "INSERT INTO customer (email, name) VALUES (%s, %s)",
                (data['email'], data['name'])
            )
            db.commit()
            flash('Registered successfully. Please log in.', 'success')
            return redirect(url_for('auth') + '?tab=login')
        except Exception:
            flash('Registration failed or user already exists.', 'error')
            return redirect(url_for('auth') + '?tab=register')

    # default to login
    cursor.execute("SELECT * FROM customer WHERE email=%s", (data['email'],))
    user = cursor.fetchone()

    if not user:
        flash('User not found. Please register first.', 'error')
        return redirect(url_for('auth') + '?tab=register')

    # reuse or create basket
    cursor.execute("""
        SELECT basket_id FROM shopping_basket
        WHERE customer_email=%s ORDER BY basket_id DESC LIMIT 1
    """, (data['email'],))

    basket = cursor.fetchone()

    if basket:
        basket_id = basket['basket_id']
    else:
        cursor.execute(
            "INSERT INTO shopping_basket (customer_email) VALUES (%s)",
            (data['email'],)
        )
        db.commit()
        basket_id = cursor.lastrowid

    # set session and go to home
    session['user_email'] = data['email']
    session['basket_id'] = basket_id

    flash('Logged in successfully.', 'success')
    return redirect(url_for('index'))


# keep old endpoints redirecting to unified auth page for compatibility
@app.route('/register')
def register():
    return redirect(url_for('auth'))


@app.route('/login')
def login():
    return redirect(url_for('auth'))


# ---------------- VIEW STOCK ----------------
@app.route('/stock')
def view_stock():
    cursor.execute("""
        SELECT b.ISBN, b.title, SUM(s.quantity) as total_stock
        FROM book b
        JOIN stock s ON b.ISBN = s.ISBN
        GROUP BY b.ISBN, b.title
    """)
    return jsonify(cursor.fetchall())


# ---------------- ADD TO BASKET ----------------
@app.route('/add_to_basket', methods=['POST'])
def add_to_basket():
    data = request.get_json(silent=True) or request.form

    basket_id = data.get('basket_id') or session.get('basket_id')
    isbn = data.get('ISBN')
    qty = int(data.get('quantity') or 1)

    # check stock
    cursor.execute("SELECT SUM(quantity) as total FROM stock WHERE ISBN=%s", (isbn,))
    result = cursor.fetchone()

    if result['total'] is None or result['total'] < qty:
        return {"message": "Not enough stock"}

    cursor.execute("""
        INSERT INTO basket_items (basket_id, ISBN, quantity)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE quantity = quantity + %s
    """, (basket_id, isbn, qty, qty))

    db.commit()

    return jsonify({"message": "Added to basket"})


@app.route('/remove_from_basket', methods=['POST'])
def remove_from_basket():
    data = request.get_json(silent=True) or request.form
    basket_id = data.get('basket_id') or session.get('basket_id')
    isbn = data.get('ISBN')

    if not basket_id or not isbn:
        return jsonify({"message": "Missing basket_id or ISBN"}), 400

    cursor.execute(
        "DELETE FROM basket_items WHERE basket_id=%s AND ISBN=%s",
        (basket_id, isbn)
    )
    db.commit()

    return jsonify({"message": "Removed"})


# ---------------- VIEW BASKET ----------------
@app.route('/view_basket/<int:basket_id>')
def view_basket(basket_id):
    cursor.execute("""
        SELECT b.title, bi.quantity
        FROM basket_items bi
        JOIN book b ON bi.ISBN = b.ISBN
        WHERE bi.basket_id = %s
    """, (basket_id,))

    return jsonify(cursor.fetchall())


# ---------------- WEB PAGES ----------------
@app.route('/')
def index():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    # Render homepage with user's basket id; JS will fetch stock and basket when needed
    return render_template('index.html', user=session.get('user_email'), basket_id=session.get('basket_id'))


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/basket')
def basket():
    if 'user_email' not in session:
        return redirect(url_for('auth'))

    basket_id = session.get('basket_id')
    if not basket_id:
        return render_template('basket.html', items=[])

    cursor.execute("""
        SELECT b.title, bi.quantity, bi.ISBN
        FROM basket_items bi
        JOIN book b ON bi.ISBN = b.ISBN
        WHERE bi.basket_id = %s
    """, (basket_id,))

    items = cursor.fetchall()
    return render_template('basket.html', items=items)


app.run(debug=True)