"""
Custom User model for Student Moving Services Marketplace.
"""

from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
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
    
    avg_rating_as_provider = models.DecimalField(
        _('average rating as provider'),
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.00'), message=_('Rating cannot be negative.')),
            MaxValueValidator(Decimal('5.00'), message=_('Rating cannot exceed 5.00.'))
        ],
        help_text=_('Average rating when acting as a service provider.')
    )
    
    avg_rating_as_student = models.DecimalField(
        _('average rating as student'),
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.00'), message=_('Rating cannot be negative.')),
            MaxValueValidator(Decimal('5.00'), message=_('Rating cannot exceed 5.00.'))
        ],
        help_text=_('Average rating when acting as a student.')
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
        constraints = [
            models.UniqueConstraint(
                fields=['service', 'booking_date'],
                name='unique_booking_per_service_slot',
                condition=~models.Q(status='cancelled')
            )
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
        
        # Check for overlapping bookings (application-level check)
        # Verify service exists before checking
        if hasattr(self, 'service_id') and self.service_id and self.booking_date:
            qs = Booking.objects.filter(
                service_id=self.service_id, 
                booking_date=self.booking_date
            ).exclude(status__in=['cancelled', 'completed']) # Completed bookings might blocking too, usually completed implies "past" but blocked.
            # Requirement: "System prevents double-booking". 
            # If it is 'pending' or 'confirmed' or 'completed', it blocks.
            
            if self.pk:
                qs = qs.exclude(pk=self.pk)
                
            if qs.exists():
                 raise ValidationError({'booking_date': _('This service is already booked for this time slot.')})
    
    def can_transition_to(self, new_status, current_time=None):
        """
        Validate if booking can transition to new status.
        
        Implements state machine logic for booking status transitions.
        
        Valid transitions:
        - pending -> confirmed (provider only)
        - pending -> cancelled (student or provider)
        - confirmed -> completed (provider only, after booking_date)
        - confirmed -> cancelled (student or provider)
        - completed -> (no transitions - terminal state)
        - cancelled -> (no transitions - terminal state)
        
        Args:
            new_status: Target status to transition to
            current_time: Current time for validation (defaults to timezone.now())
            
        Returns:
            tuple: (is_valid: bool, error_message: str or None)
        """
        from django.utils import timezone
        
        if current_time is None:
            current_time = timezone.now()
        
        current_status = self.status
        
        # No transition needed
        if current_status == new_status:
            return True, None
        
        # Terminal states cannot be changed
        if current_status == 'completed':
            return False, 'Cannot modify a completed booking.'
        
        if current_status == 'cancelled':
            return False, 'Cannot modify a cancelled booking.'
        
        # Pending transitions
        if current_status == 'pending':
            if new_status == 'confirmed':
                return True, None
            elif new_status == 'cancelled':
                return True, None
            elif new_status == 'completed':
                return False, 'Cannot transition from pending to completed. Must confirm first.'
            else:
                return False, f'Invalid status transition from {current_status} to {new_status}.'
        
        # Confirmed transitions
        if current_status == 'confirmed':
            if new_status == 'completed':
                # Business rule: Cannot complete before booking date
                if current_time < self.booking_date:
                    return False, 'Cannot complete booking before the scheduled booking date.'
                return True, None
            elif new_status == 'cancelled':
                return True, None
            elif new_status == 'pending':
                return False, 'Cannot transition from confirmed back to pending.'
            else:
                return False, f'Invalid status transition from {current_status} to {new_status}.'
        
        # Default: invalid transition
        return False, f'Invalid status transition from {current_status} to {new_status}.'
    
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


# ============================================================================
# Furniture Marketplace Models
# ============================================================================

def furniture_image_upload_path(instance, filename):
    """
    Generate upload path for furniture images.
    
    Path format: furniture_images/{item_id}/{filename}
    If item_id is not yet available (item not saved), uses 'temp' as placeholder.
    
    Args:
        instance: FurnitureImage model instance
        filename: Original filename
        
    Returns:
        str: Upload path
    """
    item_id = instance.furniture_item.id if instance.furniture_item and instance.furniture_item.id else 'temp'
    return f'furniture_images/{item_id}/{filename}'


class FurnitureItem(models.Model):
    """
    Furniture item model for marketplace listings.
    
    Fields:
    - seller: Foreign key to User (can be student or provider)
    - title: Item title
    - description: Detailed description
    - price: Item price (must be > 0)
    - condition: Item condition (new, like_new, good, fair, poor)
    - category: Item category
    - is_sold: Whether item has been sold
    - created_at: Creation timestamp
    - updated_at: Last update timestamp
    """
    
    CONDITION_CHOICES = [
        ('new', 'New'),
        ('like_new', 'Like New'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]
    
    CATEGORY_CHOICES = [
        ('furniture', 'Furniture'),
        ('appliances', 'Appliances'),
        ('electronics', 'Electronics'),
        ('books', 'Books'),
        ('clothing', 'Clothing'),
        ('other', 'Other'),
    ]
    
    seller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='furniture_items',
        help_text=_('User selling this item')
    )
    
    title = models.CharField(
        _('title'),
        max_length=200,
        blank=False,
        null=False,
        help_text=_('Title of the furniture item')
    )
    
    description = models.TextField(
        _('description'),
        blank=False,
        null=False,
        help_text=_('Detailed description of the item')
    )
    
    price = models.DecimalField(
        _('price'),
        max_digits=10,
        decimal_places=2,
        blank=False,
        null=False,
        help_text=_('Price in USD (must be greater than 0)')
    )
    
    condition = models.CharField(
        _('condition'),
        max_length=20,
        choices=CONDITION_CHOICES,
        blank=False,
        null=False,
        help_text=_('Condition of the item')
    )
    
    category = models.CharField(
        _('category'),
        max_length=20,
        choices=CATEGORY_CHOICES,
        blank=False,
        null=False,
        help_text=_('Category of the item')
    )
    
    is_sold = models.BooleanField(
        _('is sold'),
        default=False,
        help_text=_('Whether the item has been sold')
    )
    
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        help_text=_('Timestamp when the item was created')
    )
    
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
        help_text=_('Timestamp when the item was last updated')
    )
    
    class Meta:
        verbose_name = _('furniture item')
        verbose_name_plural = _('furniture items')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['seller']),
            models.Index(fields=['is_sold']),
            models.Index(fields=['category']),
            models.Index(fields=['condition']),
        ]
    
    def __str__(self):
        """Return title as string representation."""
        return self.title
    
    def clean(self):
        """
        Validate model fields.
        
        Ensures:
        - Title is not empty
        - Description is not empty
        - Price is greater than 0
        - Condition is valid choice
        - Category is valid choice
        
        Raises:
            ValidationError: If validation fails
        """
        super().clean()
        
        # Validate title is not empty
        if not self.title or not self.title.strip():
            raise ValidationError({
                'title': _('Title cannot be empty.')
            })
        
        # Validate description is not empty
        if not self.description or not self.description.strip():
            raise ValidationError({
                'description': _('Description cannot be empty.')
            })
        
        # Validate price is positive
        if self.price is not None and self.price <= 0:
            raise ValidationError({
                'price': _('Price must be greater than 0.')
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
    
    def mark_as_sold(self):
        """Mark item as sold and save."""
        self.is_sold = True
        self.save()
    
    def is_available(self):
        """
        Check if item is available for purchase.
        
        Returns:
            bool: True if not sold, False otherwise
        """
        return not self.is_sold


class FurnitureImage(models.Model):
    """
    Image model for furniture items (one-to-many relationship).
    
    Fields:
    - furniture_item: Foreign key to FurnitureItem
    - image: Image file
    - order: Display order (for sorting)
    - uploaded_at: Upload timestamp
    """
    
    furniture_item = models.ForeignKey(
        FurnitureItem,
        on_delete=models.CASCADE,
        related_name='images',
        help_text=_('Furniture item this image belongs to')
    )
    
    image = models.ImageField(
        _('image'),
        upload_to=furniture_image_upload_path,
        blank=False,
        null=False,
        validators=[validate_profile_image],  # Reuse existing validator
        help_text=_('Image file (max 5MB, formats: jpg, png, webp)')
    )
    
    order = models.PositiveIntegerField(
        _('order'),
        default=0,
        help_text=_('Display order for images')
    )
    
    uploaded_at = models.DateTimeField(
        _('uploaded at'),
        auto_now_add=True,
        help_text=_('Timestamp when the image was uploaded')
    )
    
    class Meta:
        verbose_name = _('furniture image')
        verbose_name_plural = _('furniture images')
        ordering = ['order', 'uploaded_at']
        indexes = [
            models.Index(fields=['furniture_item']),
            models.Index(fields=['order']),
        ]
    
    def __str__(self):
        """Return meaningful string representation."""
        return f"Image for {self.furniture_item.title}"
    
    def clean(self):
        """
        Validate model fields.
        
        Ensures:
        - Image is provided
        - Furniture item is provided
        
        Raises:
            ValidationError: If validation fails
        """
        super().clean()
        
        # Image validation is handled by the validator
        # Just ensure required fields are present
        if not self.image:
            raise ValidationError({
                'image': _('Image is required.')
            })
        
        # Check furniture_item_id instead of furniture_item to avoid RelatedObjectDoesNotExist
        if not self.furniture_item_id:
            raise ValidationError({
                'furniture_item': _('Furniture item is required.')
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


class FurnitureTransaction(models.Model):
    """
    Transaction model for furniture marketplace with escrow support.
    
    Fields:
    - buyer: Foreign key to User (buyer)
    - seller: Foreign key to User (seller)
    - furniture_item: Foreign key to FurnitureItem
    - escrow_status: Current escrow status (pending, held, released)
    - transaction_date: Transaction creation timestamp
    - completed_at: Timestamp when escrow was released
    - created_at: Creation timestamp
    - updated_at: Last update timestamp
    """
    
    ESCROW_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('held', 'Held'),
        ('released', 'Released'),
    ]
    
    # Valid state transitions for escrow
    VALID_TRANSITIONS = {
        'pending': ['held'],
        'held': ['released'],
        'released': [],  # Terminal state
    }
    
    buyer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='furniture_purchases',
        help_text=_('User purchasing the item')
    )
    
    seller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='furniture_sales',
        help_text=_('User selling the item')
    )
    
    furniture_item = models.ForeignKey(
        FurnitureItem,
        on_delete=models.CASCADE,
        related_name='transactions',
        help_text=_('Furniture item being transacted')
    )
    
    escrow_status = models.CharField(
        _('escrow status'),
        max_length=20,
        choices=ESCROW_STATUS_CHOICES,
        default='pending',
        help_text=_('Current status of escrow')
    )
    
    transaction_date = models.DateTimeField(
        _('transaction date'),
        auto_now_add=True,
        help_text=_('Timestamp when transaction was created')
    )
    
    completed_at = models.DateTimeField(
        _('completed at'),
        null=True,
        blank=True,
        help_text=_('Timestamp when escrow was released')
    )
    
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        help_text=_('Timestamp when the transaction was created')
    )
    
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
        help_text=_('Timestamp when the transaction was last updated')
    )
    
    class Meta:
        verbose_name = _('furniture transaction')
        verbose_name_plural = _('furniture transactions')
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['buyer']),
            models.Index(fields=['seller']),
            models.Index(fields=['furniture_item']),
            models.Index(fields=['escrow_status']),
            models.Index(fields=['transaction_date']),
        ]
    
    def __str__(self):
        """Return meaningful string representation."""
        return f"Transaction: {self.buyer.email} ← {self.furniture_item.title} ← {self.seller.email}"
    
    def clean(self):
        """
        Validate model fields and state transitions.
        
        Ensures:
        - Buyer and seller are different users
        - Furniture item is not already sold
        - Seller matches furniture item seller
        - Escrow status transitions are valid
        
        Raises:
            ValidationError: If validation fails
        """
        super().clean()
        
        # Validate buyer and seller are different
        if self.buyer_id and self.seller_id and self.buyer_id == self.seller_id:
            raise ValidationError({
                'buyer': _('Buyer and seller cannot be the same user.')
            })
        
        # Validate furniture item is not sold
        if self.furniture_item_id and self.furniture_item and self.furniture_item.is_sold:
            raise ValidationError({
                'furniture_item': _('Cannot create transaction for already-sold item.')
            })
        
        # Validate seller matches furniture item seller
        if self.seller_id and self.furniture_item_id and self.furniture_item:
            if self.seller_id != self.furniture_item.seller_id:
                raise ValidationError({
                    'seller': _('Transaction seller must match furniture item seller.')
                })
        
        # Validate escrow status transitions (only on update)
        if self.pk is not None:
            try:
                old_instance = FurnitureTransaction.objects.get(pk=self.pk)
                old_status = old_instance.escrow_status
                new_status = self.escrow_status
                
                # Check if transition is valid
                if old_status != new_status:
                    # Use old_instance's can_transition_to method with old status
                    valid_next_statuses = self.VALID_TRANSITIONS.get(old_status, [])
                    if new_status not in valid_next_statuses:
                        raise ValidationError({
                            'escrow_status': _(
                                f'Invalid escrow status transition from {old_status} to {new_status}.'
                            )
                        })
            except FurnitureTransaction.DoesNotExist:
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
    
    def can_transition_to(self, new_status):
        """
        Check if transition to new status is valid.
        
        Args:
            new_status: Target escrow status
            
        Returns:
            bool: True if transition is valid, False otherwise
        """
        current_status = self.escrow_status
        valid_next_statuses = self.VALID_TRANSITIONS.get(current_status, [])
        return new_status in valid_next_statuses or new_status == current_status
    
    def hold_escrow(self):
        """
        Transition escrow from pending to held.
        
        Raises:
            ValidationError: If current status is not pending
        """
        if self.escrow_status != 'pending':
            raise ValidationError(
                _('Can only hold escrow from pending status.')
            )
        self.escrow_status = 'held'
        self.save()
    
    def release_escrow(self):
        """
        Transition escrow from held to released and mark item as sold.
        
        Raises:
            ValidationError: If current status is not held
        """
        if self.escrow_status != 'held':
            raise ValidationError(
                _('Can only release escrow from held status.')
            )
        
        from django.utils import timezone
        
        self.escrow_status = 'released'
        self.completed_at = timezone.now()
        self.save()
        
        # Mark furniture item as sold
        self.furniture_item.mark_as_sold()


