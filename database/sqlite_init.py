import os
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'campusconnect.db')

def init_sqlite_db(force_reset=False):
    if force_reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # 1. Students table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        student_id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        phone_number TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'STUDENT',
        current_mode TEXT NOT NULL DEFAULT 'PASSENGER',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Drivers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS drivers (
        student_id INTEGER PRIMARY KEY,
        licence_id TEXT UNIQUE NOT NULL,
        licence_expiry_date DATE NOT NULL,
        upi_id TEXT,
        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
    );
    """)

    # 3. Vehicle table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicle (
        vehicle_number TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        name TEXT NOT NULL,
        colour TEXT,
        year_of_manufacture INTEGER,
        capacity INTEGER NOT NULL CHECK (capacity > 0)
    );
    """)

    # 4. Driver-Vehicle table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS driver_vehicle (
        student_id INTEGER NOT NULL,
        vehicle_number TEXT NOT NULL,
        PRIMARY KEY (student_id, vehicle_number),
        FOREIGN KEY (student_id) REFERENCES drivers(student_id) ON DELETE CASCADE,
        FOREIGN KEY (vehicle_number) REFERENCES vehicle(vehicle_number) ON DELETE CASCADE
    );
    """)

    # 5. Locations table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        location_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        latitude REAL,
        longitude REAL
    );
    """)

    # 6. Available Rides table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS available_rides (
        ride_id INTEGER PRIMARY KEY AUTOINCREMENT,
        driver_id INTEGER NOT NULL,
        vehicle_number TEXT NOT NULL,
        departure_time TIMESTAMP NOT NULL,
        total_capacity INTEGER NOT NULL CHECK (total_capacity > 0),
        remaining_capacity INTEGER NOT NULL CHECK (remaining_capacity >= 0 AND remaining_capacity <= total_capacity),
        fare_per_passenger REAL NOT NULL DEFAULT 50.00 CHECK (fare_per_passenger >= 0),
        status TEXT NOT NULL DEFAULT 'PUBLISHED',
        FOREIGN KEY (driver_id) REFERENCES drivers(student_id),
        FOREIGN KEY (vehicle_number) REFERENCES vehicle(vehicle_number)
    );
    """)

    # 7. Ride Points (Route Stops)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ride_points (
        ride_id INTEGER NOT NULL,
        sequence_no INTEGER NOT NULL,
        location_id INTEGER NOT NULL,
        PRIMARY KEY (ride_id, sequence_no),
        FOREIGN KEY (ride_id) REFERENCES available_rides(ride_id) ON DELETE CASCADE,
        FOREIGN KEY (location_id) REFERENCES locations(location_id)
    );
    """)

    # 8. Requests table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS requests (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        pickup_location_id INTEGER NOT NULL,
        drop_location_id INTEGER NOT NULL,
        schedule_time TIMESTAMP NOT NULL,
        status TEXT NOT NULL DEFAULT 'CONFIRMED',
        FOREIGN KEY (customer_id) REFERENCES students(student_id),
        FOREIGN KEY (pickup_location_id) REFERENCES locations(location_id),
        FOREIGN KEY (drop_location_id) REFERENCES locations(location_id),
        CHECK (pickup_location_id <> drop_location_id)
    );
    """)

    # 9. Bookings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER UNIQUE NOT NULL,
        customer_id INTEGER NOT NULL,
        ride_id INTEGER NOT NULL,
        pickup_location_id INTEGER NOT NULL,
        drop_location_id INTEGER NOT NULL,
        booking_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'CONFIRMED',
        fare REAL NOT NULL CHECK (fare >= 0),
        FOREIGN KEY (request_id) REFERENCES requests(request_id),
        FOREIGN KEY (customer_id) REFERENCES students(student_id),
        FOREIGN KEY (ride_id) REFERENCES available_rides(ride_id),
        FOREIGN KEY (pickup_location_id) REFERENCES locations(location_id),
        FOREIGN KEY (drop_location_id) REFERENCES locations(location_id),
        CHECK (pickup_location_id <> drop_location_id)
    );
    """)

    # 10. Payment table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payment (
        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL UNIQUE,
        payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        amount REAL NOT NULL CHECK (amount >= 0),
        status TEXT NOT NULL DEFAULT 'PAID',
        method TEXT NOT NULL DEFAULT 'UPI',
        FOREIGN KEY (booking_id) REFERENCES bookings(booking_id)
    );
    """)

    # 11. Driver Ratings table (one 1-5 star rating per completed booking)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS driver_ratings (
        rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER UNIQUE NOT NULL,
        driver_id INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
        rated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (booking_id) REFERENCES bookings(booking_id),
        FOREIGN KEY (driver_id) REFERENCES drivers(student_id),
        FOREIGN KEY (customer_id) REFERENCES students(student_id)
    );
    """)

    # 12. Feedback table (written feedback by a customer about a completed booking)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER UNIQUE NOT NULL,
        driver_id INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        category TEXT NOT NULL DEFAULT 'GENERAL'
            CHECK (category IN ('GENERAL','PUNCTUALITY','SAFETY','VEHICLE','BEHAVIOUR','PAYMENT')),
        comments TEXT NOT NULL CHECK (LENGTH(TRIM(comments)) > 0),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (booking_id) REFERENCES bookings(booking_id),
        FOREIGN KEY (driver_id) REFERENCES drivers(student_id),
        FOREIGN KEY (customer_id) REFERENCES students(student_id)
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ratings_driver ON driver_ratings(driver_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_driver ON feedback(driver_id);")

    # Views
    cursor.execute("""
    CREATE VIEW IF NOT EXISTS confirmed_bookings_view AS
    SELECT 
        booking_id, 
        customer_id, 
        ride_id,
        pickup_location_id, 
        drop_location_id, 
        fare
    FROM bookings
    WHERE status = 'CONFIRMED';
    """)

    cursor.execute("""
    CREATE VIEW IF NOT EXISTS published_rides_view AS
    SELECT 
        ride_id, 
        driver_id, 
        vehicle_number,
        departure_time, 
        remaining_capacity
    FROM available_rides
    WHERE status = 'PUBLISHED'
      AND remaining_capacity > 0;
    """)

    cursor.execute("""
    CREATE VIEW IF NOT EXISTS driver_rating_summary_view AS
    SELECT
        d.student_id AS driver_id,
        s.first_name || ' ' || s.last_name AS driver_name,
        COUNT(r.rating_id) AS total_ratings,
        ROUND(AVG(r.rating), 2) AS average_rating
    FROM drivers d
    JOIN students s ON s.student_id = d.student_id
    LEFT JOIN driver_ratings r ON r.driver_id = d.student_id
    GROUP BY d.student_id, s.first_name, s.last_name;
    """)

    # Triggers
    # Reject a confirmed booking on a ride that is not PUBLISHED or has no seats left,
    # then decrement capacity. (Dropped first so existing databases get the new version.)
    cursor.execute("DROP TRIGGER IF EXISTS trg_booking_capacity_decrement;")
    cursor.execute("DROP TRIGGER IF EXISTS trg_booking_capacity_check;")
    cursor.execute("""
    CREATE TRIGGER trg_booking_capacity_check
    BEFORE INSERT ON bookings
    FOR EACH ROW
    WHEN NEW.status = 'CONFIRMED'
    BEGIN
        SELECT CASE
            WHEN NOT EXISTS (
                SELECT 1 FROM available_rides
                WHERE ride_id = NEW.ride_id AND status = 'PUBLISHED' AND remaining_capacity > 0
            )
            THEN RAISE(ABORT, 'Ride is unavailable or has no remaining seats.')
        END;
    END;
    """)
    cursor.execute("""
    CREATE TRIGGER trg_booking_capacity_decrement
    AFTER INSERT ON bookings
    FOR EACH ROW
    WHEN NEW.status = 'CONFIRMED'
    BEGIN
        UPDATE available_rides
        SET remaining_capacity = remaining_capacity - 1
        WHERE ride_id = NEW.ride_id;
    END;
    """)

    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_booking_capacity_restore
    AFTER UPDATE OF status ON bookings
    FOR EACH ROW
    WHEN OLD.status = 'CONFIRMED' AND NEW.status = 'CANCELLED'
    BEGIN
        UPDATE available_rides
        SET remaining_capacity = MIN(total_capacity, remaining_capacity + 1)
        WHERE ride_id = NEW.ride_id;
    END;
    """)

    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_check_driver_licence
    BEFORE INSERT ON available_rides
    FOR EACH ROW
    BEGIN
        SELECT CASE
            WHEN (SELECT licence_expiry_date FROM drivers WHERE student_id = NEW.driver_id) < DATE('now')
            THEN RAISE(ABORT, 'Error: Driver licence has expired. Cannot publish ride.')
        END;
    END;
    """)

    # Rating / feedback integrity: only the customer of a COMPLETED booking may rate it,
    # and the driver recorded must be the driver of that booking's ride.
    for tbl, label in (('driver_ratings', 'rate'), ('feedback', 'leave feedback for')):
        cursor.execute(f"""
        CREATE TRIGGER IF NOT EXISTS trg_validate_{tbl}
        BEFORE INSERT ON {tbl}
        FOR EACH ROW
        BEGIN
            SELECT CASE
                WHEN (SELECT status FROM bookings WHERE booking_id = NEW.booking_id) IS NOT 'COMPLETED'
                THEN RAISE(ABORT, 'Error: You can only {label} a COMPLETED booking.')
                WHEN (SELECT customer_id FROM bookings WHERE booking_id = NEW.booking_id) IS NOT NEW.customer_id
                THEN RAISE(ABORT, 'Error: Only the customer of this booking can {label} it.')
                WHEN (SELECT ar.driver_id FROM bookings b JOIN available_rides ar ON ar.ride_id = b.ride_id
                      WHERE b.booking_id = NEW.booking_id) IS NOT NEW.driver_id
                THEN RAISE(ABORT, 'Error: Driver does not match the driver of this booking.')
            END;
        END;
        """)

    # Seed data if empty
    cursor.execute("SELECT COUNT(*) FROM students;")
    count = cursor.fetchone()[0]
    if count == 0:
        admin_hash = generate_password_hash('admin123')
        pass_hash = generate_password_hash('password123')
        now = datetime.now()
        dep1 = (now + timedelta(days=1)).strftime('%Y-%m-%d 09:00:00')
        dep2 = (now + timedelta(days=2)).strftime('%Y-%m-%d 17:30:00')

        # 1. Students
        cursor.executemany("""
        INSERT INTO students (student_id, first_name, last_name, phone_number, email, password_hash, role, current_mode)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, [
            (1, 'Admin', 'User', '9999900000', 'admin@campusconnect.edu', admin_hash, 'ADMIN', 'PASSENGER'),
            (2, 'Rahul', 'Sharma', '9811122233', 'passenger@campusconnect.edu', pass_hash, 'STUDENT', 'PASSENGER'),
            (3, 'Riya', 'Patel', '9822233344', 'riya@campusconnect.edu', pass_hash, 'STUDENT', 'PASSENGER'),
            (4, 'Arjun', 'Verma', '9833344455', 'driver@campusconnect.edu', pass_hash, 'STUDENT', 'DRIVER'),
            (5, 'Kavita', 'Rao', '9844455566', 'driver2@campusconnect.edu', pass_hash, 'STUDENT', 'DRIVER')
        ])

        # 2. Drivers
        cursor.executemany("""
        INSERT INTO drivers (student_id, licence_id, licence_expiry_date, upi_id)
        VALUES (?, ?, ?, ?);
        """, [
            (4, 'DL-1420110012345', '2028-12-31', 'arjun@okaxis'),
            (5, 'DL-1420150067890', '2027-06-30', 'kavita@okhdfc')
        ])

        # 3. Vehicles
        cursor.executemany("""
        INSERT INTO vehicle (vehicle_number, type, name, colour, year_of_manufacture, capacity)
        VALUES (?, ?, ?, ?, ?, ?);
        """, [
            ('DL-01-AB-1234', 'Sedan', 'Honda City', 'Silver', 2022, 4),
            ('DL-04-CD-5678', 'Hatchback', 'Maruti Swift', 'White', 2021, 3),
            ('HR-26-EE-9999', 'SUV', 'Hyundai Creta', 'Black', 2023, 4)
        ])

        # 4. Driver Vehicle
        cursor.executemany("""
        INSERT INTO driver_vehicle (student_id, vehicle_number)
        VALUES (?, ?);
        """, [
            (4, 'DL-01-AB-1234'),
            (5, 'DL-04-CD-5678')
        ])

        # 5. Locations (Nodes)
        cursor.executemany("""
        INSERT INTO locations (location_id, name, latitude, longitude)
        VALUES (?, ?, ?, ?);
        """, [
            (1, 'North Campus Gate 1', 28.6901230, 77.2145670),
            (2, 'University Library', 28.6885400, 77.2163400),
            (3, 'Tech Block & Labs', 28.6864100, 77.2189200),
            (4, 'Boys Hostel Block A', 28.6923000, 77.2110000),
            (5, 'Girls Hostel Block B', 28.6931000, 77.2125000),
            (6, 'University Metro Station', 28.6980000, 77.2195000),
            (7, 'City Center Mall', 28.7042000, 77.2281000),
            (8, 'Railway Junction', 28.7115000, 77.2356000)
        ])

        # Starts with 0 published rides/bookings - ready for live presentation!

    conn.commit()
    conn.close()
    print("SQLite database initialized successfully at", DB_PATH)

if __name__ == '__main__':
    init_sqlite_db(force_reset=True)
