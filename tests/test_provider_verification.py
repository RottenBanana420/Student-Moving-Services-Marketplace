"""
Comprehensive Provider Verification Security Tests

This test suite is designed to FAIL initially and validate provider verification implementation.
Tests cover authentication, authorization, validation, audit logging, and security edge cases.

CRITICAL: These tests should NEVER be modified to make them pass.
Only the implementation (permissions, serializers, views) should be updated.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
import logging

User = get_user_model()


@pytest.fixture
def api_client():
    """Provide API client for testing."""
    return APIClient()


@pytest.fixture
def staff_user(db):
    """Create a staff user for testing admin access."""
    return User.objects.create_user(
        username='staff_admin',
        email='admin@example.com',
        password='AdminPass123!',
        first_name='Admin',
        last_name='User',
        user_type='student',  # Staff can be any user_type
        is_staff=True,
        is_active=True
    )


@pytest.fixture
def regular_student(db):
    """Create a regular student user (non-staff)."""
    return User.objects.create_user(
        username='regular_student',
        email='student@example.com',
        password='StudentPass123!',
        first_name='Regular',
        last_name='Student',
        user_type='student',
        is_staff=False,
        is_active=True
    )


@pytest.fixture
def regular_provider(db):
    """Create a regular provider user (non-staff)."""
    return User.objects.create_user(
        username='regular_provider',
        email='provider@example.com',
        password='ProviderPass123!',
        first_name='Regular',
        last_name='Provider',
        user_type='provider',
        is_staff=False,
        is_active=True,
        is_verified=False
    )


@pytest.fixture
def unverified_provider(db):
    """Create an unverified provider user."""
    return User.objects.create_user(
        username='unverified_provider',
        email='unverified@example.com',
        password='ProviderPass123!',
        first_name='Unverified',
        last_name='Provider',
        user_type='provider',
        is_staff=False,
        is_active=True,
        is_verified=False
    )


@pytest.fixture
def verified_provider(db):
    """Create an already verified provider user."""
    return User.objects.create_user(
        username='verified_provider',
        email='verified@example.com',
        password='ProviderPass123!',
        first_name='Verified',
        last_name='Provider',
        user_type='provider',
        is_staff=False,
        is_active=True,
        is_verified=True
    )


def get_auth_header(user):
    """Generate JWT authentication header for a user."""
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    return f'Bearer {access_token}'


# ============================================================================
# 1. SUCCESSFUL VERIFICATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestSuccessfulVerification:
    """Test successful provider verification scenarios."""
    
    def test_staff_user_can_verify_unverified_provider(self, api_client, staff_user, unverified_provider):
        """Staff user should be able to verify an unverified provider."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(staff_user))
        
        data = {'provider_id': unverified_provider.id}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify the provider was marked as verified
        unverified_provider.refresh_from_db()
        assert unverified_provider.is_verified is True
    
    def test_verification_returns_provider_information(self, api_client, staff_user, unverified_provider):
        """Verification should return updated provider information."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(staff_user))
        
        data = {'provider_id': unverified_provider.id}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'id' in response.data
        assert 'email' in response.data
        assert 'user_type' in response.data
        assert 'is_verified' in response.data
        assert response.data['id'] == unverified_provider.id
        assert response.data['email'] == unverified_provider.email
        assert response.data['user_type'] == 'provider'
        assert response.data['is_verified'] is True
        # Ensure password is NOT in response
        assert 'password' not in response.data
    
    def test_verification_is_idempotent(self, api_client, staff_user, verified_provider):
        """Verifying an already verified provider should succeed (idempotent)."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(staff_user))
        
        # Provider is already verified
        assert verified_provider.is_verified is True
        
        data = {'provider_id': verified_provider.id}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_verified'] is True
        
        # Verify still marked as verified
        verified_provider.refresh_from_db()
        assert verified_provider.is_verified is True
    
    def test_multiple_verifications_of_same_provider(self, api_client, staff_user, unverified_provider):
        """Multiple verification attempts on same provider should all succeed."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(staff_user))
        
        data = {'provider_id': unverified_provider.id}
        
        # First verification
        response1 = api_client.post(url, data, format='json')
        assert response1.status_code == status.HTTP_200_OK
        
        # Second verification (should also succeed)
        response2 = api_client.post(url, data, format='json')
        assert response2.status_code == status.HTTP_200_OK
        
        # Third verification
        response3 = api_client.post(url, data, format='json')
        assert response3.status_code == status.HTTP_200_OK
        
        # All should return is_verified=True
        assert response1.data['is_verified'] is True
        assert response2.data['is_verified'] is True
        assert response3.data['is_verified'] is True


# ============================================================================
# 2. AUTHENTICATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestAuthentication:
    """Test authentication requirements for provider verification."""
    
    def test_unauthenticated_request_returns_401(self, api_client, unverified_provider):
        """Request without authentication should return 401."""
        url = reverse('verify_provider')
        data = {'provider_id': unverified_provider.id}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Provider should NOT be verified
        unverified_provider.refresh_from_db()
        assert unverified_provider.is_verified is False
    
    def test_invalid_jwt_token_returns_401(self, api_client, unverified_provider):
        """Request with invalid JWT token should return 401."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION='Bearer invalid_token_here')
        
        data = {'provider_id': unverified_provider.id}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Provider should NOT be verified
        unverified_provider.refresh_from_db()
        assert unverified_provider.is_verified is False
    
    def test_malformed_auth_header_returns_401(self, api_client, unverified_provider):
        """Request with malformed authorization header should return 401."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION='InvalidFormat')
        
        data = {'provider_id': unverified_provider.id}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ============================================================================
# 3. AUTHORIZATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestAuthorization:
    """Test authorization requirements (staff-only access)."""
    
    def test_non_staff_student_cannot_verify_provider(self, api_client, regular_student, unverified_provider):
        """Non-staff student user should receive 403 when attempting verification."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(regular_student))
        
        data = {'provider_id': unverified_provider.id}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Provider should NOT be verified
        unverified_provider.refresh_from_db()
        assert unverified_provider.is_verified is False
    
    def test_non_staff_provider_cannot_verify_other_provider(self, api_client, regular_provider, unverified_provider):
        """Non-staff provider user should receive 403 when attempting to verify another provider."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(regular_provider))
        
        data = {'provider_id': unverified_provider.id}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Provider should NOT be verified
        unverified_provider.refresh_from_db()
        assert unverified_provider.is_verified is False
    
    def test_provider_cannot_verify_themselves(self, api_client, regular_provider):
        """Provider cannot verify their own account (non-staff)."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(regular_provider))
        
        data = {'provider_id': regular_provider.id}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Provider should NOT be verified
        regular_provider.refresh_from_db()
        assert regular_provider.is_verified is False
    
    def test_only_staff_users_can_access_endpoint(self, api_client, staff_user, regular_student, unverified_provider):
        """Only users with is_staff=True can access the endpoint."""
        url = reverse('verify_provider')
        data = {'provider_id': unverified_provider.id}
        
        # Staff user should succeed
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(staff_user))
        response_staff = api_client.post(url, data, format='json')
        assert response_staff.status_code == status.HTTP_200_OK
        
        # Non-staff user should fail
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(regular_student))
        response_non_staff = api_client.post(url, data, format='json')
        assert response_non_staff.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# 4. VALIDATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestValidation:
    """Test input validation and error handling."""
    
    def test_missing_provider_id_returns_400(self, api_client, staff_user):
        """Request without provider_id should return 400."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(staff_user))
        
        data = {}  # Missing provider_id
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'provider_id' in str(response.data).lower()
    
    def test_invalid_provider_id_format_returns_400(self, api_client, staff_user):
        """Request with invalid provider_id format should return 400."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(staff_user))
        
        invalid_ids = ['abc', 'null', '', '12.5', '-1']
        
        for invalid_id in invalid_ids:
            data = {'provider_id': invalid_id}
            response = api_client.post(url, data, format='json')
            assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_nonexistent_provider_id_returns_404(self, api_client, staff_user):
        """Request with non-existent provider_id should return 404."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(staff_user))
        
        # Use a provider_id that doesn't exist
        data = {'provider_id': 999999}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_verifying_student_account_returns_400(self, api_client, staff_user, regular_student):
        """Attempting to verify a student account should return 400."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(staff_user))
        
        data = {'provider_id': regular_student.id}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_message = str(response.data).lower()
        assert 'provider' in error_message or 'user_type' in error_message
        
        # Student should NOT have is_verified changed
        regular_student.refresh_from_db()
        assert regular_student.is_verified is False
    
    def test_verifying_non_provider_user_returns_400(self, api_client, staff_user, regular_student):
        """Attempting to verify a non-provider user should return 400."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(staff_user))
        
        # Try to verify a student (not a provider)
        data = {'provider_id': regular_student.id}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# 5. SECURITY TESTS
# ============================================================================

@pytest.mark.django_db
class TestSecurity:
    """Test security features and attack prevention."""
    
    def test_verification_action_is_logged(self, api_client, staff_user, unverified_provider, caplog):
        """Verification action should be logged for audit trail."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(staff_user))
        
        with caplog.at_level(logging.INFO):
            data = {'provider_id': unverified_provider.id}
            response = api_client.post(url, data, format='json')
            
            assert response.status_code == status.HTTP_200_OK
            
            # Check that verification was logged
            log_messages = [record.message for record in caplog.records]
            log_text = ' '.join(log_messages).lower()
            
            # Log should contain key information
            assert 'verif' in log_text  # "verified" or "verification"
            assert staff_user.email.lower() in log_text or 'admin' in log_text
            assert unverified_provider.email.lower() in log_text or str(unverified_provider.id) in log_text
    
    def test_cannot_bypass_staff_permission_check(self, api_client, regular_student, unverified_provider):
        """Cannot bypass staff permission check with any technique."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(regular_student))
        
        # Try various bypass attempts
        bypass_attempts = [
            {'provider_id': unverified_provider.id, 'is_staff': True},
            {'provider_id': unverified_provider.id, 'force': True},
            {'provider_id': unverified_provider.id, 'admin': True},
        ]
        
        for data in bypass_attempts:
            response = api_client.post(url, data, format='json')
            assert response.status_code == status.HTTP_403_FORBIDDEN
            
            # Provider should NOT be verified
            unverified_provider.refresh_from_db()
            assert unverified_provider.is_verified is False
    
    def test_sql_injection_in_provider_id_fails_safely(self, api_client, staff_user):
        """SQL injection attempts in provider_id should fail safely."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(staff_user))
        
        sql_injection_payloads = [
            "1 OR 1=1",
            "1; DROP TABLE users;",
            "1' OR '1'='1",
        ]
        
        for payload in sql_injection_payloads:
            data = {'provider_id': payload}
            response = api_client.post(url, data, format='json')
            
            # Should fail with 400 (validation error), not 500 (server error)
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_404_NOT_FOUND
            ]
    
    def test_cannot_verify_without_authentication(self, api_client, unverified_provider):
        """Cannot verify provider without proper authentication."""
        url = reverse('verify_provider')
        
        data = {'provider_id': unverified_provider.id}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Provider should NOT be verified
        unverified_provider.refresh_from_db()
        assert unverified_provider.is_verified is False


