"""
Django signals for automatic rating recalculation.

This module contains signal receivers that automatically update user and service
ratings when reviews are created, updated, or deleted.
"""

import logging
from decimal import Decimal
from django.db import transaction
from django.db.models import Avg, F
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Review, User, MovingService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Review)
def update_ratings_on_review_save(sender, instance, created, **kwargs):
    """
    Signal receiver to update ratings when a review is created or updated.
    
    This signal:
    1. Updates the reviewee's overall rating (avg_rating_as_provider or avg_rating_as_student)
    2. If reviewee is a provider, updates the service's rating_average
    3. On creation, increments service total_reviews
    4. On update, recalculates ratings (no change to total_reviews)
    
    Uses atomic transactions and row-level locking to prevent race conditions.
    
    Note: This signal runs within the same transaction as the Review.save().
    If this signal fails, the entire transaction (including review creation/update) will be rolled back.
    This ensures data integrity - reviews and ratings are always in sync.
    
    Args:
        sender: The Review model class
        instance: The Review instance that was saved
        created: Boolean indicating if this is a new review
        **kwargs: Additional keyword arguments
    """
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
                
                # Only increment total_reviews on creation, not on update
                if created:
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
            
            action = "created" if created else "updated"
            logger.info(
                f"Updated ratings for review {instance.id} ({action}): "
                f"reviewee={reviewee.email}, rating={instance.rating}"
            )
        
    except Exception as e:
        logger.error(
            f"Error updating ratings for review {instance.id}: {e}",
            exc_info=True
        )
        # Re-raise to ensure transaction rollback and maintain data integrity
        raise


@receiver(post_delete, sender=Review)
def update_ratings_on_review_delete(sender, instance, **kwargs):
    """
    Signal receiver to update ratings when a review is deleted.
    
    This signal:
    1. Recalculates the reviewee's overall rating without the deleted review
    2. If reviewee is a provider, recalculates the service's rating_average
    3. Decrements service total_reviews
    4. Handles edge case where all reviews are deleted (sets ratings to 0.00)
    
    Uses atomic transactions and row-level locking to prevent race conditions.
    
    Args:
        sender: The Review model class
        instance: The Review instance that was deleted
        **kwargs: Additional keyword arguments
    """
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
                
                # Calculate average rating for provider role (excluding deleted review)
                provider_reviews = Review.objects.filter(
                    reviewee=user,
                    booking__provider=user
                )
                
                avg_rating = provider_reviews.aggregate(avg=Avg('rating'))['avg']
                
                # If no reviews left, set to 0.00
                user.avg_rating_as_provider = Decimal(str(avg_rating)).quantize(Decimal('0.01')) if avg_rating else Decimal('0.00')
                user.save(update_fields=['avg_rating_as_provider'])
                
                # Update service rating
                service = MovingService.objects.select_for_update().get(pk=booking.service.id)
                
                service_reviews = Review.objects.filter(booking__service=service)
                service_avg = service_reviews.aggregate(avg=Avg('rating'))['avg']
                
                service.rating_average = Decimal(str(service_avg)).quantize(Decimal('0.01')) if service_avg else Decimal('0.00')
                service.save(update_fields=['rating_average'])
                
                # Decrement total_reviews
                MovingService.objects.filter(pk=service.id).update(
                    total_reviews=F('total_reviews') - 1
                )
                
            elif reviewee.id == booking.student_id:
                # Reviewee is the student
                
                # Lock the user row to prevent concurrent updates
                user = User.objects.select_for_update().get(pk=reviewee.id)
                
                student_reviews = Review.objects.filter(
                    reviewee=user,
                    booking__student=user
                )
                
                avg_rating = student_reviews.aggregate(avg=Avg('rating'))['avg']
                
                user.avg_rating_as_student = Decimal(str(avg_rating)).quantize(Decimal('0.01')) if avg_rating else Decimal('0.00')
                user.save(update_fields=['avg_rating_as_student'])
            
            logger.info(
                f"Updated ratings after deleting review {instance.id}: "
                f"reviewee={reviewee.email}"
            )
        
    except Exception as e:
        logger.error(
            f"Error updating ratings after deleting review {instance.id}: {e}",
            exc_info=True
        )
        # Re-raise to ensure transaction rollback and maintain data integrity
        raise
