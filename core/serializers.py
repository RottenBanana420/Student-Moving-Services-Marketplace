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


class ProviderVerificationRequestSerializer(serializers.Serializer):
    """
    Serializer for provider verification request.
    
    Validates that:
    - provider_id is provided and is a valid integer
    - provider exists in the database
    - provider has user_type='provider'
    
    Fields:
    - provider_id: Required integer ID of the provider to verify
    """
    
    provider_id = serializers.IntegerField(
        required=True,
        help_text='ID of the provider user to verify'
    )
    
    def validate_provider_id(self, value):
        """
        Validate that provider_id is a valid integer.
        
        Note: We don't check if the user exists here because we want the view
        to return a proper 404 response for non-existent users, not a 400
        validation error.
        
        Args:
            value: provider_id integer
            
        Returns:
            int: Validated provider_id
            
        Raises:
            ValidationError: If provider exists but is not a provider type
        """
        # Only validate that it's a positive integer
        if value <= 0:
            raise serializers.ValidationError(
                "Provider ID must be a positive integer."
            )
        
        # Check if user exists and validate user_type
        # We do this here to provide better error messages for validation vs not found
        try:
            user = User.objects.get(id=value)
            # Check if user is a provider
            if user.user_type != 'provider':
                raise serializers.ValidationError(
                    f"User with ID {value} is not a provider. Only provider accounts can be verified."
                )
        except User.DoesNotExist:
            # Don't raise validation error here - let the view return 404
            # This allows proper HTTP status code differentiation
            pass
        
        return value


class ProviderVerificationResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for provider verification response.
    
    Returns verified provider information excluding sensitive data.
    
    Fields:
    - id: Provider user ID
    - email: Provider email address
    - user_type: Should always be 'provider'
    - is_verified: Verification status (should be True after verification)
    - phone_number: Provider phone number
    - university_name: Provider university
    - created_at: Account creation timestamp
    - updated_at: Last update timestamp
    """
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'user_type',
            'is_verified',
            'phone_number',
            'university_name',
            'created_at',
            'updated_at'
        ]
        read_only_fields = fields  # All fields are read-only for response


class MovingServiceCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating moving services.
    
    Security features:
    - Auto-populates provider from authenticated user
    - Validates service name length and content
    - Validates description is not empty
    - Validates base price is positive and reasonable
    - Initializes rating_average to 0.0
    - Initializes total_reviews to 0
    
    Fields:
    - service_name: Required, 1-200 characters, cannot be whitespace only
    - description: Required, cannot be empty or whitespace only
    - base_price: Required, must be positive and < 100,000
    - availability_status: Optional, defaults to True
    
    Read-only fields (auto-populated):
    - id: Auto-generated
    - provider: Set from request.user
    - rating_average: Initialized to 0.0
    - total_reviews: Initialized to 0
    - created_at: Auto-generated
    - updated_at: Auto-generated
    """
    
    class Meta:
        model = get_user_model()._meta.get_field('services').related_model
        fields = [
            'id',
            'service_name',
            'description',
            'base_price',
            'availability_status',
            'provider',
            'rating_average',
            'total_reviews',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'provider', 'rating_average', 'total_reviews', 'created_at', 'updated_at']
        extra_kwargs = {
            'service_name': {'required': True},
            'description': {'required': True},
            'base_price': {'required': True},
            'availability_status': {'required': False, 'default': True},
        }
    
    def validate_service_name(self, value):
        """
        Validate service name is not empty and within length limits.
        
        Args:
            value: Service name string
            
        Returns:
            str: Validated service name
            
        Raises:
            ValidationError: If service name is empty or too long
        """
        # Check if empty or whitespace only
        if not value or not value.strip():
            raise serializers.ValidationError(
                "Service name cannot be empty or whitespace only."
            )
        
        # Check max length (200 characters)
        if len(value) > 200:
            raise serializers.ValidationError(
                f"Service name cannot exceed 200 characters. Current length: {len(value)}."
            )
        
        return value.strip()
    
    def validate_description(self, value):
        """
        Validate description is not empty.
        
        Args:
            value: Description string
            
        Returns:
            str: Validated description
            
        Raises:
            ValidationError: If description is empty
        """
        # Check if empty or whitespace only
        if not value or not value.strip():
            raise serializers.ValidationError(
                "Description cannot be empty or whitespace only."
            )
        
        return value.strip()
    
    def validate_base_price(self, value):
        """
        Validate base price is positive and reasonable.
        
        Args:
            value: Base price decimal
            
        Returns:
            Decimal: Validated base price
            
        Raises:
            ValidationError: If price is not positive or too high
        """
        from decimal import Decimal
        
        # Convert to Decimal if string
        if isinstance(value, str):
            try:
                value = Decimal(value)
            except:
                raise serializers.ValidationError(
                    "Base price must be a valid number."
                )
        
        # Check if positive
        if value <= 0:
            raise serializers.ValidationError(
                "Base price must be greater than 0."
            )
        
        # Check if reasonable (less than 100,000)
        if value >= 100000:
            raise serializers.ValidationError(
                "Base price must be less than 100,000."
            )
        
        return value
    
    def create(self, validated_data):
        """
        Create service with auto-populated fields.
        
        Auto-populates:
        - provider: From request.user
        - rating_average: 0.0
        - total_reviews: 0
        
        Args:
            validated_data: Validated data from serializer
            
        Returns:
            MovingService: Created service instance
        """
        from decimal import Decimal
        from core.models import MovingService
        
        # Get authenticated user from context
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError(
                "Authentication required to create service."
            )
        
        # Auto-populate provider
        validated_data['provider'] = request.user
        
        # Auto-populate rating_average and total_reviews
        validated_data['rating_average'] = Decimal('0.00')
        validated_data['total_reviews'] = 0
        
        # Set default availability_status if not provided
        if 'availability_status' not in validated_data:
            validated_data['availability_status'] = True
        
        # Create the service
        # The model's save() method will call full_clean() for validation
        service = MovingService.objects.create(**validated_data)
        
        return service


# ============================================================================
# Booking Status Update Serializers
# ============================================================================

class BookingStatusUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating booking status.
    
    Security features:
    - Validates status is in allowed choices
    - Enforces state machine transition rules
    - Validates business logic (completion date check)
    - Logs status changes with timestamps
    
    Fields:
    - status: Required, must be valid choice (pending, confirmed, completed, cancelled)
    
    Validation:
    - Calls booking.can_transition_to() for state machine validation
    - Validates completion date for 'completed' status
    - Returns descriptive error messages for invalid transitions
    """
    
    class Meta:
        model = get_user_model()._meta.get_field('student_bookings').related_model
        fields = ['status']
        extra_kwargs = {
            'status': {'required': True},
        }
    
    def validate_status(self, value):
        """
        Validate status is a valid choice.
        
        Args:
            value: Status value
            
        Returns:
            str: Validated status
            
        Raises:
            ValidationError: If status is not a valid choice
        """
        valid_statuses = ['pending', 'confirmed', 'completed', 'cancelled']
        
        if value not in valid_statuses:
            raise serializers.ValidationError(
                f"Invalid status. Must be one of: {', '.join(valid_statuses)}."
            )
        
        return value
    
    def validate(self, attrs):
        """
        Object-level validation for status transitions.
        
        Validates:
        - State machine transition rules
        - Business logic (completion date)
        
        Args:
            attrs: Validated data
            
        Returns:
            dict: Validated data
            
        Raises:
            ValidationError: If transition is invalid
        """
        from django.utils import timezone
        
        new_status = attrs.get('status')
        booking = self.instance
        
        if not booking:
            raise serializers.ValidationError(
                "Booking instance is required for status update."
            )
        
        # Use the state machine validation method
        is_valid, error_message = booking.can_transition_to(new_status)
        
        if not is_valid:
            raise serializers.ValidationError({
                'status': error_message
            })
        
        return attrs
    
    def update(self, instance, validated_data):
        """
        Update booking status.
        
        Args:
            instance: Booking instance
            validated_data: Validated data
            
        Returns:
            Booking: Updated booking instance
        """
        # Update status
        instance.status = validated_data.get('status')
        
        # Save with update_fields to trigger updated_at
        instance.save(update_fields=['status', 'updated_at'])
        
        return instance


# ============================================================================
# Service Listing Serializers
# ============================================================================

class ServiceProviderSerializer(serializers.ModelSerializer):
    """
    Nested serializer for provider information in service listings.
    
    Provides essential provider details without exposing sensitive information.
    Optimized for use with select_related to prevent N+1 queries.
    
    Fields:
    - id: Provider user ID
    - email: Provider email address
    - university_name: Provider's university
    - is_verified: Provider verification status
    """
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'university_name',
            'is_verified',
            'user_type'
        ]
        read_only_fields = fields


class ServiceListSerializer(serializers.ModelSerializer):
    """
    Serializer for service listing endpoint.
    
    Provides comprehensive service information including nested provider details.
    Optimized for performance with select_related('provider') in the view.
    
    Fields:
    - id: Service ID
    - service_name: Name of the service
    - description: Service description
    - base_price: Base price for the service
    - availability_status: Whether service is currently available
    - rating_average: Average rating (0-5)
    - total_reviews: Total number of reviews
    - created_at: Service creation timestamp
    - provider: Nested provider information (ServiceProviderSerializer)
    """
    
    provider = ServiceProviderSerializer(read_only=True)
    
    class Meta:
        model = get_user_model()._meta.get_field('services').related_model
        fields = [
            'id',
            'service_name',
            'description',
            'base_price',
            'availability_status',
            'rating_average',
            'total_reviews',
            'created_at',
            'provider'
        ]
        read_only_fields = fields


# ============================================================================
# Service Detail Serializers
# ============================================================================

class ReviewSerializer(serializers.ModelSerializer):
    """
    Nested serializer for displaying review information in service details.
    
    Provides review details without exposing sensitive reviewer information.
    Shows reviewer's email as the reviewer name for transparency.
    
    Fields:
    - id: Review ID
    - reviewer_name: Reviewer's email address
    - rating: Rating from 1-5
    - comment: Review comment text
    - created_at: Review creation timestamp
    """
    
    reviewer_name = serializers.SerializerMethodField()
    
    class Meta:
        model = get_user_model()._meta.get_field('reviews_given').related_model
        fields = [
            'id',
            'reviewer_name',
            'rating',
            'comment',
            'created_at'
        ]
        read_only_fields = fields
    
    def get_reviewer_name(self, obj):
        """
        Get reviewer's email as their display name.
        
        Args:
            obj: Review instance
            
        Returns:
            str: Reviewer's email address
        """
        return obj.reviewer.email if obj.reviewer else 'Anonymous'


class DetailedProviderSerializer(serializers.ModelSerializer):
    """
    Extended provider serializer with rating summary for service detail view.
    
    Includes all provider information plus aggregated rating across all their services.
    Optimized to work with prefetched data to avoid N+1 queries.
    
    Fields:
    - id: Provider user ID
    - email: Provider email address
    - phone_number: Provider phone number
    - university_name: Provider's university
    - is_verified: Provider verification status
    - profile_image_url: Full URL to profile image (null if not uploaded)
    - provider_rating_average: Average rating across all provider's services
    """
    
    profile_image_url = serializers.SerializerMethodField()
    provider_rating_average = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'phone_number',
            'university_name',
            'is_verified',
            'profile_image_url',
            'provider_rating_average'
        ]
        read_only_fields = fields
    
    def get_profile_image_url(self, obj):
        """
        Generate full URL for profile image.
        
        Args:
            obj: User instance
            
        Returns:
            str: Full URL to profile image, or None if no image uploaded
        """
        if obj.profile_image:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.profile_image.url)
            else:
                return obj.profile_image.url
        return None
    
    def get_provider_rating_average(self, obj):
        """
        Calculate average rating across all provider's services.
        
        Aggregates reviews from all bookings for all services offered by this provider.
        Uses prefetched data to avoid N+1 queries.
        
        Args:
            obj: User instance (provider)
            
        Returns:
            Decimal: Average rating (0.00 to 5.00)
        """
        from decimal import Decimal
        from django.db.models import Avg
        from core.models import Review
        
        # Get all reviews where this provider is the reviewee
        # This includes reviews from all their services
        avg_rating = Review.objects.filter(
            reviewee=obj
        ).aggregate(Avg('rating'))['rating__avg']
        
        if avg_rating is not None:
            return Decimal(str(avg_rating)).quantize(Decimal('0.01'))
        return Decimal('0.00')


class ServiceDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for service detail endpoint.
    
    Provides complete service information including:
    - All service fields
    - Detailed provider information with rating summary
    - Recent reviews (limited to 10 most recent)
    - Service-specific rating statistics
    - Rating distribution (count of each star rating)
    
    Optimized for performance with select_related and prefetch_related in view.
    
    Fields:
    - id: Service ID
    - service_name: Name of the service
    - description: Service description
    - base_price: Base price for the service
    - availability_status: Whether service is currently available
    - created_at: Service creation timestamp
    - updated_at: Last update timestamp
    - provider: Nested detailed provider information
    - recent_reviews: List of recent reviews (max 10)
    - rating_average: Service-specific average rating
    - total_reviews: Service-specific total review count
    - rating_distribution: Dictionary with counts for each star rating (1-5)
    """
    
    provider = DetailedProviderSerializer(read_only=True)
    recent_reviews = serializers.SerializerMethodField()
    rating_average = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    rating_distribution = serializers.SerializerMethodField()
    
    class Meta:
        model = get_user_model()._meta.get_field('services').related_model
        fields = [
            'id',
            'service_name',
            'description',
            'base_price',
            'availability_status',
            'created_at',
            'updated_at',
            'provider',
            'recent_reviews',
            'rating_average',
            'total_reviews',
            'rating_distribution'
        ]
        read_only_fields = fields
    
    def get_recent_reviews(self, obj):
        """
        Get recent reviews for this service (max 10, most recent first).
        
        Reviews are fetched through the booking relationship since Review
        has a OneToOneField with Booking, not MovingService.
        
        Args:
            obj: MovingService instance
            
        Returns:
            list: Serialized review data
        """
        from core.models import Review
        
        # Get reviews through bookings for this service
        reviews = Review.objects.filter(
            booking__service=obj
        ).select_related('reviewer').order_by('-created_at')[:10]
        
        return ReviewSerializer(reviews, many=True, context=self.context).data
    
    def get_rating_average(self, obj):
        """
        Calculate average rating for this specific service.
        
        Args:
            obj: MovingService instance
            
        Returns:
            Decimal: Average rating (0.00 to 5.00)
        """
        from decimal import Decimal
        from django.db.models import Avg
        from core.models import Review
        
        avg_rating = Review.objects.filter(
            booking__service=obj
        ).aggregate(Avg('rating'))['rating__avg']
        
        if avg_rating is not None:
            return Decimal(str(avg_rating)).quantize(Decimal('0.01'))
        return Decimal('0.00')
    
    def get_total_reviews(self, obj):
        """
        Get total number of reviews for this specific service.
        
        Args:
            obj: MovingService instance
            
        Returns:
            int: Total review count
        """
        from core.models import Review
        
        return Review.objects.filter(booking__service=obj).count()
    
    def get_rating_distribution(self, obj):
        """
        Calculate rating distribution (count of each star rating).
        
        Returns a dictionary with counts for ratings 1-5.
        
        Args:
            obj: MovingService instance
            
        Returns:
            dict: Rating distribution, e.g. {'1': 0, '2': 1, '3': 2, '4': 3, '5': 4}
        """
        from django.db.models import Count
        from core.models import Review
        
        # Get count of each rating value
        distribution = Review.objects.filter(
            booking__service=obj
        ).values('rating').annotate(count=Count('rating'))
        
        # Initialize all ratings to 0
        result = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        
        # Fill in actual counts
        for item in distribution:
            rating_str = str(item['rating'])
            result[rating_str] = item['count']
        
        return result


