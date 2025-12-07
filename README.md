# Student Moving Services Marketplace

A Django-based web platform connecting students who need moving services with service providers. Built with Django 5.2.8, following Test-Driven Development (TDD) principles and industry best practices.

## 🚀 Project Overview

This marketplace platform facilitates connections between students requiring moving services and qualified service providers. The project emphasizes code quality, comprehensive testing, and production-ready architecture.

## ✨ Features

### Core Models

- **Custom User Model** - Extended Django user with student/provider types, phone validation, and profile images
- **MovingService Model** - Service listings with pricing, ratings, and availability tracking
- **Booking Model** - Complete booking system with status transitions and validation
- **Review Model** - Rating and review system for services
- **Furniture Marketplace** - Buy/sell furniture with transaction handling and escrow support
- **Custom Validators** - Phone number and image validation with comprehensive error handling

### Security Features

- **Rate Limiting** - Scoped throttling for login (5/min) and refresh (10/min) endpoints
- **Token Management** - Automatic token rotation and blacklisting on refresh
- **Brute Force Protection** - Generic error messages and IP-based logging
- **Concurrent Handling** - Robust database-level constraints for simultaneous registration attempts

### Technical Stack

- **Django 5.2.8** - Latest stable Django framework
- **REST API** - Built with Django REST Framework (DRF)
- **MySQL Support** - Production-ready database integration with UTF-8mb4 charset
- **Image Handling** - Pillow for image processing with size and format validation
- **CORS Support** - Cross-Origin Resource Sharing enabled for frontend integration
- **JWT Authentication** - Secure token-based authentication with rotation and blacklisting
- **Test-Driven Development** - Comprehensive test suite using `pytest` and `pytest-django`
- **Virtual Environment** - Isolated Python environment using pyenv-virtualenv

## 📋 Prerequisites

- Python 3.13.7 (managed via pyenv)
- pyenv-virtualenv
- MySQL (for production database)
- Git

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/RottenBanana420/Student-Moving-Services-Marketplace.git
cd Student-Moving-Services-Marketplace
```

### 2. Set Up Virtual Environment

```bash
# Activate the virtual environment
pyenv activate student_moving_env
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Verify Installation

```bash
# Run environment verification tests
python -m pytest tests/test_environment_setup.py -v

# Expected output: 38 passed
```

### 5. Run Django System Check

```bash
python manage.py check
```

## 📦 Dependencies

All packages are installed without version pinning to use the latest stable versions:

| Package | Version | Purpose |
|---------|---------|---------|
| Django | 5.2.8 | Web framework |
| mysqlclient | 2.2.7 | MySQL database connector |
| Pillow | 12.0.0 | Image handling |
| djangorestframework | 3.16.1 | REST API framework |
| django-cors-headers | 4.9.0 | CORS support |
| djangorestframework-simplejwt | 5.5.1 | JWT Authentication |
| python-decouple | 3.8 | Environment variable management |
| pytest | 9.0.1 | Testing framework |

## 🏗️ Project Structure

```text
Student-Moving-Services-Marketplace/
├── core/                           # Core Django app
│   ├── models.py                   # Database models (User, Service, Booking, Review, Furniture)
│   ├── validators.py               # Custom validators (phone, image)
│   ├── views.py                    # View functions
│   ├── admin.py                    # Admin interface configuration
│   ├── apps.py                     # App configuration
│   ├── tests.py                    # App-specific tests
│   └── migrations/                 # Database migrations
├── student_moving_marketplace/     # Django project settings
│   ├── settings.py                 # Project configuration (MySQL, DRF, CORS)
│   ├── urls.py                     # URL routing
│   ├── wsgi.py                     # WSGI configuration
│   └── asgi.py                     # ASGI configuration
├── tests/                          # Test suite
│   ├── test_environment_setup.py   # Environment verification tests
│   ├── test_database_config.py     # Database configuration tests
│   ├── test_user_model.py          # User model tests
│   ├── test_moving_service_model.py # MovingService model tests
│   ├── test_booking_model.py       # Booking model tests
│   ├── test_review_model.py        # Review model tests
│   ├── test_furniture_models.py    # Furniture marketplace tests
│   └── test_integration_setup.py   # Integration tests
├── docs/                           # Documentation
│   └── database_setup.md           # Database setup guide
├── scripts/                        # Database setup scripts
│   ├── setup_database.sh           # Automated database setup
│   ├── create_database.sql         # Database creation script
│   ├── grant_test_permissions.sql  # Test permissions script
│   ├── setup_db.sql                # Complete database setup SQL
│   └── populate_db.py              # Script to populate database with dummy data
├── media/                          # User-uploaded media files
├── manage.py                       # Django management script
├── requirements.txt                # Project dependencies
├── pytest.ini                      # Pytest configuration
├── pyproject.toml                  # Python project configuration
├── .env.example                    # Example environment variables
├── .gitignore                      # Git ignore rules
├── LICENSE                         # Project license
└── README.md                       # This file
```

