-- Grant permission to create test databases
GRANT ALL PRIVILEGES ON test_student_moving_db.* TO 'student_moving_user'@'localhost';
GRANT CREATE ON *.* TO 'student_moving_user'@'localhost';
FLUSH PRIVILEGES;
SELECT 'Test database permissions granted!' AS Status;
