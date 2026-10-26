from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from db import query_db, execute_db

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if session.get('role') != 'ADMIN':
            flash('Access restricted to System Administrators.', 'danger')
            return redirect(url_for('student.student_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please provide both email and password.', 'danger')
            return render_template('login.html', email=email)

        user = query_db("SELECT * FROM students WHERE email = ?", (email,), one=True)
        if not user or not check_password_hash(user['password_hash'], password):
            flash('Invalid email or password. Please check your credentials.', 'danger')
            return render_template('login.html', email=email)

        # Check driver status
        driver = query_db("SELECT * FROM drivers WHERE student_id = ?", (user['student_id'],), one=True)

        session.clear()
        session['user_id'] = user['student_id']
        session['email'] = user['email']
        session['first_name'] = user['first_name']
        session['last_name'] = user['last_name']
        session['role'] = user['role']
        session['is_driver'] = True if driver else False
        session['current_mode'] = user['current_mode'] if user['current_mode'] else ('DRIVER' if driver else 'PASSENGER')

        flash(f"Welcome back, {user['first_name']}!", 'success')

        if user['role'] == 'ADMIN':
            return redirect(url_for('admin.admin_dashboard'))
        elif session['current_mode'] == 'DRIVER':
            return redirect(url_for('driver.driver_dashboard'))
        else:
            return redirect(url_for('student.student_dashboard'))

    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not (first_name and last_name and phone_number and email and password):
            flash('All fields are required.', 'danger')
            return render_template('register.html')

        # Check uniqueness
        existing = query_db("SELECT * FROM students WHERE email = ? OR phone_number = ?", (email, phone_number), one=True)
        if existing:
            if existing['email'].lower() == email:
                flash('A student with this email address already exists (UNIQUE constraint).', 'danger')
            else:
                flash('A student with this phone number already exists (UNIQUE constraint).', 'danger')
            return render_template('register.html')

        try:
            pwd_hash = generate_password_hash(password)
            user_id = execute_db(
                "INSERT INTO students (first_name, last_name, phone_number, email, password_hash, role, current_mode) VALUES (?, ?, ?, ?, ?, 'STUDENT', 'PASSENGER')",
                (first_name, last_name, phone_number, email, pwd_hash)
            )
            flash('Registration successful! You can now log in with your credentials.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            flash(f'Database error during registration: {str(e)}', 'danger')
            return render_template('register.html')

    return render_template('register.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out safely.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/switch_mode/<mode>', methods=['POST'])
@login_required
def switch_mode(mode):
    if mode not in ['PASSENGER', 'DRIVER']:
        flash('Invalid mode selection.', 'danger')
        return redirect(url_for('student.student_dashboard'))

    session['current_mode'] = mode
    execute_db("UPDATE students SET current_mode = ? WHERE student_id = ?", (mode, session['user_id']))

    if mode == 'DRIVER':
        return redirect(url_for('driver.driver_dashboard'))
    else:
        return redirect(url_for('student.student_dashboard'))
