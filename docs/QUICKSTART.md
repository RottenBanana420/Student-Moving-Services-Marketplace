# Quick Start Guide

## Activate Virtual Environment

```bash
pyenv activate student_moving_env
```

## Verify Setup

```bash
# Check Python version
python --version
# Expected: Python 3.13.7

# Check Django version
python -m django --version
# Expected: 5.2.8

# Run system check
python manage.py check
# Expected: System check identified no issues (0 silenced).

# Run all tests
python -m pytest tests/test_environment_setup.py -v
# Expected: 38 passed
```

## Development Commands

```bash
# Run development server
python manage.py runserver

# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Open Django shell
python manage.py shell
```

## Project Structure

- **Project**: `student_moving_marketplace`
- **App**: `core`
- **Virtual Environment**: `student_moving_env`
- **Python Version**: 3.13.7
- **Django Version**: 5.2.8