# ============================================================================
# 6. EDGE CASES AND CONCURRENT ACCESS
# ============================================================================

@pytest.mark.django_db
class TestEdgeCases:
    """Test edge cases and concurrent access scenarios."""
    
    def test_concurrent_verification_attempts(self, api_client, staff_user, unverified_provider):
        """Multiple concurrent verification attempts should handle gracefully."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(staff_user))
        
        data = {'provider_id': unverified_provider.id}
        
        # Simulate rapid concurrent requests
        responses = []
        for i in range(5):
            response = api_client.post(url, data, format='json')
            responses.append(response)
        
        # All should succeed (idempotent operation)
        for response in responses:
            assert response.status_code == status.HTTP_200_OK
            assert response.data['is_verified'] is True
        
        # Provider should be verified
        unverified_provider.refresh_from_db()
        assert unverified_provider.is_verified is True
    
    def test_verify_inactive_provider(self, api_client, staff_user, db):
        """Verifying an inactive provider should still work."""
        inactive_provider = User.objects.create_user(
            username='inactive_provider',
            email='inactive_provider@example.com',
            password='ProviderPass123!',
            user_type='provider',
            is_staff=False,
            is_active=False,  # Inactive account
            is_verified=False
        )
        
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(staff_user))
        
        data = {'provider_id': inactive_provider.id}
        response = api_client.post(url, data, format='json')
        
        # Should succeed - verification is independent of active status
        assert response.status_code == status.HTTP_200_OK
        
        inactive_provider.refresh_from_db()
        assert inactive_provider.is_verified is True
    
    def test_http_methods_other_than_post_not_allowed(self, api_client, staff_user, unverified_provider):
        """Only POST method should be allowed."""
        url = reverse('verify_provider')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(staff_user))
        
        # Test GET
        response_get = api_client.get(url)
        assert response_get.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        
        # Test PUT
        response_put = api_client.put(url, {'provider_id': unverified_provider.id}, format='json')
        assert response_put.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        
        # Test DELETE
        response_delete = api_client.delete(url)
        assert response_delete.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        
        # Test PATCH
        response_patch = api_client.patch(url, {'provider_id': unverified_provider.id}, format='json')
        assert response_patch.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
