# MySQL Database Setup Guide

This guide provides step-by-step instructions for setting up the MySQL database for the Student Moving Services Marketplace project.

## Prerequisites

- MySQL 8.0+ installed on your system
- MySQL server running
- MySQL root password or administrative access

## Database Setup

### Step 1: Access MySQL

Open your terminal and access MySQL as root:

```bash
mysql -u root -p
```

Enter your MySQL root password when prompted.

### Step 2: Create Database

Execute the following SQL commands to create the database with proper UTF-8 support:

```sql
-- Create database with utf8mb4 charset for emoji and special character support
CREATE DATABASE student_moving_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
```

### Step 3: Create Database User

Create a dedicated user for the application (replace `your_secure_password` with a strong password):

```sql
-- Create user
CREATE USER 'student_moving_user'@'localhost' IDENTIFIED BY 'your_secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON student_moving_db.* TO 'student_moving_user'@'localhost';

-- Apply changes
FLUSH PRIVILEGES;
```

### Step 4: Verify Setup

Verify the database and user were created successfully:

```sql
-- Show databases
SHOW DATABASES;

-- Show user privileges
SHOW GRANTS FOR 'student_moving_user'@'localhost';

-- Exit MySQL
EXIT;
```

### Step 5: Test Connection

Test the connection with the new user:

```bash
mysql -u student_moving_user -p student_moving_db
```

If successful, you should see the MySQL prompt. Exit with `EXIT;`.

## Environment Configuration

### Step 1: Create .env File

Copy the example environment file:

```bash
cp .env.example .env
```

### Step 2: Update .env File

Edit the `.env` file and update the database credentials:

```env
DB_NAME=student_moving_db
DB_USER=student_moving_user
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=3306
```

**Important**: Never commit the `.env` file to version control. It's already included in `.gitignore`.

## Django Setup

### Step 1: Install Dependencies

Install all required Python packages:

```bash
pip install -r requirements.txt
```

### Step 2: Create Media Directory

Create the media directory for file uploads:

```bash
mkdir -p media
```

### Step 3: Run Migrations

Apply Django migrations to create database tables:

```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 4: Create Superuser (Optional)

Create a Django admin superuser:

```bash
python manage.py createsuperuser
```

## Verification

### Test Database Connection

Run the Django system check:

```bash
python manage.py check
```

### Run Tests

Execute the comprehensive test suite:

```bash
python manage.py test tests.test_database_config
```

All tests should pass if the configuration is correct.

## Common Issues and Troubleshooting

### Issue 1: "Access denied for user"

**Cause**: Incorrect username or password in `.env` file.

**Solution**: 
- Verify credentials in `.env` match those created in MySQL
- Ensure no extra spaces in `.env` file
- Try connecting directly with `mysql -u student_moving_user -p`

### Issue 2: "Can't connect to MySQL server"

**Cause**: MySQL server not running or incorrect host/port.

**Solution**:
- Check if MySQL is running: `brew services list` (macOS) or `systemctl status mysql` (Linux)
- Start MySQL if needed: `brew services start mysql` (macOS)
- Verify host and port in `.env` file

### Issue 3: "Unknown database 'student_moving_db'"

**Cause**: Database not created.

**Solution**:
- Log into MySQL and verify database exists: `SHOW DATABASES;`
- Create database if missing (see Step 2 above)

### Issue 4: mysqlclient installation fails

**Cause**: Missing MySQL client libraries.

**Solution** (macOS):
```bash
brew install mysql-client
export PATH="/usr/local/opt/mysql-client/bin:$PATH"
export LDFLAGS="-L/usr/local/opt/mysql-client/lib"
export CPPFLAGS="-I/usr/local/opt/mysql-client/include"
pip install mysqlclient
```

### Issue 5: Character encoding issues

**Cause**: Database not using utf8mb4 charset.

**Solution**:
```sql
-- Check database charset
SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME
FROM information_schema.SCHEMATA
WHERE SCHEMA_NAME = 'student_moving_db';

-- If not utf8mb4, alter database
ALTER DATABASE student_moving_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
```

## Security Best Practices

1. **Strong Passwords**: Use strong, unique passwords for database users
2. **Principle of Least Privilege**: Only grant necessary permissions
3. **Environment Variables**: Never hardcode credentials in code
4. **Regular Backups**: Set up automated database backups
5. **SSL/TLS**: Consider enabling SSL for database connections in production

## Production Considerations

For production deployments:

1. **Use a dedicated database server** (not localhost)
2. **Enable SSL/TLS** for encrypted connections
3. **Configure connection pooling** (already set in settings.py)
4. **Set up database backups** and disaster recovery
5. **Monitor database performance** and optimize queries
6. **Use read replicas** for scaling read operations
7. **Implement proper firewall rules** to restrict database access

## Quick Setup Script

For convenience, here's a complete SQL script to run all setup commands at once:

```sql
-- Create database
CREATE DATABASE IF NOT EXISTS student_moving_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- Create user (replace 'your_secure_password' with actual password)
CREATE USER IF NOT EXISTS 'student_moving_user'@'localhost' IDENTIFIED BY 'your_secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON student_moving_db.* TO 'student_moving_user'@'localhost';

-- Apply changes
FLUSH PRIVILEGES;

-- Verify
SHOW DATABASES;
SHOW GRANTS FOR 'student_moving_user'@'localhost';
```

Save this to a file (e.g., `setup_db.sql`) and run:

```bash
mysql -u root -p < setup_db.sql
```