## 🧪 Testing

This project follows **Test-Driven Development (TDD)** principles.

### Run All Tests

```bash
# Run all tests using pytest
python -m pytest -v

# Run specific test file
python -m pytest tests/test_user_model.py -v
```

### Test Coverage

The test suite includes comprehensive tests covering:

#### Environment & Config

- ✅ Environment verification
- ✅ Database configuration
- ✅ Integration setup (DRF, CORS, DB Isolation)

#### Model Tests

- ✅ User model (Validation, Types, Profiles)
- ✅ MovingService model (Pricing, Ratings)
- ✅ Booking model (Status transitions, Validation)
- ✅ Review model (Ratings, Comments)
- ✅ Furniture models (Items, Images, Transactions)

#### Integration Tests

- ✅ REST Framework Configuration (Auth, Permissions, Pagination)
- ✅ CORS Headers (Middleware, Allowed Origins)
- ✅ Database Isolation (Test vs Dev DB)
- ✅ Model Imports & Circular Dependencies
- ✅ Migration Integrity
- ✅ API Response Formatting

#### Security & Authentication

- ✅ JWT Token Generation & Validation
- ✅ Token Rotation & Blacklisting
- ✅ Custom Authentication Backend
- ✅ Email-based Login
- ✅ Protected Route Access
- ✅ Rate Limiting (Login & Refresh)
- ✅ Concurrent Registration Handling

#### Service Management

- ✅ Service Creation (Provider Verification)
- ✅ Service Listing (Filtering, Sorting, Pagination)
- ✅ Database Optimization (select_related)

**Current Status**: All tests passing ✅

## 🚦 Quick Start

### Activate Virtual Environment

```bash
pyenv activate student_moving_env
```

### Run Development Server

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` in your browser.

### Create Database Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Create Superuser

```bash
python manage.py createsuperuser
```

### Populate Database (Optional)

```bash
python scripts/populate_db.py
```

### Access Admin Interface

Navigate to `http://127.0.0.1:8000/admin/` and log in with your superuser credentials.

## 📚 Documentation

Detailed documentation is available in the `docs/` directory:

- [**Database Setup Guide**](docs/database_setup.md) - MySQL database configuration

### Database Setup Scripts

Database setup scripts are available in the `scripts/` directory:

- `setup_database.sh` - Automated database setup script
- `setup_db.sql` - Complete SQL setup script
- `create_database.sql` - Database creation script
- `grant_test_permissions.sql` - Test permissions script

## 📊 Data Models

The application implements three core models with comprehensive validation:

### User Model

Custom user model extending Django's `AbstractUser`:

**Fields:**

- `email` - Required, unique email address (case-insensitive)
- `username` - Standard Django username field
- `phone_number` - Optional, validated international phone format
- `university_name` - Educational institution (optional)
- `user_type` - Required: 'student' or 'provider'
- `profile_image` - Optional profile picture (max 5MB, jpg/png/webp)
- `is_verified` - Provider verification status (boolean)
- `created_at` - Auto-generated timestamp
- `updated_at` - Auto-updated timestamp

**Validation:**

- Email uniqueness and normalization to lowercase
- Phone number format validation (international format, min 10 digits)
- Profile image size (max 5MB) and format validation
- User type must be specified

**Methods:**

- `is_student()` - Check if user is a student
- `is_provider()` - Check if user is a service provider

### MovingService Model

Service listings created by providers:

**Fields:**

- `provider` - Foreign key to User (must be provider type)
- `service_name` - Name of the service (required)
- `description` - Detailed description (required)
- `base_price` - Base price in USD (Decimal, must be > 0)
- `availability_status` - Boolean, default True
- `rating_average` - Decimal (0.00 to 5.00)
- `total_reviews` - Positive integer, default 0
- `created_at` - Auto-generated timestamp
- `updated_at` - Auto-updated timestamp

**Validation:**

- Provider must have user_type='provider'
- Service name and description cannot be empty
- Base price must be greater than 0
- Rating average must be between 0 and 5
- Total reviews cannot be negative

### Booking Model

Booking system for students to book services:

**Fields:**

- `student` - Foreign key to User (must be student type)
- `provider` - Foreign key to User (must be provider type)
- `service` - Foreign key to MovingService
- `booking_date` - Date and time of scheduled service
- `pickup_location` - Pickup address (required)
- `dropoff_location` - Dropoff address (required)
- `status` - Choice field: 'pending', 'confirmed', 'completed', 'cancelled'
- `total_price` - Total price in USD (Decimal, must be > 0)
- `created_at` - Auto-generated timestamp
- `updated_at` - Auto-updated timestamp

**Validation:**

- Student must have user_type='student'
- Provider must have user_type='provider'
- Pickup and dropoff locations cannot be empty
- Total price must be greater than 0
- Status transitions follow business rules:
  - Cannot go from 'pending' to 'completed' (must confirm first)
  - Cannot modify 'completed' bookings

