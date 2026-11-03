from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
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
    sort_by = request.args.get('sort_by', 'time').strip()
    search_date = request.args.get('search_date', '').strip()
    if search_date:
        try:
            datetime.strptime(search_date, '%Y-%m-%d')
        except ValueError:
            flash('Invalid search date. Please select a valid date.', 'warning')
            search_date = ''
    
    # 3. Query published rides with seats remaining and driver ratings
    # We load all published rides first, then match stops sequence
    order_clause = "ORDER BY r_stat.avg_rating DESC, ar.departure_time ASC" if sort_by == 'rating' else "ORDER BY ar.departure_time ASC"
    rides_query = f"""
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
        v.colour AS vehicle_colour,
        COALESCE(r_stat.avg_rating, 0) AS avg_rating,
        COALESCE(r_stat.total_ratings, 0) AS total_ratings
    FROM available_rides ar
    JOIN drivers d ON d.student_id = ar.driver_id
    JOIN students s ON s.student_id = d.student_id
    JOIN vehicle v ON v.vehicle_number = ar.vehicle_number
    LEFT JOIN (
        SELECT driver_id, ROUND(AVG(rating), 1) AS avg_rating, COUNT(*) AS total_ratings
        FROM driver_ratings
        GROUP BY driver_id
    ) r_stat ON r_stat.driver_id = ar.driver_id
    WHERE ar.status = 'PUBLISHED'
      AND ar.remaining_capacity > 0
      AND ar.departure_time >= ?
    {order_clause};
    """
    now_str = datetime.now().strftime('%Y-%m-%dT%H:%M')
    all_rides = query_db(rides_query, (now_str,))
    
    # Attach ordered route stops to each ride (one query for all rides)
    stops_by_ride = {}
    for stop in query_db("""
        SELECT rp.ride_id, rp.sequence_no, rp.location_id, l.name
        FROM ride_points rp
        JOIN locations l ON l.location_id = rp.location_id
        ORDER BY rp.ride_id, rp.sequence_no ASC
    """):
        stops_by_ride.setdefault(stop['ride_id'], []).append(stop)

    matched_rides = []
    for ride in all_rides:
        stops = stops_by_ride.get(ride['ride_id'], [])
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
            v.vehicle_number,
            dr.rating AS my_rating,
            f.category AS fb_category,
            f.comments AS fb_comments
        FROM bookings b
        JOIN available_rides ar ON ar.ride_id = b.ride_id
        JOIN drivers d ON d.student_id = ar.driver_id
        JOIN students s_driver ON s_driver.student_id = d.student_id
        JOIN vehicle v ON v.vehicle_number = ar.vehicle_number
        JOIN locations l_pick ON l_pick.location_id = b.pickup_location_id
        JOIN locations l_drop ON l_drop.location_id = b.drop_location_id
        LEFT JOIN payment p ON p.booking_id = b.booking_id
        LEFT JOIN driver_ratings dr ON dr.booking_id = b.booking_id
        LEFT JOIN feedback f ON f.booking_id = b.booking_id
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
        search_date=search_date,
        sort_by=sort_by
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

            # Validation: ride must still be open and not already departed
            if ride['status'] != 'PUBLISHED':
                flash('This ride is no longer available for booking.', 'warning')
                return redirect(url_for('student.student_dashboard'))
            try:
                if datetime.fromisoformat(str(ride['departure_time'])) <= datetime.now():
                    flash('You cannot book a ride that has already departed.', 'warning')
                    return redirect(url_for('student.student_dashboard'))
            except ValueError:
                pass

            # Validation: pickup/drop must be stops of THIS ride, pickup before drop
            if pickup_location_id == drop_location_id:
                flash('Pickup and drop-off locations must be different.', 'warning')
                return redirect(url_for('student.student_dashboard'))
            cursor.execute("SELECT sequence_no, location_id FROM ride_points WHERE ride_id = ?", (ride_id,))
            stop_order = {r[1]: r[0] for r in cursor.fetchall()}
            if pickup_location_id not in stop_order or drop_location_id not in stop_order:
                flash('Pickup and drop-off must both be stops on this ride\'s route.', 'danger')
                return redirect(url_for('student.student_dashboard'))
            if stop_order[pickup_location_id] >= stop_order[drop_location_id]:
                flash('Pickup stop must come before the drop-off stop on the route.', 'danger')
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
    except Exception:
        current_app.logger.exception('Booking transaction failed')
        flash('Booking could not be completed. Please try again.', 'danger')
        
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
    except Exception:
        current_app.logger.exception('Cancellation failed')
        flash('Cancellation could not be completed. Please try again.', 'danger')
        
    return redirect(url_for('student.student_dashboard'))

FEEDBACK_CATEGORIES = ['GENERAL', 'PUNCTUALITY', 'SAFETY', 'VEHICLE', 'BEHAVIOUR', 'PAYMENT']

@student_bp.route('/bookings/<int:booking_id>/review', methods=['POST'])
@login_required
def review_booking(booking_id):
    """Save the student's driver rating (driver_ratings) and/or written feedback (feedback)."""
    user_id = session['user_id']
    rating = request.form.get('rating', type=int)
    category = request.form.get('category', 'GENERAL').strip().upper()
    comments = request.form.get('comments', '').strip()

    if rating is None and not comments:
        flash('Please give a star rating, write feedback, or both.', 'warning')
        return redirect(url_for('student.student_dashboard'))
    if rating is not None and not (1 <= rating <= 5):
        flash('Rating must be between 1 and 5 stars.', 'danger')
        return redirect(url_for('student.student_dashboard'))
    if category not in FEEDBACK_CATEGORIES:
        category = 'GENERAL'

    try:
        with get_db_transaction() as (cursor, db_type):
            cursor.execute("""
                SELECT b.booking_id, b.status, ar.driver_id
                FROM bookings b
                JOIN available_rides ar ON ar.ride_id = b.ride_id
                WHERE b.booking_id = ? AND b.customer_id = ?
            """, (booking_id, user_id))
            row = cursor.fetchone()
            if not row:
                flash('Booking not found or not owned by you.', 'danger')
                return redirect(url_for('student.student_dashboard'))
            status, driver_id = row[1], row[2]
            if status != 'COMPLETED':
                flash('You can rate a driver only after the ride is completed.', 'warning')
                return redirect(url_for('student.student_dashboard'))

            saved = []
            if rating is not None:
                cursor.execute("SELECT 1 FROM driver_ratings WHERE booking_id = ?", (booking_id,))
                if cursor.fetchone():
                    flash('You have already rated this ride.', 'warning')
                else:
                    cursor.execute("""
                        INSERT INTO driver_ratings (booking_id, driver_id, customer_id, rating)
                        VALUES (?, ?, ?, ?);
                    """, (booking_id, driver_id, user_id, rating))
                    saved.append('rating')
            if comments:
                cursor.execute("SELECT 1 FROM feedback WHERE booking_id = ?", (booking_id,))
                if cursor.fetchone():
                    flash('You have already submitted feedback for this ride.', 'warning')
                else:
                    cursor.execute("""
                        INSERT INTO feedback (booking_id, driver_id, customer_id, category, comments)
                        VALUES (?, ?, ?, ?, ?);
                    """, (booking_id, driver_id, user_id, category, comments))
                    saved.append('feedback')

        if saved:
            flash(f"Thank you! Your {' and '.join(saved)} for booking #{booking_id} was saved.", 'success')
    except Exception:
        current_app.logger.exception('Saving review failed')
        flash('Could not save your review. Please try again.', 'danger')

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
