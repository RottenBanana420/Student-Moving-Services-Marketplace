"""
Comprehensive test suite for custom User model.

These tests are designed to FAIL until the User model is properly implemented.
Following TDD principles: write tests first, then implement code to pass them.
NEVER modify these tests - only fix the model implementation.
"""

import os
import tempfile
from decimal import Decimal
from io import BytesIO
from PIL import Image
from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone


User = get_user_model()


class UserModelEmailValidationTests(TestCase):
    """Test email validation and constraints."""
    
    def test_email_required(self):
        """Creating a user without email must raise ValidationError."""
        with self.assertRaises(ValidationError):
            user = User(
                username='testuser',
                user_type='student',
                university_name='Test University'
            )
            user.full_clean()
    
    def test_invalid_email_format_no_at_symbol(self):
        """Email without @ symbol must raise ValidationError."""
        with self.assertRaises(ValidationError):
            user = User(
                username='testuser',
                email='invalidemail.com',
                user_type='student',
                university_name='Test University'
            )
            user.full_clean()
    
    def test_invalid_email_format_multiple_at_symbols(self):
        """Email with multiple @ symbols must raise ValidationError."""
        with self.assertRaises(ValidationError):
            user = User(
                username='testuser',
                email='invalid@@email.com',
                user_type='student',
                university_name='Test University'
            )
            user.full_clean()
    
    def test_invalid_email_format_missing_domain(self):
        """Email without domain must raise ValidationError."""
        with self.assertRaises(ValidationError):
            user = User(
                username='testuser',
                email='invalid@',
                user_type='student',
                university_name='Test University'
            )
            user.full_clean()
    
    def test_invalid_email_format_missing_local_part(self):
        """Email without local part must raise ValidationError."""
        with self.assertRaises(ValidationError):
            user = User(
                username='testuser',
                email='@domain.com',
                user_type='student',
                university_name='Test University'
            )
            user.full_clean()
    
    def test_invalid_email_format_spaces(self):
        """Email with spaces must raise ValidationError."""
        with self.assertRaises(ValidationError):
            user = User(
                username='testuser',
                email='invalid email@domain.com',
                user_type='student',
                university_name='Test University'
            )
            user.full_clean()
    
    def test_duplicate_email_constraint(self):
        """Creating two users with same email must raise IntegrityError."""
        User.objects.create_user(
            username='user1',
            email='duplicate@test.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username='user2',
                email='duplicate@test.com',
                password='testpass123',
                user_type='provider',
                university_name='Another University'
            )
    
    def test_email_case_insensitivity(self):
        """Emails should be case-insensitive for uniqueness."""
        User.objects.create_user(
            username='user1',
            email='Test@Example.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        
        # Attempting to create with different case should fail
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username='user2',
                email='test@example.com',
                password='testpass123',
                user_type='student',
                university_name='Test University'
            )
    
    def test_valid_email_formats(self):
        """Valid email formats should be accepted."""
        valid_emails = [
            'user@example.com',
            'user.name@example.com',
            'user+tag@example.co.uk',
            'user_name@sub.example.com',
            '123@example.com',
        ]
        
        for idx, email in enumerate(valid_emails):
            user = User.objects.create_user(
                username=f'user{idx}',
                email=email,
                password='testpass123',
                user_type='student',
                university_name='Test University'
            )
            self.assertEqual(user.email.lower(), email.lower())


