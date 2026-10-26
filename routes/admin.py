from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import query_db, execute_db
from routes.auth import admin_required
from database.sqlite_init import init_sqlite_db

admin_bp = Blueprint('admin', __name__)

ALL_TABLES = [
    'students',
    'drivers',
    'vehicle',
    'driver_vehicle',
    'locations',
    'available_rides',
    'ride_points',
    'requests',
    'bookings',
    'payment'
]

ALL_VIEWS = [
    'confirmed_bookings_view',
    'published_rides_view'
]

@admin_bp.route('/admin')
@admin_required
def admin_dashboard():
    # 1. Selected table to inspect
    selected_table = request.args.get('table', 'students')
    if selected_table not in ALL_TABLES and selected_table not in ALL_VIEWS:
        selected_table = 'students'
        
    table_data = query_db(f"SELECT * FROM {selected_table} LIMIT 100")
    columns = list(table_data[0].keys()) if table_data else []
    
    # 2. Count summary across all tables
    table_counts = {}
    for tbl in ALL_TABLES:
        res = query_db(f"SELECT COUNT(*) AS cnt FROM {tbl}", one=True)
        table_counts[tbl] = res['cnt'] if res else 0

    # 3. Locations for quick node management
    locations = query_db("SELECT * FROM locations ORDER BY location_id ASC")
    
    return render_template(
        'admin_view.html',
        all_tables=ALL_TABLES,
        all_views=ALL_VIEWS,
        selected_table=selected_table,
        table_data=table_data,
        columns=columns,
        table_counts=table_counts,
        locations=locations,
        active_tab='tables'
    )

@admin_bp.route('/admin/reset_demo_data', methods=['POST'])
@admin_required
def reset_demo_data():
    try:
        init_sqlite_db(force_reset=True)
        flash('All test history, rides, bookings, and payments have been completely removed! Clean presentation state restored (0 rides).', 'success')
    except Exception as e:
        flash(f'Error resetting database: {str(e)}', 'danger')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/locations/add', methods=['POST'])
@admin_required
def add_location():
    name = request.form.get('name', '').strip()
    latitude = request.form.get('latitude', type=float)
    longitude = request.form.get('longitude', type=float)
    
    if not name:
        flash('Location name is required.', 'danger')
        return redirect(url_for('admin.admin_dashboard', table='locations'))
        
    try:
        execute_db(
            "INSERT INTO locations (name, latitude, longitude) VALUES (?, ?, ?)",
            (name, latitude, longitude)
        )
        flash(f'Campus node "{name}" added successfully to locations table!', 'success')
    except Exception as e:
        flash(f'Failed to add location: {str(e)}', 'danger')
        
    return redirect(url_for('admin.admin_dashboard', table='locations'))

@admin_bp.route('/admin/reports')
@admin_required
def admin_reports():
    # Run the 7 standard DBMS queries from Blueprint Section 7
    
    # Report 1: Rides with Driver and Vehicle
    rep1 = query_db("""
        SELECT 
            ar.ride_id, 
            s.first_name, 
            s.last_name,
            v.name AS vehicle_name,
            v.vehicle_number,
            ar.departure_time, 
            ar.remaining_capacity,
            ar.total_capacity
        FROM available_rides ar
        JOIN drivers d ON d.student_id = ar.driver_id
        JOIN students s ON s.student_id = d.student_id
        JOIN vehicle v ON v.vehicle_number = ar.vehicle_number
        WHERE ar.status = 'PUBLISHED'
        ORDER BY ar.departure_time ASC;
    """)

    # Report 2: Confirmed Bookings Per Ride
    rep2 = query_db("""
        SELECT 
            b.ride_id, 
            COUNT(*) AS total_bookings,
            SUM(b.fare) AS total_revenue
        FROM bookings b
        WHERE b.status = 'CONFIRMED'
        GROUP BY b.ride_id;
    """)

    # Report 3: Popular Pickup Locations
    rep3 = query_db("""
        SELECT 
            l.location_id,
            l.name AS pickup_location, 
            COUNT(*) AS total_pickups
        FROM bookings b
        JOIN locations l ON l.location_id = b.pickup_location_id
        WHERE b.status = 'CONFIRMED'
        GROUP BY l.location_id, l.name
        ORDER BY total_pickups DESC;
    """)

    # Report 4: Confirmed Booking Fares by Driver
    rep4 = query_db("""
        SELECT 
            ar.driver_id,
            s.first_name || ' ' || s.last_name AS driver_name,
            COUNT(b.booking_id) AS total_rides_booked,
            COALESCE(SUM(b.fare), 0) AS total_fares
        FROM available_rides ar
        JOIN drivers d ON d.student_id = ar.driver_id
        JOIN students s ON s.student_id = d.student_id
        JOIN bookings b ON b.ride_id = ar.ride_id
        WHERE b.status = 'CONFIRMED'
        GROUP BY ar.driver_id, s.first_name, s.last_name;
    """)

    # Report 5: Payment Audit Log (LEFT JOIN)
    rep5 = query_db("""
        SELECT 
            b.booking_id, 
            s.first_name || ' ' || s.last_name AS student_name,
            b.fare, 
            p.amount AS payment_amount,
            p.method AS payment_method,
            p.status AS payment_status,
            p.payment_date
        FROM bookings b
        JOIN students s ON s.student_id = b.customer_id
        LEFT JOIN payment p ON p.booking_id = b.booking_id
        ORDER BY b.booking_id DESC;
    """)

    # Report 6: Rides Without Confirmed Bookings (LEFT JOIN ... IS NULL)
    rep6 = query_db("""
        SELECT 
            ar.ride_id,
            ar.departure_time,
            ar.total_capacity,
            ar.remaining_capacity
        FROM available_rides ar
        LEFT JOIN bookings b ON b.ride_id = ar.ride_id AND b.status = 'CONFIRMED'
        WHERE b.booking_id IS NULL;
    """)

    # Report 7: Seat Utilisation
    rep7 = query_db("""
        SELECT 
            ar.ride_id,
            ar.total_capacity,
            ar.remaining_capacity,
            (ar.total_capacity - ar.remaining_capacity) AS seats_booked,
            ROUND(((ar.total_capacity - ar.remaining_capacity) * 100.0 / ar.total_capacity), 1) AS utilisation_percentage
        FROM available_rides ar;
    """)

    return render_template(
        'admin_reports.html',
        rep1=rep1,
        rep2=rep2,
        rep3=rep3,
        rep4=rep4,
        rep5=rep5,
        rep6=rep6,
        rep7=rep7
    )

@admin_bp.route('/admin/sql', methods=['GET', 'POST'])
@admin_required
def admin_sql():
    sql_query = ""
    results = []
    columns = []
    error = None
    
    if request.method == 'POST':
        sql_query = request.form.get('sql_query', '').strip()
        # Security sanity check: Allow SELECT/SHOW/EXPLAIN for DBMS presentation
        if not sql_query.lower().startswith(('select', 'show', 'explain', 'pragma')):
            error = "For safety in this console, only SELECT / analytical queries are permitted."
        else:
            try:
                data = query_db(sql_query)
                if data:
                    columns = list(data[0].keys())
                    results = data
                else:
                    results = []
            except Exception as e:
                error = str(e)

    return render_template(
        'admin_sql.html',
        sql_query=sql_query,
        results=results,
        columns=columns,
        error=error
    )