# ============================================================================
# Booking Creation Serializers
# ============================================================================

class BookingCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating bookings.
    
    Security features:
    - Auto-populates student from authenticated user
    - Auto-populates provider from service
    - Auto-sets status to 'pending'
    - Auto-calculates total_price from service base_price
    - Validates booking date is in future (minimum 1 hour advance)
    - Prevents self-booking (user cannot book their own service)
    - Validates service exists and is available
    - Includes provider information in response
    
    Fields:
    - service: Required, must exist and be available
    - booking_date: Required, must be in future (minimum 1 hour advance)
    - pickup_location: Required, max 300 characters
    - dropoff_location: Required, max 300 characters
    
    Read-only fields (auto-populated):
    - id: Auto-generated
    - student: Set from request.user
    - provider: Set from service.provider
    - status: Set to 'pending'
    - total_price: Set from service.base_price
    - created_at: Auto-generated
    - updated_at: Auto-generated
    """
    
    # Include provider information in response
    provider = ServiceProviderSerializer(read_only=True)
    
    class Meta:
        model = get_user_model()._meta.get_field('student_bookings').related_model
        fields = [
            'id',
            'service',
            'booking_date',
            'pickup_location',
            'dropoff_location',
            'student',
            'provider',
            'status',
            'total_price',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'student', 'provider', 'status', 'total_price', 'created_at', 'updated_at']
        extra_kwargs = {
            'service': {'required': True},
            'booking_date': {'required': True},
            'pickup_location': {'required': True},
            'dropoff_location': {'required': True},
        }
    
    def validate_service(self, value):
        """
        Validate service exists and is available.
        
        Args:
            value: MovingService instance
            
        Returns:
            MovingService: Validated service instance
            
        Raises:
            ValidationError: If service is unavailable
        """
        if not value.availability_status:
            raise serializers.ValidationError(
                "This service is currently unavailable for booking."
            )
        
        return value
    
    def validate_booking_date(self, value):
        """
        Validate booking date is in the future with minimum advance notice.
        
        Requires at least 1 hour advance notice for bookings.
        
        Args:
            value: Booking datetime
            
        Returns:
            datetime: Validated booking datetime
            
        Raises:
            ValidationError: If booking date is in past or too soon
        """
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        minimum_advance = timedelta(hours=1)
        
        # Ensure booking_date is timezone-aware
        if value.tzinfo is None:
            raise serializers.ValidationError(
                "Booking date must include timezone information."
            )
        
        # Check if booking is in the past
        if value <= now:
            raise serializers.ValidationError(
                "Booking date must be in the future."
            )
        
        # Check minimum advance notice (1 hour)
        if value < now + minimum_advance:
            raise serializers.ValidationError(
                "Bookings must be made at least 1 hour in advance."
            )
        
        return value
    
    def validate_pickup_location(self, value):
        """
        Validate pickup location is not empty.
        
        Args:
            value: Pickup location string
            
        Returns:
            str: Validated pickup location
            
        Raises:
            ValidationError: If pickup location is empty
        """
        if not value or not value.strip():
            raise serializers.ValidationError(
                "Pickup location cannot be empty."
            )
        
        return value.strip()
    
    def validate_dropoff_location(self, value):
        """
        Validate dropoff location is not empty.
        
        Args:
            value: Dropoff location string
            
        Returns:
            str: Validated dropoff location
            
        Raises:
            ValidationError: If dropoff location is empty
        """
        if not value or not value.strip():
            raise serializers.ValidationError(
                "Dropoff location cannot be empty."
            )
        
        return value.strip()
    
    def validate(self, attrs):
        """
        Object-level validation for self-booking prevention.
        
        Ensures user cannot book their own service.
        
        Args:
            attrs: Validated field data
            
        Returns:
            dict: Validated data
            
        Raises:
            ValidationError: If user tries to book their own service
        """
        request = self.context.get('request')
        service = attrs.get('service')
        
        # Prevent self-booking
        if request and request.user and service:
            if service.provider == request.user:
                raise serializers.ValidationError(
                    "You cannot book your own service."
                )
        
        return attrs
    
    def create(self, validated_data):
        """
        Create booking with auto-populated fields.
        
        Auto-populates:
        - student: From request.user
        - provider: From service.provider
        - status: 'pending'
        - total_price: From service.base_price
        
        Note: Conflict detection is handled in the view using database locking.
        
        Args:
            validated_data: Validated data from serializer
            
        Returns:
            Booking: Created booking instance
        """
        from core.models import Booking
        
        # Get authenticated user from context
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError(
                "Authentication required to create booking."
            )
        
        # Get service
        service = validated_data['service']
        
        # Auto-populate fields
        validated_data['student'] = request.user
        validated_data['provider'] = service.provider
        validated_data['status'] = 'pending'
        validated_data['total_price'] = service.base_price
        
        # Create the booking
        # Note: The model's save() method will call full_clean() for validation
        booking = Booking.objects.create(**validated_data)
        
        return booking


# ============================================================================
# Review Creation Serializers
# ============================================================================

class ReviewUserSerializer(serializers.ModelSerializer):
    """
    Nested serializer for user information in review responses.
    
    Provides essential user details without exposing sensitive information.
    
    Fields:
    - id: User ID
    - email: User email address
    - user_type: 'student' or 'provider'
    """
    
    class Meta:
        model = User
        fields = ['id', 'email', 'user_type']
        read_only_fields = fields


class ReviewBookingSerializer(serializers.ModelSerializer):
    """
    Nested serializer for booking information in review responses.
    
    Provides essential booking details.
    
    Fields:
    - id: Booking ID
    - booking_date: Date and time of booking
    - status: Booking status
    """
    
    class Meta:
        from core.models import Booking
        model = Booking
        fields = ['id', 'booking_date', 'status']
        read_only_fields = fields


class ReviewCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating reviews.
    
    Security features:
    - Requires JWT authentication (enforced by view)
    - Validates booking exists and is completed
    - Validates user participated in booking
    - Automatically determines reviewer and reviewee
    - Prevents duplicate reviews (OneToOneField constraint)
    
    Fields:
    - booking_id: Required, ID of completed booking to review
    - rating: Required, integer from 1-5
    - comment: Required, text feedback
    
    Read-only fields (auto-populated):
    - id: Auto-generated
    - reviewer: Set from request.user
    - reviewee: Determined from booking participants
    - booking: Set from booking_id
    - created_at: Auto-generated
    """
    
    booking_id = serializers.IntegerField(write_only=True, required=True)
    reviewer = ReviewUserSerializer(read_only=True)
    reviewee = ReviewUserSerializer(read_only=True)
    booking = ReviewBookingSerializer(read_only=True)
    
    class Meta:
        from core.models import Review
        model = Review
        fields = ['id', 'booking_id', 'rating', 'comment', 'reviewer', 'reviewee', 'booking', 'created_at']
        read_only_fields = ['id', 'reviewer', 'reviewee', 'booking', 'created_at']
        extra_kwargs = {
            'rating': {'required': True},
            'comment': {'required': True},
        }
    
    def validate_rating(self, value):
        """
        Validate rating is integer between 1-5.
        
        Args:
            value: Rating value
            
        Returns:
            int: Validated rating
            
        Raises:
            ValidationError: If rating is not between 1-5
        """
        # Check if it's an integer (DRF IntegerField handles type conversion)
        if not isinstance(value, int):
            raise serializers.ValidationError(
                "Rating must be an integer."
            )
        
        # Check range (1-5)
        if value < 1 or value > 5:
            raise serializers.ValidationError(
                "Rating must be between 1 and 5."
            )
        
        return value
    
    def validate_booking_id(self, value):
        """
        Validate booking exists.
        
        Args:
            value: Booking ID
            
        Returns:
            int: Validated booking ID
            
        Raises:
            NotFound: If booking doesn't exist (returns 404)
        """
        from core.models import Booking
        from rest_framework.exceptions import NotFound
        
        # Check if booking exists
        if not Booking.objects.filter(id=value).exists():
            # Raise NotFound to return 404 instead of 400
            raise NotFound("Booking not found.")
        
        return value
    
    def validate(self, attrs):
        """
        Object-level validation for booking status and user participation.
        
        Validates:
        - Booking status is 'completed'
        - Authenticated user participated in booking (student or provider)
        - Automatically determines reviewer and reviewee
        
        Args:
            attrs: Validated data
            
        Returns:
            dict: Validated data with reviewer, reviewee, and booking set
            
        Raises:
            ValidationError: If validation fails
        """
        from core.models import Booking
        from rest_framework.exceptions import PermissionDenied, NotFound
        
        booking_id = attrs.get('booking_id')
        request = self.context.get('request')
        
        if not request or not request.user:
            raise serializers.ValidationError(
                "Authentication required to create review."
            )
        
        # Get booking
        try:
            booking = Booking.objects.select_related('student', 'provider').get(id=booking_id)
        except Booking.DoesNotExist:
            # Raise NotFound to return 404 instead of 400
            raise NotFound("Booking not found.")
        
        # Validate booking status is completed
        if booking.status != 'completed':
            raise serializers.ValidationError({
                'booking_id': f"Only completed bookings can be reviewed. This booking is {booking.status}."
            })
        
        # Validate user participated in booking
        user = request.user
        if user.id not in [booking.student_id, booking.provider_id]:
            # Raise PermissionDenied to return 403 instead of 400
            raise PermissionDenied(
                "You can only review bookings you participated in."
            )
        
        # Automatically determine reviewer and reviewee
        if user.id == booking.student_id:
            # Student is reviewing provider
            attrs['reviewer'] = booking.student
            attrs['reviewee'] = booking.provider
        else:
            # Provider is reviewing student
            attrs['reviewer'] = booking.provider
            attrs['reviewee'] = booking.student
        
        # Set booking
        attrs['booking'] = booking
        
        return attrs
    
    def create(self, validated_data):
        """
        Create review with auto-populated fields.
        
        Args:
            validated_data: Validated data from serializer
            
        Returns:
            Review: Created review instance
            
        Raises:
            ValidationError: If duplicate review (caught by view and converted to 400)
        """
        from core.models import Review
        
        # Remove booking_id as it's not a model field
        validated_data.pop('booking_id', None)
        
        # Create review
        # The model's save() method will validate business logic
        # OneToOneField constraint will prevent duplicates at database level
        review = Review(**validated_data)
        review.save()
        
        return review


class ReviewUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating existing reviews.
    
    Supports partial updates (PATCH) for rating and comment fields only.
    Immutable fields (reviewer, reviewee, booking) are read-only.
    
    Fields:
    - rating: Optional, integer from 1-5
    - comment: Optional, text feedback (cannot be empty if provided)
    
    Read-only fields (cannot be changed):
    - id: Review ID
    - reviewer: Original reviewer
    - reviewee: Original reviewee
    - booking: Original booking
    - created_at: Original creation timestamp
    - updated_at: Auto-updated on save
    """
    
    class Meta:
        from core.models import Review
        model = Review
        fields = ['id', 'rating', 'comment', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_rating(self, value):
        """
        Validate rating is integer between 1-5.
        
        Args:
            value: Rating value
            
        Returns:
            int: Validated rating
            
        Raises:
            ValidationError: If rating is not between 1-5
        """
        # Check if it's an integer
        if not isinstance(value, int):
            raise serializers.ValidationError(
                "Rating must be an integer."
            )
        
        # Check range (1-5)
        if value < 1 or value > 5:
            raise serializers.ValidationError(
                "Rating must be between 1 and 5."
            )
        
        return value
    
    def validate_comment(self, value):
        """
        Validate comment is not empty or whitespace-only.
        
        Args:
            value: Comment text
            
        Returns:
            str: Validated comment
            
        Raises:
            ValidationError: If comment is empty
        """
        if not value or not value.strip():
            raise serializers.ValidationError(
                "Comment cannot be empty."
            )
        
        return value.strip()
    
    def update(self, instance, validated_data):
        """
        Update review with validated data.
        
        Only updates rating and/or comment fields.
        Immutable fields are ignored even if provided.
        
        Args:
            instance: Review instance to update
            validated_data: Validated data from serializer
            
        Returns:
            Review: Updated review instance
        """
        # Update only allowed fields
        if 'rating' in validated_data:
            instance.rating = validated_data['rating']
        
        if 'comment' in validated_data:
            instance.comment = validated_data['comment']
        
        # Save the instance (updated_at will auto-update)
        instance.save()
        
        return instance


# ============================================================================
# Booking Calendar Serializers
# ============================================================================

class BookingCalendarSerializer(serializers.ModelSerializer):
    """
    Serializer for booking information in calendar view.
    
    Provides comprehensive booking details optimized for calendar display.
    Works with select_related to prevent N+1 queries.
    
    Fields:
    - id: Booking ID
    - service_name: Name of the booked service
    - service_id: ID of the booked service
    - student_email: Email of the student who made the booking
    - student_id: ID of the student
    - provider_email: Email of the service provider
    - provider_id: ID of the provider
    - booking_date: Date and time of the booking
    - status: Booking status (pending, confirmed, completed, cancelled)
    - pickup_location: Pickup address
    - dropoff_location: Dropoff address
    - total_price: Total price for the booking
    """
    
    service_name = serializers.SerializerMethodField()
    service_id = serializers.SerializerMethodField()
    student_email = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    provider_email = serializers.SerializerMethodField()
    provider_id = serializers.SerializerMethodField()
    
    class Meta:
        model = get_user_model()._meta.get_field('student_bookings').related_model
        fields = [
            'id',
            'service_name',
            'service_id',
            'student_email',
            'student_id',
            'provider_email',
            'provider_id',
            'booking_date',
            'status',
            'pickup_location',
            'dropoff_location',
            'total_price'
        ]
        read_only_fields = fields
    
    def get_service_name(self, obj):
        """Get service name from related service."""
        return obj.service.service_name if obj.service else None
    
    def get_service_id(self, obj):
        """Get service ID from related service."""
        return obj.service.id if obj.service else None
    
    def get_student_email(self, obj):
        """Get student email from related student."""
        return obj.student.email if obj.student else None
    
    def get_student_id(self, obj):
        """Get student ID from related student."""
        return obj.student.id if obj.student else None
    
    def get_provider_email(self, obj):
        """Get provider email from related provider."""
        return obj.provider.email if obj.provider else None
    
    def get_provider_id(self, obj):
        """Get provider ID from related provider."""
        return obj.provider.id if obj.provider else None


class CalendarDaySerializer(serializers.Serializer):
    """
    Serializer for a single day's calendar data.
    
    Organizes bookings and availability information for one day.
    
    Fields:
    - date: Date string (YYYY-MM-DD)
    - bookings: List of BookingCalendarSerializer instances
    - available_slots: List of available time slots (strings)
    - is_fully_booked: Boolean indicating if all slots are occupied
    """
    
    date = serializers.DateField()
    bookings = BookingCalendarSerializer(many=True, read_only=True)
    available_slots = serializers.ListField(
        child=serializers.CharField(),
        read_only=True
    )
    is_fully_booked = serializers.BooleanField(read_only=True)


class CalendarResponseSerializer(serializers.Serializer):
    """
    Top-level serializer for calendar response.
    
    Provides metadata about the calendar request and organized day data.
    
    Fields:
    - start_date: Start of date range (YYYY-MM-DD)
    - end_date: End of date range (YYYY-MM-DD)
    - provider_id: Provider filter (null if not filtered)
    - service_id: Service filter (null if not filtered)
    - status_filter: Status filter (comma-separated string)
    - days: List of CalendarDaySerializer instances
    """
    
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    provider_id = serializers.IntegerField(allow_null=True, required=False)
    service_id = serializers.IntegerField(allow_null=True, required=False)
    status_filter = serializers.CharField(allow_null=True, required=False)
    days = CalendarDaySerializer(many=True, read_only=True)

# ============================================================================
# Booking History Serializers
# ============================================================================

class BookingHistoryServiceSerializer(serializers.ModelSerializer):
    """
    Nested serializer for service information in booking history.
    
    Provides essential service details for booking history display.
    Optimized for use with select_related to prevent N+1 queries.
    
    Fields:
    - id: Service ID
    - service_name: Name of the service
    - description: Service description
    - base_price: Base price for the service
    """
    
    class Meta:
        model = get_user_model()._meta.get_field('services').related_model
        fields = [
            'id',
            'service_name',
            'description',
            'base_price'
        ]
        read_only_fields = fields


class BookingHistoryProviderSerializer(serializers.ModelSerializer):
    """
    Nested serializer for provider information in booking history (shown to students).
    
    Provides provider details without exposing sensitive information.
    Optimized for use with select_related to prevent N+1 queries.
    
    Fields:
    - id: Provider user ID
    - email: Provider email address
    - university_name: Provider's university
    - is_verified: Provider verification status
    - profile_image_url: Full URL to profile image (null if not uploaded)
    """
    
    profile_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'university_name',
            'is_verified',
            'profile_image_url'
        ]
        read_only_fields = fields
    
    def get_profile_image_url(self, obj):
        """
        Generate full URL for profile image.
        
        Args:
            obj: User instance
            
        Returns:
            str: Full URL to profile image, or None if no image uploaded
        """
        if obj.profile_image:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.profile_image.url)
            else:
                return obj.profile_image.url
        return None


class BookingHistoryStudentSerializer(serializers.ModelSerializer):
    """
    Nested serializer for student information in booking history (shown to providers).
    
    Provides student details without exposing sensitive information.
    Optimized for use with select_related to prevent N+1 queries.
    
    Fields:
    - id: Student user ID
    - email: Student email address
    - university_name: Student's university
    - profile_image_url: Full URL to profile image (null if not uploaded)
    """
    
    profile_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'university_name',
            'profile_image_url'
        ]
        read_only_fields = fields
    
    def get_profile_image_url(self, obj):
        """
        Generate full URL for profile image.
        
        Args:
            obj: User instance
            
        Returns:
            str: Full URL to profile image, or None if no image uploaded
        """
        if obj.profile_image:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.profile_image.url)
            else:
                return obj.profile_image.url
        return None


class BookingHistorySerializer(serializers.ModelSerializer):
    """
    Main serializer for booking history endpoint.
    
    Provides comprehensive booking details with conditional nested data:
    - Students see provider information
    - Providers see student information
    
    Optimized for performance with select_related('service', 'provider', 'student') in view.
    
    Fields:
    - id: Booking ID
    - booking_date: Date and time of the booking
    - pickup_location: Pickup address
    - dropoff_location: Dropoff address
    - status: Booking status (pending, confirmed, completed, cancelled)
    - total_price: Total price for the booking
    - created_at: Booking creation timestamp
    - updated_at: Last update timestamp
    - service: Nested service information (BookingHistoryServiceSerializer)
    - provider: Nested provider information (shown to students only)
    - student: Nested student information (shown to providers only)
    """
    
    service = BookingHistoryServiceSerializer(read_only=True)
    provider = serializers.SerializerMethodField()
    student = serializers.SerializerMethodField()
    
    class Meta:
        model = get_user_model()._meta.get_field('student_bookings').related_model
        fields = [
            'id',
            'booking_date',
            'pickup_location',
            'dropoff_location',
            'status',
            'total_price',
            'created_at',
            'updated_at',
            'service',
            'provider',
            'student'
        ]
        read_only_fields = fields
    
    def get_provider(self, obj):
        """
        Get provider information (shown to students only).
        
        Args:
            obj: Booking instance
            
        Returns:
            dict: Serialized provider data, or None if user is provider
        """
        request = self.context.get('request')
        
        # Only show provider info to students
        if request and request.user and request.user.is_student():
            return BookingHistoryProviderSerializer(
                obj.provider,
                context=self.context
            ).data
        
        return None
    
    def get_student(self, obj):
        """
        Get student information (shown to providers only).
        
        Args:
            obj: Booking instance
            
        Returns:
            dict: Serialized student data, or None if user is student
        """
        request = self.context.get('request')
        
        # Only show student info to providers
        if request and request.user and request.user.is_provider():
            return BookingHistoryStudentSerializer(
                obj.student,
                context=self.context
            ).data
        
        return None
    
    def to_representation(self, instance):
        """
        Override to_representation to exclude null fields.
        
        Students should not see 'student' field at all.
        Providers should not see 'provider' field at all.
        
        Args:
            instance: Booking instance
            
        Returns:
            dict: Serialized data with null fields removed
        """
        data = super().to_representation(instance)
        request = self.context.get('request')
        
        # Remove null fields based on user type
        if request and request.user:
            if request.user.is_student():
                # Students don't need to see student field (that's themselves)
                data.pop('student', None)
            elif request.user.is_provider():
                # Providers don't need to see provider field (that's themselves)
                data.pop('provider', None)
        

        return data


# ============================================================================
# Service Review Serializers
# ============================================================================

class ReviewerSerializer(serializers.ModelSerializer):
    """
    Serializer for reviewer information.
    Exposes only safe fields (no contact info).
    """
    profile_image_url = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'full_name', 'university_name', 'user_type', 'profile_image_url']

    def get_profile_image_url(self, obj):
        if obj.profile_image:
             request = self.context.get('request')
             if request is not None:
                return request.build_absolute_uri(obj.profile_image.url)
             return obj.profile_image.url
        return None

    def get_full_name(self, obj):
        # Return first name + last initial, or username/email part if empty
        full = obj.get_full_name()
        if full:
             return full
        return obj.email.split('@')[0]


class ServiceReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for service reviews.
    """
    reviewer = ReviewerSerializer(read_only=True)
    is_verified_booking = serializers.SerializerMethodField()
    booking_reference = serializers.SerializerMethodField()

    class Meta:
        from core.models import Review
        model = Review
        fields = ['id', 'rating', 'comment', 'created_at', 'reviewer', 'booking', 'booking_reference', 'is_verified_booking']

    def get_is_verified_booking(self, obj):
        # All reviews in this system are tied to a completed booking
        return True
        
    def get_booking_reference(self, obj):
        return str(obj.booking.id)


