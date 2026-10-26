from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
from db import query_db, execute_db, get_db_transaction
from routes.auth import login_required

student_bp = Blueprint('student', __name__)

@student_bp.route('/')
def home():
    if 'user_id' in session:
        if session.get('role') == 'ADMIN':
            return redirect(url_for('admin.admin_dashboard'))
        elif session.get('current_mode') == 'DRIVER':
            return redirect(url_for('driver.driver_dashboard'))
        return redirect(url_for('student.student_dashboard'))
    return redirect(url_for('auth.login'))

@student_bp.route('/student')
@login_required
def student_dashboard():
    user_id = session['user_id']
    
    # 1. Fetch all locations for search dropdowns
    locations = query_db("SELECT * FROM locations ORDER BY name ASC")
    
    # 2. Get search filters if any
    pickup_id = request.args.get('pickup_id', type=int)
    drop_id = request.args.get('drop_id', type=int)
    search_date = request.args.get('search_date', '').strip()
    
    # 3. Query published rides with seats remaining
    # We load all published rides first, then match stops sequence
    rides_query = """
    SELECT 
        ar.ride_id,
        ar.driver_id,
        ar.vehicle_number,
        ar.departure_time,
        ar.total_capacity,
        ar.remaining_capacity,
        ar.fare_per_passenger,
        ar.status,
        s.first_name AS driver_first_name,
        s.last_name AS driver_last_name,
        s.phone_number AS driver_phone,
        v.name AS vehicle_name,
        v.type AS vehicle_type,
        v.colour AS vehicle_colour
    FROM available_rides ar
    JOIN drivers d ON d.student_id = ar.driver_id
    JOIN students s ON s.student_id = d.student_id
    JOIN vehicle v ON v.vehicle_number = ar.vehicle_number
    WHERE ar.status = 'PUBLISHED'
      AND ar.remaining_capacity > 0
      AND ar.departure_time >= datetime('now')
    ORDER BY ar.departure_time ASC;
    """
    all_rides = query_db(rides_query)
    
    # Attach ordered route stops to each ride
    matched_rides = []
    for ride in all_rides:
        stops = query_db("""
            SELECT rp.sequence_no, rp.location_id, l.name
            FROM ride_points rp
            JOIN locations l ON l.location_id = rp.location_id
            WHERE rp.ride_id = ?
            ORDER BY rp.sequence_no ASC
        """, (ride['ride_id'],))
        ride['stops'] = stops
        
        # Check matching filter if pickup & drop are specified
        qualifies = True
        if pickup_id and drop_id:
            p_seq = None
            d_seq = None
            for s in stops:
                if s['location_id'] == pickup_id:
                    p_seq = s['sequence_no']
                elif s['location_id'] == drop_id:
                    d_seq = s['sequence_no']
            
            # Rule: pickup stop sequence must be less than drop stop sequence
            if p_seq is None or d_seq is None or p_seq >= d_seq:
                qualifies = False
                
        if search_date:
            try:
                ride_date_str = str(ride['departure_time'])[:10]
                if ride_date_str != search_date:
                    qualifies = False
            except Exception:
                pass
                
        if qualifies:
            matched_rides.append(ride)
            
    # 4. Fetch THIS student's bookings only (Privacy & Role restriction)
    my_bookings = query_db("""
        SELECT 
            b.booking_id,
            b.ride_id,
            b.booking_time,
            b.status AS booking_status,
            b.fare,
            p.status AS payment_status,
            p.method AS payment_method,
            l_pick.name AS pickup_name,
            l_drop.name AS drop_name,
            ar.departure_time,
            s_driver.first_name AS driver_first_name,
            s_driver.last_name AS driver_last_name,
            s_driver.phone_number AS driver_phone,
            v.name AS vehicle_name,
            v.vehicle_number
        FROM bookings b
        JOIN available_rides ar ON ar.ride_id = b.ride_id
        JOIN drivers d ON d.student_id = ar.driver_id
        JOIN students s_driver ON s_driver.student_id = d.student_id
        JOIN vehicle v ON v.vehicle_number = ar.vehicle_number
        JOIN locations l_pick ON l_pick.location_id = b.pickup_location_id
        JOIN locations l_drop ON l_drop.location_id = b.drop_location_id
        LEFT JOIN payment p ON p.booking_id = b.booking_id
        WHERE b.customer_id = ?
        ORDER BY b.booking_id DESC;
    """, (user_id,))
    
    return render_template(
        'student_view.html',
        locations=locations,
        rides=matched_rides,
        my_bookings=my_bookings,
        selected_pickup=pickup_id,
        selected_drop=drop_id,
        search_date=search_date
    )

