import unittest
import os
import json
from app import create_app
from database.sqlite_init import init_sqlite_db

class CampusConnectTestCase(unittest.TestCase):
    def setUp(self):
        # Reset DB for test consistency
        init_sqlite_db(force_reset=True)
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

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
            'departure_time': '2026-12-01T10:00',
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

    @classmethod
    def tearDownClass(cls):
        # Always ensure database is left completely clean with 0 rides for presentation!
        init_sqlite_db(force_reset=True)

if __name__ == '__main__':
    unittest.main()