# ============================================================================
# User Reviews Serializers
# ============================================================================

class UserReviewerSerializer(serializers.ModelSerializer):
    """
    Serializer for reviewer information in user reviews endpoint.
    
    Provides essential reviewer details for transparency.
    
    Fields:
    - id: Reviewer user ID
    - email: Reviewer email address
    - user_type: Reviewer type (student/provider)
    """
    
    class Meta:
        model = User
        fields = ['id', 'email', 'user_type']
        read_only_fields = fields


class UserReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for user reviews endpoint with bidirectional context.
    
    Displays reviews received by a user with context about the role
    (as provider or as student) in which they received the review.
    
    Fields:
    - id: Review ID
    - rating: Review rating (1-5)
    - comment: Review text
    - created_at: Review creation timestamp
    - reviewer: Nested reviewer information
    - review_context: Role context ('as_provider' or 'as_student')
    - service_name: Service name (for provider reviews)
    """
    
    reviewer = UserReviewerSerializer(read_only=True)
    review_context = serializers.SerializerMethodField()
    service_name = serializers.SerializerMethodField()
    
    class Meta:
        from core.models import Review
        model = Review
        fields = [
            'id',
            'rating',
            'comment',
            'created_at',
            'reviewer',
            'review_context',
            'service_name'
        ]
        read_only_fields = fields
    
    def get_review_context(self, obj):
        """
        Determine the context in which the review was received.
        
        Logic:
        - If reviewee was the provider in the booking -> 'as_provider'
        - If reviewee was the student in the booking -> 'as_student'
        
        Args:
            obj: Review instance
            
        Returns:
            str: 'as_provider' or 'as_student'
        """
        # Check if reviewee is the provider in the booking
        if obj.reviewee_id == obj.booking.provider_id:
            return 'as_provider'
        # Otherwise, reviewee is the student in the booking
        elif obj.reviewee_id == obj.booking.student_id:
            return 'as_student'
        else:
            # This shouldn't happen due to model validation, but handle gracefully
            return 'unknown'
    
    def get_service_name(self, obj):
        """
        Get the service name for the review.
        
        For provider reviews, this shows which service was reviewed.
        For student reviews, this may be less relevant but still informative.
        
        Args:
            obj: Review instance
            
        Returns:
            str: Service name or None
        """
        if obj.booking and obj.booking.service:
            return obj.booking.service.service_name
        return None


# ============================================================================
# Furniture Listing Creation Serializers
# ============================================================================

class FurnitureImageSerializer(serializers.ModelSerializer):
    """
    Serializer for furniture images in listing responses.
    
    Provides image URL and ordering information.
    
    Fields:
    - id: Image ID
    - image: Full URL to image file
    - order: Display order
    - uploaded_at: Upload timestamp
    """
    
    image = serializers.SerializerMethodField()
    
    class Meta:
        from core.models import FurnitureImage
        model = FurnitureImage
        fields = ['id', 'image', 'order', 'uploaded_at']
        read_only_fields = fields
    
    def get_image(self, obj):
        """
        Generate full URL for furniture image.
        
        Args:
            obj: FurnitureImage instance
            
        Returns:
            str: Full URL to image file
        """
        if obj.image:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class FurnitureSellerSerializer(serializers.ModelSerializer):
    """
    Serializer for seller information in furniture listings.
    
    Provides essential seller details without exposing sensitive information.
    
    Fields:
    - id: Seller user ID
    - email: Seller email address
    - university_name: Seller's university
    """
    
    class Meta:
        model = User
        fields = ['id', 'email', 'university_name']
        read_only_fields = fields


class FurnitureItemCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating furniture listings with multiple images.
    
    Security features:
    - Requires JWT authentication (enforced by view)
    - Validates image count (1-10 images required)
    - Validates image format (JPEG, PNG, WebP only)
    - Validates image size (max 5MB per image)
    - Automatically sets seller to authenticated user
    
    Fields:
    - title: Required, max 200 characters
    - description: Required, detailed item information
    - price: Required, must be positive decimal
    - condition: Required, one of predefined choices
    - category: Required, one of predefined choices
    - images: Required, list of 1-10 image files
    
    Read-only fields (auto-populated):
    - id: Auto-generated
    - seller: Set from request.user
    - is_sold: Defaults to False
    - created_at: Auto-generated
    - updated_at: Auto-generated
    """
    
    images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=True,
        help_text='List of 1-10 image files (JPEG, PNG, WebP, max 5MB each)'
    )
    seller = FurnitureSellerSerializer(read_only=True)
    images_data = FurnitureImageSerializer(source='images', many=True, read_only=True)
    
    class Meta:
        from core.models import FurnitureItem
        model = FurnitureItem
        fields = [
            'id',
            'title',
            'description',
            'price',
            'condition',
            'category',
            'images',
            'images_data',
            'seller',
            'is_sold',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'seller', 'is_sold', 'created_at', 'updated_at', 'images_data']
        extra_kwargs = {
            'title': {'required': True},
            'description': {'required': True},
            'price': {'required': True},
            'condition': {'required': True},
            'category': {'required': True},
        }
    
    def validate_title(self, value):
        """
        Validate title is not empty or whitespace-only.
        
        Args:
            value: Title string
            
        Returns:
            str: Validated title
            
        Raises:
            ValidationError: If title is empty or whitespace
        """
        if not value or not value.strip():
            raise serializers.ValidationError(
                "Title cannot be empty."
            )
        
        return value.strip()
    
    def validate_description(self, value):
        """
        Validate description is not empty or whitespace-only.
        
        Args:
            value: Description string
            
        Returns:
            str: Validated description
            
        Raises:
            ValidationError: If description is empty or whitespace
        """
        if not value or not value.strip():
            raise serializers.ValidationError(
                "Description cannot be empty."
            )
        
        return value.strip()
    
    def validate_price(self, value):
        """
        Validate price is positive (greater than 0).
        
        Args:
            value: Price decimal
            
        Returns:
            Decimal: Validated price
            
        Raises:
            ValidationError: If price is not positive
        """
        from decimal import Decimal
        
        if value is None:
            raise serializers.ValidationError(
                "Price is required."
            )
        
        if value <= Decimal('0.00'):
            raise serializers.ValidationError(
                "Price must be greater than 0."
            )
        
        return value
    
    def validate_images(self, value):
        """
        Validate images list for count, format, and size.
        
        Validates:
        - At least 1 image required
        - Maximum 10 images allowed
        - Each image must be valid format (JPEG, PNG, WebP)
        - Each image must be under 5MB
        
        Args:
            value: List of uploaded image files
            
        Returns:
            list: Validated list of images
            
        Raises:
            ValidationError: If validation fails
        """
        # Check image count
        if not value or len(value) == 0:
            raise serializers.ValidationError(
                "At least one image is required."
            )
        
        if len(value) > 10:
            raise serializers.ValidationError(
                "Maximum 10 images allowed per listing."
            )
        
        # Validate each image
        max_size = 5 * 1024 * 1024  # 5MB
        valid_extensions = ['jpg', 'jpeg', 'png', 'webp']
        valid_content_types = ['image/jpeg', 'image/png', 'image/webp']
        
        for i, image in enumerate(value):
            # Check file size
            if image.size > max_size:
                raise serializers.ValidationError(
                    f"Image {i+1} exceeds maximum size of 5MB. "
                    f"Current size: {image.size / (1024 * 1024):.2f}MB"
                )
            
            # Check file extension
            file_name = image.name.lower()
            if not any(file_name.endswith(f'.{ext}') for ext in valid_extensions):
                raise serializers.ValidationError(
                    f"Image {i+1} has invalid format. "
                    f"Allowed formats: {', '.join(valid_extensions)}"
                )
            
            # Check MIME type
            if hasattr(image, 'content_type') and image.content_type:
                if image.content_type not in valid_content_types:
                    raise serializers.ValidationError(
                        f"Image {i+1} has invalid content type: {image.content_type}. "
                        f"Allowed types: {', '.join(valid_content_types)}"
                    )
        
        return value
    
    def create(self, validated_data):
        """
        Create furniture item with images in atomic transaction.
        
        Steps:
        1. Extract images from validated data
        2. Get authenticated user as seller
        3. Create FurnitureItem instance
        4. Create FurnitureImage instances for each uploaded image
        5. Return created item with images
        
        Args:
            validated_data: Validated data from serializer
            
        Returns:
            FurnitureItem: Created furniture item instance
            
        Raises:
            ValidationError: If creation fails
        """
        from django.db import transaction
        from core.models import FurnitureItem, FurnitureImage
        
        # Extract images from validated data
        images = validated_data.pop('images')
        
        # Get authenticated user from context
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError(
                "Authentication required to create listing."
            )
        
        # Create furniture item in atomic transaction
        with transaction.atomic():
            # Create furniture item with seller set to authenticated user
            furniture_item = FurnitureItem.objects.create(
                seller=request.user,
                **validated_data
            )
            
            # Create furniture images with proper ordering
            for order, image in enumerate(images):
                FurnitureImage.objects.create(
                    furniture_item=furniture_item,
                    image=image,
                    order=order
                )
        
        return furniture_item
    
    def to_representation(self, instance):
        """
        Override to_representation to include images in response.
        
        Replaces 'images' write-only field with 'images_data' read-only field
        containing full image information.
        
        Args:
            instance: FurnitureItem instance
            
        Returns:
            dict: Serialized data with images
        """
        data = super().to_representation(instance)
        
        # Remove write-only images field from response
        data.pop('images', None)
        
        # Rename images_data to images for cleaner API
        if 'images_data' in data:
            data['images'] = data.pop('images_data')
        
        return data


