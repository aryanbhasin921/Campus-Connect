-- ========================================================
-- CampusConnect Database Views (Blueprint Section 8)
-- ========================================================

USE campusconnect;

-- 1. Confirmed Bookings View
CREATE OR REPLACE VIEW confirmed_bookings_view AS
SELECT 
    booking_id, 
    customer_id, 
    ride_id,
    pickup_location_id, 
    drop_location_id, 
    fare
FROM bookings
WHERE status = 'CONFIRMED';

-- 2. Published Available Rides View
CREATE OR REPLACE VIEW published_rides_view AS
SELECT 
    ride_id, 
    driver_id, 
    vehicle_number,
    departure_time, 
    remaining_capacity
FROM available_rides
WHERE status = 'PUBLISHED'
  AND remaining_capacity > 0;

-- 3. Driver Rating Summary View (average rating per driver)
CREATE OR REPLACE VIEW driver_rating_summary_view AS
SELECT
    d.student_id AS driver_id,
    CONCAT(s.first_name, ' ', s.last_name) AS driver_name,
    COUNT(r.rating_id) AS total_ratings,
    ROUND(AVG(r.rating), 2) AS average_rating
FROM drivers d
JOIN students s ON s.student_id = d.student_id
LEFT JOIN driver_ratings r ON r.driver_id = d.student_id
GROUP BY d.student_id, s.first_name, s.last_name;
