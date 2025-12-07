"""
Comprehensive Logout Security Tests

This test suite validates JWT logout implementation with token blacklisting.
Tests cover successful logout, token blacklisting verification, post-logout security,
edge cases, and error handling.

CRITICAL: These tests should NEVER be modified to make them pass.
Only the logout implementation should be updated.
"""

import pytest
import jwt
import time
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

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
def student_user(db):
    """Create a student user for testing."""
    return User.objects.create_user(
        username='logout_student',
        email='logout_student@test.com',
        password='TestPass123!',
        first_name='Logout',
        last_name='Student',
        user_type='student',
        phone_number='+1234567890'
    )


@pytest.fixture
def provider_user(db):
    """Create a provider user for testing."""
    return User.objects.create_user(
        username='logout_provider',
        email='logout_provider@test.com',
        password='TestPass123!',
        first_name='Logout',
        last_name='Provider',
        user_type='provider',
        phone_number='+1234567891'
    )


@pytest.fixture
def valid_tokens(student_user):
    """Generate valid token pair for testing."""
    refresh = RefreshToken.for_user(student_user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token)
    }


# ============================================================================
# 1. SUCCESSFUL LOGOUT TESTS
# ============================================================================

@pytest.mark.django_db
class TestSuccessfulLogout:
    """Test successful logout scenarios."""
    
    def test_logout_with_valid_refresh_token_succeeds(self, api_client, valid_tokens):
        """Logout with valid refresh token should return 200 OK."""
        url = reverse('user_logout')
        response = api_client.post(url, {'refresh': valid_tokens['refresh']}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_logout_response_format(self, api_client, valid_tokens):
        """Logout should return appropriate success message."""
        url = reverse('user_logout')
        response = api_client.post(url, {'refresh': valid_tokens['refresh']}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        # Response should indicate success (may be empty or contain message)
        # Accept both empty response and response with message
    
    def test_logout_with_different_user_types(self, api_client, provider_user):
        """Logout should work for all user types."""
        refresh = RefreshToken.for_user(provider_user)
        refresh_token = str(refresh)
        
        url = reverse('user_logout')
        response = api_client.post(url, {'refresh': refresh_token}, format='json')
        
        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# 2. TOKEN BLACKLISTING VERIFICATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestTokenBlacklisting:
    """Test that tokens are properly blacklisted on logout."""
    
    def test_refresh_token_added_to_blacklist_on_logout(self, api_client, valid_tokens):
        """Refresh token should be added to blacklist database on logout."""
        # Decode token to get jti
        decoded = jwt.decode(
            valid_tokens['refresh'],
            settings.SECRET_KEY,
            algorithms=['HS256']
        )
        jti = decoded['jti']
        
        # Logout
        url = reverse('user_logout')
        response = api_client.post(url, {'refresh': valid_tokens['refresh']}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify token is in blacklist
        assert BlacklistedToken.objects.filter(token__jti=jti).exists()
    
    def test_blacklisted_token_cannot_be_used_for_refresh(self, api_client, valid_tokens):
        """Blacklisted refresh token should not generate new access token."""
        # Logout (blacklist token)
        logout_url = reverse('user_logout')
        api_client.post(logout_url, {'refresh': valid_tokens['refresh']}, format='json')
        
        # Try to use blacklisted token for refresh
        refresh_url = reverse('token_refresh')
        response = api_client.post(refresh_url, {'refresh': valid_tokens['refresh']}, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'access' not in response.data
    
    def test_outstanding_token_created_on_logout(self, api_client, valid_tokens):
        """Outstanding token should be created/tracked on logout."""
        # Decode token to get jti
        decoded = jwt.decode(
            valid_tokens['refresh'],
            settings.SECRET_KEY,
            algorithms=['HS256']
        )
        jti = decoded['jti']
        
        # Logout
        url = reverse('user_logout')
        api_client.post(url, {'refresh': valid_tokens['refresh']}, format='json')
        
        # Verify outstanding token exists
        assert OutstandingToken.objects.filter(jti=jti).exists()


# ============================================================================
# 3. POST-LOGOUT SECURITY TESTS
# ============================================================================

@pytest.mark.django_db
class TestPostLogoutSecurity:
    """Test security measures after logout."""
    
    def test_access_token_still_works_after_logout(self, api_client, valid_tokens):
        """Access token should work until expiry even after logout."""
        # Logout (blacklist refresh token)
        logout_url = reverse('user_logout')
        api_client.post(logout_url, {'refresh': valid_tokens['refresh']}, format='json')
        
        # Access token should still work
        verify_url = reverse('token_verify')
        response = api_client.post(verify_url, {'token': valid_tokens['access']}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_cannot_refresh_after_logout(self, api_client, valid_tokens):
        """Cannot obtain new access token after logout."""
        # Logout
        logout_url = reverse('user_logout')
        api_client.post(logout_url, {'refresh': valid_tokens['refresh']}, format='json')
        
        # Try to refresh
        refresh_url = reverse('token_refresh')
        response = api_client.post(refresh_url, {'refresh': valid_tokens['refresh']}, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_user_can_login_again_after_logout(self, api_client, student_user, valid_tokens):
        """User should be able to login again after logout."""
        # Logout
        logout_url = reverse('user_logout')
        api_client.post(logout_url, {'refresh': valid_tokens['refresh']}, format='json')
        
        # Login again
        login_url = reverse('user_login')
        response = api_client.post(login_url, {
            'email': 'logout_student@test.com',
            'password': 'TestPass123!'
        }, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data
        # New tokens should be different from old ones
        assert response.data['refresh'] != valid_tokens['refresh']


# ============================================================================
# 4. EDGE CASE TESTS
# ============================================================================

@pytest.mark.django_db
class TestLogoutEdgeCases:
    """Test edge cases and unusual scenarios."""
    
    def test_logout_with_already_blacklisted_token(self, api_client, valid_tokens):
        """Logging out with already blacklisted token should be handled gracefully."""
        url = reverse('user_logout')
        
        # First logout
        response1 = api_client.post(url, {'refresh': valid_tokens['refresh']}, format='json')
        assert response1.status_code == status.HTTP_200_OK
        
        # Second logout with same token
        response2 = api_client.post(url, {'refresh': valid_tokens['refresh']}, format='json')
        
        # Should either succeed (idempotent) or return 400/401
        assert response2.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED
        ]
    
    def test_logout_with_invalid_token_format(self, api_client):
        """Logout with invalid token format should return 400 or 401."""
        url = reverse('user_logout')
        invalid_tokens = [
            'not.a.valid.jwt',
            'only_one_part',
            'two.parts',
            '',
            '...',
        ]
        
        for invalid_token in invalid_tokens:
            response = api_client.post(url, {'refresh': invalid_token}, format='json')
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_401_UNAUTHORIZED
            ]
    
    def test_logout_with_missing_refresh_token(self, api_client):
        """Logout without refresh token should return 400."""
        url = reverse('user_logout')
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_logout_with_empty_refresh_token(self, api_client):
        """Logout with empty refresh token should return 400 or 401."""
        url = reverse('user_logout')
        response = api_client.post(url, {'refresh': ''}, format='json')
        
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED
        ]
    
    def test_logout_with_null_refresh_token(self, api_client):
        """Logout with null refresh token should return 400."""
        url = reverse('user_logout')
        response = api_client.post(url, {'refresh': None}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_logout_with_access_token_instead_of_refresh(self, api_client, valid_tokens):
        """Using access token for logout should fail."""
        url = reverse('user_logout')
        response = api_client.post(url, {'refresh': valid_tokens['access']}, format='json')
        
        # Should be rejected as access tokens have different token_type
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_logout_with_expired_refresh_token(self, api_client, student_user):
        """Logout with expired refresh token should be handled appropriately."""
        from datetime import timedelta
        
        # Create expired refresh token
        refresh = RefreshToken.for_user(student_user)
        refresh.set_exp(lifetime=-timedelta(hours=1))
        expired_token = str(refresh)
        
        url = reverse('user_logout')
        response = api_client.post(url, {'refresh': expired_token}, format='json')
        
        # Should return 401 for expired token
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_logout_with_tampered_signature(self, api_client, valid_tokens):
        """Logout with tampered token signature should fail."""
        parts = valid_tokens['refresh'].split('.')
        tampered_token = f"{parts[0]}.{parts[1]}.TAMPERED_SIGNATURE"
        
        url = reverse('user_logout')
        response = api_client.post(url, {'refresh': tampered_token}, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ============================================================================
# 5. CONCURRENT LOGOUT TESTS
# ============================================================================

@pytest.mark.django_db
class TestConcurrentLogout:
    """Test concurrent logout scenarios."""
    
    def test_multiple_rapid_logout_attempts_handled(self, api_client, student_user):
        """Multiple rapid logout attempts should be handled gracefully."""
        url = reverse('user_logout')
        
        # Generate multiple tokens
        tokens = []
        for i in range(5):
            refresh = RefreshToken.for_user(student_user)
            tokens.append(str(refresh))
        
        # Logout all tokens rapidly
        responses = []
        for token in tokens:
            response = api_client.post(url, {'refresh': token}, format='json')
            responses.append(response)
        
        # All should return valid HTTP responses (no 500 errors)
        for response in responses:
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_401_UNAUTHORIZED
            ]
    
    def test_concurrent_logout_same_token_handled(self, api_client, valid_tokens):
        """Concurrent logout attempts with same token should be handled."""
        url = reverse('user_logout')
        
        # Make rapid requests with same token
        responses = []
        for i in range(3):
            response = api_client.post(url, {'refresh': valid_tokens['refresh']}, format='json')
            responses.append(response)
        
        # First should succeed, others may fail or succeed (idempotent)
        assert responses[0].status_code == status.HTTP_200_OK
        
        # All should return valid HTTP responses
        for response in responses:
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_401_UNAUTHORIZED
            ]


# ============================================================================
# 6. ERROR MESSAGE TESTS
# ============================================================================

@pytest.mark.django_db
class TestLogoutErrorMessages:
    """Test error messages for various failure scenarios."""
    
    def test_invalid_token_error_message(self, api_client):
        """Invalid token should return appropriate error message."""
        url = reverse('user_logout')
        response = api_client.post(url, {'refresh': 'invalid_token'}, format='json')
        
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED
        ]
        # Error message should indicate token issue
        error_str = str(response.data).lower()
        assert any(word in error_str for word in ['invalid', 'token', 'error'])
    
    def test_missing_token_error_message(self, api_client):
        """Missing token should return appropriate error message."""
        url = reverse('user_logout')
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Error message should indicate missing field
        error_str = str(response.data).lower()
        assert any(word in error_str for word in ['required', 'field', 'refresh'])
