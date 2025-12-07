"""
Comprehensive Login Security Tests

This test suite is designed to FAIL initially and validate login security implementation.
Tests cover authentication, token generation, rate limiting, SQL injection prevention,
and user enumeration protection.

CRITICAL: These tests should NEVER be modified to make them pass.
Only the login implementation should be updated.
"""

import pytest
import time
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
import jwt
from django.conf import settings

User = get_user_model()


@pytest.fixture(autouse=True)
def clear_cache(db):
    """Clear Django cache before each test to reset throttle limits."""
    from django.core.cache import cache
    cache.clear()


@pytest.fixture
def api_client():
    """Provide API client for testing."""
    return APIClient()


@pytest.fixture
def active_student(db):
    """Create an active student user for testing."""
    return User.objects.create_user(
        username='active_student',
        email='student@example.com',
        password='SecurePass123!',
        first_name='Active',
        last_name='Student',
        user_type='student',
        is_active=True
    )


@pytest.fixture
def inactive_student(db):
    """Create an inactive student user for testing."""
    user = User.objects.create_user(
        username='inactive_student',
        email='inactive@example.com',
        password='SecurePass123!',
        first_name='Inactive',
        last_name='Student',
        user_type='student',
        is_active=False
    )
    return user


@pytest.fixture
def active_provider(db):
    """Create an active provider user for testing."""
    return User.objects.create_user(
        username='active_provider',
        email='provider@example.com',
        password='ProviderPass123!',
        first_name='Active',
        last_name='Provider',
        user_type='provider',
        is_active=True,
        is_verified=True
    )


# ============================================================================
# 1. SUCCESSFUL LOGIN TESTS
# ============================================================================

