from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime, date
from db import query_db, execute_db, get_db_transaction
from routes.auth import login_required

driver_bp = Blueprint('driver', __name__)

@driver_bp.route('/driver')
@login_required
def driver_dashboard():
    user_id = session['user_id']
    
    # 1. Check if student is registered as a driver
    driver_info = query_db("""
        SELECT d.*, s.first_name, s.last_name, s.phone_number, s.email
        FROM drivers d
        JOIN students s ON s.student_id = d.student_id
        WHERE d.student_id = ?
    """, (user_id,), one=True)
    
    # 2. Fetch driver's registered vehicles
    vehicles = []
    if driver_info:
        vehicles = query_db("""
            SELECT v.* 
            FROM vehicle v
            JOIN driver_vehicle dv ON dv.vehicle_number = v.vehicle_number
            WHERE dv.student_id = ?
        """, (user_id,))
        
    # 3. Fetch all campus locations for route creation
    locations = query_db("SELECT * FROM locations ORDER BY name ASC")
    
    # 4. Fetch THIS driver's published rides only (Strict privacy rule)
    my_rides = []
    if driver_info:
        rides_raw = query_db("""
            SELECT 
                ar.*,
                v.name AS vehicle_name,
                v.type AS vehicle_type
            FROM available_rides ar
            JOIN vehicle v ON v.vehicle_number = ar.vehicle_number
            WHERE ar.driver_id = ?
            ORDER BY ar.departure_time DESC
        """, (user_id,))
        
        for r in rides_raw:
            # Fetch route stops in order
            stops = query_db("""
                SELECT rp.sequence_no, l.name
                FROM ride_points rp
                JOIN locations l ON l.location_id = rp.location_id
                WHERE rp.ride_id = ?
                ORDER BY rp.sequence_no ASC
            """, (r['ride_id'],))
            r['stops'] = stops
            
            # Fetch booked passengers for this ride
            passengers = query_db("""
                SELECT 
                    b.booking_id,
                    b.booking_time,
                    b.status AS booking_status,
                    b.fare,
                    s.first_name,
                    s.last_name,
                    s.phone_number,
                    l_pick.name AS pickup_name,
                    l_drop.name AS drop_name,
                    p.status AS payment_status,
                    p.method AS payment_method
                FROM bookings b
                JOIN students s ON s.student_id = b.customer_id
                JOIN locations l_pick ON l_pick.location_id = b.pickup_location_id
                JOIN locations l_drop ON l_drop.location_id = b.drop_location_id
                LEFT JOIN payment p ON p.booking_id = b.booking_id
                WHERE b.ride_id = ?
                ORDER BY b.booking_time DESC
            """, (r['ride_id'],))
            r['passengers'] = passengers
            my_rides.append(r)
            
    return render_template(
        'driver_view.html',
        driver_info=driver_info,
        vehicles=vehicles,
        locations=locations,
        my_rides=my_rides,
        today=date.today().isoformat()
    )

