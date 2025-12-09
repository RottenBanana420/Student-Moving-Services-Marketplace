"""
Django signals for automatic rating recalculation.

This module contains signal receivers that automatically update user and service
ratings when reviews are created.
"""

import logging
from decimal import Decimal
from django.db import transaction
from django.db.models import Avg, F
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Review, User, MovingService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Review)
def update_ratings_on_review_save(sender, instance, created, **kwargs):
    """
    Signal receiver to update ratings when a review is created.
    
    This signal:
    1. Updates the reviewee's overall rating (avg_rating_as_provider or avg_rating_as_student)
    2. If reviewee is a provider, updates the service's rating_average and total_reviews
    
    Uses atomic transactions and row-level locking to prevent race conditions.
    
    Note: This signal runs within the same transaction as the Review.save().
    If this signal fails, the entire transaction (including review creation) will be rolled back.
    This ensures data integrity - reviews and ratings are always in sync.
    
    Args:
        sender: The Review model class
        instance: The Review instance that was saved
        created: Boolean indicating if this is a new review
        **kwargs: Additional keyword arguments
    """
    # Only process on review creation, not updates
    if not created:
        return
    
    try:
        with transaction.atomic():
            # Get the booking to determine roles
            booking = instance.booking
            reviewee = instance.reviewee
            
            # Determine which rating field to update based on reviewee's role in booking
            if reviewee.id == booking.provider_id:
                # Reviewee is the provider
                
                # Lock the user row to prevent concurrent updates
                user = User.objects.select_for_update().get(pk=reviewee.id)
                
                # Calculate average rating for provider role
                # Get all reviews where this user is reviewee and acted as provider
                provider_reviews = Review.objects.filter(
                    reviewee=user,
                    booking__provider=user
                )
                
                avg_rating = provider_reviews.aggregate(avg=Avg('rating'))['avg']
                
                # Update user's provider rating
                if avg_rating is not None:
                    user.avg_rating_as_provider = Decimal(str(avg_rating)).quantize(Decimal('0.01'))
                    user.save(update_fields=['avg_rating_as_provider'])
                
                # Update service rating
                service = booking.service
                
                # Lock the service row to prevent concurrent updates
                service = MovingService.objects.select_for_update().get(pk=service.id)
                
                # Calculate average rating for this specific service
                service_reviews = Review.objects.filter(
                    booking__service=service
                )
                
                service_avg = service_reviews.aggregate(avg=Avg('rating'))['avg']
                
                if service_avg is not None:
                    service.rating_average = Decimal(str(service_avg)).quantize(Decimal('0.01'))
                    service.save(update_fields=['rating_average'])
                
                # Increment total_reviews using update() to bypass validation
                # This avoids the F() expression validation issue
                MovingService.objects.filter(pk=service.id).update(
                    total_reviews=F('total_reviews') + 1
                )
                
            elif reviewee.id == booking.student_id:
                # Reviewee is the student
                
                # Lock the user row to prevent concurrent updates
                user = User.objects.select_for_update().get(pk=reviewee.id)
                
                # Calculate average rating for student role
                # Get all reviews where this user is reviewee and acted as student
                student_reviews = Review.objects.filter(
                    reviewee=user,
                    booking__student=user
                )
                
                avg_rating = student_reviews.aggregate(avg=Avg('rating'))['avg']
                
                # Update user's student rating
                if avg_rating is not None:
                    user.avg_rating_as_student = Decimal(str(avg_rating)).quantize(Decimal('0.01'))
                    user.save(update_fields=['avg_rating_as_student'])
            
            logger.info(
                f"Updated ratings for review {instance.id}: "
                f"reviewee={reviewee.email}, rating={instance.rating}"
            )
        
    except Exception as e:
        logger.error(
            f"Error updating ratings for review {instance.id}: {e}",
            exc_info=True
        )
        # Re-raise to ensure transaction rollback and maintain data integrity
        raise
