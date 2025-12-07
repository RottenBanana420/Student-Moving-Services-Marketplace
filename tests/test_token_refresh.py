"""
Comprehensive Token Refresh Security Tests

This test suite is designed to FAIL initially and validate token refresh implementation.
Tests cover refresh token validation, expiration, signature tampering, blacklisting,
rotation, rate limiting, and edge cases.

CRITICAL: These tests should NEVER be modified to make them pass.
Only the token refresh implementation should be updated.
"""

import pytest
import jwt
import time
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
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
        username='refresh_test_student',
        email='refresh@test.com',
        password='TestPass123!',
        first_name='Refresh',
        last_name='Test',
        user_type='student',
        phone_number='+1234567890'
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
# 1. VALID REFRESH TOKEN TESTS
# ============================================================================

@pytest.mark.django_db
class TestValidRefreshToken:
    """Test successful token refresh with valid refresh token."""
    
    def test_refresh_with_valid_token_returns_new_access_token(self, api_client, valid_tokens):
        """Valid refresh token should generate new access token."""
        url = reverse('token_refresh')
        response = api_client.post(url, {'refresh': valid_tokens['refresh']}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert isinstance(response.data['access'], str)
        assert len(response.data['access']) > 0
        # New access token should be different from original
        assert response.data['access'] != valid_tokens['access']
    
    def test_refresh_returns_new_refresh_token_rotation(self, api_client, valid_tokens):
        """Token rotation should provide new refresh token."""
        url = reverse('token_refresh')
        response = api_client.post(url, {'refresh': valid_tokens['refresh']}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        # Check if rotation is enabled (new refresh token provided)
        if 'refresh' in response.data:
            assert isinstance(response.data['refresh'], str)
            assert response.data['refresh'] != valid_tokens['refresh']
    
    def test_new_access_token_is_valid_jwt(self, api_client, valid_tokens):
        """New access token should be a valid JWT with correct claims."""
        url = reverse('token_refresh')
        response = api_client.post(url, {'refresh': valid_tokens['refresh']}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        new_access_token = response.data['access']
        
        # Decode and verify token
        decoded = jwt.decode(
            new_access_token,
            settings.SECRET_KEY,
            algorithms=['HS256']
        )
        
        assert 'user_id' in decoded
        assert 'exp' in decoded
        assert 'token_type' in decoded
        assert decoded['token_type'] == 'access'
    
    def test_new_access_token_can_be_verified(self, api_client, valid_tokens):
        """New access token should pass verification."""
        refresh_url = reverse('token_refresh')
        refresh_response = api_client.post(refresh_url, {'refresh': valid_tokens['refresh']}, format='json')
        
        assert refresh_response.status_code == status.HTTP_200_OK
        new_access_token = refresh_response.data['access']
        
        verify_url = reverse('token_verify')
        verify_response = api_client.post(verify_url, {'token': new_access_token}, format='json')
        
        assert verify_response.status_code == status.HTTP_200_OK


# ============================================================================
# 2. EXPIRED REFRESH TOKEN TESTS
# ============================================================================

@pytest.mark.django_db
class TestExpiredRefreshToken:
    """Test that expired refresh tokens are rejected."""
    
    def test_expired_refresh_token_rejected(self, api_client, student_user):
        """Expired refresh token should not generate new access token."""
        # Create refresh token with immediate expiration
        refresh = RefreshToken.for_user(student_user)
        refresh.set_exp(lifetime=-timedelta(hours=1))
        expired_refresh = str(refresh)
        
        url = reverse('token_refresh')
        response = api_client.post(url, {'refresh': expired_refresh}, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'access' not in response.data
    
    def test_expired_refresh_token_error_message(self, api_client, student_user):
        """Expired token should return appropriate error message."""
        refresh = RefreshToken.for_user(student_user)
        refresh.set_exp(lifetime=-timedelta(hours=1))
        expired_refresh = str(refresh)
        
        url = reverse('token_refresh')
        response = api_client.post(url, {'refresh': expired_refresh}, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        # Error message should indicate token issue
        error_str = str(response.data).lower()
        assert any(word in error_str for word in ['expired', 'invalid', 'token'])


# ============================================================================
# 3. ACCESS TOKEN MISUSE TESTS
# ============================================================================

@pytest.mark.django_db
class TestAccessTokenMisuse:
    """Test that access tokens cannot be used for refresh."""
    
    def test_access_token_instead_of_refresh_token_rejected(self, api_client, valid_tokens):
        """Using access token for refresh should fail."""
        url = reverse('token_refresh')
        # Try to use access token instead of refresh token
        response = api_client.post(url, {'refresh': valid_tokens['access']}, format='json')
        
        # Should be rejected (access tokens have different token_type)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'access' not in response.data
    
    def test_access_token_error_indicates_wrong_type(self, api_client, valid_tokens):
        """Error should indicate wrong token type."""
        url = reverse('token_refresh')
        response = api_client.post(url, {'refresh': valid_tokens['access']}, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        # Error should relate to token type or invalidity
        error_str = str(response.data).lower()
        assert any(word in error_str for word in ['invalid', 'token', 'type'])


# ============================================================================
# 4. SIGNATURE TAMPERING TESTS
# ============================================================================

@pytest.mark.django_db
class TestSignatureTampering:
    """Test security against token signature manipulation."""
    
    def test_tampered_signature_rejected(self, api_client, valid_tokens):
        """Refresh token with tampered signature should be rejected."""
        parts = valid_tokens['refresh'].split('.')
        tampered_token = f"{parts[0]}.{parts[1]}.TAMPERED_SIGNATURE_HERE"
        
        url = reverse('token_refresh')
        response = api_client.post(url, {'refresh': tampered_token}, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'access' not in response.data
    
    def test_modified_payload_rejected(self, api_client, student_user):
        """Token with modified payload should be rejected."""
        import base64
        import json
        
        refresh = RefreshToken.for_user(student_user)
        token_str = str(refresh)
        parts = token_str.split('.')
        
        # Decode and modify payload
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))
        payload['user_id'] = 99999  # Modify user_id
        
        # Re-encode payload
        modified_payload = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode().rstrip('=')
        
        # Create token with modified payload (signature won't match)
        modified_token = f"{parts[0]}.{modified_payload}.{parts[2]}"
        
        url = reverse('token_refresh')
        response = api_client.post(url, {'refresh': modified_token}, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_malformed_token_rejected(self, api_client):
        """Malformed tokens should be rejected."""
        malformed_tokens = [
            'not.a.valid.jwt',
            'only_one_part',
            'two.parts',
            '',
            '...',
            'Bearer token',
        ]
        
        url = reverse('token_refresh')
        for malformed_token in malformed_tokens:
            response = api_client.post(url, {'refresh': malformed_token}, format='json')
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_401_UNAUTHORIZED
            ]


# ============================================================================
# 5. BLACKLISTED TOKEN TESTS
# ============================================================================

@pytest.mark.django_db
class TestBlacklistedToken:
    """Test that blacklisted tokens are rejected."""
    
    def test_blacklisted_refresh_token_rejected(self, api_client, valid_tokens):
        """Blacklisted refresh token should not generate new access token."""
        # Blacklist the token
        blacklist_url = reverse('token_blacklist')
        api_client.post(blacklist_url, {'refresh': valid_tokens['refresh']}, format='json')
        
        # Try to use blacklisted token
        refresh_url = reverse('token_refresh')
        response = api_client.post(refresh_url, {'refresh': valid_tokens['refresh']}, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'access' not in response.data
    
    def test_token_blacklisted_after_logout(self, api_client, student_user):
        """Token should be blacklisted after logout and unusable."""
        # Generate tokens
        refresh = RefreshToken.for_user(student_user)
        refresh_token = str(refresh)
        
        # Logout (blacklist token)
        blacklist_url = reverse('token_blacklist')
        blacklist_response = api_client.post(blacklist_url, {'refresh': refresh_token}, format='json')
        assert blacklist_response.status_code == status.HTTP_200_OK
        
        # Verify token is in blacklist database
        decoded = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=['HS256'])
        jti = decoded['jti']
        assert BlacklistedToken.objects.filter(token__jti=jti).exists()
        
        # Try to use blacklisted token
        refresh_url = reverse('token_refresh')
        response = api_client.post(refresh_url, {'refresh': refresh_token}, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ============================================================================
# 6. TOKEN ROTATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestTokenRotation:
    """Test refresh token rotation security."""
    
    def test_old_refresh_token_invalid_after_rotation(self, api_client, valid_tokens):
        """Old refresh token should be invalid after rotation."""
        url = reverse('token_refresh')
        
        # First refresh (rotation occurs)
        response1 = api_client.post(url, {'refresh': valid_tokens['refresh']}, format='json')
        assert response1.status_code == status.HTTP_200_OK
        
        # Try to use old refresh token again
        response2 = api_client.post(url, {'refresh': valid_tokens['refresh']}, format='json')
        
        # Old token should be rejected if rotation is enabled
        assert response2.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_new_refresh_token_works_after_rotation(self, api_client, valid_tokens):
        """New refresh token from rotation should work."""
        url = reverse('token_refresh')
        
        # First refresh
        response1 = api_client.post(url, {'refresh': valid_tokens['refresh']}, format='json')
        assert response1.status_code == status.HTTP_200_OK
        
        # If rotation is enabled, we should have a new refresh token
        if 'refresh' in response1.data:
            new_refresh_token = response1.data['refresh']
            
            # Use new refresh token
            response2 = api_client.post(url, {'refresh': new_refresh_token}, format='json')
            assert response2.status_code == status.HTTP_200_OK
            assert 'access' in response2.data
    
    def test_old_refresh_token_blacklisted_after_rotation(self, api_client, valid_tokens):
        """Old refresh token should be blacklisted after rotation."""
        url = reverse('token_refresh')
        
        # Decode original token to get jti
        decoded = jwt.decode(valid_tokens['refresh'], settings.SECRET_KEY, algorithms=['HS256'])
        old_jti = decoded['jti']
        
        # Refresh (rotation occurs)
        response = api_client.post(url, {'refresh': valid_tokens['refresh']}, format='json')
        assert response.status_code == status.HTTP_200_OK
        
        # Check if old token is blacklisted
        # Note: There may be a slight delay, so we check the database
        time.sleep(0.1)  # Small delay to ensure database update
        is_blacklisted = BlacklistedToken.objects.filter(token__jti=old_jti).exists()
        assert is_blacklisted


# ============================================================================
# 7. OLD ACCESS TOKEN VALIDITY TESTS
# ============================================================================

@pytest.mark.django_db
class TestOldAccessTokenValidity:
    """Test that old access tokens remain valid until expiration."""
    
    def test_old_access_token_works_after_refresh(self, api_client, valid_tokens):
        """Old access token should work until expiry even after refresh."""
        # Refresh to get new tokens
        refresh_url = reverse('token_refresh')
        refresh_response = api_client.post(refresh_url, {'refresh': valid_tokens['refresh']}, format='json')
        assert refresh_response.status_code == status.HTTP_200_OK
        
        # Old access token should still work
        verify_url = reverse('token_verify')
        verify_response = api_client.post(verify_url, {'token': valid_tokens['access']}, format='json')
        
        assert verify_response.status_code == status.HTTP_200_OK
    
    def test_old_access_token_independent_of_refresh_blacklist(self, api_client, valid_tokens):
        """Access token validity is independent of refresh token blacklist status."""
        # Blacklist refresh token
        blacklist_url = reverse('token_blacklist')
        api_client.post(blacklist_url, {'refresh': valid_tokens['refresh']}, format='json')
        
        # Old access token should still work
        verify_url = reverse('token_verify')
        verify_response = api_client.post(verify_url, {'token': valid_tokens['access']}, format='json')
        
        assert verify_response.status_code == status.HTTP_200_OK


# ============================================================================
# 8. RATE LIMITING TESTS
# ============================================================================

@pytest.mark.django_db
class TestRateLimiting:
    """Test rate limiting for refresh endpoint."""
    
    def test_excessive_refresh_attempts_rate_limited(self, api_client, student_user):
        """More than 10 refresh attempts per minute should be rate limited."""
        url = reverse('token_refresh')
        
        # Generate multiple refresh tokens
        responses = []
        for i in range(12):
            refresh = RefreshToken.for_user(student_user)
            refresh_token = str(refresh)
            response = api_client.post(url, {'refresh': refresh_token}, format='json')
            responses.append(response)
        
        # At least one should be rate limited (429)
        status_codes = [r.status_code for r in responses]
        assert status.HTTP_429_TOO_MANY_REQUESTS in status_codes
    
    def test_rate_limit_error_message(self, api_client, student_user):
        """Rate limit should return appropriate error message."""
        url = reverse('token_refresh')
        
        # Make many requests to trigger rate limit
        for i in range(15):
            refresh = RefreshToken.for_user(student_user)
            response = api_client.post(url, {'refresh': str(refresh)}, format='json')
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                # Check error message
                error_str = str(response.data).lower()
                assert any(word in error_str for word in ['throttled', 'rate', 'limit', 'many'])
                break


# ============================================================================
# 9. EDGE CASE TESTS
# ============================================================================

@pytest.mark.django_db
class TestEdgeCases:
    """Test edge cases and unusual scenarios."""
    
    def test_missing_refresh_token_field(self, api_client):
        """Request without refresh token field should return 400."""
        url = reverse('token_refresh')
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_empty_refresh_token_field(self, api_client):
        """Empty refresh token should return 400 or 401."""
        url = reverse('token_refresh')
        response = api_client.post(url, {'refresh': ''}, format='json')
        
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED
        ]
    
    def test_null_refresh_token_field(self, api_client):
        """Null refresh token should return 400."""
        url = reverse('token_refresh')
        response = api_client.post(url, {'refresh': None}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_extremely_long_token_rejected(self, api_client):
        """Extremely long token value should be rejected."""
        url = reverse('token_refresh')
        extremely_long_token = 'A' * 10000
        response = api_client.post(url, {'refresh': extremely_long_token}, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_refresh_with_extra_fields_ignored(self, api_client, valid_tokens):
        """Extra fields in request should be ignored."""
        url = reverse('token_refresh')
        response = api_client.post(url, {
            'refresh': valid_tokens['refresh'],
            'extra_field': 'should_be_ignored',
            'another_field': 123
        }, format='json')
        
        # Should still work
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
    
    def test_concurrent_refresh_requests_handled(self, api_client, valid_tokens):
        """Concurrent refresh requests should be handled gracefully."""
        url = reverse('token_refresh')
        
        # Make rapid concurrent requests with same token
        responses = []
        for i in range(3):
            response = api_client.post(url, {'refresh': valid_tokens['refresh']}, format='json')
            responses.append(response)
        
        # First should succeed, subsequent may fail due to rotation
        assert responses[0].status_code == status.HTTP_200_OK
        
        # All should return valid HTTP responses (no 500 errors)
        for response in responses:
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_429_TOO_MANY_REQUESTS
            ]