@driver_bp.route('/driver/register', methods=['POST'])
@login_required
def register_driver():
    user_id = session['user_id']
    licence_id = request.form.get('licence_id', '').strip()
    licence_expiry_date = request.form.get('licence_expiry_date', '').strip()
    upi_id = request.form.get('upi_id', '').strip()
    
    # Vehicle fields
    vehicle_number = request.form.get('vehicle_number', '').strip().upper()
    vehicle_name = request.form.get('vehicle_name', '').strip()
    vehicle_type = request.form.get('vehicle_type', '').strip()
    vehicle_colour = request.form.get('vehicle_colour', '').strip()
    year = request.form.get('year_of_manufacture', type=int)
    capacity = request.form.get('capacity', type=int)
    
    if not (licence_id and licence_expiry_date and vehicle_number and vehicle_name and vehicle_type and capacity):
        flash('All driver and vehicle registration fields are required.', 'danger')
        return redirect(url_for('driver.driver_dashboard'))
        
    try:
        with get_db_transaction() as (cursor, db_type):
            # 1. Insert Driver
            cursor.execute("""
                INSERT INTO drivers (student_id, licence_id, licence_expiry_date, upi_id)
                VALUES (?, ?, ?, ?);
            """, (user_id, licence_id, licence_expiry_date, upi_id))
            
            # 2. Insert Vehicle
            cursor.execute("""
                INSERT OR IGNORE INTO vehicle (vehicle_number, type, name, colour, year_of_manufacture, capacity)
                VALUES (?, ?, ?, ?, ?, ?);
            """ if db_type == 'sqlite' else """
                INSERT INTO vehicle (vehicle_number, type, name, colour, year_of_manufacture, capacity)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE name=VALUES(name);
            """, (vehicle_number, vehicle_type, vehicle_name, vehicle_colour, year, capacity))
            
            # 3. Associate Driver with Vehicle
            cursor.execute("""
                INSERT OR IGNORE INTO driver_vehicle (student_id, vehicle_number)
                VALUES (?, ?);
            """ if db_type == 'sqlite' else """
                INSERT INTO driver_vehicle (student_id, vehicle_number)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE student_id=student_id;
            """, (user_id, vehicle_number))
            
            # Update student current_mode
            cursor.execute("UPDATE students SET current_mode = 'DRIVER' WHERE student_id = ?", (user_id,))
            
        session['is_driver'] = True
        session['current_mode'] = 'DRIVER'
        flash('Congratulations! You are now registered as a Campus Driver and your vehicle is linked.', 'success')
    except Exception as e:
        flash(f'Driver registration failed: {str(e)}', 'danger')
        
    return redirect(url_for('driver.driver_dashboard'))

@driver_bp.route('/vehicles/add', methods=['POST'])
@login_required
def add_vehicle():
    user_id = session['user_id']
    vehicle_number = request.form.get('vehicle_number', '').strip().upper()
    vehicle_name = request.form.get('vehicle_name', '').strip()
    vehicle_type = request.form.get('vehicle_type', '').strip()
    vehicle_colour = request.form.get('vehicle_colour', '').strip()
    year = request.form.get('year_of_manufacture', type=int)
    capacity = request.form.get('capacity', type=int)
    
    if not (vehicle_number and vehicle_name and vehicle_type and capacity):
        flash('Please fill all required vehicle fields.', 'danger')
        return redirect(url_for('driver.driver_dashboard'))
        
    try:
        with get_db_transaction() as (cursor, db_type):
            cursor.execute("""
                INSERT OR IGNORE INTO vehicle (vehicle_number, type, name, colour, year_of_manufacture, capacity)
                VALUES (?, ?, ?, ?, ?, ?);
            """ if db_type == 'sqlite' else """
                INSERT INTO vehicle (vehicle_number, type, name, colour, year_of_manufacture, capacity)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE name=VALUES(name);
            """, (vehicle_number, vehicle_type, vehicle_name, vehicle_colour, year, capacity))
            
            cursor.execute("""
                INSERT OR IGNORE INTO driver_vehicle (student_id, vehicle_number)
                VALUES (?, ?);
            """ if db_type == 'sqlite' else """
                INSERT INTO driver_vehicle (student_id, vehicle_number)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE student_id=student_id;
            """, (user_id, vehicle_number))
            
        flash(f'Vehicle {vehicle_number} successfully registered to your profile.', 'success')
    except Exception as e:
        flash(f'Could not register vehicle: {str(e)}', 'danger')
        
    return redirect(url_for('driver.driver_dashboard'))