@student_bp.route('/bookings/create', methods=['POST'])
@login_required
def create_booking():
    user_id = session['user_id']
    ride_id = request.form.get('ride_id', type=int)
    pickup_location_id = request.form.get('pickup_location_id', type=int)
    drop_location_id = request.form.get('drop_location_id', type=int)
    
    if not (ride_id and pickup_location_id and drop_location_id):
        flash('Invalid booking parameters.', 'danger')
        return redirect(url_for('student.student_dashboard'))
        
    try:
        # Atomic Transaction for Booking & Capacity Decrement
        with get_db_transaction() as (cursor, db_type):
            # 1. Fetch Ride details
            cursor.execute("SELECT * FROM available_rides WHERE ride_id = ?", (ride_id,))
            row = cursor.fetchone()
            if not row:
                flash('The requested ride does not exist.', 'danger')
                return redirect(url_for('student.student_dashboard'))
                
            ride = dict(row) if hasattr(row, 'keys') else {
                'driver_id': row[1],
                'departure_time': row[3],
                'remaining_capacity': row[5],
                'fare_per_passenger': row[6],
                'status': row[7]
            }
            
            # Validation: cannot book own ride
            if ride['driver_id'] == user_id:
                flash('You cannot book a seat on your own published ride!', 'warning')
                return redirect(url_for('student.student_dashboard'))
                
            # Validation: capacity check
            if ride['remaining_capacity'] <= 0:
                flash('Sorry, this ride is already fully booked!', 'danger')
                return redirect(url_for('student.student_dashboard'))
                
            # Validation: check existing active booking
            cursor.execute(
                "SELECT booking_id FROM bookings WHERE customer_id = ? AND ride_id = ? AND status = 'CONFIRMED'",
                (user_id, ride_id)
            )
            existing = cursor.fetchone()
            if existing:
                flash('You already have an active confirmed booking for this ride.', 'warning')
                return redirect(url_for('student.student_dashboard'))
                
            fare = ride['fare_per_passenger']
            now_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 2. Insert Request
            cursor.execute("""
                INSERT INTO requests (customer_id, pickup_location_id, drop_location_id, schedule_time, status)
                VALUES (?, ?, ?, ?, 'CONFIRMED');
            """, (user_id, pickup_location_id, drop_location_id, ride['departure_time']))
            request_id = cursor.lastrowid
            
            # 3. Insert Booking (Trigger will decrement remaining_capacity in MySQL/SQLite)
            cursor.execute("""
                INSERT INTO bookings (request_id, customer_id, ride_id, pickup_location_id, drop_location_id, booking_time, status, fare)
                VALUES (?, ?, ?, ?, ?, ?, 'CONFIRMED', ?);
            """, (request_id, user_id, ride_id, pickup_location_id, drop_location_id, now_iso, fare))
            booking_id = cursor.lastrowid
            
            # Note: For SQLite/MySQL triggers, capacity is automatically decremented by trg_booking_capacity_decrement!
            
            # 4. Insert Simulated Payment Record (Section 5 & 7 of Blueprint)
            cursor.execute("""
                INSERT INTO payment (booking_id, payment_date, amount, status, method)
                VALUES (?, ?, ?, 'PAID', 'UPI_CAMPUS');
            """, (booking_id, now_iso, fare))
            
        flash(f'Seat booked successfully! Booking #{booking_id} confirmed. Remaining capacity decremented.', 'success')
    except Exception as e:
        flash(f'Booking failed due to transaction rollback: {str(e)}', 'danger')
        
    return redirect(url_for('student.student_dashboard'))

@student_bp.route('/bookings/cancel/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    user_id = session['user_id']
    
    try:
        with get_db_transaction() as (cursor, db_type):
            cursor.execute(
                "SELECT * FROM bookings WHERE booking_id = ? AND customer_id = ?",
                (booking_id, user_id)
            )
            row = cursor.fetchone()
            if not row:
                flash('Booking not found or not owned by you.', 'danger')
                return redirect(url_for('student.student_dashboard'))
                
            booking = dict(row) if hasattr(row, 'keys') else {'status': row[7], 'ride_id': row[3]}
            if booking['status'] != 'CONFIRMED':
                flash('Only CONFIRMED bookings can be cancelled.', 'warning')
                return redirect(url_for('student.student_dashboard'))
                
            # 1. Update Booking status to CANCELLED (Triggers seat restoration)
            cursor.execute("UPDATE bookings SET status = 'CANCELLED' WHERE booking_id = ?", (booking_id,))
            
            # 2. Update Payment status to REFUNDED
            cursor.execute("UPDATE payment SET status = 'REFUNDED' WHERE booking_id = ?", (booking_id,))
            
        flash(f'Booking #{booking_id} cancelled successfully! Seat restored to available ride.', 'info')
    except Exception as e:
        flash(f'Cancellation failed: {str(e)}', 'danger')
        
    return redirect(url_for('student.student_dashboard'))

@student_bp.route('/api/rides')
@login_required
def api_rides():
    """Live API endpoint for asynchronous polling of available seats."""
    rides = query_db("""
        SELECT ride_id, remaining_capacity, total_capacity, status
        FROM available_rides
        WHERE status = 'PUBLISHED'
    """)
    return jsonify(rides)
