# Student Moving Services Marketplace

A Django-based web platform connecting students who need moving services with service providers. Built with Django 5.2.8, following Test-Driven Development (TDD) principles and industry best practices.

## 🚀 Project Overview

This marketplace platform facilitates connections between students requiring moving services and qualified service providers. The project emphasizes code quality, comprehensive testing, and production-ready architecture.

## ✨ Features

- **Django 5.2.8** - Latest stable Django framework
- **REST API** - Built with Django REST Framework
- **MySQL Support** - Production-ready database integration
- **Image Handling** - Pillow for image processing
- **CORS Support** - Cross-Origin Resource Sharing enabled
- **Test-Driven Development** - 38 comprehensive environment tests
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
| pytest | 9.0.1 | Testing framework |

## 🏗️ Project Structure

```
Student-Moving-Services-Marketplace/
├── core/                           # Core Django app
│   ├── models.py                   # Database models
│   ├── views.py                    # View functions
│   ├── admin.py                    # Admin interface
│   ├── apps.py                     # App configuration
│   └── tests.py                    # App-specific tests
├── student_moving_marketplace/     # Django project settings
│   ├── settings.py                 # Project configuration
│   ├── urls.py                     # URL routing
│   ├── wsgi.py                     # WSGI configuration
│   └── asgi.py                     # ASGI configuration
├── tests/                          # Environment verification tests
│   └── test_environment_setup.py   # 38 comprehensive tests
├── docs/                           # Documentation
│   ├── QUICKSTART.md              # Quick start guide
│   └── SETUP_SUMMARY.md           # Setup summary
├── manage.py                       # Django management script
├── requirements.txt                # Project dependencies
├── pyproject.toml                  # pytest configuration
├── .gitignore                      # Git ignore rules
├── LICENSE                         # Project license
└── README.md                       # This file
```

## 🧪 Testing

This project follows **Test-Driven Development (TDD)** principles.

### Run All Tests

```bash
python -m pytest tests/test_environment_setup.py -v
```

### Test Coverage

The test suite includes 38 comprehensive tests covering:

- ✅ Django installation and version verification
- ✅ Required package installation
- ✅ Django project structure validation
- ✅ Virtual environment isolation
- ✅ Requirements.txt validation
- ✅ Django functionality checks

**Current Status**: 38/38 tests passing ✅

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

### Access Admin Interface

Navigate to `http://127.0.0.1:8000/admin/` and log in with your superuser credentials.

## 📚 Documentation

Detailed documentation is available in the `docs/` directory:

- [**Quick Start Guide**](docs/QUICKSTART.md) - Get started quickly
- [**Setup Summary**](docs/SETUP_SUMMARY.md) - Detailed setup information

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

**Current Version**: 1.0.0 (Initial Setup)

- ✅ Environment setup complete
- ✅ Django project initialized
- ✅ Core app created
- ✅ Comprehensive test suite (38 tests)
- ✅ Documentation complete
- 🚧 Feature development in progress

## 🎯 Next Steps

1. Configure MySQL database
2. Define data models for marketplace
3. Implement user authentication
4. Create REST API endpoints
5. Build frontend interface
6. Add comprehensive feature tests
7. Deploy to production

---

**Built with ❤️ using Django and Test-Driven Development**