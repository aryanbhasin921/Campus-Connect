-- ========================================================
-- CampusCommute Database Triggers (Blueprint Section 8)
-- ========================================================

USE campuscommute;

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
        -- Check remaining capacity
        IF (SELECT remaining_capacity FROM available_rides WHERE ride_id = NEW.ride_id) <= 0 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Error: No seats remaining on this ride.';
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

DELIMITER ;