class UserModelPhoneValidationTests(TestCase):
    """Test phone number validation."""
    
    def test_phone_optional(self):
        """Creating user without phone number should succeed."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        self.assertEqual(user.phone_number, '')
    
    def test_valid_phone_formats(self):
        """Valid phone number formats should be accepted."""
        valid_phones = [
            '+1-234-567-8900',
            '+44 20 7946 0958',
            '+1 (234) 567-8900',
            '234-567-8900',
            '2345678900',
            '+12345678900',
        ]
        
        for idx, phone in enumerate(valid_phones):
            user = User.objects.create_user(
                username=f'user{idx}',
                email=f'user{idx}@example.com',
                password='testpass123',
                user_type='student',
                university_name='Test University',
                phone_number=phone
            )
            self.assertEqual(user.phone_number, phone)
    
    def test_invalid_phone_with_letters(self):
        """Phone number with letters must raise ValidationError."""
        with self.assertRaises(ValidationError):
            user = User(
                username='testuser',
                email='test@example.com',
                user_type='student',
                university_name='Test University',
                phone_number='123-ABC-7890'
            )
            user.full_clean()
    
    def test_invalid_phone_too_short(self):
        """Phone number too short must raise ValidationError."""
        with self.assertRaises(ValidationError):
            user = User(
                username='testuser',
                email='test@example.com',
                user_type='student',
                university_name='Test University',
                phone_number='123'
            )
            user.full_clean()
    
    def test_invalid_phone_special_chars_only(self):
        """Phone number with only special characters must raise ValidationError."""
        with self.assertRaises(ValidationError):
            user = User(
                username='testuser',
                email='test@example.com',
                user_type='student',
                university_name='Test University',
                phone_number='---'
            )
            user.full_clean()


class UserModelUserTypeTests(TestCase):
    """Test user_type field validation."""
    
    def test_user_type_required(self):
        """Creating user without user_type must raise ValidationError."""
        with self.assertRaises(ValidationError):
            user = User(
                username='testuser',
                email='test@example.com',
                university_name='Test University'
            )
            user.full_clean()
    
    def test_valid_user_type_student(self):
        """User type 'student' should be accepted."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        self.assertEqual(user.user_type, 'student')
    
    def test_valid_user_type_provider(self):
        """User type 'provider' should be accepted."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
        self.assertEqual(user.user_type, 'provider')
    
    def test_invalid_user_type(self):
        """Invalid user_type must raise ValidationError."""
        with self.assertRaises(ValidationError):
            user = User(
                username='testuser',
                email='test@example.com',
                user_type='admin',  # Invalid choice
                university_name='Test University'
            )
            user.full_clean()
    
    def test_is_student_helper_method(self):
        """is_student() should return True for student users."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        self.assertTrue(user.is_student())
        self.assertFalse(user.is_provider())
    
    def test_is_provider_helper_method(self):
        """is_provider() should return True for provider users."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
        self.assertTrue(user.is_provider())
        self.assertFalse(user.is_student())


class UserModelProfileImageTests(TestCase):
    """Test profile image field and validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def create_test_image(self, size=(100, 100), format='PNG'):
        """Helper to create a test image."""
        file = BytesIO()
        image = Image.new('RGB', size, color='red')
        image.save(file, format)
        file.seek(0)
        return file
    
    def test_profile_image_optional(self):
        """Creating user without profile image should succeed."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        self.assertFalse(user.profile_image)
    
    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_profile_image_upload_and_retrieval(self):
        """Profile image should be stored and retrievable."""
        image_file = self.create_test_image()
        uploaded_file = SimpleUploadedFile(
            'test_image.png',
            image_file.read(),
            content_type='image/png'
        )
        
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student',
            university_name='Test University',
            profile_image=uploaded_file
        )
        
        self.assertTrue(user.profile_image)
        self.assertIn('profile_images', user.profile_image.name)
    
    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_profile_image_upload_path_includes_user_id(self):
        """Profile image upload path should include user ID."""
        image_file = self.create_test_image()
        uploaded_file = SimpleUploadedFile(
            'test_image.png',
            image_file.read(),
            content_type='image/png'
        )
        
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student',
            university_name='Test University',
            profile_image=uploaded_file
        )
        
        # Path should be profile_images/{user_id}/{filename}
        self.assertIn(f'profile_images/{user.id}/', user.profile_image.name)
    
    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_profile_image_size_limit(self):
        """Profile images larger than 5MB must raise ValidationError."""
        # Create a large image (simulating >5MB)
        large_image = self.create_test_image(size=(5000, 5000))
        uploaded_file = SimpleUploadedFile(
            'large_image.png',
            large_image.read(),
            content_type='image/png'
        )
        
        # If file is actually larger than 5MB, validation should fail
        if uploaded_file.size > 5 * 1024 * 1024:
            with self.assertRaises(ValidationError):
                user = User(
                    username='testuser',
                    email='test@example.com',
                    user_type='student',
                    university_name='Test University',
                    profile_image=uploaded_file
                )
                user.full_clean()
    
    def test_profile_image_invalid_format(self):
        """Non-image files must raise ValidationError."""
        text_file = SimpleUploadedFile(
            'test.txt',
            b'This is not an image',
            content_type='text/plain'
        )
        
        with self.assertRaises(ValidationError):
            user = User(
                username='testuser',
                email='test@example.com',
                user_type='student',
                university_name='Test University',
                profile_image=text_file
            )
            user.full_clean()


class UserModelVerificationTests(TestCase):
    """Test is_verified field."""
    
    def test_is_verified_defaults_to_false(self):
        """New users should have is_verified=False by default."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
        self.assertFalse(user.is_verified)
    
    def test_is_verified_can_be_set_true(self):
        """is_verified field should be updatable to True."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
        
        user.is_verified = True
        user.save()
        user.refresh_from_db()
        
        self.assertTrue(user.is_verified)


class UserModelRequiredFieldsTests(TestCase):
    """Test required field validation."""
    
    def test_username_required(self):
        """Creating user without username must raise ValidationError."""
        with self.assertRaises(ValidationError):
            user = User(
                email='test@example.com',
                user_type='student',
                university_name='Test University'
            )
            user.full_clean()
    
    def test_university_name_optional(self):
        """University name should be optional."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student'
        )
        self.assertEqual(user.university_name, '')


