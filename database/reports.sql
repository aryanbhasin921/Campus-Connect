-- ========================================================
-- CampusCommute Analytical DBMS Reports (Blueprint Section 7)
-- ========================================================

USE campuscommute;

-- 1. Rides with Driver and Vehicle Details
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
  AND ar.remaining_capacity > 0;

-- 2. Count Confirmed Bookings Per Ride
SELECT 
    b.ride_id, 
    COUNT(*) AS total_bookings,
    SUM(b.fare) AS total_revenue
FROM bookings b
WHERE b.status = 'CONFIRMED'
GROUP BY b.ride_id;

-- 3. Popular Pickup Locations (Aggregation & JOIN)
SELECT 
    l.location_id,
    l.name AS pickup_location, 
    COUNT(*) AS total_pickups
FROM bookings b
JOIN locations l ON l.location_id = b.pickup_location_id
WHERE b.status = 'CONFIRMED'
GROUP BY l.location_id, l.name
ORDER BY total_pickups DESC;

-- 4. Confirmed Booking Fares by Driver
SELECT 
    ar.driver_id,
    CONCAT(s.first_name, ' ', s.last_name) AS driver_name,
    COUNT(b.booking_id) AS total_rides_booked,
    COALESCE(SUM(b.fare), 0) AS total_fares
FROM available_rides ar
JOIN drivers d ON d.student_id = ar.driver_id
JOIN students s ON s.student_id = d.student_id
JOIN bookings b ON b.ride_id = ar.ride_id
WHERE b.status = 'CONFIRMED'
GROUP BY ar.driver_id, s.first_name, s.last_name;

-- 5. Payment History with Booking & Student Details
SELECT 
    b.booking_id, 
    CONCAT(s.first_name, ' ', s.last_name) AS student_name,
    b.fare, 
    p.amount AS payment_amount,
    p.method AS payment_method,
    p.status AS payment_status,
    p.payment_date
FROM bookings b
JOIN students s ON s.student_id = b.customer_id
LEFT JOIN payment p ON p.booking_id = b.booking_id;

-- 6. Rides Without Confirmed Bookings (LEFT JOIN)
SELECT 
    ar.ride_id,
    ar.departure_time,
    ar.total_capacity,
    ar.remaining_capacity
FROM available_rides ar
LEFT JOIN bookings b ON b.ride_id = ar.ride_id AND b.status = 'CONFIRMED'
WHERE b.booking_id IS NULL;

-- 7. Seat Utilisation Analysis
SELECT 
    ar.ride_id,
    ar.total_capacity,
    ar.remaining_capacity,
    (ar.total_capacity - ar.remaining_capacity) AS seats_booked,
    ROUND(((ar.total_capacity - ar.remaining_capacity) * 100.0 / ar.total_capacity), 1) AS utilisation_percentage
FROM available_rides ar;
