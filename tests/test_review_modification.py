"""
Tests for review update and deletion endpoints.

Following TDD principles: These tests are written FIRST, before implementation.
They define the expected behavior of the review modification endpoints.
"""

import pytest
from decimal import Decimal
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from core.models import User, MovingService, Booking, Review


@pytest.mark.django_db
class TestReviewUpdateEndpoint:
    """
    Test suite for PATCH /api/reviews/<review_id>/ endpoint.
    
    Tests verify:
    - Authentication requirements
    - Authorization (only original reviewer can update)
    - Partial update support (rating and/or comment)
    - Rating validation (1-5 range)
    - Immutable fields (reviewer, reviewee, booking)
    - Rating recalculation triggers
    - Error handling (404, 403, 401, 400)
    """
    
    @pytest.fixture
    def setup_users(self):
        """Create test users."""
        student = User.objects.create_user(
            username='student1',
            email='student1@test.com',
            password='testpass123',
            user_type='student'
        )
        provider = User.objects.create_user(
            username='provider1',
            email='provider1@test.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        other_student = User.objects.create_user(
            username='student2',
            email='student2@test.com',
            password='testpass123',
            user_type='student'
        )
        return {
            'student': student,
            'provider': provider,
            'other_student': other_student
        }
    
    @pytest.fixture
    def setup_booking_and_review(self, setup_users):
        """Create a completed booking and review."""
        users = setup_users
        
        # Create service
        service = MovingService.objects.create(
            provider=users['provider'],
            service_name='Test Moving Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
        
        # Create completed booking
        booking = Booking.objects.create(
            student=users['student'],
            provider=users['provider'],
            service=service,
            booking_date=timezone.now() - timezone.timedelta(days=2),
            pickup_location='123 Start St',
            dropoff_location='456 End Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        # Create review (student reviewing provider)
        review = Review.objects.create(
            reviewer=users['student'],
            reviewee=users['provider'],
            booking=booking,
            rating=4,
            comment='Good service, would recommend.'
        )
        
        return {
            'users': users,
            'service': service,
            'booking': booking,
            'review': review
        }
    
    def test_reviewer_can_update_own_review_rating(self, setup_booking_and_review):
        """Test that reviewers can update their own review's rating."""
        data = setup_booking_and_review
        client = APIClient()
        client.force_authenticate(user=data['users']['student'])
        
        url = f'/api/reviews/{data["review"].id}/'
        response = client.patch(url, {'rating': 5}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['rating'] == 5
        assert response.data['comment'] == 'Good service, would recommend.'
        
        # Verify database was updated
        data['review'].refresh_from_db()
        assert data['review'].rating == 5
    
    def test_reviewer_can_update_own_review_comment(self, setup_booking_and_review):
        """Test that reviewers can update their own review's comment."""
        data = setup_booking_and_review
        client = APIClient()
        client.force_authenticate(user=data['users']['student'])
        
        url = f'/api/reviews/{data["review"].id}/'
        new_comment = 'Updated: Excellent service, highly recommend!'
        response = client.patch(url, {'comment': new_comment}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['rating'] == 4
        assert response.data['comment'] == new_comment
        
        # Verify database was updated
        data['review'].refresh_from_db()
        assert data['review'].comment == new_comment
    
    def test_reviewer_can_update_both_rating_and_comment(self, setup_booking_and_review):
        """Test that reviewers can update both rating and comment simultaneously."""
        data = setup_booking_and_review
        client = APIClient()
        client.force_authenticate(user=data['users']['student'])
        
        url = f'/api/reviews/{data["review"].id}/'
        update_data = {
            'rating': 3,
            'comment': 'Service was okay, had some issues.'
        }
        response = client.patch(url, update_data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['rating'] == 3
        assert response.data['comment'] == 'Service was okay, had some issues.'
        
        # Verify database was updated
        data['review'].refresh_from_db()
        assert data['review'].rating == 3
        assert data['review'].comment == 'Service was okay, had some issues.'
    
    def test_cannot_update_others_review(self, setup_booking_and_review):
        """Test that users cannot update reviews they didn't write (403 Forbidden)."""
        data = setup_booking_and_review
        client = APIClient()
        client.force_authenticate(user=data['users']['other_student'])
        
        url = f'/api/reviews/{data["review"].id}/'
        response = client.patch(url, {'rating': 5}, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Verify database was NOT updated
        data['review'].refresh_from_db()
        assert data['review'].rating == 4
    
    def test_updated_rating_triggers_recalculation(self, setup_booking_and_review):
        """Test that updating a review's rating triggers rating recalculation."""
        data = setup_booking_and_review
        client = APIClient()
        client.force_authenticate(user=data['users']['student'])
        
        # Get initial ratings
        data['users']['provider'].refresh_from_db()
        data['service'].refresh_from_db()
        initial_provider_rating = data['users']['provider'].avg_rating_as_provider
        initial_service_rating = data['service'].rating_average
        
        # Update review rating
        url = f'/api/reviews/{data["review"].id}/'
        response = client.patch(url, {'rating': 5}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify ratings were recalculated
        data['users']['provider'].refresh_from_db()
        data['service'].refresh_from_db()
        
        # Rating should have increased from 4 to 5
        assert data['users']['provider'].avg_rating_as_provider == Decimal('5.00')
        assert data['service'].rating_average == Decimal('5.00')
    
    def test_rating_validation_too_low(self, setup_booking_and_review):
        """Test that ratings below 1 are rejected."""
        data = setup_booking_and_review
        client = APIClient()
        client.force_authenticate(user=data['users']['student'])
        
        url = f'/api/reviews/{data["review"].id}/'
        response = client.patch(url, {'rating': 0}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'rating' in response.data
        
        # Verify database was NOT updated
        data['review'].refresh_from_db()
        assert data['review'].rating == 4
    
    def test_rating_validation_too_high(self, setup_booking_and_review):
        """Test that ratings above 5 are rejected."""
        data = setup_booking_and_review
        client = APIClient()
        client.force_authenticate(user=data['users']['student'])
        
        url = f'/api/reviews/{data["review"].id}/'
        response = client.patch(url, {'rating': 6}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'rating' in response.data
        
        # Verify database was NOT updated
        data['review'].refresh_from_db()
        assert data['review'].rating == 4
    
    def test_cannot_change_reviewer(self, setup_booking_and_review):
        """Test that the reviewer field cannot be changed."""
        data = setup_booking_and_review
        client = APIClient()
        client.force_authenticate(user=data['users']['student'])
        
        url = f'/api/reviews/{data["review"].id}/'
        response = client.patch(
            url,
            {'reviewer': data['users']['other_student'].id},
            format='json'
        )
        
        # Should either ignore the field or return 400
        # Verify reviewer was NOT changed
        data['review'].refresh_from_db()
        assert data['review'].reviewer_id == data['users']['student'].id
    
    def test_cannot_change_reviewee(self, setup_booking_and_review):
        """Test that the reviewee field cannot be changed."""
        data = setup_booking_and_review
        client = APIClient()
        client.force_authenticate(user=data['users']['student'])
        
        url = f'/api/reviews/{data["review"].id}/'
        response = client.patch(
            url,
            {'reviewee': data['users']['other_student'].id},
            format='json'
        )
        
        # Verify reviewee was NOT changed
        data['review'].refresh_from_db()
        assert data['review'].reviewee_id == data['users']['provider'].id
    
    def test_cannot_change_booking(self, setup_booking_and_review):
        """Test that the booking field cannot be changed."""
        data = setup_booking_and_review
        client = APIClient()
        client.force_authenticate(user=data['users']['student'])
        
        # Create another booking
        other_booking = Booking.objects.create(
            student=data['users']['student'],
            provider=data['users']['provider'],
            service=data['service'],
            booking_date=timezone.now() - timezone.timedelta(days=1),
            pickup_location='789 Other St',
            dropoff_location='012 Another Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        url = f'/api/reviews/{data["review"].id}/'
        response = client.patch(url, {'booking': other_booking.id}, format='json')
        
        # Verify booking was NOT changed
        data['review'].refresh_from_db()
        assert data['review'].booking_id == data['booking'].id
    
    def test_update_without_authentication(self, setup_booking_and_review):
        """Test that unauthenticated requests are rejected (401)."""
        data = setup_booking_and_review
        client = APIClient()
        
        url = f'/api/reviews/{data["review"].id}/'
        response = client.patch(url, {'rating': 5}, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Verify database was NOT updated
        data['review'].refresh_from_db()
        assert data['review'].rating == 4
    
    def test_update_nonexistent_review(self, setup_booking_and_review):
        """Test that updating a non-existent review returns 404."""
        data = setup_booking_and_review
        client = APIClient()
        client.force_authenticate(user=data['users']['student'])
        
        url = '/api/reviews/99999/'
        response = client.patch(url, {'rating': 5}, format='json')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestReviewDeleteEndpoint:
    """
    Test suite for DELETE /api/reviews/<review_id>/ endpoint.
    
    Tests verify:
    - Authentication requirements
    - Authorization (only original reviewer can delete)
    - Rating recalculation triggers
    - Service total_reviews decrement
    - Rating averages update correctly
    - Error handling (404, 403, 401)
    """
    
    @pytest.fixture
    def setup_users(self):
        """Create test users."""
        student = User.objects.create_user(
            username='student1',
            email='student1@test.com',
            password='testpass123',
            user_type='student'
        )
        provider = User.objects.create_user(
            username='provider1',
            email='provider1@test.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        other_student = User.objects.create_user(
            username='student2',
            email='student2@test.com',
            password='testpass123',
            user_type='student'
        )
        return {
            'student': student,
            'provider': provider,
            'other_student': other_student
        }
    
    @pytest.fixture
    def setup_booking_and_review(self, setup_users):
        """Create a completed booking and review."""
        users = setup_users
        
        # Create service
        service = MovingService.objects.create(
            provider=users['provider'],
            service_name='Test Moving Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
        
        # Create completed booking
        booking = Booking.objects.create(
            student=users['student'],
            provider=users['provider'],
            service=service,
            booking_date=timezone.now() - timezone.timedelta(days=2),
            pickup_location='123 Start St',
            dropoff_location='456 End Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        # Create review (student reviewing provider)
        review = Review.objects.create(
            reviewer=users['student'],
            reviewee=users['provider'],
            booking=booking,
            rating=4,
            comment='Good service, would recommend.'
        )
        
        return {
            'users': users,
            'service': service,
            'booking': booking,
            'review': review
        }
    
    def test_reviewer_can_delete_own_review(self, setup_booking_and_review):
        """Test that reviewers can delete their own reviews."""
        data = setup_booking_and_review
        client = APIClient()
        client.force_authenticate(user=data['users']['student'])
        
        review_id = data['review'].id
        url = f'/api/reviews/{review_id}/'
        response = client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify review was deleted
        assert not Review.objects.filter(id=review_id).exists()
    
    def test_cannot_delete_others_review(self, setup_booking_and_review):
        """Test that users cannot delete reviews they didn't write (403 Forbidden)."""
        data = setup_booking_and_review
        client = APIClient()
        client.force_authenticate(user=data['users']['other_student'])
        
        review_id = data['review'].id
        url = f'/api/reviews/{review_id}/'
        response = client.delete(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Verify review was NOT deleted
        assert Review.objects.filter(id=review_id).exists()
    
    def test_deletion_triggers_rating_recalculation(self, setup_booking_and_review):
        """Test that deleting a review triggers rating recalculation."""
        data = setup_booking_and_review
        
        # Create another review to ensure ratings don't go to zero
        other_booking = Booking.objects.create(
            student=data['users']['other_student'],
            provider=data['users']['provider'],
            service=data['service'],
            booking_date=timezone.now() - timezone.timedelta(days=1),
            pickup_location='789 Other St',
            dropoff_location='012 Another Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        other_review = Review.objects.create(
            reviewer=data['users']['other_student'],
            reviewee=data['users']['provider'],
            booking=other_booking,
            rating=5,
            comment='Excellent service!'
        )
        
        # Verify initial state: avg should be (4 + 5) / 2 = 4.5
        data['users']['provider'].refresh_from_db()
        data['service'].refresh_from_db()
        assert data['users']['provider'].avg_rating_as_provider == Decimal('4.50')
        assert data['service'].rating_average == Decimal('4.50')
        
        # Delete first review (rating 4)
        client = APIClient()
        client.force_authenticate(user=data['users']['student'])
        url = f'/api/reviews/{data["review"].id}/'
        response = client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify ratings were recalculated to only include remaining review (rating 5)
        data['users']['provider'].refresh_from_db()
        data['service'].refresh_from_db()
        assert data['users']['provider'].avg_rating_as_provider == Decimal('5.00')
        assert data['service'].rating_average == Decimal('5.00')
    
    def test_deletion_decrements_service_total_reviews(self, setup_booking_and_review):
        """Test that deleting a review decrements service total_reviews count."""
        data = setup_booking_and_review
        
        # Get initial total_reviews count
        data['service'].refresh_from_db()
        initial_count = data['service'].total_reviews
        
        # Delete review
        client = APIClient()
        client.force_authenticate(user=data['users']['student'])
        url = f'/api/reviews/{data["review"].id}/'
        response = client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify total_reviews was decremented
        data['service'].refresh_from_db()
        assert data['service'].total_reviews == initial_count - 1
    
    def test_deletion_updates_rating_averages_correctly(self, setup_booking_and_review):
        """Test that rating averages update correctly after deletion."""
        data = setup_booking_and_review
        
        # Create two more reviews with different ratings
        for i, rating in enumerate([3, 5], start=1):
            other_student = User.objects.create_user(
                username=f'student{i+2}',
                email=f'student{i+2}@test.com',
                password='testpass123',
                user_type='student'
            )
            
            other_booking = Booking.objects.create(
                student=other_student,
                provider=data['users']['provider'],
                service=data['service'],
                booking_date=timezone.now() - timezone.timedelta(days=i),
                pickup_location=f'{i} Other St',
                dropoff_location=f'{i} Another Ave',
                total_price=Decimal('100.00'),
                status='completed'
            )
            
            Review.objects.create(
                reviewer=other_student,
                reviewee=data['users']['provider'],
                booking=other_booking,
                rating=rating,
                comment=f'Review {i}'
            )
        
        # Now we have reviews with ratings: 4, 3, 5
        # Average should be (4 + 3 + 5) / 3 = 4.00
        data['users']['provider'].refresh_from_db()
        data['service'].refresh_from_db()
        assert data['users']['provider'].avg_rating_as_provider == Decimal('4.00')
        assert data['service'].rating_average == Decimal('4.00')
        
        # Delete the first review (rating 4)
        client = APIClient()
        client.force_authenticate(user=data['users']['student'])
        url = f'/api/reviews/{data["review"].id}/'
        response = client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Average should now be (3 + 5) / 2 = 4.00
        data['users']['provider'].refresh_from_db()
        data['service'].refresh_from_db()
        assert data['users']['provider'].avg_rating_as_provider == Decimal('4.00')
        assert data['service'].rating_average == Decimal('4.00')
    
    def test_delete_without_authentication(self, setup_booking_and_review):
        """Test that unauthenticated delete requests are rejected (401)."""
        data = setup_booking_and_review
        client = APIClient()
        
        review_id = data['review'].id
        url = f'/api/reviews/{review_id}/'
        response = client.delete(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Verify review was NOT deleted
        assert Review.objects.filter(id=review_id).exists()
    
    def test_delete_nonexistent_review(self, setup_booking_and_review):
        """Test that deleting a non-existent review returns 404."""
        data = setup_booking_and_review
        client = APIClient()
        client.force_authenticate(user=data['users']['student'])
        
        url = '/api/reviews/99999/'
        response = client.delete(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
