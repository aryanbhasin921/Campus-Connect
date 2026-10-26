-- ========================================================
-- CampusCommute Database Views (Blueprint Section 8)
-- ========================================================

USE campuscommute;

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
