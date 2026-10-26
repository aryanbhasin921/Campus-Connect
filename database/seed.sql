-- ========================================================
-- CampusCommute Seed Data (MySQL 8.x)
-- ========================================================

USE campuscommute;

-- 1. Seed Students (Admin, Passengers, Drivers)
INSERT INTO students (student_id, first_name, last_name, phone_number, email, password_hash, role, current_mode) VALUES
(1, 'Admin', 'User', '9999900000', 'admin@campuscommute.edu', 'scrypt:32768:8:1$JPbjtzMFVbcxGSlN$e5df27551e8f9e928324a09d960f2708ef66a97413fc4f911fed983df385f818959397d2cedf7d40e72963090f766cf0cc52be39953b59dc77eb0409edc88dea', 'ADMIN', 'PASSENGER'),
(2, 'Rahul', 'Sharma', '9811122233', 'passenger@campuscommute.edu', 'scrypt:32768:8:1$53bswvkg8Azu3sS8$6c5f1adfb6f853f8beef4264b5bf4a24123c43b00d854eb05777b83b5cc9815c52dfcb4b94cae06a91cb0fce77ac8fb9d913098e1f1176c996ac2ea80bd697f6', 'STUDENT', 'PASSENGER'),
(3, 'Riya', 'Patel', '9822233344', 'riya@campuscommute.edu', 'scrypt:32768:8:1$53bswvkg8Azu3sS8$6c5f1adfb6f853f8beef4264b5bf4a24123c43b00d854eb05777b83b5cc9815c52dfcb4b94cae06a91cb0fce77ac8fb9d913098e1f1176c996ac2ea80bd697f6', 'STUDENT', 'PASSENGER'),
(4, 'Arjun', 'Verma', '9833344455', 'driver@campuscommute.edu', 'scrypt:32768:8:1$53bswvkg8Azu3sS8$6c5f1adfb6f853f8beef4264b5bf4a24123c43b00d854eb05777b83b5cc9815c52dfcb4b94cae06a91cb0fce77ac8fb9d913098e1f1176c996ac2ea80bd697f6', 'STUDENT', 'DRIVER'),
(5, 'Kavita', 'Rao', '9844455566', 'driver2@campuscommute.edu', 'scrypt:32768:8:1$53bswvkg8Azu3sS8$6c5f1adfb6f853f8beef4264b5bf4a24123c43b00d854eb05777b83b5cc9815c52dfcb4b94cae06a91cb0fce77ac8fb9d913098e1f1176c996ac2ea80bd697f6', 'STUDENT', 'DRIVER')
ON DUPLICATE KEY UPDATE student_id=student_id;

-- 2. Seed Drivers
INSERT INTO drivers (student_id, licence_id, licence_expiry_date, upi_id) VALUES
(4, 'DL-1420110012345', '2028-12-31', 'arjun@okaxis'),
(5, 'DL-1420150067890', '2027-06-30', 'kavita@okhdfc')
ON DUPLICATE KEY UPDATE student_id=student_id;

-- 3. Seed Vehicles
INSERT INTO vehicle (vehicle_number, type, name, colour, year_of_manufacture, capacity) VALUES
('DL-01-AB-1234', 'Sedan', 'Honda City', 'Silver', 2022, 4),
('DL-04-CD-5678', 'Hatchback', 'Maruti Swift', 'White', 2021, 3),
('HR-26-EE-9999', 'SUV', 'Hyundai Creta', 'Black', 2023, 4)
ON DUPLICATE KEY UPDATE vehicle_number=vehicle_number;

-- 4. Seed Driver-Vehicle Link
INSERT INTO driver_vehicle (student_id, vehicle_number) VALUES
(4, 'DL-01-AB-1234'),
(5, 'DL-04-CD-5678')
ON DUPLICATE KEY UPDATE student_id=student_id;

-- 5. Seed Campus Locations (Nodes)
INSERT INTO locations (location_id, name, latitude, longitude) VALUES
(1, 'North Campus Gate 1', 28.6901230, 77.2145670),
(2, 'University Library', 28.6885400, 77.2163400),
(3, 'Tech Block & Labs', 28.6864100, 77.2189200),
(4, 'Boys Hostel Block A', 28.6923000, 77.2110000),
(5, 'Girls Hostel Block B', 28.6931000, 77.2125000),
(6, 'University Metro Station', 28.6980000, 77.2195000),
(7, 'City Center Mall', 28.7042000, 77.2281000),
(8, 'Railway Junction', 28.7115000, 77.2356000)
ON DUPLICATE KEY UPDATE location_id=location_id;

-- Rides, Ride Points, Requests, Bookings, and Payments start empty for live presentation.

