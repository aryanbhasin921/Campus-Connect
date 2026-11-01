import unittest
import os
import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta
from app import create_app
from config import Config
import database.sqlite_init as sqlite_init
from database.sqlite_init import init_sqlite_db

FUTURE_DEPARTURE = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%dT10:00')

class CampusConnectTestCase(unittest.TestCase):
    def setUp(self):
        # Every test runs against its own temporary database, never the demo database
        self._tmpdir = tempfile.mkdtemp()
        self._orig_paths = (Config.SQLITE_DB_PATH, sqlite_init.DB_PATH)
        test_db = os.path.join(self._tmpdir, 'test.db')
        Config.SQLITE_DB_PATH = test_db
        sqlite_init.DB_PATH = test_db
        init_sqlite_db(force_reset=True)
        self.app = create_app({'TESTING': True, 'CSRF_ENABLED': False})
        self.client = self.app.test_client()

    def tearDown(self):
        Config.SQLITE_DB_PATH, sqlite_init.DB_PATH = self._orig_paths
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def login(self, email, password):
        return self.client.post('/login', data={
            'email': email,
            'password': password
        }, follow_redirects=True)

    def test_01_predecided_admin_login(self):
        """Test pre-decided admin login and access to all DBMS tables"""
        response = self.login('admin@campusconnect.edu', 'admin123')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Admin DBMS Explorer', response.data)
        self.assertIn(b'students', response.data)
        self.assertIn(b'available_rides', response.data)

    def test_02_student_registration_and_unique_constraint(self):
        """Test student registration and enforcement of UNIQUE email & phone constraints"""
        # Register new student
        res1 = self.client.post('/register', data={
            'first_name': 'Test',
            'last_name': 'User',
            'phone_number': '9998887776',
            'email': 'testuser@campusconnect.edu',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertIn(b'Registration successful', res1.data)

        # Duplicate email
        res2 = self.client.post('/register', data={
            'first_name': 'Test2',
            'last_name': 'User2',
            'phone_number': '1112223334',
            'email': 'testuser@campusconnect.edu',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertIn(b'already exists', res2.data)

    def _publish_test_ride(self):
        """Helper to publish a ride for tests"""
        self.login('driver@campusconnect.edu', 'password123')
        return self.client.post('/rides/publish', data={
            'vehicle_number': 'DL-01-AB-1234',
            'departure_time': FUTURE_DEPARTURE,
            'total_capacity': 4,
            'fare_per_passenger': 50.0,
            'start_point': 1,
            'intermediate_points[]': [3],
            'end_point': 6
        }, follow_redirects=True)

    def test_03_driver_publishes_ride_with_intermediate_stops(self):
        """Test driver publishing a ride with start, intermediate, and end stops"""
        res = self._publish_test_ride()
        self.assertIn(b'successfully published with 3 ordered stops', res.data)

    def test_04_booking_and_dynamic_capacity_reflection(self):
        """Test student booking, capacity decrement, and live reflection across students"""
        # Publish ride
        self._publish_test_ride()

        # Student 2 (Riya) logs in
        self.login('riya@campusconnect.edu', 'password123')
        
        # Check API rides before booking
        api_res1 = self.client.get('/api/rides')
        rides1 = json.loads(api_res1.data)
        self.assertTrue(len(rides1) > 0)
        ride1 = rides1[0]
        initial_capacity = ride1['remaining_capacity']

        # Book a seat on Ride 1 (from Gate 1 [1] to Metro [6])
        book_res = self.client.post('/bookings/create', data={
            'ride_id': ride1['ride_id'],
            'pickup_location_id': 1,
            'drop_location_id': 6
        }, follow_redirects=True)
        self.assertIn(b'Seat booked successfully', book_res.data)

        # Student 1 (Rahul) checks API / sees dynamic updated remaining capacity
        self.login('passenger@campusconnect.edu', 'password123')
        api_res2 = self.client.get('/api/rides')
        rides2 = json.loads(api_res2.data)
        ride1_after = next(r for r in rides2 if r['ride_id'] == ride1['ride_id'])
        self.assertEqual(ride1_after['remaining_capacity'], initial_capacity - 1)

    def test_05_cancellation_and_seat_restoration(self):
        """Test booking cancellation and automatic seat capacity restoration via trigger"""
        # Publish ride
        self._publish_test_ride()

        # Book seat
        self.login('passenger@campusconnect.edu', 'password123')
        self.client.post('/bookings/create', data={
            'ride_id': 1,
            'pickup_location_id': 1,
            'drop_location_id': 6
        }, follow_redirects=True)
        
        # Cancel booking #1
        res = self.client.post('/bookings/cancel/1', follow_redirects=True)
        self.assertIn(b'cancelled successfully', res.data)
        self.assertIn(b'Seat restored', res.data)

        # Check API capacity restored back to 4
        api_res = self.client.get('/api/rides')
        rides = json.loads(api_res.data)
        ride1 = next(r for r in rides if r['ride_id'] == 1)
        self.assertEqual(ride1['remaining_capacity'], 4)

    def test_06_admin_add_campus_node(self):
        """Test admin adding a new campus location node"""
        self.login('admin@campusconnect.edu', 'admin123')
        res = self.client.post('/admin/locations/add', data={
            'name': 'Indoor Sports Arena',
            'latitude': 28.6945,
            'longitude': 77.2180
        }, follow_redirects=True)
        self.assertIn(b'Indoor Sports Arena', res.data)

    def test_07_admin_reports_and_views(self):
        """Test admin analytical reports and SQL queries"""
        self.login('admin@campusconnect.edu', 'admin123')
        res = self.client.get('/admin/reports')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Rides with Driver', res.data)
        self.assertIn(b'Popular Pickup Nodes', res.data)

    def test_08_driver_ends_ride_completion(self):
        """Test driver ending/completing a ride and updating passenger bookings"""
        self._publish_test_ride()
        self.login('driver@campusconnect.edu', 'password123')
        # Complete ride 1
        res = self.client.post('/rides/complete/1', follow_redirects=True)
        self.assertIn(b'successfully completed', res.data)

        # Verify that ride 1 status is COMPLETED
        api_res = self.client.get('/api/rides')
        # Ride 1 is no longer in published status
        rides = json.loads(api_res.data)
        self.assertFalse(any(r['ride_id'] == 1 for r in rides))

    # ---- driver_ratings / feedback tests ----
    def _completed_booking(self):
        """Publish ride 1, Rahul (id 2) books it, driver (id 4) completes it."""
        self._publish_test_ride()
        self.login('passenger@campusconnect.edu', 'password123')
        self.client.post('/bookings/create', data={
            'ride_id': 1, 'pickup_location_id': 1, 'drop_location_id': 6
        }, follow_redirects=True)
        self.login('driver@campusconnect.edu', 'password123')
        self.client.post('/rides/complete/1', follow_redirects=True)

    def _raw(self):
        import sqlite3
        conn = sqlite3.connect(Config.SQLITE_DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def test_09_rating_and_feedback_tables_exist_and_admin_lists_them(self):
        conn = self._raw()
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
        conn.close()
        self.assertTrue({'driver_ratings', 'feedback', 'driver_rating_summary_view'} <= names)
        self.login('admin@campusconnect.edu', 'admin123')
        res = self.client.get('/admin?table=driver_ratings')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'feedback', res.data)

    def test_10_rating_and_feedback_on_completed_booking(self):
        self._completed_booking()
        conn = self._raw()
        conn.execute("INSERT INTO driver_ratings (booking_id, driver_id, customer_id, rating) VALUES (1, 4, 2, 5)")
        conn.execute("INSERT INTO feedback (booking_id, driver_id, customer_id, category, comments) VALUES (1, 4, 2, 'PUNCTUALITY', 'On time and smooth ride')")
        conn.commit()
        row = conn.execute("SELECT total_ratings, average_rating FROM driver_rating_summary_view WHERE driver_id = 4").fetchone()
        conn.close()
        self.assertEqual(row, (1, 5.0))

    def test_11_rating_constraints_and_triggers(self):
        import sqlite3
        # Not completed yet: booking is only CONFIRMED
        self._publish_test_ride()
        self.login('passenger@campusconnect.edu', 'password123')
        self.client.post('/bookings/create', data={
            'ride_id': 1, 'pickup_location_id': 1, 'drop_location_id': 6
        }, follow_redirects=True)
        conn = self._raw()
        with self.assertRaises(sqlite3.DatabaseError):
            conn.execute("INSERT INTO driver_ratings (booking_id, driver_id, customer_id, rating) VALUES (1, 4, 2, 5)")
        conn.close()

        self.login('driver@campusconnect.edu', 'password123')
        self.client.post('/rides/complete/1', follow_redirects=True)
        conn = self._raw()
        # Out-of-range rating
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO driver_ratings (booking_id, driver_id, customer_id, rating) VALUES (1, 4, 2, 6)")
        # Wrong customer
        with self.assertRaises(sqlite3.DatabaseError):
            conn.execute("INSERT INTO driver_ratings (booking_id, driver_id, customer_id, rating) VALUES (1, 4, 3, 4)")
        # Wrong driver
        with self.assertRaises(sqlite3.DatabaseError):
            conn.execute("INSERT INTO driver_ratings (booking_id, driver_id, customer_id, rating) VALUES (1, 5, 2, 4)")
        # Valid, then duplicate (UNIQUE booking_id)
        conn.execute("INSERT INTO driver_ratings (booking_id, driver_id, customer_id, rating) VALUES (1, 4, 2, 4)")
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO driver_ratings (booking_id, driver_id, customer_id, rating) VALUES (1, 4, 2, 3)")
        # Feedback: bad category and blank comment
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO feedback (booking_id, driver_id, customer_id, category, comments) VALUES (1, 4, 2, 'BOGUS', 'x')")
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO feedback (booking_id, driver_id, customer_id, category, comments) VALUES (1, 4, 2, 'GENERAL', '   ')")
        conn.close()

    def test_12_student_submits_rating_and_feedback_via_app(self):
        # Not allowed before the ride is completed
        self._publish_test_ride()
        self.login('passenger@campusconnect.edu', 'password123')
        self.client.post('/bookings/create', data={
            'ride_id': 1, 'pickup_location_id': 1, 'drop_location_id': 6
        }, follow_redirects=True)
        early = self.client.post('/bookings/1/review', data={'rating': 5}, follow_redirects=True)
        self.assertIn(b'only after the ride is completed', early.data)

        self.login('driver@campusconnect.edu', 'password123')
        self.client.post('/rides/complete/1', follow_redirects=True)

        # Another student cannot review Rahul's booking
        self.login('riya@campusconnect.edu', 'password123')
        other = self.client.post('/bookings/1/review', data={'rating': 1}, follow_redirects=True)
        self.assertIn(b'not owned by you', other.data)

        # Rahul submits rating + feedback
        self.login('passenger@campusconnect.edu', 'password123')
        page = self.client.get('/student')
        self.assertIn(b'Submit Review', page.data)
        res = self.client.post('/bookings/1/review', data={
            'rating': 4, 'category': 'SAFETY', 'comments': 'Drove carefully'
        }, follow_redirects=True)
        self.assertIn(b'rating and feedback', res.data)
        self.assertIn(b'Drove carefully', res.data)

        conn = self._raw()
        self.assertEqual(conn.execute("SELECT driver_id, customer_id, rating FROM driver_ratings").fetchall(), [(4, 2, 4)])
        self.assertEqual(conn.execute("SELECT driver_id, customer_id, category, comments FROM feedback").fetchall(),
                         [(4, 2, 'SAFETY', 'Drove carefully')])
        conn.close()

        # Duplicate review is rejected
        dup = self.client.post('/bookings/1/review', data={'rating': 2}, follow_redirects=True)
        self.assertIn(b'already rated', dup.data)

        # Driver and admin see it
        self.login('driver@campusconnect.edu', 'password123')
        self.assertIn(b'Drove carefully', self.client.get('/driver').data)
        self.login('admin@campusconnect.edu', 'admin123')
        self.assertIn(b'Drove carefully', self.client.get('/admin/reports').data)

    # ---- validation, security and hardening tests ----
    def _publish(self, **overrides):
        data = {
            'vehicle_number': 'DL-01-AB-1234', 'departure_time': FUTURE_DEPARTURE,
            'total_capacity': 4, 'fare_per_passenger': 50.0,
            'start_point': 1, 'intermediate_points[]': [3], 'end_point': 6,
        }
        data.update(overrides)
        return self.client.post('/rides/publish', data=data, follow_redirects=True)

    def _ride_count(self):
        conn = self._raw()
        n = conn.execute("SELECT COUNT(*) FROM available_rides").fetchone()[0]
        conn.close()
        return n

    def test_13_ride_publish_validation(self):
        self.login('driver@campusconnect.edu', 'password123')
        self.assertIn(b'only publish rides using your own', self._publish(vehicle_number='DL-04-CD-5678').data)
        self.assertIn(b'cannot exceed it', self._publish(total_capacity=50).data)
        self.assertIn(b'must be in the future', self._publish(departure_time='2020-01-01T10:00').data)
        self.assertIn(b'valid departure', self._publish(departure_time='garbage').data)
        self.assertIn(b'invalid location', self._publish(**{'intermediate_points[]': ['abc']}).data)
        self.assertEqual(self._ride_count(), 0)
        self.assertIn(b'successfully published', self._publish().data)
        self.assertEqual(self._ride_count(), 1)

    def test_14_booking_route_validation(self):
        self._publish_test_ride()  # route: 1 -> 3 -> 6
        self.login('passenger@campusconnect.edu', 'password123')
        for pick, drop, msg in [(7, 8, b'both be stops'), (6, 1, b'must come before'), (1, 1, b'must be different')]:
            res = self.client.post('/bookings/create', data={
                'ride_id': 1, 'pickup_location_id': pick, 'drop_location_id': drop}, follow_redirects=True)
            self.assertIn(msg, res.data)
        conn = self._raw()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0], 0)
        conn.close()
        ok = self.client.post('/bookings/create', data={
            'ride_id': 1, 'pickup_location_id': 3, 'drop_location_id': 6}, follow_redirects=True)
        self.assertIn(b'Seat booked successfully', ok.data)

    def test_15_cannot_book_own_ride_or_completed_ride(self):
        self._publish_test_ride()
        res = self.client.post('/bookings/create', data={
            'ride_id': 1, 'pickup_location_id': 1, 'drop_location_id': 6}, follow_redirects=True)
        self.assertIn(b'own published ride', res.data)
        self.client.post('/rides/complete/1', follow_redirects=True)
        again = self.client.post('/rides/complete/1', follow_redirects=True)
        self.assertIn(b'Only a published ride', again.data)
        self.login('passenger@campusconnect.edu', 'password123')
        late = self.client.post('/bookings/create', data={
            'ride_id': 1, 'pickup_location_id': 1, 'drop_location_id': 6}, follow_redirects=True)
        self.assertIn(b'no longer available', late.data)

    def test_16_database_constraints_and_triggers(self):
        self._publish_test_ride()
        conn = self._raw()
        conn.execute("INSERT INTO requests (customer_id, pickup_location_id, drop_location_id, schedule_time) VALUES (2,1,6,'x')")
        with self.assertRaises(sqlite3.IntegrityError):  # identical pickup/drop
            conn.execute("INSERT INTO requests (customer_id, pickup_location_id, drop_location_id, schedule_time) VALUES (2,1,1,'x')")
        conn.execute("UPDATE available_rides SET remaining_capacity = 0 WHERE ride_id = 1")
        with self.assertRaises(sqlite3.DatabaseError):  # trigger: no seats left
            conn.execute("INSERT INTO bookings (request_id, customer_id, ride_id, pickup_location_id, drop_location_id, fare) VALUES (1,2,1,1,6,50)")
        conn.close()

    def test_17_registration_validation(self):
        base = {'first_name': 'A', 'last_name': 'B', 'phone_number': '9990001112',
                'email': 'a@b.edu', 'password': 'longenough1'}
        for override, msg in [({'phone_number': '12ab'}, b'valid phone'), ({'email': 'nope'}, b'valid email'),
                              ({'password': 'short'}, b'at least 8')]:
            res = self.client.post('/register', data={**base, **override}, follow_redirects=True)
            self.assertIn(msg, res.data)

    def test_18_csrf_and_logout(self):
        import re
        self.app.config['CSRF_ENABLED'] = True
        # POST without a token is rejected
        res = self.client.post('/login', data={'email': 'admin@campusconnect.edu', 'password': 'admin123'})
        self.assertEqual(res.status_code, 400)
        # With the token from the form it works
        page = self.client.get('/login').get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        res = self.client.post('/login', data={'email': 'admin@campusconnect.edu',
                                               'password': 'admin123', 'csrf_token': token}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        # Logout is POST-only and token protected
        self.assertEqual(self.client.get('/logout').status_code, 405)
        self.assertEqual(self.client.post('/logout').status_code, 400)
        page = self.client.get('/admin').get_data(as_text=True)
        token = re.search(r'action="/logout" method="POST"[^>]*>\s*<input type="hidden" name="csrf_token" value="([^"]+)"', page).group(1)
        res = self.client.post('/logout', data={'csrf_token': token})
        self.assertEqual(res.status_code, 302)

    def test_19_sql_console_is_read_only_and_hides_hashes(self):
        self.login('admin@campusconnect.edu', 'admin123')
        res = self.client.post('/admin/sql', data={'sql_query': 'SELECT * FROM students'}, follow_redirects=True)
        self.assertNotIn(b'scrypt', res.data)
        self.assertIn(b'Rahul', res.data)
        res = self.client.post('/admin/sql', data={'sql_query': 'DELETE FROM payment'}, follow_redirects=True)
        self.assertIn(b'read-only', res.data)
        res = self.client.post('/admin/sql', data={'sql_query': "SELECT 1; DELETE FROM payment"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        explorer = self.client.get('/admin?table=students')
        self.assertNotIn(b'scrypt', explorer.data)

    def test_20_error_pages_and_vehicle_registration(self):
        res = self.client.get('/does-not-exist')
        self.assertEqual(res.status_code, 404)
        self.assertIn(b'Page Not Found', res.data)
        self.login('driver@campusconnect.edu', 'password123')
        res = self.client.post('/vehicles/add', data={
            'vehicle_number': 'DL-04-CD-5678', 'vehicle_name': 'Hijack', 'vehicle_type': 'Sedan',
            'year_of_manufacture': 2020, 'capacity': 4}, follow_redirects=True)
        self.assertIn(b'already registered to another driver', res.data)
        res = self.client.post('/vehicles/add', data={
            'vehicle_number': 'DL-09-ZZ-0001', 'vehicle_name': 'Own Car', 'vehicle_type': 'Sedan',
            'year_of_manufacture': 2020, 'capacity': 4}, follow_redirects=True)
        self.assertIn(b'successfully registered', res.data)
        res = self.client.post('/vehicles/add', data={
            'vehicle_number': 'DL-09-ZZ-0002', 'vehicle_name': 'Bad', 'vehicle_type': 'Sedan',
            'year_of_manufacture': 1800, 'capacity': 4}, follow_redirects=True)
        self.assertIn(b'valid vehicle manufacture year', res.data)

if __name__ == '__main__':
    unittest.main()
