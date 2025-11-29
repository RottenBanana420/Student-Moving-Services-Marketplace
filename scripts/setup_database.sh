#!/bin/bash

# Database Setup Script for Student Moving Services Marketplace
# This script helps set up the MySQL database and create the .env file

echo "=========================================="
echo "Student Moving Services - Database Setup"
echo "=========================================="
echo ""

# Check if MySQL is running
if ! command -v mysql &> /dev/null; then
    echo "ERROR: MySQL is not installed or not in PATH"
    echo "Please install MySQL first: brew install mysql"
    exit 1
fi

# Prompt for MySQL root password
echo "Step 1: MySQL Root Access"
echo "-------------------------"
read -sp "Enter MySQL root password: " MYSQL_ROOT_PASSWORD
echo ""

# Prompt for application database password
echo ""
echo "Step 2: Application Database Password"
echo "-------------------------------------"
read -sp "Enter password for 'student_moving_user' (will be created): " DB_PASSWORD
echo ""
read -sp "Confirm password: " DB_PASSWORD_CONFIRM
echo ""

if [ "$DB_PASSWORD" != "$DB_PASSWORD_CONFIRM" ]; then
    echo "ERROR: Passwords do not match!"
    exit 1
fi

# Create database and user
echo ""
echo "Step 3: Creating Database and User"
echo "-----------------------------------"

# Create temporary SQL file
SQL_FILE=$(mktemp)
cat > "$SQL_FILE" << EOF
CREATE DATABASE IF NOT EXISTS student_moving_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'student_moving_user'@'localhost' IDENTIFIED BY '$DB_PASSWORD';

GRANT ALL PRIVILEGES ON student_moving_db.* TO 'student_moving_user'@'localhost';

FLUSH PRIVILEGES;

SHOW DATABASES LIKE 'student_moving_db';
SHOW GRANTS FOR 'student_moving_user'@'localhost';
EOF

# Execute SQL
mysql -u root -p"$MYSQL_ROOT_PASSWORD" < "$SQL_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Database and user created successfully!"
else
    echo "✗ Failed to create database and user"
    rm "$SQL_FILE"
    exit 1
fi

# Clean up SQL file
rm "$SQL_FILE"

# Create .env file
echo ""
echo "Step 4: Creating .env File"
echo "--------------------------"

if [ -f .env ]; then
    echo "WARNING: .env file already exists"
    read -p "Overwrite? (y/N): " OVERWRITE
    if [ "$OVERWRITE" != "y" ] && [ "$OVERWRITE" != "Y" ]; then
        echo "Skipping .env creation"
        exit 0
    fi
fi

cat > .env << EOF
# Database Configuration
DB_NAME=student_moving_db
DB_USER=student_moving_user
DB_PASSWORD=$DB_PASSWORD
DB_HOST=localhost
DB_PORT=3306

# Django Settings
SECRET_KEY=django-insecure-diwma557_w7lny!ndqyxpf2^4i(a6erv!qd3gjbl382m-)e=-s
DEBUG=True

# CORS Settings (comma-separated for multiple origins)
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:8000
EOF

echo "✓ .env file created successfully!"

# Test database connection
echo ""
echo "Step 5: Testing Database Connection"
echo "------------------------------------"

mysql -u student_moving_user -p"$DB_PASSWORD" student_moving_db -e "SELECT 'Connection successful!' AS Status;" 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Database connection test passed!"
else
    echo "✗ Database connection test failed"
    exit 1
fi

# Create media directory
echo ""
echo "Step 6: Creating Media Directory"
echo "---------------------------------"
mkdir -p media
echo "✓ Media directory created"

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Run migrations: python manage.py migrate"
echo "2. Create superuser: python manage.py createsuperuser"
echo "3. Run tests: python manage.py test tests.test_database_config"
echo ""
