"""
Comprehensive test suite for user registration API endpoint.

Tests cover:
- Valid registration scenarios
- Email validation (format, uniqueness)
- Password validation (strength, matching)
- Field validation (user_type, phone, university_name)
- Security tests (SQL injection, XSS, concurrent requests)
- Edge cases (whitespace, case sensitivity, unicode)
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.db import connection
from django.test.utils import CaptureQueriesContext
import threading
import time

User = get_user_model()


@pytest.fixture
def api_client():
    """Fixture to provide API client."""
    return APIClient()


@pytest.fixture
def valid_student_data():
    """Fixture for valid student registration data."""
    return {
        'email': 'student@university.edu',
        'password': 'SecurePass123!',
        'confirm_password': 'SecurePass123!',
        'phone_number': '+1234567890',
        'university_name': 'Test University',
        'user_type': 'student'
    }


@pytest.fixture
def valid_provider_data():
    """Fixture for valid provider registration data."""
    return {
        'email': 'provider@company.com',
        'password': 'ProviderPass456!',
        'confirm_password': 'ProviderPass456!',
        'phone_number': '+9876543210',
        'university_name': 'Business School',
        'user_type': 'provider'
    }


@pytest.fixture(autouse=True)
def clean_database(db):
    """Automatically clean database before each test."""
    User.objects.all().delete()
    yield
    User.objects.all().delete()


@pytest.mark.django_db
class TestValidRegistration:
    """Test valid registration scenarios."""
    
    def test_register_student_success(self, api_client, valid_student_data):
        """Test successful student registration."""
        url = reverse('user_register')
        response = api_client.post(url, valid_student_data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'email' in response.data
        assert response.data['email'] == valid_student_data['email'].lower()
        assert 'password' not in response.data
        assert 'confirm_password' not in response.data
        assert response.data['user_type'] == 'student'
        assert response.data['is_verified'] is False
        
        # Verify user was created in database
        user = User.objects.get(email=valid_student_data['email'].lower())
        assert user.email == valid_student_data['email'].lower()
        assert user.user_type == 'student'
        assert user.is_verified is False
        assert user.check_password(valid_student_data['password'])
    
    def test_register_provider_success(self, api_client, valid_provider_data):
        """Test successful provider registration."""
        url = reverse('user_register')
        response = api_client.post(url, valid_provider_data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['email'] == valid_provider_data['email'].lower()
        assert 'password' not in response.data
        assert response.data['user_type'] == 'provider'
        assert response.data['is_verified'] is False
        
        # Verify user was created in database
        user = User.objects.get(email=valid_provider_data['email'].lower())
        assert user.user_type == 'provider'
        assert user.check_password(valid_provider_data['password'])
    
    def test_password_is_hashed(self, api_client, valid_student_data):
        """Test that password is properly hashed, not stored in plaintext."""
        url = reverse('user_register')
        api_client.post(url, valid_student_data, format='json')
        
        user = User.objects.get(email=valid_student_data['email'].lower())
        # Password should be hashed (starts with algorithm identifier)
        assert user.password.startswith('pbkdf2_sha256$')
        assert user.password != valid_student_data['password']
        # But should validate correctly
        assert user.check_password(valid_student_data['password'])


@pytest.mark.django_db
class TestEmailValidation:
    """Test email validation scenarios."""
    
    @pytest.mark.parametrize('invalid_email', [
        'notanemail',
        'missing@domain',
        '@nodomain.com',
        'spaces in@email.com',
        'double@@domain.com',
        'trailing.dot.@domain.com',
        '.leadingdot@domain.com',
        'no-tld@domain',
        '',
    ])
    def test_invalid_email_format(self, api_client, valid_student_data, invalid_email):
        """Test registration with invalid email formats."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        data['email'] = invalid_email
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'email' in response.data
    
    def test_duplicate_email_registration(self, api_client, valid_student_data):
        """Test that duplicate email registration is rejected."""
        url = reverse('user_register')
        
        # First registration should succeed
        response1 = api_client.post(url, valid_student_data, format='json')
        assert response1.status_code == status.HTTP_201_CREATED
        
        # Second registration with same email should fail
        response2 = api_client.post(url, valid_student_data, format='json')
        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        assert 'email' in response2.data
    
    def test_email_case_insensitive_uniqueness(self, api_client, valid_student_data):
        """Test that email uniqueness is case-insensitive."""
        url = reverse('user_register')
        
        # Register with lowercase email
        response1 = api_client.post(url, valid_student_data, format='json')
        assert response1.status_code == status.HTTP_201_CREATED
        
        # Try to register with uppercase version of same email
        data = valid_student_data.copy()
        data['email'] = valid_student_data['email'].upper()
        response2 = api_client.post(url, data, format='json')
        
        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        assert 'email' in response2.data
    
    def test_missing_email(self, api_client, valid_student_data):
        """Test registration without email."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        del data['email']
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'email' in response.data


@pytest.mark.django_db
class TestPasswordValidation:
    """Test password validation scenarios."""
    
    @pytest.mark.parametrize('weak_password', [
        'short',           # Too short
        '12345678',        # Only numbers
        'password',        # Common password
        'abcdefgh',        # Only lowercase letters
        'ABCDEFGH',        # Only uppercase letters
        'Pass123',         # Too short even with complexity
    ])
    def test_weak_password_rejected(self, api_client, valid_student_data, weak_password):
        """Test that weak passwords are rejected."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        data['password'] = weak_password
        data['confirm_password'] = weak_password
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Should have password validation error
        assert 'password' in response.data or 'non_field_errors' in response.data
    
    def test_password_confirmation_mismatch(self, api_client, valid_student_data):
        """Test that mismatched password confirmation is rejected."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        data['confirm_password'] = 'DifferentPassword123!'
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'non_field_errors' in response.data or 'confirm_password' in response.data
    
    def test_missing_password(self, api_client, valid_student_data):
        """Test registration without password."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        del data['password']
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'password' in response.data
    
    def test_missing_confirm_password(self, api_client, valid_student_data):
        """Test registration without confirm_password."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        del data['confirm_password']
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'confirm_password' in response.data


@pytest.mark.django_db
class TestUserTypeValidation:
    """Test user_type field validation."""
    
    @pytest.mark.parametrize('invalid_user_type', [
        'admin',
        'superuser',
        'moderator',
        'STUDENT',      # Wrong case
        'Provider',     # Wrong case
        '',
        'student provider',
        '123',
    ])
    def test_invalid_user_type(self, api_client, valid_student_data, invalid_user_type):
        """Test that invalid user_type values are rejected."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        data['user_type'] = invalid_user_type
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'user_type' in response.data
    
    def test_missing_user_type(self, api_client, valid_student_data):
        """Test registration without user_type."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        del data['user_type']
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'user_type' in response.data


@pytest.mark.django_db
class TestPhoneValidation:
    """Test phone number validation."""
    
    @pytest.mark.parametrize('invalid_phone', [
        '123',                    # Too short
        'abcdefghij',            # Letters
        '123-456-7890-extra',    # Too long
        '(555) 555-5555 ext 123',  # Invalid format
    ])
    def test_invalid_phone_format(self, api_client, valid_student_data, invalid_phone):
        """Test that invalid phone formats are rejected."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        data['phone_number'] = invalid_phone
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'phone_number' in response.data
    
    def test_phone_optional(self, api_client, valid_student_data):
        """Test that phone number is optional."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        data['phone_number'] = ''
        
        response = api_client.post(url, data, format='json')
        
        # Should succeed even without phone
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestUniversityNameValidation:
    """Test university_name field validation."""
    
    def test_university_name_optional(self, api_client, valid_student_data):
        """Test that university_name is optional."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        data['university_name'] = ''
        
        response = api_client.post(url, data, format='json')
        
        # Should succeed even without university_name
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_university_name_with_unicode(self, api_client, valid_student_data):
        """Test that unicode characters in university_name are handled."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        data['university_name'] = 'Université de Paris'
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['university_name'] == 'Université de Paris'


@pytest.mark.django_db(transaction=True)
class TestSecurityVulnerabilities:
    """Test security vulnerabilities and attack vectors."""
    
    @pytest.mark.parametrize('sql_injection', [
        "admin'--",
        "admin' OR '1'='1",
        "'; DROP TABLE users; --",
        "1' UNION SELECT * FROM users--",
        "admin'; DELETE FROM users WHERE '1'='1",
    ])
    def test_sql_injection_in_email(self, api_client, valid_student_data, sql_injection):
        """Test that SQL injection attempts in email are sanitized."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        data['email'] = sql_injection
        
        response = api_client.post(url, data, format='json')
        
        # Should fail validation, not execute SQL
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Verify no users were created or deleted
        assert User.objects.count() == 0
    
    @pytest.mark.parametrize('xss_attempt', [
        '<script>alert("XSS")</script>',
        '<img src=x onerror=alert("XSS")>',
        'javascript:alert("XSS")',
        '<iframe src="evil.com"></iframe>',
    ])
    def test_xss_in_fields(self, api_client, valid_student_data, xss_attempt):
        """Test that XSS attempts are handled properly."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        data['university_name'] = xss_attempt
        
        response = api_client.post(url, data, format='json')
        
        # Should either succeed with sanitized data or fail validation
        if response.status_code == status.HTTP_201_CREATED:
            # Verify the data is stored safely
            user = User.objects.get(email=data['email'].lower())
            # The value should be stored as-is (Django templates will escape it)
            assert user.university_name == xss_attempt
    
    def test_concurrent_registration_same_email(self, valid_student_data):
        """Test concurrent registration requests with same email."""
        from django.db import connection
        
        url = reverse('user_register')
        results = []
        
        def register():
            try:
                # Each thread needs its own APIClient for proper isolation
                client = APIClient()
                # Close old connections to ensure fresh connection per thread
                connection.close()
                response = client.post(url, valid_student_data, format='json')
                results.append(response.status_code)
            except Exception as e:
                results.append(str(e))
        
        # Create multiple threads trying to register simultaneously
        threads = [threading.Thread(target=register) for _ in range(5)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Only one should succeed (201), others should fail (400)
        success_count = sum(1 for r in results if r == status.HTTP_201_CREATED)
        assert success_count == 1, f"Expected 1 success, got {success_count}"
        
        # Verify only one user was created
        assert User.objects.filter(email=valid_student_data['email'].lower()).count() == 1


@pytest.mark.django_db
class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_email_with_whitespace(self, api_client, valid_student_data):
        """Test that emails with whitespace are handled properly."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        data['email'] = '  whitespace@university.edu  '
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        # Email should be trimmed and normalized
        assert response.data['email'] == 'whitespace@university.edu'
    
    def test_very_long_email(self, api_client, valid_student_data):
        """Test email with maximum length."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        # Create a very long but valid email
        data['email'] = 'a' * 240 + '@test.com'
        
        response = api_client.post(url, data, format='json')
        
        # Should either succeed or fail gracefully
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]
    
    def test_unicode_in_password(self, api_client, valid_student_data):
        """Test that unicode characters in password are handled."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        data['email'] = 'unicode@university.edu'
        data['password'] = 'Pässwörd123!🔒'
        data['confirm_password'] = 'Pässwörd123!🔒'
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        user = User.objects.get(email=data['email'].lower())
        assert user.check_password('Pässwörd123!🔒')
    
    def test_extra_fields_ignored(self, api_client, valid_student_data):
        """Test that extra fields in request are ignored."""
        url = reverse('user_register')
        data = valid_student_data.copy()
        data['email'] = 'extrafields@university.edu'
        data['is_verified'] = True  # Try to set verified status
        data['is_superuser'] = True  # Try to set superuser
        data['is_staff'] = True  # Try to set staff
        
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        user = User.objects.get(email=data['email'].lower())
        # These should not be set by the registration
        assert user.is_verified is False
        assert user.is_superuser is False
        assert user.is_staff is False
    
    def test_missing_all_fields(self, api_client):
        """Test registration with no data."""
        url = reverse('user_register')
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Should have errors for all required fields
        assert 'email' in response.data
        assert 'password' in response.data
        assert 'user_type' in response.data