# ============================================================================
# Review Model
# ============================================================================

class Review(models.Model):
    """
    Review model for users to review each other after completed bookings.
    
    Fields:
    - reviewer: Foreign key to User (person giving the review)
    - reviewee: Foreign key to User (person receiving the review)
    - booking: Foreign key to Booking (the completed booking being reviewed)
    - rating: Integer rating from 1 to 5
    - comment: Text field for written feedback
    - created_at: Timestamp when review was created
    """
    
    reviewer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reviews_given',
        help_text=_('User writing the review')
    )
    
    reviewee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reviews_received',
        help_text=_('User receiving the review')
    )
    
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='review',
        help_text=_('Booking being reviewed (one review per booking)')
    )
    
    rating = models.PositiveSmallIntegerField(
        _('rating'),
        validators=[
            MinValueValidator(1, message=_('Rating must be at least 1.')),
            MaxValueValidator(5, message=_('Rating must be at most 5.'))
        ],
        help_text=_('Rating from 1 to 5 stars')
    )
    
    comment = models.TextField(
        _('comment'),
        blank=False,
        help_text=_('Written feedback about the experience')
    )
    
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        help_text=_('Timestamp when the review was created')
    )
    
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
        help_text=_('Timestamp when the review was last updated')
    )
    
    class Meta:
        verbose_name = _('review')
        verbose_name_plural = _('reviews')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reviewer']),
            models.Index(fields=['reviewee']),
            models.Index(fields=['booking']),
            models.Index(fields=['rating']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        """Return meaningful string representation."""
        return f"Review by {self.reviewer.email} for {self.reviewee.email} - {self.rating}★"
    
    def clean(self):
        """
        Validate model fields.
        
        Ensures:
        - Reviewer and reviewee are different users
        - Booking status is 'completed'
        - Reviewer is part of the booking (student or provider)
        - Reviewee is the other party in the booking
        - Comment is not empty or whitespace-only
        
        Raises:
            ValidationError: If validation fails
        """
        super().clean()
        
        # Validate reviewer and reviewee are different
        if self.reviewer_id and self.reviewee_id and self.reviewer_id == self.reviewee_id:
            raise ValidationError({
                'reviewee': _('Reviewer and reviewee cannot be the same user.')
            })
        
        # Validate booking status is completed
        if self.booking_id and self.booking:
            if self.booking.status != 'completed':
                raise ValidationError({
                    'booking': _('Only completed bookings can be reviewed.')
                })
            
            # Validate reviewer is part of the booking
            if self.reviewer_id:
                if self.reviewer_id not in [self.booking.student_id, self.booking.provider_id]:
                    raise ValidationError({
                        'reviewer': _('Reviewer must be either the student or provider from the booking.')
                    })
            
            # Validate reviewee is the other party in the booking
            if self.reviewer_id and self.reviewee_id:
                # If reviewer is student, reviewee must be provider
                if self.reviewer_id == self.booking.student_id:
                    if self.reviewee_id != self.booking.provider_id:
                        raise ValidationError({
                            'reviewee': _('Reviewee must be the provider from the booking.')
                        })
                # If reviewer is provider, reviewee must be student
                elif self.reviewer_id == self.booking.provider_id:
                    if self.reviewee_id != self.booking.student_id:
                        raise ValidationError({
                            'reviewee': _('Reviewee must be the student from the booking.')
                        })
        
        # Validate comment is not empty or whitespace-only
        if not self.comment or not self.comment.strip():
            raise ValidationError({
                'comment': _('Comment cannot be empty.')
            })
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure validation.
        
        Note: We don't call full_clean() here to allow database-level
        unique constraints to raise IntegrityError as expected.
        Validation should be done explicitly before calling save().
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        # Validate fields manually (excluding unique constraints)
        # This ensures business logic validation while allowing DB constraints
        if not self.pk:  # Only validate on creation
            # Validate reviewer and reviewee are different
            if self.reviewer_id and self.reviewee_id and self.reviewer_id == self.reviewee_id:
                raise ValidationError({
                    'reviewee': _('Reviewer and reviewee cannot be the same user.')
                })
            
            # Validate booking status is completed
            if self.booking_id and self.booking:
                if self.booking.status != 'completed':
                    raise ValidationError({
                        'booking': _('Only completed bookings can be reviewed.')
                    })
                
                # Validate reviewer is part of the booking
                if self.reviewer_id:
                    if self.reviewer_id not in [self.booking.student_id, self.booking.provider_id]:
                        raise ValidationError({
                            'reviewer': _('Reviewer must be either the student or provider from the booking.')
                        })
                
                # Validate reviewee is the other party in the booking
                if self.reviewer_id and self.reviewee_id:
                    # If reviewer is student, reviewee must be provider
                    if self.reviewer_id == self.booking.student_id:
                        if self.reviewee_id != self.booking.provider_id:
                            raise ValidationError({
                                'reviewee': _('Reviewee must be the provider from the booking.')
                            })
                    # If reviewer is provider, reviewee must be student
                    elif self.reviewer_id == self.booking.provider_id:
                        if self.reviewee_id != self.booking.student_id:
                            raise ValidationError({
                                'reviewee': _('Reviewee must be the student from the booking.')
                            })
            
            # Validate comment is not empty or whitespace-only
            if not self.comment or not self.comment.strip():
                raise ValidationError({
                    'comment': _('Comment cannot be empty.')
                })
        
        super().save(*args, **kwargs)
