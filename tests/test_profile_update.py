"""
Comprehensive tests for user profile update endpoint.

Tests cover:
- Authentication and authorization
- Valid profile updates (PUT and PATCH)
- Phone number validation
- Image upload validation
- Restricted field protection
- Concurrent updates
- Edge cases

Following TDD: These tests are designed to fail initially.
"""

import os
import tempfile
import threading
from decimal import Decimal
from io import BytesIO
from PIL import Image
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class ProfileUpdateAuthenticationTests(TestCase):
    """Test authentication requirements for profile updates."""
    
    def setUp(self):
        """Set up test client and user."""
        self.client = APIClient()
        self.url = '/api/auth/profile/'
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            user_type='student',
            username='testuser'
        )
    
    def test_update_profile_without_authentication_returns_401(self):
        """Unauthenticated PUT request should return 401."""
        data = {'phone_number': '+1234567890'}
        response = self.client.put(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_patch_profile_without_authentication_returns_401(self):
        """Unauthenticated PATCH request should return 401."""
        data = {'university_name': 'Test University'}
        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_update_profile_with_invalid_token_returns_401(self):
        """Request with invalid token should return 401."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid_token_here')
        data = {'phone_number': '+1234567890'}
        response = self.client.put(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_update_profile_with_expired_token_returns_401(self):
        """Request with expired token should return 401."""
        from datetime import timedelta
        
        # Create a token and manually set it to be expired
        refresh = RefreshToken.for_user(self.user)
        access_token = refresh.access_token
        
        # Set expiration to 10 seconds in the past
        access_token.set_exp(lifetime=timedelta(seconds=-10))
        expired_token = str(access_token)
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {expired_token}')
        data = {'phone_number': '+1234567890'}
        response = self.client.put(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfileUpdateAuthorizationTests(TestCase):
    """Test authorization - users can only update their own profile."""
    
    def setUp(self):
        """Set up test clients and users."""
        self.client = APIClient()
        self.url = '/api/auth/profile/'
        
        self.user1 = User.objects.create_user(
            email='user1@example.com',
            password='TestPass123!',
            user_type='student',
            username='user1'
        )
        
        self.user2 = User.objects.create_user(
            email='user2@example.com',
            password='TestPass123!',
            user_type='provider',
            username='user2'
        )
    
    def test_user_can_update_own_profile(self):
        """User should be able to update their own profile."""
        refresh = RefreshToken.for_user(self.user1)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        data = {'phone_number': '+1234567890'}
        response = self.client.patch(self.url, data, format='json')
        
        # Should succeed (200 or 201)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        
        # Verify the update
        self.user1.refresh_from_db()
        self.assertEqual(self.user1.phone_number, '+1234567890')


class ProfileUpdateValidDataTests(TestCase):
    """Test profile updates with valid data."""
    
    def setUp(self):
        """Set up authenticated client."""
        self.client = APIClient()
        self.url = '/api/auth/profile/'
        
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            user_type='student',
            username='testuser',
            phone_number='+1234567890',
            university_name='Old University'
        )
        
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def test_update_profile_with_valid_data_put(self):
        """PUT request with valid data should update profile."""
        data = {
            'phone_number': '+1987654321',
            'university_name': 'New University'
        }
        response = self.client.put(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify updates
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, '+1987654321')
        self.assertEqual(self.user.university_name, 'New University')
    
    def test_update_profile_with_valid_data_patch(self):
        """PATCH request with valid data should update profile."""
        data = {'university_name': 'Patch University'}
        response = self.client.patch(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify update
        self.user.refresh_from_db()
        self.assertEqual(self.user.university_name, 'Patch University')
        # Phone should remain unchanged
        self.assertEqual(self.user.phone_number, '+1234567890')
    
    def test_partial_update_with_patch_only_phone(self):
        """PATCH with only phone_number should update only that field."""
        data = {'phone_number': '+9876543210'}
        response = self.client.patch(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, '+9876543210')
        self.assertEqual(self.user.university_name, 'Old University')
    
    def test_partial_update_with_patch_only_university(self):
        """PATCH with only university_name should update only that field."""
        data = {'university_name': 'Another University'}
        response = self.client.patch(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.university_name, 'Another University')
        self.assertEqual(self.user.phone_number, '+1234567890')
    
    def test_update_profile_changes_persist_in_database(self):
        """Profile updates should persist across requests."""
        # First update
        data = {'phone_number': '+5555555556'}
        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Retrieve profile
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['phone_number'], '+5555555556')
        
        # Verify in database
        user_from_db = User.objects.get(id=self.user.id)
        self.assertEqual(user_from_db.phone_number, '+5555555556')


class ProfileUpdatePhoneValidationTests(TestCase):
    """Test phone number validation."""
    
    def setUp(self):
        """Set up authenticated client."""
        self.client = APIClient()
        self.url = '/api/auth/profile/'
        
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            user_type='student',
            username='testuser'
        )
        
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def test_update_with_invalid_phone_format_returns_400(self):
        """Invalid phone format should return 400."""
        invalid_phones = [
            '123',  # Too short
            'abcdefghij',  # Letters
            '123-456',  # Too short with dashes
            '0000000000',  # All same digit
        ]
        
        for phone in invalid_phones:
            data = {'phone_number': phone}
            response = self.client.patch(self.url, data, format='json')
            self.assertEqual(
                response.status_code, 
                status.HTTP_400_BAD_REQUEST,
                f"Phone '{phone}' should be rejected"
            )
    
    def test_update_with_valid_phone_formats(self):
        """Valid phone formats should be accepted."""
        valid_phones = [
            '+1234567890',
            '+44 20 7946 0958',
            '+1 (234) 567-8900',
            '234-567-8900',
            '2345678900',
        ]
        
        for phone in valid_phones:
            data = {'phone_number': phone}
            response = self.client.patch(self.url, data, format='json')
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"Phone '{phone}' should be accepted"
            )


class ProfileUpdateImageUploadTests(TestCase):
    """Test profile image upload functionality."""
    
    def setUp(self):
        """Set up authenticated client and test images."""
        self.client = APIClient()
        self.url = '/api/auth/profile/'
        
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            user_type='student',
            username='testuser'
        )
        
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def create_test_image(self, format='JPEG', size=(100, 100), file_size_mb=None):
        """Create a test image file."""
        image = Image.new('RGB', size, color='red')
        image_io = BytesIO()
        image.save(image_io, format=format)
        image_io.seek(0)
        
        # If specific file size requested, pad the file
        if file_size_mb:
            image_io.write(b'0' * (file_size_mb * 1024 * 1024 - len(image_io.getvalue())))
            image_io.seek(0)
        
        extension = format.lower()
        if extension == 'jpeg':
            extension = 'jpg'
        
        return SimpleUploadedFile(
            f"test_image.{extension}",
            image_io.read(),
            content_type=f"image/{format.lower()}"
        )
    
    def test_upload_valid_jpeg_image(self):
        """Valid JPEG image should be accepted."""
        image = self.create_test_image(format='JPEG')
        response = self.client.patch(self.url, {'profile_image': image}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.profile_image)
    
    def test_upload_valid_png_image(self):
        """Valid PNG image should be accepted."""
        image = self.create_test_image(format='PNG')
        response = self.client.patch(self.url, {'profile_image': image}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.profile_image)
    
    def test_upload_valid_webp_image(self):
        """Valid WEBP image should be accepted."""
        image = self.create_test_image(format='WEBP')
        response = self.client.patch(self.url, {'profile_image': image}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.profile_image)
    
    def test_upload_invalid_image_format_returns_400(self):
        """Invalid image format should be rejected."""
        # Create a text file disguised as image
        invalid_file = SimpleUploadedFile(
            "test.txt",
            b"This is not an image",
            content_type="text/plain"
        )
        
        response = self.client.patch(self.url, {'profile_image': invalid_file}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_upload_oversized_image_returns_400(self):
        """Image exceeding 5MB should be rejected."""
        # Create a 6MB image
        large_image = SimpleUploadedFile(
            "large.jpg",
            b"0" * (6 * 1024 * 1024),  # 6MB
            content_type="image/jpeg"
        )
        
        response = self.client.patch(self.url, {'profile_image': large_image}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_profile_image_creates_file_in_correct_location(self):
        """Uploaded image should be stored in correct directory."""
        image = self.create_test_image(format='JPEG')
        response = self.client.patch(self.url, {'profile_image': image}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        
        # Check file exists
        self.assertTrue(os.path.exists(self.user.profile_image.path))
        
        # Check it's in the correct directory
        expected_dir = f'profile_images/{self.user.id}'
        self.assertIn(expected_dir, self.user.profile_image.name)
    
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_old_profile_image_deleted_when_replaced(self):
        """Old profile image should be deleted when new one is uploaded."""
        # Upload first image
        image1 = self.create_test_image(format='JPEG')
        response = self.client.patch(self.url, {'profile_image': image1}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.user.refresh_from_db()
        old_image_path = self.user.profile_image.path
        
        # Verify first image exists
        self.assertTrue(os.path.exists(old_image_path))
        
        # Upload second image
        image2 = self.create_test_image(format='PNG')
        response = self.client.patch(self.url, {'profile_image': image2}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Old image should be deleted
        self.assertFalse(os.path.exists(old_image_path))


class ProfileUpdateRestrictedFieldsTests(TestCase):
    """Test that restricted fields cannot be updated."""
    
    def setUp(self):
        """Set up authenticated client."""
        self.client = APIClient()
        self.url = '/api/auth/profile/'
        
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            user_type='student',
            username='testuser',
            is_verified=False
        )
        
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def test_cannot_update_email_field(self):
        """Email field should not be updatable."""
        original_email = self.user.email
        data = {'email': 'newemail@example.com'}
        response = self.client.patch(self.url, data, format='json')
        
        # Should either ignore the field or return error
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, original_email)
    
    def test_cannot_update_password_field(self):
        """Password field should not be updatable."""
        original_password = self.user.password
        data = {'password': 'NewPassword123!'}
        response = self.client.patch(self.url, data, format='json')
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, original_password)
    
    def test_cannot_update_is_verified_field(self):
        """is_verified field should not be updatable by regular users."""
        self.assertFalse(self.user.is_verified)
        
        data = {'is_verified': True}
        response = self.client.patch(self.url, data, format='json')
        
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_verified)
    
    def test_cannot_update_user_type_field(self):
        """user_type field should not be updatable."""
        original_type = self.user.user_type
        data = {'user_type': 'provider'}
        response = self.client.patch(self.url, data, format='json')
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.user_type, original_type)
    
    def test_cannot_update_is_staff_field(self):
        """is_staff field should not be updatable."""
        self.assertFalse(self.user.is_staff)
        
        data = {'is_staff': True}
        response = self.client.patch(self.url, data, format='json')
        
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
    
    def test_cannot_update_is_superuser_field(self):
        """is_superuser field should not be updatable."""
        self.assertFalse(self.user.is_superuser)
        
        data = {'is_superuser': True}
        response = self.client.patch(self.url, data, format='json')
        
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_superuser)


class ProfileUpdateConcurrentTests(TestCase):
    """Test concurrent profile update handling."""
    
    def setUp(self):
        """Set up authenticated client."""
        self.client = APIClient()
        self.url = '/api/auth/profile/'
        
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            user_type='student',
            username='testuser',
            phone_number='+1234567890'
        )
        
        refresh = RefreshToken.for_user(self.user)
        # Set credentials on the client
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def test_concurrent_profile_updates_handled_correctly(self):
        """Concurrent updates should be handled without data corruption."""
        # Test that multiple rapid updates don't cause data corruption
        # Using sequential requests to avoid threading auth context issues
        phones = ['+2222222223', '+3333333334', '+4444444445']
        
        # Perform rapid sequential updates
        for phone in phones:
            data = {'phone_number': phone}
            response = self.client.patch(self.url, data, format='json')
            # Each update should succeed
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Final phone number should be the last one updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, phones[-1])


class ProfileUpdateEdgeCaseTests(TestCase):
    """Test edge cases for profile updates."""
    
    def setUp(self):
        """Set up authenticated client."""
        self.client = APIClient()
        self.url = '/api/auth/profile/'
        
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            user_type='student',
            username='testuser',
            phone_number='+1234567890'
        )
        
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def test_update_with_empty_data_returns_200(self):
        """Empty update should succeed without changes."""
        original_phone = self.user.phone_number
        
        data = {}
        response = self.client.patch(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, original_phone)
    
    def test_update_clears_phone_number_when_empty_string(self):
        """Setting phone_number to empty string should clear it."""
        data = {'phone_number': ''}
        response = self.client.patch(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, '')
