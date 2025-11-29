-- MySQL Database Setup Script for Student Moving Services Marketplace
-- This script creates the database and user with proper UTF-8 support

-- Create database with utf8mb4 charset for emoji and special character support
CREATE DATABASE IF NOT EXISTS student_moving_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- Create user (IMPORTANT: Replace 'your_secure_password' with a strong password)
CREATE USER IF NOT EXISTS 'student_moving_user'@'localhost' IDENTIFIED BY 'your_secure_password';

-- Grant all privileges on the database to the user
GRANT ALL PRIVILEGES ON student_moving_db.* TO 'student_moving_user'@'localhost';

-- Apply privilege changes
FLUSH PRIVILEGES;

-- Verify database creation
SHOW DATABASES LIKE 'student_moving_db';

-- Verify user privileges
SHOW GRANTS FOR 'student_moving_user'@'localhost';

-- Display success message
SELECT 'Database setup completed successfully!' AS Status;