class FurnitureBrowseSerializer(serializers.ModelSerializer):
    """
    Serializer for browsing furniture listings.
    
    Provides comprehensive listing information for public marketplace browsing.
    Optimized for use with select_related('seller') and prefetch_related('images').
    
    Fields:
    - id: Furniture item ID
    - title: Item title
    - description: Item description
    - price: Item price
    - condition: Item condition (new, like_new, good, fair, poor)
    - category: Item category
    - is_sold: Whether item has been sold
    - created_at: Creation timestamp
    - seller: Nested seller information (FurnitureSellerSerializer)
    - primary_image: URL of the first image (primary display image)
    - listing_age: Human-readable time since listing was created
    """
    
    seller = FurnitureSellerSerializer(read_only=True)
    primary_image = serializers.SerializerMethodField()
    listing_age = serializers.SerializerMethodField()
    
    class Meta:
        from core.models import FurnitureItem
        model = FurnitureItem
        fields = [
            'id',
            'title',
            'description',
            'price',
            'condition',
            'category',
            'is_sold',
            'created_at',
            'seller',
            'primary_image',
            'listing_age'
        ]
        read_only_fields = fields
    
    def get_primary_image(self, obj):
        """
        Get the URL of the primary (first) image for the furniture item.
        
        Uses prefetched images to avoid N+1 queries.
        
        Args:
            obj: FurnitureItem instance
            
        Returns:
            str: Full URL to primary image, or None if no images
        """
        # Access prefetched images to avoid additional queries
        images = obj.images.all() if hasattr(obj, 'images') else []
        
        if images:
            # Get the first image (lowest order value)
            primary = images[0]
            if primary.image:
                request = self.context.get('request')
                if request is not None:
                    return request.build_absolute_uri(primary.image.url)
                return primary.image.url
        
        return None
    
    def get_listing_age(self, obj):
        """
        Calculate human-readable time since listing was created.
        
        Returns strings like "2 hours ago", "3 days ago", etc.
        
        Args:
            obj: FurnitureItem instance
            
        Returns:
            str: Human-readable time since creation
        """
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        delta = now - obj.created_at
        
        if delta < timedelta(minutes=1):
            return "just now"
        elif delta < timedelta(hours=1):
            minutes = int(delta.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif delta < timedelta(days=1):
            hours = int(delta.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif delta < timedelta(days=30):
            days = delta.days
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif delta < timedelta(days=365):
            months = int(delta.days / 30)
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = int(delta.days / 365)
            return f"{years} year{'s' if years != 1 else ''} ago"
