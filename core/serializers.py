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