### Review Model

Feedback system for completed bookings:

**Fields:**

- `booking` - One-to-one relationship with Booking
- `reviewer` - User who wrote the review
- `reviewee` - User being reviewed
- `rating` - Integer 1-5
- `comment` - Text content
- `created_at` - Timestamp

### Furniture Marketplace Models

Complete system for buying and selling furniture:

**FurnitureItem:**

- `seller` - User selling the item
- `title`, `description` - Item details
- `price` - Cost in USD
- `condition` - New, Like New, Good, Fair, Poor
- `category` - Sofa, Bed, Table, etc.
- `is_sold` - Status flag

**FurnitureTransaction:**

- `item` - Reference to FurnitureItem
- `buyer`, `seller` - Users involved
- `sale_price` - Final price
- `status` - Pending, Completed, Cancelled

## 🔌 API Endpoints

### Authentication & Profile

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/auth/register/` | Register a new user | No |
| POST | `/api/auth/login/` | Login with email/password | No |
| POST | `/api/auth/logout/` | Logout (Blacklist refresh token) | Yes |
| GET | `/api/auth/profile/` | Retrieve user profile | Yes |
| PUT/PATCH | `/api/auth/profile/` | Update user profile | Yes |
| POST | `/api/auth/verify-provider/` | Verify provider account (Admin only) | Yes (Admin) |

### Token Management

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/token/` | Obtain access/refresh pair | No |
| POST | `/api/token/refresh/` | Refresh access token (rotates refresh token) | No |
| POST | `/api/token/verify/` | Verify token validity | No |
| POST | `/api/token/blacklist/` | Blacklist a refresh token | Yes |

### Service Management

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/services/list/` | List services with filtering, sorting, and pagination | No |
| POST | `/api/services/` | Create a new service listing | Yes (Provider) |

*Note: Login and Refresh endpoints are rate-limited to prevent abuse.*

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root for sensitive configuration:

```bash
# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=student_moving_db
DB_USER=your-db-user
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=3306
```

> **Note**: Never commit `.env` files to version control. They are already excluded in `.gitignore`.

### Database Configuration

Update `student_moving_marketplace/settings.py` to use MySQL:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}
```

## 🤝 Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Write Tests First (TDD)

Create tests in the appropriate test file before implementing features.

### 3. Implement Feature

Write code to make the tests pass.

### 4. Run Tests

```bash
python -m pytest -v
```

### 5. Commit Changes

```bash
git add .
git commit -m "feat: add your feature description"
```

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

## 🏆 Best Practices

This project follows Django and Python best practices:

- ✅ **Test-Driven Development** - Write tests first
- ✅ **Virtual Environment Isolation** - No system Python conflicts
- ✅ **Latest Stable Versions** - Django 5.2.8, Python 3.13.7
- ✅ **Comprehensive Testing** - 100% test pass rate
- ✅ **Clean Code Structure** - Following Django conventions
- ✅ **Documentation** - Well-documented codebase
- ✅ **Security** - Sensitive data in environment variables
- ✅ **Version Control** - Proper .gitignore configuration

## 🐛 Troubleshooting

### Virtual Environment Not Activated

```bash
pyenv activate student_moving_env
```

### Import Errors

```bash
pip install -r requirements.txt
```

### Database Connection Issues

Verify MySQL is running and credentials are correct in `.env` file.

### Test Failures

```bash
# Run tests with verbose output
python -m pytest tests/test_environment_setup.py -v --tb=short
```

## 📝 License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.

## 👥 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Write tests for your changes
4. Implement your changes
5. Ensure all tests pass
6. Submit a pull request

## 📞 Support

For issues, questions, or contributions, please open an issue on the GitHub repository.

## 🔄 Project Status

**Current Version**: 2.4.0 (Service Management System)

- ✅ Environment setup complete
- ✅ MySQL database configured
- ✅ REST API framework installed & configured
- ✅ CORS support configured
- ✅ Custom User model implemented
- ✅ MovingService & Booking models implemented
- ✅ Review model implemented
- ✅ Furniture marketplace models implemented
- ✅ Users authentication (Login, Register, Logout)
- ✅ Profile Management (Get, Update)
- ✅ Provider Verification System
- ✅ Service Management (Create, List, Filter, Sort)
- ✅ Comprehensive test suite (Pytest integration)
- ✅ Documentation complete
- 🚧 Booking & Review System API implementation
- 🚧 Frontend interface

## 🎯 Next Steps

1. ✅ ~~Implement user authentication~~ (Complete)
2. ✅ ~~Implement profile management~~ (Complete)
3. ✅ ~~Implement provider verification~~ (Complete)
4. ✅ ~~Implement service management~~ (Complete)
5. Implement Booking System endpoints
6. Implement Review System endpoints
7. Build frontend interface
8. Add payment integration
9. Deploy to production

---

> **Built with ❤️ using Django and Test-Driven Development**