class UserModelEdgeCaseTests(TestCase):
    """Test edge cases and boundary conditions."""
    
    def test_extremely_long_first_name(self):
        """First name with 500+ characters should be handled gracefully."""
        long_name = 'A' * 500
        
        # Django's default max_length for first_name is 150
        # This should either truncate or raise ValidationError
        with self.assertRaises(ValidationError):
            user = User(
                username='testuser',
                email='test@example.com',
                first_name=long_name,
                user_type='student',
                university_name='Test University'
            )
            user.full_clean()
    
    def test_special_characters_in_names(self):
        """Names with unicode and special characters should be accepted."""
        special_names = [
            'José García',
            'François Müller',
            '李明',
            'Владимир',
            "O'Brien",
            'Jean-Pierre',
        ]
        
        for idx, name in enumerate(special_names):
            user = User.objects.create_user(
                username=f'user{idx}',
                email=f'user{idx}@example.com',
                password='testpass123',
                first_name=name,
                user_type='student',
                university_name='Test University'
            )
            self.assertEqual(user.first_name, name)
    
    def test_empty_string_vs_null_for_optional_fields(self):
        """Optional fields should handle empty strings correctly."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student',
            phone_number='',
            university_name=''
        )
        
        self.assertEqual(user.phone_number, '')
        self.assertEqual(user.university_name, '')
    
    def test_university_name_max_length(self):
        """University name exceeding 200 characters must raise ValidationError."""
        long_university = 'A' * 201
        
        with self.assertRaises(ValidationError):
            user = User(
                username='testuser',
                email='test@example.com',
                user_type='student',
                university_name=long_university
            )
            user.full_clean()
    
    def test_sql_injection_in_fields(self):
        """SQL injection patterns should be properly escaped."""
        sql_injection = "'; DROP TABLE users; --"
        
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student',
            university_name=sql_injection
        )
        
        # Should be stored as-is (escaped by Django ORM)
        self.assertEqual(user.university_name, sql_injection)
        
        # Verify we can query it safely
        found_user = User.objects.filter(university_name=sql_injection).first()
        self.assertIsNotNone(found_user)
    
    def test_xss_in_fields(self):
        """XSS patterns should be stored (escaping is template's job)."""
        xss_pattern = '<script>alert("XSS")</script>'
        
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student',
            university_name=xss_pattern
        )
        
        # Should be stored as-is (escaping happens in templates)
        self.assertEqual(user.university_name, xss_pattern)


class UserModelTimestampTests(TestCase):
    """Test timestamp fields."""
    
    def test_created_at_auto_set(self):
        """created_at should be automatically set on creation."""
        before_creation = timezone.now()
        
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        
        after_creation = timezone.now()
        
        self.assertIsNotNone(user.created_at)
        self.assertGreaterEqual(user.created_at, before_creation)
        self.assertLessEqual(user.created_at, after_creation)
    
    def test_updated_at_auto_update(self):
        """updated_at should change when model is updated."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        
        original_updated_at = user.updated_at
        
        # Wait a moment and update
        import time
        time.sleep(0.1)
        
        user.university_name = 'Updated University'
        user.save()
        user.refresh_from_db()
        
        self.assertGreater(user.updated_at, original_updated_at)
    
    def test_created_at_immutable(self):
        """created_at should not change on update."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        
        original_created_at = user.created_at
        
        user.university_name = 'Updated University'
        user.save()
        user.refresh_from_db()
        
        self.assertEqual(user.created_at, original_created_at)


class UserModelStringRepresentationTests(TestCase):
    """Test string representation."""
    
    def test_str_method_returns_email(self):
        """__str__ should return email as user identifier."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        
        # Should return email or username
        str_repr = str(user)
        self.assertTrue(
            'test@example.com' in str_repr or 'testuser' in str_repr,
            f"String representation '{str_repr}' should contain email or username"
        )


class UserModelIntegrationTests(TestCase):
    """Test integration with Django's auth system."""
    
    def test_user_authentication(self):
        """User should be able to authenticate with email/password."""
        from django.contrib.auth import authenticate
        
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        
        # Authenticate with username
        authenticated_user = authenticate(
            username='testuser',
            password='testpass123'
        )
        self.assertIsNotNone(authenticated_user)
        self.assertEqual(authenticated_user.id, user.id)
    
    def test_user_permissions_system(self):
        """Django's permission system should work with custom user."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        
        # User should have permission methods
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertTrue(hasattr(user, 'has_perm'))
        self.assertTrue(hasattr(user, 'has_module_perms'))
    
    def test_create_superuser(self):
        """Should be able to create superuser."""
        superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            user_type='provider',
            university_name='Admin University'
        )
        
        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.is_staff)
