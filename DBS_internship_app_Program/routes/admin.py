from flask import Blueprint, request, render_template, redirect, url_for, session, flash, g
import bcrypt
import functools
from utils.db import execute_query, execute_dml

admin_bp = Blueprint('admin', __name__)

@admin_bp.before_app_request
def load_logged_in_user():
    """Before every request, load the session user to Flask g.user global object."""
    username = session.get('username')
    if username is None:
        g.user = None
    else:
        g.user = username

def login_required(view):
    """Decorator to require admin login for protected dashboard views."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('admin.login'))
        return view(**kwargs)
    return wrapped_view

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handles admin authentication with plain text fallback for existing admins."""
    if g.user:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash("Please enter both username and password.", "danger")
            return render_template('login.html')

        user = execute_query("SELECT * FROM admin_users WHERE username = %s", (username,), fetch="one")

        if user:
            stored_hash = user['password_hash']
            authenticated = False

            # 1. Try secure bcrypt check
            try:
                # If stored_hash is a proper bcrypt string, this succeeds
                if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                    authenticated = True
            except Exception:
                pass  # Not a valid bcrypt string, fallback

            # 2. Try plain-text match (fallback for existing database user 'qwert' / 'JoeyBada$$')
            if not authenticated and password == stored_hash:
                authenticated = True

            if authenticated:
                session.clear()
                session['username'] = username
                flash("Login successful! Welcome to the Placement Tracking System.", "success")
                return redirect(url_for('dashboard'))
            else:
                flash("Incorrect password. Access denied.", "danger")
        else:
            flash("Admin username not found.", "danger")

    return render_template('login.html')

@admin_bp.route('/logout')
def logout():
    """Clears session and logs out."""
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('admin.login'))
