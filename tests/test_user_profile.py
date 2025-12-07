"""
Comprehensive test suite for user profile retrieval endpoint.

Tests are designed to fail initially (TDD approach) and define security requirements.
DO NOT MODIFY THESE TESTS - fix the implementation to make them pass.

Test Coverage:
- Authentication enforcement (401 for missing/invalid/expired tokens)
- Authorization (users can only access their own profile)
- Data integrity (profile matches database)
- Security (sensitive data excluded)
- Field validation (all expected fields present)
- Profile image URL generation
- Token expiration handling
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import timedelta
from unittest.mock import patch
import time

User = get_user_model()


@pytest.fixture
def api_client():
    """Fixture for API client."""
    return APIClient()


@pytest.fixture
def student_user(db):
    """Fixture for creating a student user."""
    user = User.objects.create_user(
        username='student_test',
        email='student@example.com',
        password='SecurePass123!',
        user_type='student',
        phone_number='+1234567890',
        university_name='Test University',
        is_verified=False
    )
    return user


@pytest.fixture
def provider_user(db):
    """Fixture for creating a provider user."""
    user = User.objects.create_user(
        username='provider_test',
        email='provider@example.com',
        password='SecurePass456!',
        user_type='provider',
        phone_number='+9876543210',
        university_name='Provider University',
        is_verified=True
    )
    return user


@pytest.fixture
def student_access_token(student_user):
    """Fixture for generating access token for student user."""
    refresh = RefreshToken.for_user(student_user)
    return str(refresh.access_token)


@pytest.fixture
def provider_access_token(provider_user):
    """Fixture for generating access token for provider user."""
    refresh = RefreshToken.for_user(provider_user)
    return str(refresh.access_token)


@pytest.mark.django_db
class TestUserProfileEndpoint:
    """Test suite for user profile retrieval endpoint."""
    
    def test_get_profile_authenticated(self, api_client, student_user, student_access_token):
        """
        Test that authenticated user can retrieve their own profile.
        
        Expected: 200 OK with profile data
        """
        url = reverse('user_profile')
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {student_access_token}')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'id' in response.data
        assert 'email' in response.data
        assert response.data['email'] == student_user.email
    
    def test_get_profile_no_token(self, api_client):
        """
        Test that request without authentication token returns 401.
        
        Security requirement: Endpoint must be protected.
        Expected: 401 Unauthorized
        """
        url = reverse('user_profile')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'detail' in response.data or 'error' in response.data
    
    def test_get_profile_invalid_token(self, api_client):
        """
        Test that request with invalid token returns 401.
        
        Security requirement: Token validation must be enforced.
        Expected: 401 Unauthorized
        """
        url = reverse('user_profile')
        api_client.credentials(HTTP_AUTHORIZATION='Bearer invalid_token_string_12345')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_profile_malformed_token(self, api_client):
        """
        Test that request with malformed token returns 401.
        
        Security requirement: Token format validation.
        Expected: 401 Unauthorized
        """
        url = reverse('user_profile')
        api_client.credentials(HTTP_AUTHORIZATION='Bearer not.a.valid.jwt.token')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_profile_expired_token(self, api_client, student_user):
        """
        Test that request with expired token returns 401.
        
        Security requirement: Token expiration must be enforced.
        Expected: 401 Unauthorized
        """
        url = reverse('user_profile')
        
        # Create a token that's already expired
        refresh = RefreshToken.for_user(student_user)
        access_token = refresh.access_token
        
        # Set expiration to past time
        access_token.set_exp(lifetime=timedelta(seconds=-10))
        expired_token = str(access_token)
        
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {expired_token}')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'expired' in str(response.data).lower() or 'invalid' in str(response.data).lower()
    
    def test_profile_data_matches_database(self, api_client, student_user, student_access_token):
        """
        Test that profile data matches database records.
        
        Data integrity requirement: Profile must reflect actual user data.
        Expected: All fields match database values
        """
        url = reverse('user_profile')
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {student_access_token}')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == student_user.id
        assert response.data['email'] == student_user.email
        assert response.data['phone_number'] == student_user.phone_number
        assert response.data['university_name'] == student_user.university_name
        assert response.data['user_type'] == student_user.user_type
        assert response.data['is_verified'] == student_user.is_verified
    
    def test_profile_includes_expected_fields(self, api_client, student_user, student_access_token):
        """
        Test that profile includes all expected fields.
        
        API contract requirement: All specified fields must be present.
        Expected fields: id, email, phone_number, university_name, user_type, 
                        is_verified, profile_image_url, created_at
        """
        url = reverse('user_profile')
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {student_access_token}')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        expected_fields = [
            'id',
            'email',
            'phone_number',
            'university_name',
            'user_type',
            'is_verified',
            'profile_image_url',
            'created_at'
        ]
        
        for field in expected_fields:
            assert field in response.data, f"Missing required field: {field}"
    
    def test_profile_excludes_sensitive_data(self, api_client, student_user, student_access_token):
        """
        Test that profile excludes sensitive data like password hash.
        
        Security requirement: Sensitive fields must never be exposed.
        Expected: password, is_staff, is_superuser, groups, user_permissions excluded
        """
        url = reverse('user_profile')
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {student_access_token}')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        sensitive_fields = [
            'password',
            'is_staff',
            'is_superuser',
            'groups',
            'user_permissions'
        ]
        
        for field in sensitive_fields:
            assert field not in response.data, f"Sensitive field exposed: {field}"
    
    def test_profile_image_url_null_when_no_image(self, api_client, student_user, student_access_token):
        """
        Test that profile_image_url is null when no image is uploaded.
        
        Expected: profile_image_url should be null or empty string
        """
        url = reverse('user_profile')
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {student_access_token}')
        
        # Ensure user has no profile image
        student_user.profile_image = None
        student_user.save()
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['profile_image_url'] is None or response.data['profile_image_url'] == ''
    
    def test_profile_image_url_formatting_with_image(self, api_client, student_user, student_access_token):
        """
        Test that profile_image_url is correctly formatted when image exists.
        
        Expected: Full URL or proper relative path to image
        """
        url = reverse('user_profile')
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {student_access_token}')
        
        # Mock profile image
        from django.core.files.uploadedfile import SimpleUploadedFile
        image_content = b'fake_image_content'
        student_user.profile_image = SimpleUploadedFile(
            "test_profile.jpg",
            image_content,
            content_type="image/jpeg"
        )
        student_user.save()
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['profile_image_url'] is not None
        assert 'profile_images' in response.data['profile_image_url']
        # Should contain either full URL or path to media file
        assert (
            response.data['profile_image_url'].startswith('http') or 
            response.data['profile_image_url'].startswith('/media/')
        )
    
    def test_different_users_get_different_profiles(self, api_client, student_user, provider_user, 
                                                     student_access_token, provider_access_token):
        """
        Test that different authenticated users get their own profiles.
        
        Authorization requirement: Users must only see their own data.
        Expected: Each user gets their own profile data
        """
        url = reverse('user_profile')
        
        # Student gets their profile
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {student_access_token}')
        student_response = api_client.get(url)
        
        # Provider gets their profile
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {provider_access_token}')
        provider_response = api_client.get(url)
        
        assert student_response.status_code == status.HTTP_200_OK
        assert provider_response.status_code == status.HTTP_200_OK
        
        # Verify they got different profiles
        assert student_response.data['id'] == student_user.id
        assert provider_response.data['id'] == provider_user.id
        assert student_response.data['email'] == student_user.email
        assert provider_response.data['email'] == provider_user.email
        assert student_response.data['user_type'] == 'student'
        assert provider_response.data['user_type'] == 'provider'
    
    def test_profile_after_token_expiration_simulation(self, api_client, student_user):
        """
        Test accessing profile after token expiration.
        
        Security requirement: Expired tokens must be rejected.
        Expected: 401 Unauthorized after expiration
        """
        url = reverse('user_profile')
        
        # Create token with very short lifetime
        from django.conf import settings
        original_lifetime = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']
        
        # Create an expired token by manipulating the exp claim
        refresh = RefreshToken.for_user(student_user)
        access_token = refresh.access_token
        
        # Manually set expiration to 1 second ago
        access_token.set_exp(lifetime=timedelta(seconds=-1))
        expired_token = str(access_token)
        
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {expired_token}')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_profile_with_missing_bearer_prefix(self, api_client, student_access_token):
        """
        Test that token without 'Bearer' prefix is rejected.
        
        Security requirement: Proper authorization header format.
        Expected: 401 Unauthorized
        """
        url = reverse('user_profile')
        # Send token without 'Bearer' prefix
        api_client.credentials(HTTP_AUTHORIZATION=student_access_token)
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_profile_with_wrong_auth_scheme(self, api_client, student_access_token):
        """
        Test that token with wrong authentication scheme is rejected.
        
        Security requirement: Only 'Bearer' scheme should be accepted.
        Expected: 401 Unauthorized
        """
        url = reverse('user_profile')
        # Use 'Token' instead of 'Bearer'
        api_client.credentials(HTTP_AUTHORIZATION=f'Token {student_access_token}')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_profile_created_at_format(self, api_client, student_user, student_access_token):
        """
        Test that created_at field is properly formatted.
        
        Expected: ISO 8601 datetime format
        """
        url = reverse('user_profile')
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {student_access_token}')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'created_at' in response.data
        # Should be a valid datetime string
        assert isinstance(response.data['created_at'], str)
        # Should contain date and time components
        assert 'T' in response.data['created_at'] or ' ' in response.data['created_at']
    
    def test_profile_endpoint_only_allows_get(self, api_client, student_access_token):
        """
        Test that profile endpoint accepts GET, PUT, and PATCH requests.
        
        Expected: GET, PUT, PATCH should work (200 OK)
                  POST, DELETE should return 405 Method Not Allowed
        """
        url = reverse('user_profile')
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {student_access_token}')
        
        # Test GET - should work
        get_response = api_client.get(url)
        assert get_response.status_code == status.HTTP_200_OK
        
        # Test PUT - should work (profile update)
        put_response = api_client.put(url, {'phone_number': '+1234567890'}, format='json')
        assert put_response.status_code == status.HTTP_200_OK
        
        # Test PATCH - should work (profile update)
        patch_response = api_client.patch(url, {'university_name': 'Test University'}, format='json')
        assert patch_response.status_code == status.HTTP_200_OK
        
        # Test POST - should NOT be allowed
        post_response = api_client.post(url, {})
        assert post_response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        
        # Test DELETE - should NOT be allowed
        delete_response = api_client.delete(url)
        assert delete_response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    
    def test_profile_verification_status_accuracy(self, api_client, provider_user, provider_access_token):
        """
        Test that is_verified field accurately reflects user status.
        
        Expected: Provider user should have is_verified=True
        """
        url = reverse('user_profile')
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {provider_access_token}')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_verified'] == True
        assert response.data['user_type'] == 'provider'
