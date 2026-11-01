-- ========================================================
-- CampusConnect Database Triggers (Blueprint Section 8)
-- ========================================================

USE campusconnect;

DELIMITER $$

-- 1. Licence Validation Trigger: Reject publishing a ride if licence is expired
DROP TRIGGER IF EXISTS trg_check_driver_licence $$
CREATE TRIGGER trg_check_driver_licence
BEFORE INSERT ON available_rides
FOR EACH ROW
BEGIN
    DECLARE expiry_date DATE;
    SELECT licence_expiry_date INTO expiry_date
    FROM drivers
    WHERE student_id = NEW.driver_id;
    
    IF expiry_date IS NULL OR expiry_date < CURDATE() THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Error: Cannot publish ride. Driver licence is missing or expired.';
    END IF;
END $$

-- 2. Capacity Trigger: Decrement remaining seats when booking is created as CONFIRMED
DROP TRIGGER IF EXISTS trg_booking_capacity_decrement $$
CREATE TRIGGER trg_booking_capacity_decrement
AFTER INSERT ON bookings
FOR EACH ROW
BEGIN
    IF NEW.status = 'CONFIRMED' THEN
        -- Reject unpublished rides and rides with no seats left
        IF (SELECT status FROM available_rides WHERE ride_id = NEW.ride_id) <> 'PUBLISHED'
           OR (SELECT remaining_capacity FROM available_rides WHERE ride_id = NEW.ride_id) <= 0 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Error: Ride is unavailable or has no seats remaining.';
        ELSE
            UPDATE available_rides
            SET remaining_capacity = remaining_capacity - 1
            WHERE ride_id = NEW.ride_id;
        END IF;
    END IF;
END $$

-- 3. Cancellation Trigger: Restore remaining seats when booking status changes to CANCELLED
DROP TRIGGER IF EXISTS trg_booking_capacity_restore $$
CREATE TRIGGER trg_booking_capacity_restore
AFTER UPDATE ON bookings
FOR EACH ROW
BEGIN
    IF OLD.status = 'CONFIRMED' AND NEW.status = 'CANCELLED' THEN
        UPDATE available_rides
        SET remaining_capacity = LEAST(total_capacity, remaining_capacity + 1)
        WHERE ride_id = NEW.ride_id;
    END IF;
END $$

-- Validate driver_ratings: booking must be COMPLETED, belong to the customer, and match the ride's driver
DROP TRIGGER IF EXISTS trg_validate_driver_ratings $$
CREATE TRIGGER trg_validate_driver_ratings
BEFORE INSERT ON driver_ratings
FOR EACH ROW
BEGIN
    DECLARE b_status VARCHAR(20);
    DECLARE b_customer INT;
    DECLARE r_driver INT;
    SELECT b.status, b.customer_id, ar.driver_id INTO b_status, b_customer, r_driver
    FROM bookings b JOIN available_rides ar ON ar.ride_id = b.ride_id
    WHERE b.booking_id = NEW.booking_id;
    IF b_status IS NULL OR b_status <> 'COMPLETED' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error: You can only rate a COMPLETED booking.';
    ELSEIF b_customer <> NEW.customer_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error: Only the customer of this booking can rate it.';
    ELSEIF r_driver <> NEW.driver_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error: Driver does not match the driver of this booking.';
    END IF;
END $$

-- Validate feedback: booking must be COMPLETED, belong to the customer, and match the ride's driver
DROP TRIGGER IF EXISTS trg_validate_feedback $$
CREATE TRIGGER trg_validate_feedback
BEFORE INSERT ON feedback
FOR EACH ROW
BEGIN
    DECLARE b_status VARCHAR(20);
    DECLARE b_customer INT;
    DECLARE r_driver INT;
    SELECT b.status, b.customer_id, ar.driver_id INTO b_status, b_customer, r_driver
    FROM bookings b JOIN available_rides ar ON ar.ride_id = b.ride_id
    WHERE b.booking_id = NEW.booking_id;
    IF b_status IS NULL OR b_status <> 'COMPLETED' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error: You can only leave feedback for a COMPLETED booking.';
    ELSEIF b_customer <> NEW.customer_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error: Only the customer of this booking can leave feedback for it.';
    ELSEIF r_driver <> NEW.driver_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error: Driver does not match the driver of this booking.';
    END IF;
END $$

DELIMITER ;
