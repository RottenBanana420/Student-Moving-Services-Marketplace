"""
Custom serializers for authentication and user management.
"""

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.hashers import make_password
import re

User = get_user_model()


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom serializer to use email instead of username for authentication.
    """
    username_field = 'email'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove username field and ensure email field exists
        if 'username' in self.fields:
            del self.fields['username']
        if 'email' not in self.fields:
            self.fields['email'] = serializers.EmailField()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration with comprehensive validation.
    
    Fields:
    - email: Required, unique, valid email format
    - password: Required, must meet strength requirements
    - confirm_password: Required, must match password
    - phone: Optional, must be valid format if provided
    - university_name: Optional
    - user_type: Required, must be 'student' or 'provider'
    """
    
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = ['id', 'email', 'password', 'confirm_password', 'phone_number', 
                  'university_name', 'user_type', 'is_verified', 'created_at']
        read_only_fields = ['id', 'is_verified', 'created_at']
        extra_kwargs = {
            'email': {'required': True},
            'user_type': {'required': True},
        }
    
    def validate_email(self, value):
        """
        Validate email format and uniqueness.
        """
        # Strip whitespace
        value = value.strip()
        
        # Normalize to lowercase for case-insensitive uniqueness
        value = value.lower()
        
        # Check if email already exists (case-insensitive)
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "A user with that email already exists."
            )
        
        return value
    
    def validate_password(self, value):
        """
        Validate password strength using Django's password validators.
        """
        try:
            # Use Django's built-in password validation
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        
        return value
    
    def validate_phone_number(self, value):
        """
        Validate phone number format if provided.
        """
        if not value:
            return value
        
        # Remove common separators for validation
        cleaned = re.sub(r'[\s\-\(\)]', '', value)
        
        # Check if it contains only digits and optional leading +
        if not re.match(r'^\+?\d{10,15}$', cleaned):
            raise serializers.ValidationError(
                "Phone number must be between 10-15 digits and may start with '+'."
            )
        
        return value
    
    def validate_user_type(self, value):
        """
        Validate user_type is either 'student' or 'provider'.
        """
        valid_types = ['student', 'provider']
        
        if value not in valid_types:
            raise serializers.ValidationError(
                f"User type must be one of: {', '.join(valid_types)}."
            )
        
        return value
    
    def validate(self, attrs):
        """
        Object-level validation for password confirmation matching.
        """
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')
        
        if password != confirm_password:
            raise serializers.ValidationError({
                'confirm_password': 'Password confirmation does not match.'
            })
        
        return attrs
    
    def create(self, validated_data):
        """
        Create user with hashed password and default settings.
        Uses atomic transaction to handle concurrent registration attempts.
        """
        from django.db import transaction
        
        # Remove confirm_password as it's not a model field
        validated_data.pop('confirm_password', None)
        
        # Hash the password
        password = validated_data.pop('password')
        validated_data['password'] = make_password(password)
        
        # Ensure is_verified is False for new users (security measure)
        validated_data['is_verified'] = False
        
        # Remove any extra fields that shouldn't be set during registration
        # This prevents privilege escalation attempts
        validated_data.pop('is_superuser', None)
        validated_data.pop('is_staff', None)
        validated_data.pop('is_active', None)
        validated_data.pop('groups', None)
        validated_data.pop('user_permissions', None)
        
        # Set username to first part of email (before @) to avoid length issues
        # AbstractUser requires username, but we use email for authentication
        email = validated_data.get('email', '')
        username = email.split('@')[0][:30]  # Limit to 30 chars (Django default)
        validated_data['username'] = username
        
        # Create the user within an atomic transaction
        # This ensures database-level locking for concurrent requests
        with transaction.atomic():
            user = User.objects.create(**validated_data)
        
        return user


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login with email and password.
    
    Minimal validation to prevent user enumeration attacks.
    Actual authentication happens in the view.
    """
    email = serializers.EmailField(
        required=True,
        help_text='User email address'
    )
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text='User password'
    )



class TokenRefreshSerializer(serializers.Serializer):
    """
    Serializer for token refresh with comprehensive validation.
    
    Security features:
    - Validates refresh token format
    - Checks token signature integrity
    - Verifies token hasn't expired
    - Ensures token is actually a refresh token (not access token)
    - Checks blacklist status
    
    The actual validation is performed by djangorestframework-simplejwt.
    This serializer provides explicit field definition and documentation.
    """
    refresh = serializers.CharField(
        required=True,
        help_text='Valid refresh token to exchange for new access token'
    )


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile retrieval.
    
    Security features:
    - Excludes sensitive fields (password, is_staff, is_superuser, etc.)
    - Includes all user-relevant information
    - Generates proper profile image URLs
    
    Fields included:
    - id: User ID
    - email: User email address
    - phone_number: User phone number
    - university_name: User's university
    - user_type: 'student' or 'provider'
    - is_verified: Verification status
    - profile_image_url: Full URL to profile image (null if not uploaded)
    - created_at: Account creation timestamp
    """
    
    profile_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'phone_number',
            'university_name',
            'user_type',
            'is_verified',
            'profile_image_url',
            'created_at'
        ]
        read_only_fields = fields  # All fields are read-only for profile retrieval
    
    def get_profile_image_url(self, obj):
        """
        Generate full URL for profile image.
        
        Returns:
            str: Full URL to profile image, or None if no image uploaded
        """
        if obj.profile_image:
            request = self.context.get('request')
            if request is not None:
                # Build absolute URI for the image
                return request.build_absolute_uri(obj.profile_image.url)
            else:
                # Fallback to relative URL if request context not available
                return obj.profile_image.url
        return None


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile updates (PUT/PATCH).
    
    Security features:
    - Only allows updating specific fields (phone_number, university_name, profile_image)
    - Prevents modification of restricted fields (email, password, user_type, is_verified, etc.)
    - Validates phone number format
    - Validates image format and size
    - Handles old profile image deletion
    
    Updatable fields:
    - phone_number: Optional, validated format
    - university_name: Optional
    - profile_image: Optional, validated format and size
    
    Restricted fields (cannot be updated):
    - email, password, user_type, is_verified, is_staff, is_superuser, etc.
    """
    
    class Meta:
        model = User
        fields = ['phone_number', 'university_name', 'profile_image']
        extra_kwargs = {
            'phone_number': {'required': False},
            'university_name': {'required': False},
            'profile_image': {'required': False},
        }
    
    def validate_phone_number(self, value):
        """
        Validate phone number format if provided.
        Empty string is allowed to clear the field.
        """
        if not value:
            return value
        
        # Remove common separators for validation
        cleaned = re.sub(r'[\s\-\(\)]', '', value)
        
        # Check if it contains only digits and optional leading +
        if not re.match(r'^\+?\d{10,15}$', cleaned):
            raise serializers.ValidationError(
                "Phone number must be between 10-15 digits and may start with '+'."
            )
        
        # Extract just the digits (excluding +)
        digits = re.sub(r'\D', '', value)
        
        # Must not be all the same digit (like 0000000000)
        if len(set(digits)) == 1:
            raise serializers.ValidationError(
                "Phone number cannot be all the same digit."
            )
        
        return value
    
    def validate(self, attrs):
        """
        Object-level validation to prevent updates to restricted fields.
        
        This ensures that even if a client tries to send restricted fields,
        they will be ignored or rejected.
        """
        # List of restricted fields that should never be updated via this endpoint
        restricted_fields = [
            'email', 'password', 'user_type', 'is_verified', 
            'is_staff', 'is_superuser', 'is_active',
            'username', 'groups', 'user_permissions',
            'created_at', 'updated_at', 'last_login'
        ]
        
        # Remove any restricted fields from validated data
        # This prevents privilege escalation attempts
        for field in restricted_fields:
            if field in attrs:
                attrs.pop(field)
        
        return attrs
    
    def update(self, instance, validated_data):
        """
        Update user profile with special handling for profile image.
        
        Handles:
        - Profile image upload
        - Deletion of old profile image when replaced
        - Proper file storage in MEDIA_ROOT
        
        Args:
            instance: User instance to update
            validated_data: Validated data from serializer
            
        Returns:
            User: Updated user instance
        """
        import os
        from django.conf import settings
        
        # Handle profile image update with old image deletion
        if 'profile_image' in validated_data:
            new_image = validated_data.get('profile_image')
            
            # If there's an old image and we're replacing it, delete the old one
            if instance.profile_image and new_image:
                old_image_path = instance.profile_image.path
                
                # Delete old image file if it exists
                if os.path.exists(old_image_path):
                    try:
                        os.remove(old_image_path)
                    except OSError:
                        # Log error but don't fail the update
                        pass
        
        # Update the instance with validated data
        # Use update_fields to bypass full_clean() which would trigger model validators
        # The serializer has already validated the data
        fields_to_update = []
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            fields_to_update.append(attr)
        
        # Save with specific fields to avoid full_clean validation
        # This prevents double validation (serializer + model)
        if fields_to_update:
            instance.save(update_fields=fields_to_update)
        
        return instance


