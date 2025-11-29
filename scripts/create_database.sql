-- MySQL Database Setup Script
-- Run this with: mysql -u root -p < create_database.sql

CREATE DATABASE IF NOT EXISTS student_moving_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'student_moving_user'@'localhost' IDENTIFIED BY 'SecurePass123!';

GRANT ALL PRIVILEGES ON student_moving_db.* TO 'student_moving_user'@'localhost';

FLUSH PRIVILEGES;

SELECT 'Database setup completed successfully!' AS Status;
