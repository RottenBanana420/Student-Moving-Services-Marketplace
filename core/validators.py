"""
Custom validators for the User model.
"""

import re
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator


def validate_phone_number(value):
    """
    Validate phone number format.
    
    Accepts international formats with optional country codes, spaces, dashes, and parentheses.
    Requires at least 10 digits.
    
    Valid formats:
    - +1-234-567-8900
    - +44 20 7946 0958
    - +1 (234) 567-8900
    - 234-567-8900
    - 2345678900
    
    Args:
        value: Phone number string to validate
        
    Raises:
        ValidationError: If phone number format is invalid
    """
    if not value:  # Empty string is allowed (optional field)
        return
    
    # Remove all non-digit characters except +
    digits_only = re.sub(r'[^\d+]', '', value)
    
    # Check if it contains only valid characters (digits, spaces, dashes, parentheses, plus)
    if not re.match(r'^[\d\s\-\+\(\)]+$', value):
        raise ValidationError(
            'Phone number can only contain digits, spaces, dashes, parentheses, and plus sign.',
            code='invalid_phone_chars'
        )
    
    # Extract just the digits (excluding +)
    digits = re.sub(r'\D', '', value)
    
    # Must have at least 10 digits
    if len(digits) < 10:
        raise ValidationError(
            'Phone number must contain at least 10 digits.',
            code='phone_too_short'
        )
    
    # Must not be all the same digit (like 0000000000)
    if len(set(digits)) == 1:
        raise ValidationError(
            'Phone number cannot be all the same digit.',
            code='invalid_phone_pattern'
        )


def validate_profile_image(image):
    """
    Validate profile image file.
    
    Checks:
    - File size (max 5MB)
    - File format (jpg, jpeg, png, webp)
    
    Args:
        image: UploadedFile object
        
    Raises:
        ValidationError: If image is invalid
    """
    if not image:
        return
    
    # Check file size (5MB = 5 * 1024 * 1024 bytes)
    max_size = 5 * 1024 * 1024
    if image.size > max_size:
        raise ValidationError(
            f'Image file size cannot exceed 5MB. Current size: {image.size / (1024 * 1024):.2f}MB',
            code='image_too_large'
        )
    
    # Check file extension
    valid_extensions = ['jpg', 'jpeg', 'png', 'webp']
    file_name = image.name.lower()
    
    if not any(file_name.endswith(f'.{ext}') for ext in valid_extensions):
        raise ValidationError(
            f'Invalid image format. Allowed formats: {", ".join(valid_extensions)}',
            code='invalid_image_format'
        )
    
    # Check MIME type
    valid_content_types = [
        'image/jpeg',
        'image/png',
        'image/webp'
    ]
    
    if hasattr(image, 'content_type') and image.content_type:
        if image.content_type not in valid_content_types:
            raise ValidationError(
                f'Invalid image content type: {image.content_type}',
                code='invalid_content_type'
            )