@driver_bp.route('/rides/publish', methods=['POST'])
@login_required
def publish_ride():
    user_id = session['user_id']
    vehicle_number = request.form.get('vehicle_number', '').strip()
    departure_time = request.form.get('departure_time', '').strip()
    total_capacity = request.form.get('total_capacity', type=int)
    fare = request.form.get('fare_per_passenger', type=float, default=50.0)
    
    # Ordered stops from form (start stop, intermediate stops, end stop)
    start_point = request.form.get('start_point', type=int)
    end_point = request.form.get('end_point', type=int)
    intermediate_points = request.form.getlist('intermediate_points[]')
    
    if not (vehicle_number and departure_time and total_capacity and start_point and end_point):
        flash('Please complete all ride publishing details and choose valid start/end points.', 'danger')
        return redirect(url_for('driver.driver_dashboard'))
        
    if start_point == end_point:
        flash('Start location and destination cannot be identical!', 'warning')
        return redirect(url_for('driver.driver_dashboard'))
        
    # Build complete ordered list of location IDs
    ordered_location_ids = [start_point]
    for pt in intermediate_points:
        try:
            pt_int = int(pt)
            if pt_int not in ordered_location_ids and pt_int != end_point:
                ordered_location_ids.append(pt_int)
        except (ValueError, TypeError):
            continue
    ordered_location_ids.append(end_point)
    
    try:
        with get_db_transaction() as (cursor, db_type):
            # Check licence expiry (Section 6 & 8: Licence validation trigger/rule)
            cursor.execute("SELECT licence_expiry_date FROM drivers WHERE student_id = ?", (user_id,))
            licence_row = cursor.fetchone()
            if not licence_row:
                flash('You must be a registered driver to publish a ride.', 'danger')
                return redirect(url_for('driver.driver_dashboard'))
                
            expiry = licence_row[0] if isinstance(licence_row, tuple) else licence_row['licence_expiry_date']
            if str(expiry) < date.today().isoformat():
                flash('Cannot publish ride: Your driver licence has expired! (DBMS Rule / Trigger constraint)', 'danger')
                return redirect(url_for('driver.driver_dashboard'))
                
            # 1. Insert into available_rides
            cursor.execute("""
                INSERT INTO available_rides (
                    driver_id, vehicle_number, departure_time, total_capacity, remaining_capacity, fare_per_passenger, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'PUBLISHED');
            """, (user_id, vehicle_number, departure_time, total_capacity, total_capacity, fare))
            ride_id = cursor.lastrowid
            
            # 2. Insert ordered ride_points
            for seq, loc_id in enumerate(ordered_location_ids, start=1):
                cursor.execute("""
                    INSERT INTO ride_points (ride_id, sequence_no, location_id)
                    VALUES (?, ?, ?);
                """, (ride_id, seq, loc_id))
                
        flash(f'Ride #{ride_id} successfully published with {len(ordered_location_ids)} ordered stops! Passengers can now book seats.', 'success')
    except Exception as e:
        flash(f'Failed to publish ride: {str(e)}', 'danger')
        
    return redirect(url_for('driver.driver_dashboard'))

@driver_bp.route('/rides/complete/<int:ride_id>', methods=['POST'])
@login_required
def complete_ride(ride_id):
    user_id = session['user_id']
    
    try:
        with get_db_transaction() as (cursor, db_type):
            # 1. Verify that the ride belongs to this driver
            cursor.execute("SELECT * FROM available_rides WHERE ride_id = ? AND driver_id = ?", (ride_id, user_id))
            ride = cursor.fetchone()
            if not ride:
                flash('Ride not found or not owned by you.', 'danger')
                return redirect(url_for('driver.driver_dashboard'))
                
            # 2. Update Ride status to COMPLETED
            cursor.execute("UPDATE available_rides SET status = 'COMPLETED' WHERE ride_id = ?", (ride_id,))
            
            # 3. Update all confirmed bookings for this ride to COMPLETED
            cursor.execute("""
                UPDATE bookings 
                SET status = 'COMPLETED' 
                WHERE ride_id = ? AND status = 'CONFIRMED'
            """, (ride_id,))
            
            # 4. Update requests status to COMPLETED
            cursor.execute("""
                UPDATE requests
                SET status = 'COMPLETED'
                WHERE request_id IN (SELECT request_id FROM bookings WHERE ride_id = ?)
            """, (ride_id,))
            
        flash(f'Ride #{ride_id} has been successfully completed! All passenger trips are marked as COMPLETED.', 'success')
    except Exception as e:
        flash(f'Error completing ride: {str(e)}', 'danger')
        
    return redirect(url_for('driver.driver_dashboard'))

