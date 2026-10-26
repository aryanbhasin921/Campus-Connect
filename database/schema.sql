-- ========================================================
-- CampusConnect Database Schema (MySQL 8.x / InnoDB)
-- Student Mobility & Ride-Sharing System
-- Enforces: PK/FK, UNIQUE, CHECK, NOT NULL constraints
-- ========================================================

CREATE DATABASE IF NOT EXISTS campusconnect;
USE campusconnect;

-- 1. Students Table
CREATE TABLE IF NOT EXISTS students (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    phone_number VARCHAR(15) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'STUDENT',
    current_mode VARCHAR(20) NOT NULL DEFAULT 'PASSENGER',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. Drivers Table (1-to-0..1 relationship with Students)
CREATE TABLE IF NOT EXISTS drivers (
    student_id INT PRIMARY KEY,
    licence_id VARCHAR(50) UNIQUE NOT NULL,
    licence_expiry_date DATE NOT NULL,
    upi_id VARCHAR(100) NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 3. Vehicle Table
CREATE TABLE IF NOT EXISTS vehicle (
    vehicle_number VARCHAR(20) PRIMARY KEY,
    type VARCHAR(30) NOT NULL,
    name VARCHAR(60) NOT NULL,
    colour VARCHAR(30) NULL,
    year_of_manufacture INT NULL,
    capacity INT NOT NULL,
    CONSTRAINT chk_vehicle_capacity CHECK (capacity > 0)
) ENGINE=InnoDB;

-- 4. Driver-Vehicle Association (Many-to-Many)
CREATE TABLE IF NOT EXISTS driver_vehicle (
    student_id INT NOT NULL,
    vehicle_number VARCHAR(20) NOT NULL,
    PRIMARY KEY (student_id, vehicle_number),
    FOREIGN KEY (student_id) REFERENCES drivers(student_id) ON DELETE CASCADE,
    FOREIGN KEY (vehicle_number) REFERENCES vehicle(vehicle_number) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 5. Locations (Nodes) Table
CREATE TABLE IF NOT EXISTS locations (
    location_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    latitude DECIMAL(10,7) NULL,
    longitude DECIMAL(10,7) NULL
) ENGINE=InnoDB;

-- 6. Available Rides Table
CREATE TABLE IF NOT EXISTS available_rides (
    ride_id INT AUTO_INCREMENT PRIMARY KEY,
    driver_id INT NOT NULL,
    vehicle_number VARCHAR(20) NOT NULL,
    departure_time DATETIME NOT NULL,
    total_capacity INT NOT NULL,
    remaining_capacity INT NOT NULL,
    fare_per_passenger DECIMAL(10,2) NOT NULL DEFAULT 50.00,
    status VARCHAR(20) NOT NULL DEFAULT 'PUBLISHED',
    FOREIGN KEY (driver_id) REFERENCES drivers(student_id),
    FOREIGN KEY (vehicle_number) REFERENCES vehicle(vehicle_number),
    CONSTRAINT chk_capacity_bounds CHECK (remaining_capacity >= 0 AND remaining_capacity <= total_capacity),
    CONSTRAINT chk_fare_positive CHECK (fare_per_passenger >= 0)
) ENGINE=InnoDB;

-- 7. Ride Points (Ordered Route Stops)
CREATE TABLE IF NOT EXISTS ride_points (
    ride_id INT NOT NULL,
    sequence_no INT NOT NULL,
    location_id INT NOT NULL,
    PRIMARY KEY (ride_id, sequence_no),
    FOREIGN KEY (ride_id) REFERENCES available_rides(ride_id) ON DELETE CASCADE,
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
) ENGINE=InnoDB;

-- 8. Requests Table
CREATE TABLE IF NOT EXISTS requests (
    request_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    pickup_location_id INT NOT NULL,
    drop_location_id INT NOT NULL,
    schedule_time DATETIME NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'CONFIRMED',
    FOREIGN KEY (customer_id) REFERENCES students(student_id),
    FOREIGN KEY (pickup_location_id) REFERENCES locations(location_id),
    FOREIGN KEY (drop_location_id) REFERENCES locations(location_id)
) ENGINE=InnoDB;

-- 9. Bookings Table
CREATE TABLE IF NOT EXISTS bookings (
    booking_id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT UNIQUE NOT NULL,
    customer_id INT NOT NULL,
    ride_id INT NOT NULL,
    pickup_location_id INT NOT NULL,
    drop_location_id INT NOT NULL,
    booking_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'CONFIRMED',
    fare DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (request_id) REFERENCES requests(request_id),
    FOREIGN KEY (customer_id) REFERENCES students(student_id),
    FOREIGN KEY (ride_id) REFERENCES available_rides(ride_id),
    FOREIGN KEY (pickup_location_id) REFERENCES locations(location_id),
    FOREIGN KEY (drop_location_id) REFERENCES locations(location_id),
    CONSTRAINT chk_booking_fare CHECK (fare >= 0)
) ENGINE=InnoDB;

-- 10. Payment Table
CREATE TABLE IF NOT EXISTS payment (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PAID',
    method VARCHAR(20) NOT NULL DEFAULT 'UPI',
    FOREIGN KEY (booking_id) REFERENCES bookings(booking_id),
    CONSTRAINT chk_payment_amount CHECK (amount >= 0)
) ENGINE=InnoDB;

-- Indexes for performance
CREATE INDEX idx_rides_driver ON available_rides(driver_id);
CREATE INDEX idx_rides_departure ON available_rides(departure_time);
CREATE INDEX idx_bookings_customer ON bookings(customer_id);
CREATE INDEX idx_bookings_ride ON bookings(ride_id);
