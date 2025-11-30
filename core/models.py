"""
Custom User model for Student Moving Services Marketplace.
"""

from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from .validators import validate_phone_number, validate_profile_image


def user_profile_image_upload_path(instance, filename):
    """
    Generate upload path for user profile images.
    
    Path format: profile_images/{user_id}/{filename}
    If user_id is not yet available (user not saved), uses 'temp' as placeholder.
    
    Args:
        instance: User model instance
        filename: Original filename
        
    Returns:
        str: Upload path
    """
    user_id = instance.id if instance.id else 'temp'
    return f'profile_images/{user_id}/{filename}'


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    
    Additional fields:
    - email: Required, unique email address
    - phone_number: Optional phone number with validation
    - university_name: User's educational institution
    - user_type: Either 'student' or 'provider'
    - profile_image: Optional profile picture
    - is_verified: Provider verification status
    - created_at: Account creation timestamp
    - updated_at: Last update timestamp
    """
    
    USER_TYPE_CHOICES = [
        ('student', 'Student'),
        ('provider', 'Service Provider'),
    ]
    
    # Override email to make it required and unique
    email = models.EmailField(
        _('email address'),
        unique=True,
        blank=False,
        null=False,
        error_messages={
            'unique': _('A user with that email already exists.'),
        },
        help_text=_('Required. Enter a valid email address.')
    )
    
    phone_number = models.CharField(
        _('phone number'),
        max_length=20,
        blank=True,
        default='',
        validators=[validate_phone_number],
        help_text=_('Optional. Enter phone number in international format.')
    )
    
    university_name = models.CharField(
        _('university name'),
        max_length=200,
        blank=True,
        default='',
        help_text=_('Educational institution name.')
    )
    
    user_type = models.CharField(
        _('user type'),
        max_length=10,
        choices=USER_TYPE_CHOICES,
        blank=False,
        null=False,
        help_text=_('Required. Select whether you are a student or service provider.')
    )
    
    profile_image = models.ImageField(
        _('profile image'),
        upload_to=user_profile_image_upload_path,
        blank=True,
        null=True,
        validators=[validate_profile_image],
        help_text=_('Optional. Upload a profile picture (max 5MB, formats: jpg, png, webp).')
    )
    
    is_verified = models.BooleanField(
        _('verified status'),
        default=False,
        help_text=_('Indicates whether a service provider has been verified.')
    )
    
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        help_text=_('Timestamp when the account was created.')
    )
    
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
        help_text=_('Timestamp when the account was last updated.')
    )
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['user_type']),
            models.Index(fields=['is_verified']),
        ]
    
    def __str__(self):
        """Return email as string representation."""
        return self.email or self.username
    
    def is_student(self):
        """
        Check if user is a student.
        
        Returns:
            bool: True if user_type is 'student', False otherwise
        """
        return self.user_type == 'student'
    
    def is_provider(self):
        """
        Check if user is a service provider.
        
        Returns:
            bool: True if user_type is 'provider', False otherwise
        """
        return self.user_type == 'provider'
    
    def clean(self):
        """
        Validate model fields.
        
        Ensures:
        - Email is provided and valid
        - Email is lowercase for case-insensitive uniqueness
        - User type is provided
        
        Raises:
            ValidationError: If validation fails
        """
        super().clean()
        
        # Normalize email to lowercase for case-insensitive uniqueness
        if self.email:
            self.email = self.email.lower()
        
        # Validate email is provided
        if not self.email:
            raise ValidationError({
                'email': _('Email address is required.')
            })
        
        # Validate user_type is provided
        if not self.user_type:
            raise ValidationError({
                'user_type': _('User type is required.')
            })
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure validation and email normalization.
        
        Handles profile image upload by:
        1. Saving user first to get ID if profile_image is provided and user is new
        2. Then updating with the correct image path
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        # Normalize email to lowercase
        if self.email:
            self.email = self.email.lower()
        
        # For updates (not initial creation), run full_clean
        # For creation, skip full_clean to allow database IntegrityError for duplicates
        if self.pk is not None:
            self.full_clean()
        
        # Handle profile image upload for new users
        # Save user first to get ID, then save again with image
        if self.profile_image and not self.pk:
            # Temporarily store the image
            profile_image_temp = self.profile_image
            self.profile_image = None
            
            # Save to get an ID
            super().save(*args, **kwargs)
            
            # Now set the image and save again
            self.profile_image = profile_image_temp
            super().save(update_fields=['profile_image'])
        else:
            super().save(*args, **kwargs)


class MovingService(models.Model):
    """
    Moving service model for providers to list their services.
    
    Fields:
    - provider: Foreign key to User (must be provider type)
    - service_name: Name of the service
    - description: Detailed description of the service
    - base_price: Base price for the service
    - availability_status: Whether service is currently available
    - rating_average: Average rating (0-5)
    - total_reviews: Total number of reviews
    - created_at: Creation timestamp
    - updated_at: Last update timestamp
    """
    
    provider = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='services',
        help_text=_('Provider offering this service')
    )
    
    service_name = models.CharField(
        _('service name'),
        max_length=200,
        blank=False,
        null=False,
        help_text=_('Name of the moving service')
    )
    
    description = models.TextField(
        _('description'),
        blank=False,
        null=False,
        help_text=_('Detailed description of the service')
    )
    
    base_price = models.DecimalField(
        _('base price'),
        max_digits=10,
        decimal_places=2,
        blank=False,
        null=False,
        help_text=_('Base price for the service in USD')
    )
    
    availability_status = models.BooleanField(
        _('availability status'),
        default=True,
        help_text=_('Whether the service is currently available')
    )
    
    rating_average = models.DecimalField(
        _('rating average'),
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Average rating from 0.00 to 5.00')
    )
    
    total_reviews = models.PositiveIntegerField(
        _('total reviews'),
        default=0,
        help_text=_('Total number of reviews received')
    )
    
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        help_text=_('Timestamp when the service was created')
    )
    
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
        help_text=_('Timestamp when the service was last updated')
    )
    
    class Meta:
        verbose_name = _('moving service')
        verbose_name_plural = _('moving services')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider']),
            models.Index(fields=['availability_status']),
            models.Index(fields=['rating_average']),
        ]
    
    def __str__(self):
        """Return service name as string representation."""
        return self.service_name
    
    def clean(self):
        """
        Validate model fields.
        
        Ensures:
        - Provider is a user with user_type='provider'
        - Service name is not empty
        - Description is not empty
        - Base price is greater than 0
        - Rating average is between 0 and 5
        - Total reviews is not negative
        
        Raises:
            ValidationError: If validation fails
        """
        super().clean()
        
        # Validate provider is a provider type user
        if self.provider_id and self.provider and not self.provider.is_provider():
            raise ValidationError({
                'provider': _('Only users with user_type="provider" can create services.')
            })
        
        # Validate service_name is not empty
        if not self.service_name or not self.service_name.strip():
            raise ValidationError({
                'service_name': _('Service name cannot be empty.')
            })
        
        # Validate description is not empty
        if not self.description or not self.description.strip():
            raise ValidationError({
                'description': _('Description cannot be empty.')
            })
        
        # Validate base_price is positive
        if self.base_price is not None and self.base_price <= 0:
            raise ValidationError({
                'base_price': _('Base price must be greater than 0.')
            })
        
        # Validate rating_average is between 0 and 5
        if self.rating_average is not None:
            if self.rating_average < 0 or self.rating_average > 5:
                raise ValidationError({
                    'rating_average': _('Rating average must be between 0.00 and 5.00.')
                })
        
        # Validate total_reviews is not negative (handled by PositiveIntegerField)
        # But we add explicit check for safety
        if self.total_reviews is not None and self.total_reviews < 0:
            raise ValidationError({
                'total_reviews': _('Total reviews cannot be negative.')
            })
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure validation.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        # Run full_clean for validation
        self.full_clean()
        super().save(*args, **kwargs)


class Booking(models.Model):
    """
    Booking model for students to book moving services.
    
    Fields:
    - student: Foreign key to User (must be student type)
    - provider: Foreign key to User (must be provider type)
    - service: Foreign key to MovingService
    - booking_date: Date and time of the booking
    - pickup_location: Pickup address
    - dropoff_location: Dropoff address
    - status: Booking status (pending, confirmed, completed, cancelled)
    - total_price: Total price for the booking
    - created_at: Creation timestamp
    - updated_at: Last update timestamp
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='student_bookings',
        help_text=_('Student making the booking')
    )
    
    provider = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='provider_bookings',
        help_text=_('Provider offering the service')
    )
    
    service = models.ForeignKey(
        MovingService,
        on_delete=models.CASCADE,
        related_name='bookings',
        help_text=_('Service being booked')
    )
    
    booking_date = models.DateTimeField(
        _('booking date'),
        blank=False,
        null=False,
        help_text=_('Date and time when the service is scheduled')
    )
    
    pickup_location = models.CharField(
        _('pickup location'),
        max_length=300,
        blank=False,
        null=False,
        help_text=_('Address for pickup')
    )
    
    dropoff_location = models.CharField(
        _('dropoff location'),
        max_length=300,
        blank=False,
        null=False,
        help_text=_('Address for dropoff')
    )
    
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text=_('Current status of the booking')
    )
    
    total_price = models.DecimalField(
        _('total price'),
        max_digits=10,
        decimal_places=2,
        blank=False,
        null=False,
        help_text=_('Total price for the booking in USD')
    )
    
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        help_text=_('Timestamp when the booking was created')
    )
    
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
        help_text=_('Timestamp when the booking was last updated')
    )
    
    class Meta:
        verbose_name = _('booking')
        verbose_name_plural = _('bookings')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student']),
            models.Index(fields=['provider']),
            models.Index(fields=['service']),
            models.Index(fields=['status']),
            models.Index(fields=['booking_date']),
        ]
    
    def __str__(self):
        """Return meaningful string representation."""
        return f"Booking by {self.student.email} - {self.service.service_name}"
    
    def clean(self):
        """
        Validate model fields and status transitions.
        
        Ensures:
        - Student is a user with user_type='student'
        - Provider is a user with user_type='provider'
        - Pickup location is not empty
        - Dropoff location is not empty
        - Total price is greater than 0
        - Status transitions follow business rules
        
        Raises:
            ValidationError: If validation fails
        """
        super().clean()
        
        # Validate student is a student type user
        if self.student_id and self.student and not self.student.is_student():
            raise ValidationError({
                'student': _('Only users with user_type="student" can make bookings.')
            })
        
        # Validate provider is a provider type user
        if self.provider_id and self.provider and not self.provider.is_provider():
            raise ValidationError({
                'provider': _('Booking provider must have user_type="provider".')
            })
        
        # Validate pickup_location is not empty
        if not self.pickup_location or not self.pickup_location.strip():
            raise ValidationError({
                'pickup_location': _('Pickup location cannot be empty.')
            })
        
        # Validate dropoff_location is not empty
        if not self.dropoff_location or not self.dropoff_location.strip():
            raise ValidationError({
                'dropoff_location': _('Dropoff location cannot be empty.')
            })
        
        # Validate total_price is positive
        if self.total_price is not None and self.total_price <= 0:
            raise ValidationError({
                'total_price': _('Total price must be greater than 0.')
            })
        
        # Validate status transitions
        if self.pk is not None:  # Only validate on update
            try:
                old_instance = Booking.objects.get(pk=self.pk)
                old_status = old_instance.status
                new_status = self.status
                
                # Cannot go from pending to completed (must confirm first)
                if old_status == 'pending' and new_status == 'completed':
                    raise ValidationError({
                        'status': _('Cannot transition from pending to completed. Must confirm first.')
                    })
                
                # Cannot modify completed bookings
                if old_status == 'completed' and new_status != 'completed':
                    raise ValidationError({
                        'status': _('Cannot modify a completed booking.')
                    })
                
                # Cannot modify cancelled bookings
                if old_status == 'cancelled' and new_status != 'cancelled':
                    raise ValidationError({
                        'status': _('Cannot modify a cancelled booking.')
                    })
            except Booking.DoesNotExist:
                # New instance, no validation needed
                pass
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure validation.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        # Run full_clean for validation
        self.full_clean()
        super().save(*args, **kwargs)
