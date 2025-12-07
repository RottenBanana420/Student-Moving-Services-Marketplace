"""
Comprehensive Authentication System Integration Tests

This test suite validates the entire authentication system works end-to-end.
Tests cover complete user journeys, authentication flows, admin workflows,
security scenarios, and cross-endpoint verification.

CRITICAL: These tests should NEVER be modified to make them pass.
Only the authentication system implementation should be updated.
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
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

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


# ============================================================================
# 1. COMPLETE USER JOURNEY TESTS
# ============================================================================

@pytest.mark.django_db
class TestCompleteUserJourneys:
    """Test complete user journeys from registration to logout."""
    
    def test_student_complete_journey(self, api_client):
        """Test complete student journey: register → login → profile → update → logout."""
        # Step 1: Register
        register_url = reverse('user_register')
        register_data = {
            'email': 'journey_student@test.com',
            'password': 'SecurePass123!',
            'confirm_password': 'SecurePass123!',
            'user_type': 'student',
            'phone_number': '+1234567890',
            'university_name': 'Test University'
        }
        register_response = api_client.post(register_url, register_data, format='json')
        assert register_response.status_code == status.HTTP_201_CREATED
        user_id = register_response.data['id']
        
        # Step 2: Login
        login_url = reverse('user_login')
        login_data = {
            'email': 'journey_student@test.com',
            'password': 'SecurePass123!'
        }
        login_response = api_client.post(login_url, login_data, format='json')
        assert login_response.status_code == status.HTTP_200_OK
        assert 'access' in login_response.data
        assert 'refresh' in login_response.data
        access_token = login_response.data['access']
        refresh_token = login_response.data['refresh']
        
        # Step 3: Access profile
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        profile_url = reverse('user_profile')
        profile_response = api_client.get(profile_url)
        assert profile_response.status_code == status.HTTP_200_OK
        assert profile_response.data['id'] == user_id
        assert profile_response.data['email'] == 'journey_student@test.com'
        
        # Step 4: Update profile
        update_data = {
            'phone_number': '+9876543210',
            'university_name': 'Updated University'
        }
        update_response = api_client.patch(profile_url, update_data, format='json')
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.data['phone_number'] == '+9876543210'
        
        # Step 5: Verify update persisted
        profile_response2 = api_client.get(profile_url)
        assert profile_response2.status_code == status.HTTP_200_OK
        assert profile_response2.data['phone_number'] == '+9876543210'
        assert profile_response2.data['university_name'] == 'Updated University'
        
        # Step 6: Logout
        api_client.credentials()  # Clear auth header
        logout_url = reverse('user_logout')
        logout_response = api_client.post(logout_url, {'refresh': refresh_token}, format='json')
        assert logout_response.status_code == status.HTTP_200_OK
        
        # Step 7: Verify cannot refresh after logout
        refresh_url = reverse('token_refresh')
        refresh_response = api_client.post(refresh_url, {'refresh': refresh_token}, format='json')
        assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_provider_complete_journey(self, api_client):
        """Test complete provider journey: register → login → profile → update → logout."""
        # Step 1: Register
        register_url = reverse('user_register')
        register_data = {
            'email': 'journey_provider@test.com',
            'password': 'ProviderPass123!',
            'confirm_password': 'ProviderPass123!',
            'user_type': 'provider',
            'phone_number': '+1234567891'
        }
        register_response = api_client.post(register_url, register_data, format='json')
        assert register_response.status_code == status.HTTP_201_CREATED
        
        # Step 2: Login
        login_url = reverse('user_login')
        login_response = api_client.post(login_url, {
            'email': 'journey_provider@test.com',
            'password': 'ProviderPass123!'
        }, format='json')
        assert login_response.status_code == status.HTTP_200_OK
        access_token = login_response.data['access']
        refresh_token = login_response.data['refresh']
        
        # Step 3: Access profile
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        profile_url = reverse('user_profile')
        profile_response = api_client.get(profile_url)
        assert profile_response.status_code == status.HTTP_200_OK
        assert profile_response.data['user_type'] == 'provider'
        assert profile_response.data['is_verified'] == False  # Not verified yet
        
        # Step 4: Update profile
        update_response = api_client.patch(profile_url, {
            'phone_number': '+9876543211'
        }, format='json')
        assert update_response.status_code == status.HTTP_200_OK
        
        # Step 5: Logout
        api_client.credentials()
        logout_url = reverse('user_logout')
        logout_response = api_client.post(logout_url, {'refresh': refresh_token}, format='json')
        assert logout_response.status_code == status.HTTP_200_OK


# ============================================================================
# 2. AUTHENTICATION FLOW TESTS
# ============================================================================

@pytest.mark.django_db
class TestAuthenticationFlows:
    """Test authentication flows with token usage and refresh."""
    
    def test_register_login_access_refresh_logout_flow(self, api_client):
        """Test: register → login → use access token → refresh token → use new access → logout."""
        # Register
        register_url = reverse('user_register')
        api_client.post(register_url, {
            'email': 'flow_test@test.com',
            'password': 'FlowPass123!',
            'confirm_password': 'FlowPass123!',
            'user_type': 'student'
        }, format='json')
        
        # Login
        login_url = reverse('user_login')
        login_response = api_client.post(login_url, {
            'email': 'flow_test@test.com',
            'password': 'FlowPass123!'
        }, format='json')
        original_access = login_response.data['access']
        original_refresh = login_response.data['refresh']
        
        # Use access token
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {original_access}')
        profile_url = reverse('user_profile')
        profile_response = api_client.get(profile_url)
        assert profile_response.status_code == status.HTTP_200_OK
        
        # Refresh token
        api_client.credentials()
        refresh_url = reverse('token_refresh')
        refresh_response = api_client.post(refresh_url, {
            'refresh': original_refresh
        }, format='json')
        assert refresh_response.status_code == status.HTTP_200_OK
        new_access = refresh_response.data['access']
        new_refresh = refresh_response.data.get('refresh', original_refresh)
        
        # Use new access token
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {new_access}')
        profile_response2 = api_client.get(profile_url)
        assert profile_response2.status_code == status.HTTP_200_OK
        
        # Logout with new refresh token
        api_client.credentials()
        logout_url = reverse('user_logout')
        logout_response = api_client.post(logout_url, {'refresh': new_refresh}, format='json')
        assert logout_response.status_code == status.HTTP_200_OK
        
        # Verify cannot refresh after logout
        refresh_response2 = api_client.post(refresh_url, {'refresh': new_refresh}, format='json')
        assert refresh_response2.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_login_access_logout_access_denied_flow(self, api_client):
        """Test: login → access protected endpoints → logout → verify access denied."""
        # Create user
        user = User.objects.create_user(
            username='access_test',
            email='access_test@test.com',
            password='AccessPass123!',
            user_type='student'
        )
        
        # Login
        login_url = reverse('user_login')
        login_response = api_client.post(login_url, {
            'email': 'access_test@test.com',
            'password': 'AccessPass123!'
        }, format='json')
        access_token = login_response.data['access']
        refresh_token = login_response.data['refresh']
        
        # Access protected endpoint
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        profile_url = reverse('user_profile')
        profile_response = api_client.get(profile_url)
        assert profile_response.status_code == status.HTTP_200_OK
        
        # Logout
        api_client.credentials()
        logout_url = reverse('user_logout')
        api_client.post(logout_url, {'refresh': refresh_token}, format='json')
        
        # Try to get new access token (should fail)
        refresh_url = reverse('token_refresh')
        refresh_response = api_client.post(refresh_url, {'refresh': refresh_token}, format='json')
        assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Old access token still works until expiry
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        profile_response2 = api_client.get(profile_url)
        assert profile_response2.status_code == status.HTTP_200_OK


# ============================================================================
# 3. ADMIN WORKFLOW TESTS
# ============================================================================

@pytest.mark.django_db
class TestAdminWorkflows:
    """Test admin workflows including provider verification."""
    
    def test_admin_login_verify_provider_logout(self, api_client):
        """Test: admin login → verify provider → logout."""
        # Create admin user
        admin = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='AdminPass123!',
            user_type='student',
            is_staff=True
        )
        
        # Create provider to verify
        provider = User.objects.create_user(
            username='provider_verify',
            email='provider_verify@test.com',
            password='ProviderPass123!',
            user_type='provider',
            is_verified=False
        )
        
        # Admin login
        login_url = reverse('user_login')
        login_response = api_client.post(login_url, {
            'email': 'admin@test.com',
            'password': 'AdminPass123!'
        }, format='json')
        assert login_response.status_code == status.HTTP_200_OK
        access_token = login_response.data['access']
        refresh_token = login_response.data['refresh']
        
        # Verify provider
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        verify_url = reverse('verify_provider')
        verify_response = api_client.post(verify_url, {
            'provider_id': provider.id
        }, format='json')
        assert verify_response.status_code == status.HTTP_200_OK
        assert verify_response.data['is_verified'] == True
        
        # Verify provider is actually verified in database
        provider.refresh_from_db()
        assert provider.is_verified == True
        
        # Admin logout
        api_client.credentials()
        logout_url = reverse('user_logout')
        logout_response = api_client.post(logout_url, {'refresh': refresh_token}, format='json')
        assert logout_response.status_code == status.HTTP_200_OK


# ============================================================================
# 4. SECURITY SCENARIO TESTS
# ============================================================================

@pytest.mark.django_db
class TestSecurityScenarios:
    """Test security scenarios and edge cases."""
    
    def test_profile_access_after_logout_denied(self, api_client):
        """Attempt to access profile after logout should fail for new tokens."""
        # Create user and login
        user = User.objects.create_user(
            username='security_test',
            email='security@test.com',
            password='SecurePass123!',
            user_type='student'
        )
        
        login_url = reverse('user_login')
        login_response = api_client.post(login_url, {
            'email': 'security@test.com',
            'password': 'SecurePass123!'
        }, format='json')
        access_token = login_response.data['access']
        refresh_token = login_response.data['refresh']
        
        # Logout
        logout_url = reverse('user_logout')
        api_client.post(logout_url, {'refresh': refresh_token}, format='json')
        
        # Try to get new access token (should fail)
        refresh_url = reverse('token_refresh')
        refresh_response = api_client.post(refresh_url, {'refresh': refresh_token}, format='json')
        assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'access' not in refresh_response.data
    
    def test_blacklisted_tokens_cannot_be_reused(self, api_client):
        """Blacklisted refresh tokens cannot be used for new access tokens."""
        user = User.objects.create_user(
            username='blacklist_test',
            email='blacklist@test.com',
            password='BlacklistPass123!',
            user_type='student'
        )
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        refresh_token = str(refresh)
        
        # Blacklist token
        logout_url = reverse('user_logout')
        api_client.post(logout_url, {'refresh': refresh_token}, format='json')
        
        # Try to use blacklisted token
        refresh_url = reverse('token_refresh')
        refresh_response = api_client.post(refresh_url, {'refresh': refresh_token}, format='json')
        assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Try multiple times (should consistently fail)
        for _ in range(3):
            response = api_client.post(refresh_url, {'refresh': refresh_token}, format='json')
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_concurrent_user_sessions_independent(self, api_client):
        """Concurrent user sessions should work independently."""
        # Create two users
        user1 = User.objects.create_user(
            username='concurrent1',
            email='concurrent1@test.com',
            password='Pass123!',
            user_type='student'
        )
        user2 = User.objects.create_user(
            username='concurrent2',
            email='concurrent2@test.com',
            password='Pass123!',
            user_type='student'
        )
        
        # Login both users
        login_url = reverse('user_login')
        
        login1 = api_client.post(login_url, {
            'email': 'concurrent1@test.com',
            'password': 'Pass123!'
        }, format='json')
        tokens1 = {'access': login1.data['access'], 'refresh': login1.data['refresh']}
        
        login2 = api_client.post(login_url, {
            'email': 'concurrent2@test.com',
            'password': 'Pass123!'
        }, format='json')
        tokens2 = {'access': login2.data['access'], 'refresh': login2.data['refresh']}
        
        # Logout user1
        logout_url = reverse('user_logout')
        api_client.post(logout_url, {'refresh': tokens1['refresh']}, format='json')
        
        # User1's tokens should be invalid for refresh
        refresh_url = reverse('token_refresh')
        refresh1 = api_client.post(refresh_url, {'refresh': tokens1['refresh']}, format='json')
        assert refresh1.status_code == status.HTTP_401_UNAUTHORIZED
        
        # User2's tokens should still work
        refresh2 = api_client.post(refresh_url, {'refresh': tokens2['refresh']}, format='json')
        assert refresh2.status_code == status.HTTP_200_OK
        assert 'access' in refresh2.data
    
    def test_rapid_successive_requests_no_race_conditions(self, api_client):
        """Rapid successive requests should not cause race conditions."""
        user = User.objects.create_user(
            username='rapid_test',
            email='rapid@test.com',
            password='RapidPass123!',
            user_type='student'
        )
        
        # Login
        login_url = reverse('user_login')
        login_response = api_client.post(login_url, {
            'email': 'rapid@test.com',
            'password': 'RapidPass123!'
        }, format='json')
        access_token = login_response.data['access']
        
        # Make rapid successive profile requests
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        profile_url = reverse('user_profile')
        
        responses = []
        for _ in range(10):
            response = api_client.get(profile_url)
            responses.append(response)
        
        # All should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK
            assert response.data['email'] == 'rapid@test.com'


# ============================================================================
# 5. CROSS-ENDPOINT VERIFICATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestCrossEndpointVerification:
    """Test that all endpoints work together correctly."""
    
    def test_registration_creates_users_that_can_login(self, api_client):
        """Registration should create users that can successfully log in."""
        # Register
        register_url = reverse('user_register')
        register_response = api_client.post(register_url, {
            'email': 'cross_test@test.com',
            'password': 'CrossPass123!',
            'confirm_password': 'CrossPass123!',
            'user_type': 'student'
        }, format='json')
        assert register_response.status_code == status.HTTP_201_CREATED
        
        # Login
        login_url = reverse('user_login')
        login_response = api_client.post(login_url, {
            'email': 'cross_test@test.com',
            'password': 'CrossPass123!'
        }, format='json')
        assert login_response.status_code == status.HTTP_200_OK
        assert 'access' in login_response.data
    
    def test_login_tokens_work_across_all_protected_endpoints(self, api_client):
        """Login tokens should work across all protected endpoints."""
        # Create user
        user = User.objects.create_user(
            username='token_test',
            email='token_test@test.com',
            password='TokenPass123!',
            user_type='student'
        )
        
        # Login
        login_url = reverse('user_login')
        login_response = api_client.post(login_url, {
            'email': 'token_test@test.com',
            'password': 'TokenPass123!'
        }, format='json')
        access_token = login_response.data['access']
        
        # Test profile endpoint
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        profile_url = reverse('user_profile')
        profile_response = api_client.get(profile_url)
        assert profile_response.status_code == status.HTTP_200_OK
        
        # Test profile update endpoint
        update_response = api_client.patch(profile_url, {
            'phone_number': '+1234567890'
        }, format='json')
        assert update_response.status_code == status.HTTP_200_OK
    
    def test_profile_updates_reflect_in_subsequent_retrievals(self, api_client):
        """Profile updates should be reflected in subsequent profile retrievals."""
        # Create user and login
        user = User.objects.create_user(
            username='update_test',
            email='update_test@test.com',
            password='UpdatePass123!',
            user_type='student',
            phone_number='+1234567890'
        )
        
        login_url = reverse('user_login')
        login_response = api_client.post(login_url, {
            'email': 'update_test@test.com',
            'password': 'UpdatePass123!'
        }, format='json')
        access_token = login_response.data['access']
        
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        profile_url = reverse('user_profile')
        
        # Update profile
        api_client.patch(profile_url, {
            'phone_number': '+9876543210',
            'university_name': 'New University'
        }, format='json')
        
        # Retrieve profile
        profile_response = api_client.get(profile_url)
        assert profile_response.status_code == status.HTTP_200_OK
        assert profile_response.data['phone_number'] == '+9876543210'
        assert profile_response.data['university_name'] == 'New University'
    
    def test_provider_verification_changes_user_status(self, api_client):
        """Provider verification should correctly change user verification status."""
        # Create admin
        admin = User.objects.create_user(
            username='admin_verify',
            email='admin_verify@test.com',
            password='AdminPass123!',
            user_type='student',
            is_staff=True
        )
        
        # Create provider
        provider = User.objects.create_user(
            username='provider_status',
            email='provider_status@test.com',
            password='ProviderPass123!',
            user_type='provider',
            is_verified=False
        )
        
        # Admin login
        login_url = reverse('user_login')
        login_response = api_client.post(login_url, {
            'email': 'admin_verify@test.com',
            'password': 'AdminPass123!'
        }, format='json')
        access_token = login_response.data['access']
        
        # Verify provider
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        verify_url = reverse('verify_provider')
        verify_response = api_client.post(verify_url, {
            'provider_id': provider.id
        }, format='json')
        assert verify_response.status_code == status.HTTP_200_OK
        
        # Check provider status in database
        provider.refresh_from_db()
        assert provider.is_verified == True
        
        # Provider login and check profile
        api_client.credentials()
        provider_login = api_client.post(login_url, {
            'email': 'provider_status@test.com',
            'password': 'ProviderPass123!'
        }, format='json')
        provider_access = provider_login.data['access']
        
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {provider_access}')
        profile_url = reverse('user_profile')
        profile_response = api_client.get(profile_url)
        assert profile_response.status_code == status.HTTP_200_OK
        assert profile_response.data['is_verified'] == True
    
    def test_logout_invalidates_tokens_across_all_endpoints(self, api_client):
        """Logout should properly invalidate tokens for all endpoints."""
        # Create user and login
        user = User.objects.create_user(
            username='logout_all',
            email='logout_all@test.com',
            password='LogoutPass123!',
            user_type='student'
        )
        
        login_url = reverse('user_login')
        login_response = api_client.post(login_url, {
            'email': 'logout_all@test.com',
            'password': 'LogoutPass123!'
        }, format='json')
        refresh_token = login_response.data['refresh']
        
        # Logout
        logout_url = reverse('user_logout')
        api_client.post(logout_url, {'refresh': refresh_token}, format='json')
        
        # Try to refresh (should fail)
        refresh_url = reverse('token_refresh')
        refresh_response = api_client.post(refresh_url, {'refresh': refresh_token}, format='json')
        assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Try to blacklist again (should handle gracefully)
        logout_response2 = api_client.post(logout_url, {'refresh': refresh_token}, format='json')
        assert logout_response2.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED
        ]


# ============================================================================
# 6. TOKEN EXPIRATION INTEGRATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestTokenExpirationIntegration:
    """Test token expiration is properly enforced across all endpoints."""
    
    def test_expired_access_token_rejected_by_protected_endpoints(self, api_client):
        """Expired access tokens should be rejected by protected endpoints."""
        from datetime import timedelta
        
        user = User.objects.create_user(
            username='expired_test',
            email='expired@test.com',
            password='ExpiredPass123!',
            user_type='student'
        )
        
        # Create expired access token
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token
        access.set_exp(lifetime=-timedelta(minutes=1))
        expired_access = str(access)
        
        # Try to access profile with expired token
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {expired_access}')
        profile_url = reverse('user_profile')
        profile_response = api_client.get(profile_url)
        
        assert profile_response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_logging_out_multiple_times_handled_gracefully(self, api_client):
        """Logging out multiple times should be handled gracefully."""
        user = User.objects.create_user(
            username='multi_logout',
            email='multi_logout@test.com',
            password='MultiPass123!',
            user_type='student'
        )
        
        # Generate multiple tokens
        tokens = []
        for i in range(3):
            refresh = RefreshToken.for_user(user)
            tokens.append(str(refresh))
        
        # Logout all tokens
        logout_url = reverse('user_logout')
        for token in tokens:
            response = api_client.post(logout_url, {'refresh': token}, format='json')
            assert response.status_code == status.HTTP_200_OK
        
        # Try to use any token (all should fail)
        refresh_url = reverse('token_refresh')
        for token in tokens:
            response = api_client.post(refresh_url, {'refresh': token}, format='json')
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