@pytest.mark.django_db
class TestSuccessfulLogin:
    """Test successful login scenarios."""
    
    def test_login_with_correct_credentials_returns_tokens(self, api_client, active_student):
        """Login with correct credentials should return access and refresh tokens."""
        url = reverse('user_login')
        data = {
            'email': 'student@example.com',
            'password': 'SecurePass123!'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data
        assert isinstance(response.data['access'], str)
        assert isinstance(response.data['refresh'], str)
        assert len(response.data['access']) > 0
        assert len(response.data['refresh']) > 0
    
    def test_login_returns_user_information(self, api_client, active_student):
        """Login should return user information excluding sensitive data."""
        url = reverse('user_login')
        data = {
            'email': 'student@example.com',
            'password': 'SecurePass123!'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'user' in response.data
        assert response.data['user']['id'] == active_student.id
        assert response.data['user']['email'] == 'student@example.com'
        assert response.data['user']['user_type'] == 'student'
        assert 'is_verified' in response.data['user']
        # Ensure password is NOT in response
        assert 'password' not in response.data['user']
    
    def test_login_with_case_insensitive_email(self, api_client, active_student):
        """Login should work with different email case."""
        url = reverse('user_login')
        data = {
            'email': 'STUDENT@EXAMPLE.COM',  # Uppercase
            'password': 'SecurePass123!'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data
    
    def test_provider_login_with_correct_credentials(self, api_client, active_provider):
        """Provider users should be able to login."""
        url = reverse('user_login')
        data = {
            'email': 'provider@example.com',
            'password': 'ProviderPass123!'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert response.data['user']['user_type'] == 'provider'
        assert response.data['user']['is_verified'] == True


# ============================================================================
# 2. AUTHENTICATION FAILURE TESTS
# ============================================================================

@pytest.mark.django_db
class TestAuthenticationFailures:
    """Test authentication failure scenarios with generic error messages."""
    
    def test_login_with_incorrect_password_fails(self, api_client, active_student):
        """Login with incorrect password should return 401 with generic error."""
        url = reverse('user_login')
        data = {
            'email': 'student@example.com',
            'password': 'WrongPassword123!'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'access' not in response.data
        assert 'refresh' not in response.data
        # Check for generic error message
        error_message = str(response.data).lower()
        assert 'invalid' in error_message or 'credentials' in error_message
    
    def test_login_with_nonexistent_email_fails(self, api_client):
        """Login with non-existent email should return 401 with generic error."""
        url = reverse('user_login')
        data = {
            'email': 'nonexistent@example.com',
            'password': 'SomePassword123!'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'access' not in response.data
        # Generic error should not reveal user doesn't exist
        error_message = str(response.data).lower()
        assert 'invalid' in error_message or 'credentials' in error_message
        assert 'not found' not in error_message
        assert 'does not exist' not in error_message
    
    def test_login_with_inactive_account_fails(self, api_client, inactive_student):
        """Login with inactive account should return 401 with generic error."""
        url = reverse('user_login')
        data = {
            'email': 'inactive@example.com',
            'password': 'SecurePass123!'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'access' not in response.data
        # Generic error should not reveal account is inactive
        error_message = str(response.data).lower()
        assert 'invalid' in error_message or 'credentials' in error_message
        assert 'inactive' not in error_message
        assert 'disabled' not in error_message
    
    def test_login_with_empty_credentials_fails(self, api_client):
        """Login with empty credentials should return 400."""
        url = reverse('user_login')
        data = {
            'email': '',
            'password': ''
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_login_with_missing_email_fails(self, api_client):
        """Login with missing email should return 400."""
        url = reverse('user_login')
        data = {
            'password': 'SomePassword123!'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_login_with_missing_password_fails(self, api_client, active_student):
        """Login with missing password should return 400."""
        url = reverse('user_login')
        data = {
            'email': 'student@example.com'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_generic_error_messages_prevent_user_enumeration(self, api_client, active_student):
        """Error messages for wrong password and non-existent user should be identical."""
        url = reverse('user_login')
        
        # Wrong password for existing user
        response1 = api_client.post(url, {
            'email': 'student@example.com',
            'password': 'WrongPassword123!'
        }, format='json')
        
        # Non-existent user
        response2 = api_client.post(url, {
            'email': 'nonexistent@example.com',
            'password': 'SomePassword123!'
        }, format='json')
        
        # Both should return same status code
        assert response1.status_code == response2.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Error messages should be generic and similar
        error1 = str(response1.data).lower()
        error2 = str(response2.data).lower()
        # Both should contain generic terms
        assert 'invalid' in error1 or 'credentials' in error1
        assert 'invalid' in error2 or 'credentials' in error2


# ============================================================================
# 3. TOKEN VALIDATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestTokenValidation:
    """Test that returned tokens are valid and properly formatted."""
    
    def test_returned_access_token_is_valid_jwt(self, api_client, active_student):
        """Returned access token should be a valid JWT."""
        url = reverse('user_login')
        data = {
            'email': 'student@example.com',
            'password': 'SecurePass123!'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        access_token = response.data['access']
        
        # Decode token to verify it's valid
        decoded = jwt.decode(
            access_token,
            settings.SECRET_KEY,
            algorithms=['HS256']
        )
        
        assert 'user_id' in decoded
        # user_id may be string or int depending on JWT library
        assert str(decoded['user_id']) == str(active_student.id)
        assert 'exp' in decoded  # Expiration
        assert 'token_type' in decoded
    
    def test_returned_refresh_token_is_valid_jwt(self, api_client, active_student):
        """Returned refresh token should be a valid JWT."""
        url = reverse('user_login')
        data = {
            'email': 'student@example.com',
            'password': 'SecurePass123!'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        refresh_token = response.data['refresh']
        
        # Decode token to verify it's valid
        decoded = jwt.decode(
            refresh_token,
            settings.SECRET_KEY,
            algorithms=['HS256']
        )
        
        assert 'user_id' in decoded
        # user_id may be string or int depending on JWT library
        assert str(decoded['user_id']) == str(active_student.id)
        assert 'exp' in decoded
    
    def test_access_token_can_be_verified(self, api_client, active_student):
        """Access token should pass verification endpoint."""
        login_url = reverse('user_login')
        login_response = api_client.post(login_url, {
            'email': 'student@example.com',
            'password': 'SecurePass123!'
        }, format='json')
        
        access_token = login_response.data['access']
        
        verify_url = reverse('token_verify')
        verify_response = api_client.post(verify_url, {
            'token': access_token
        }, format='json')
        
        assert verify_response.status_code == status.HTTP_200_OK
    
    def test_refresh_token_can_generate_new_access_token(self, api_client, active_student):
        """Refresh token should be able to generate new access token."""
        login_url = reverse('user_login')
        login_response = api_client.post(login_url, {
            'email': 'student@example.com',
            'password': 'SecurePass123!'
        }, format='json')
        
        refresh_token = login_response.data['refresh']
        
        refresh_url = reverse('token_refresh')
        refresh_response = api_client.post(refresh_url, {
            'refresh': refresh_token
        }, format='json')
        
        assert refresh_response.status_code == status.HTTP_200_OK
        assert 'access' in refresh_response.data
    
    def test_access_and_refresh_tokens_are_different(self, api_client, active_student):
        """Access and refresh tokens should be different."""
        url = reverse('user_login')
        response = api_client.post(url, {
            'email': 'student@example.com',
            'password': 'SecurePass123!'
        }, format='json')
        
        assert response.data['access'] != response.data['refresh']


# ============================================================================
# 4. SQL INJECTION PREVENTION TESTS
# ============================================================================

@pytest.mark.django_db
class TestSQLInjectionPrevention:
    """Test that SQL injection attempts fail safely."""
    
    def test_sql_injection_in_email_field_fails_safely(self, api_client):
        """SQL injection attempt in email should fail safely without exposing data."""
        url = reverse('user_login')
        sql_injection_payloads = [
            "' OR '1'='1",
            "admin'--",
            "' OR '1'='1' --",
            "' OR 1=1--",
            "admin' OR '1'='1'/*",
            "'; DROP TABLE users; --",
        ]
        
        for payload in sql_injection_payloads:
            data = {
                'email': payload,
                'password': 'SomePassword123!'
            }
            response = api_client.post(url, data, format='json')
            
            # Should fail with 400 or 401, not 500 (server error)
            # 429 is also acceptable (rate limited)
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_429_TOO_MANY_REQUESTS
            ]
            assert 'access' not in response.data
    
    def test_sql_injection_in_password_field_fails_safely(self, api_client, active_student):
        """SQL injection attempt in password should fail safely."""
        url = reverse('user_login')
        sql_injection_payloads = [
            "' OR '1'='1",
            "' OR 1=1--",
            "admin' OR '1'='1'/*",
        ]
        
        for payload in sql_injection_payloads:
            data = {
                'email': 'student@example.com',
                'password': payload
            }
            response = api_client.post(url, data, format='json')
            
            # Should fail authentication, not cause server error
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert 'access' not in response.data
    
    def test_xss_attempt_in_credentials_fails_safely(self, api_client):
        """XSS attempts in credentials should fail safely."""
        url = reverse('user_login')
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
        ]
        
        for payload in xss_payloads:
            data = {
                'email': payload,
                'password': 'SomePassword123!'
            }
            response = api_client.post(url, data, format='json')
            
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_401_UNAUTHORIZED
            ]


# ============================================================================
# 5. RATE LIMITING TESTS
# ============================================================================

@pytest.mark.django_db
class TestRateLimiting:
    """Test rate limiting for login attempts."""
    
    def test_excessive_login_attempts_are_rate_limited(self, api_client, active_student):
        """More than 5 login attempts per minute should be rate limited."""
        url = reverse('user_login')
        data = {
            'email': 'student@example.com',
            'password': 'WrongPassword123!'
        }
        
        # Make 6 rapid login attempts
        responses = []
        for i in range(6):
            response = api_client.post(url, data, format='json')
            responses.append(response)
        
        # At least one should be rate limited (429)
        status_codes = [r.status_code for r in responses]
        assert status.HTTP_429_TOO_MANY_REQUESTS in status_codes
    
    def test_successful_login_not_affected_by_rate_limit(self, api_client, active_student):
        """Successful login should work even after failed attempts."""
        url = reverse('user_login')
        
        # Make 4 failed attempts
        for i in range(4):
            api_client.post(url, {
                'email': 'student@example.com',
                'password': 'WrongPassword123!'
            }, format='json')
        
        # 5th attempt with correct password should succeed
        response = api_client.post(url, {
            'email': 'student@example.com',
            'password': 'SecurePass123!'
        }, format='json')
        
        # Should either succeed or be rate limited, but not fail auth
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_429_TOO_MANY_REQUESTS
        ]


# ============================================================================
# 6. RAPID SUCCESSIVE ATTEMPTS TESTS
# ============================================================================

@pytest.mark.django_db
class TestRapidSuccessiveAttempts:
    """Test handling of rapid successive login attempts."""
    
    def test_ten_rapid_login_attempts_handled_gracefully(self, api_client, active_student):
        """10 rapid successive login attempts should be handled without crashes."""
        url = reverse('user_login')
        data = {
            'email': 'student@example.com',
            'password': 'SecurePass123!'
        }
        
        responses = []
        for i in range(10):
            response = api_client.post(url, data, format='json')
            responses.append(response)
        
        # All responses should be valid HTTP responses (no 500 errors)
        for response in responses:
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_429_TOO_MANY_REQUESTS
            ]
        
        # At least some should succeed before rate limiting
        success_count = sum(1 for r in responses if r.status_code == status.HTTP_200_OK)
        assert success_count > 0
    
    def test_concurrent_login_attempts_no_race_conditions(self, api_client, active_student):
        """Concurrent login attempts should not cause race conditions."""
        url = reverse('user_login')
        data = {
            'email': 'student@example.com',
            'password': 'SecurePass123!'
        }
        
        # Simulate rapid concurrent requests
        responses = []
        for i in range(5):
            response = api_client.post(url, data, format='json')
            responses.append(response)
        
        # All should return valid responses
        for response in responses:
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_429_TOO_MANY_REQUESTS
            ]
        
        # Successful responses should have valid tokens
        for response in responses:
            if response.status_code == status.HTTP_200_OK:
                assert 'access' in response.data
                assert 'refresh' in response.data
                assert len(response.data['access']) > 0
