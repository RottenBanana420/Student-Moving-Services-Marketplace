"""
Comprehensive Integration Tests for Review System.

Following TDD principles: write tests first, then implement code to pass them.
NEVER modify these tests - only fix the implementation.

These tests verify:
- Complete review workflows end-to-end
- Automatic rating updates through signals
- Bidirectional review system (providers reviewing students and vice versa)
- Rating calculation accuracy under all conditions
- Concurrent operations don't corrupt data
- Data consistency across all related models
- Edge cases don't cause system failures
- Authorization enforced at every step
- Review modifications properly trigger recalculations

Test Requirements:
- Tests must simulate real-world review scenarios
- Tests must deliberately stress the system
- Tests must verify mathematical correctness of rating calculations
- Tests must ensure data integrity under concurrent operations
- Tests must validate authorization at every step
"""

from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
import time

from core.models import MovingService, Booking, Review


User = get_user_model()


class CompleteReviewWorkflowTests(TestCase):
    """Test complete review workflow from booking to bidirectional reviews."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        
        self.student = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123',
            user_type='student'
        )
        
        self.provider = User.objects.create_user(
            username='provider',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Premium Moving Service',
            description='High quality moving service',
            base_price=Decimal('150.00')
        )
    
    def test_complete_bidirectional_review_workflow(self):
        """
        Test complete workflow:
        1. Student books service from provider
        2. Provider confirms and completes booking
        3. Student submits review with rating and comment
        4. Verify review is created with correct associations
        5. Verify provider's rating updates automatically
        6. Verify service rating_average updates automatically
        7. Provider submits reciprocal review for student
        8. Verify student's rating updates automatically
        9. Verify both reviews appear in appropriate endpoints
        """
        # Step 1: Create booking
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('150.00'),
            status='pending'
        )
        
        # Step 2: Provider confirms and completes booking
        booking.status = 'confirmed'
        booking.save()
        
        booking.status = 'completed'
        booking.save()
        
        # Verify initial ratings are zero
        self.provider.refresh_from_db()
        self.student.refresh_from_db()
        self.service.refresh_from_db()
        
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('0.00'))
        self.assertEqual(self.student.avg_rating_as_student, Decimal('0.00'))
        self.assertEqual(self.service.rating_average, Decimal('0.00'))
        self.assertEqual(self.service.total_reviews, 0)
        
        # Step 3: Student submits review
        self.client.force_authenticate(user=self.student)
        
        student_review_data = {
            'booking_id': booking.id,
            'rating': 5,
            'comment': 'Excellent service! Very professional and careful with my belongings.'
        }
        
        response = self.client.post('/api/reviews/', student_review_data, format='json')
        
        # Step 4: Verify review created with correct associations
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['rating'], 5)
        self.assertEqual(response.data['reviewer']['id'], self.student.id)
        self.assertEqual(response.data['reviewee']['id'], self.provider.id)
        self.assertEqual(response.data['booking']['id'], booking.id)
        
        student_review = Review.objects.get(id=response.data['id'])
        self.assertEqual(student_review.reviewer, self.student)
        self.assertEqual(student_review.reviewee, self.provider)
        self.assertEqual(student_review.booking, booking)
        
        # Step 5: Verify provider's rating updates automatically
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('5.00'))
        
        # Step 6: Verify service rating_average updates automatically
        self.service.refresh_from_db()
        self.assertEqual(self.service.rating_average, Decimal('5.00'))
        self.assertEqual(self.service.total_reviews, 1)
        
        # Step 7: Provider submits reciprocal review for student
        self.client.force_authenticate(user=self.provider)
        
        provider_review_data = {
            'booking_id': booking.id,
            'rating': 4,
            'comment': 'Good student, easy to work with and punctual.'
        }
        
        response = self.client.post('/api/reviews/', provider_review_data, format='json')
        
        # Verify provider review created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['rating'], 4)
        self.assertEqual(response.data['reviewer']['id'], self.provider.id)
        self.assertEqual(response.data['reviewee']['id'], self.student.id)
        
        # Step 8: Verify student's rating updates automatically
        self.student.refresh_from_db()
        self.assertEqual(self.student.avg_rating_as_student, Decimal('4.00'))
        
        # Step 9: Verify both reviews exist
        self.assertEqual(Review.objects.count(), 2)
        
        # Verify reviews are associated correctly
        student_given_reviews = Review.objects.filter(reviewer=self.student)
        self.assertEqual(student_given_reviews.count(), 1)
        self.assertEqual(student_given_reviews.first().reviewee, self.provider)
        
        provider_given_reviews = Review.objects.filter(reviewer=self.provider)
        self.assertEqual(provider_given_reviews.count(), 1)
        self.assertEqual(provider_given_reviews.first().reviewee, self.student)
        
        # Verify service rating unchanged (provider review doesn't affect service)
        self.service.refresh_from_db()
        self.assertEqual(self.service.rating_average, Decimal('5.00'))
        self.assertEqual(self.service.total_reviews, 1)


class RatingCalculationAccuracyTests(TestCase):
    """Test rating calculation accuracy under various scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.student = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123',
            user_type='student'
        )
        
        self.provider = User.objects.create_user(
            username='provider',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
    
    def test_rating_average_with_multiple_reviews_all_fives(self):
        """Verify rating averages calculated correctly with all 5-star reviews."""
        # Create 5 completed bookings and reviews
        for i in range(5):
            booking = Booking.objects.create(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=timezone.now() + timedelta(days=i+1),
                pickup_location=f'{i} Main St',
                dropoff_location=f'{i} Oak Ave',
                total_price=Decimal('100.00'),
                status='completed'
            )
            
            Review.objects.create(
                reviewer=self.student,
                reviewee=self.provider,
                booking=booking,
                rating=5,
                comment=f'Review {i+1}'
            )
        
        # Verify provider rating
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('5.00'))
        
        # Verify service rating
        self.service.refresh_from_db()
        self.assertEqual(self.service.rating_average, Decimal('5.00'))
        self.assertEqual(self.service.total_reviews, 5)
    
    def test_rating_average_with_multiple_reviews_all_ones(self):
        """Verify rating averages calculated correctly with all 1-star reviews."""
        # Create 3 completed bookings and reviews
        for i in range(3):
            booking = Booking.objects.create(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=timezone.now() + timedelta(days=i+1),
                pickup_location=f'{i} Main St',
                dropoff_location=f'{i} Oak Ave',
                total_price=Decimal('100.00'),
                status='completed'
            )
            
            Review.objects.create(
                reviewer=self.student,
                reviewee=self.provider,
                booking=booking,
                rating=1,
                comment=f'Poor service {i+1}'
            )
        
        # Verify provider rating
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('1.00'))
        
        # Verify service rating
        self.service.refresh_from_db()
        self.assertEqual(self.service.rating_average, Decimal('1.00'))
        self.assertEqual(self.service.total_reviews, 3)
    
    def test_rating_average_with_mixed_ratings(self):
        """Verify rating averages calculated correctly with mixed ratings."""
        ratings = [5, 4, 3, 4, 5, 2, 4]  # Average = 3.857... ≈ 3.86
        
        for i, rating in enumerate(ratings):
            booking = Booking.objects.create(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=timezone.now() + timedelta(days=i+1),
                pickup_location=f'{i} Main St',
                dropoff_location=f'{i} Oak Ave',
                total_price=Decimal('100.00'),
                status='completed'
            )
            
            Review.objects.create(
                reviewer=self.student,
                reviewee=self.provider,
                booking=booking,
                rating=rating,
                comment=f'Review {i+1}'
            )
        
        # Calculate expected average: (5+4+3+4+5+2+4)/7 = 27/7 = 3.857142...
        expected_avg = Decimal('3.86')
        
        # Verify provider rating
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.avg_rating_as_provider, expected_avg)
        
        # Verify service rating
        self.service.refresh_from_db()
        self.assertEqual(self.service.rating_average, expected_avg)
        self.assertEqual(self.service.total_reviews, 7)
    
    def test_service_ratings_reflect_only_their_specific_reviews(self):
        """Verify service ratings reflect only their specific reviews."""
        # Create second service
        service2 = MovingService.objects.create(
            provider=self.provider,
            service_name='Second Service',
            description='Another service',
            base_price=Decimal('200.00')
        )
        
        # Create reviews for first service (ratings: 5, 5)
        for i in range(2):
            booking = Booking.objects.create(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=timezone.now() + timedelta(days=i+1),
                pickup_location=f'{i} Main St',
                dropoff_location=f'{i} Oak Ave',
                total_price=Decimal('100.00'),
                status='completed'
            )
            
            Review.objects.create(
                reviewer=self.student,
                reviewee=self.provider,
                booking=booking,
                rating=5,
                comment=f'Service 1 Review {i+1}'
            )
        
        # Create reviews for second service (ratings: 2, 3)
        for i in range(2):
            booking = Booking.objects.create(
                student=self.student,
                provider=self.provider,
                service=service2,
                booking_date=timezone.now() + timedelta(days=i+10),
                pickup_location=f'{i+10} Main St',
                dropoff_location=f'{i+10} Oak Ave',
                total_price=Decimal('200.00'),
                status='completed'
            )
            
            Review.objects.create(
                reviewer=self.student,
                reviewee=self.provider,
                booking=booking,
                rating=2 + i,  # 2, 3
                comment=f'Service 2 Review {i+1}'
            )
        
        # Verify first service rating (5+5)/2 = 5.00
        self.service.refresh_from_db()
        self.assertEqual(self.service.rating_average, Decimal('5.00'))
        self.assertEqual(self.service.total_reviews, 2)
        
        # Verify second service rating (2+3)/2 = 2.50
        service2.refresh_from_db()
        self.assertEqual(service2.rating_average, Decimal('2.50'))
        self.assertEqual(service2.total_reviews, 2)
        
        # Verify provider rating aggregates all reviews (5+5+2+3)/4 = 3.75
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('3.75'))
    
    def test_user_ratings_aggregate_correctly_across_multiple_services(self):
        """Verify user ratings aggregate correctly across multiple services."""
        # Create second service
        service2 = MovingService.objects.create(
            provider=self.provider,
            service_name='Second Service',
            description='Another service',
            base_price=Decimal('200.00')
        )
        
        # Create reviews across both services
        ratings_service1 = [5, 4, 5]
        ratings_service2 = [3, 4]
        
        for i, rating in enumerate(ratings_service1):
            booking = Booking.objects.create(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=timezone.now() + timedelta(days=i+1),
                pickup_location=f'{i} Main St',
                dropoff_location=f'{i} Oak Ave',
                total_price=Decimal('100.00'),
                status='completed'
            )
            
            Review.objects.create(
                reviewer=self.student,
                reviewee=self.provider,
                booking=booking,
                rating=rating,
                comment=f'Service 1 Review {i+1}'
            )
        
        for i, rating in enumerate(ratings_service2):
            booking = Booking.objects.create(
                student=self.student,
                provider=self.provider,
                service=service2,
                booking_date=timezone.now() + timedelta(days=i+10),
                pickup_location=f'{i+10} Main St',
                dropoff_location=f'{i+10} Oak Ave',
                total_price=Decimal('200.00'),
                status='completed'
            )
            
            Review.objects.create(
                reviewer=self.student,
                reviewee=self.provider,
                booking=booking,
                rating=rating,
                comment=f'Service 2 Review {i+1}'
            )
        
        # Expected provider rating: (5+4+5+3+4)/5 = 21/5 = 4.20
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('4.20'))


class BidirectionalReviewSystemTests(TestCase):
    """Test bidirectional review system (providers reviewing students and vice versa)."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        
        self.student = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123',
            user_type='student'
        )
        
        self.provider = User.objects.create_user(
            username='provider',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
    
    def test_providers_can_review_students(self):
        """Verify providers can review students."""
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        self.client.force_authenticate(user=self.provider)
        
        data = {
            'booking_id': booking.id,
            'rating': 4,
            'comment': 'Good student, easy to work with.'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['reviewer']['id'], self.provider.id)
        self.assertEqual(response.data['reviewee']['id'], self.student.id)
        
        # Verify student rating updated
        self.student.refresh_from_db()
        self.assertEqual(self.student.avg_rating_as_student, Decimal('4.00'))
    
    def test_students_can_review_providers(self):
        """Verify students can review providers."""
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        self.client.force_authenticate(user=self.student)
        
        data = {
            'booking_id': booking.id,
            'rating': 5,
            'comment': 'Excellent provider!'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['reviewer']['id'], self.student.id)
        self.assertEqual(response.data['reviewee']['id'], self.provider.id)
        
        # Verify provider rating updated
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('5.00'))
    
    def test_both_parties_can_review_same_booking(self):
        """Verify both student and provider can review the same booking."""
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        # Student reviews provider
        self.client.force_authenticate(user=self.student)
        
        student_data = {
            'booking_id': booking.id,
            'rating': 5,
            'comment': 'Great service!'
        }
        
        response1 = self.client.post('/api/reviews/', student_data, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Provider reviews student
        self.client.force_authenticate(user=self.provider)
        
        provider_data = {
            'booking_id': booking.id,
            'rating': 4,
            'comment': 'Good student!'
        }
        
        response2 = self.client.post('/api/reviews/', provider_data, format='json')
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        
        # Verify both reviews exist
        self.assertEqual(Review.objects.count(), 2)
        
        # Verify ratings updated correctly
        self.provider.refresh_from_db()
        self.student.refresh_from_db()
        
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('5.00'))
        self.assertEqual(self.student.avg_rating_as_student, Decimal('4.00'))
    
    def test_user_rating_summary_shows_both_roles_separately(self):
        """Verify each user's rating summary shows both roles separately."""
        # Create a user who acts as both student and provider
        dual_user = User.objects.create_user(
            username='dual',
            email='dual@test.com',
            password='testpass123',
            user_type='provider',  # Can act as both
            is_verified=True
        )
        
        dual_service = MovingService.objects.create(
            provider=dual_user,
            service_name='Dual Service',
            description='Service by dual user',
            base_price=Decimal('100.00')
        )
        
        # Booking 1: dual_user as provider, student as student
        booking1 = Booking.objects.create(
            student=self.student,
            provider=dual_user,
            service=dual_service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        # Student reviews dual_user as provider (rating: 5)
        Review.objects.create(
            reviewer=self.student,
            reviewee=dual_user,
            booking=booking1,
            rating=5,
            comment='Great provider!'
        )
        
        # Booking 2: provider as provider, dual_user as student
        booking2 = Booking.objects.create(
            student=dual_user,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=2),
            pickup_location='789 Elm St',
            dropoff_location='321 Pine Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        # Provider reviews dual_user as student (rating: 3)
        Review.objects.create(
            reviewer=self.provider,
            reviewee=dual_user,
            booking=booking2,
            rating=3,
            comment='Average student'
        )
        
        # Verify dual_user has different ratings for different roles
        dual_user.refresh_from_db()
        self.assertEqual(dual_user.avg_rating_as_provider, Decimal('5.00'))
        self.assertEqual(dual_user.avg_rating_as_student, Decimal('3.00'))


class ValidationAndAuthorizationTests(TestCase):
    """Test validation and authorization for review system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        
        self.student = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123',
            user_type='student'
        )
        
        self.provider = User.objects.create_user(
            username='provider',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        
        self.other_user = User.objects.create_user(
            username='other',
            email='other@test.com',
            password='testpass123',
            user_type='student'
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
    
    def test_cannot_review_incomplete_booking(self):
        """Attempt to review incomplete booking should be rejected."""
        pending_booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='pending'
        )
        
        self.client.force_authenticate(user=self.student)
        
        data = {
            'booking_id': pending_booking.id,
            'rating': 5,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 0)
    
    def test_cannot_create_duplicate_review_same_reviewer(self):
        """Attempt to create duplicate review from same reviewer should be prevented."""
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        self.client.force_authenticate(user=self.student)
        
        data = {
            'booking_id': booking.id,
            'rating': 5,
            'comment': 'First review'
        }
        
        # First review should succeed
        response1 = self.client.post('/api/reviews/', data, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Second review should fail
        data['comment'] = 'Second review'
        response2 = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 1)
    
    def test_cannot_review_booking_not_participated_in(self):
        """Attempt to review booking user didn't participate in should return 403."""
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        self.client.force_authenticate(user=self.other_user)
        
        data = {
            'booking_id': booking.id,
            'rating': 5,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Review.objects.count(), 0)
    
    def test_invalid_rating_zero_rejected(self):
        """Attempt to create review with rating 0 should be rejected."""
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        self.client.force_authenticate(user=self.student)
        
        data = {
            'booking_id': booking.id,
            'rating': 0,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 0)
    
    def test_invalid_rating_six_rejected(self):
        """Attempt to create review with rating 6 should be rejected."""
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        self.client.force_authenticate(user=self.student)
        
        data = {
            'booking_id': booking.id,
            'rating': 6,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 0)
    
    def test_invalid_rating_negative_rejected(self):
        """Attempt to create review with negative rating should be rejected."""
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        self.client.force_authenticate(user=self.student)
        
        data = {
            'booking_id': booking.id,
            'rating': -1,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 0)


class ReviewModificationWorkflowTests(TestCase):
    """Test review modification workflow (update and delete)."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        
        self.student = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123',
            user_type='student'
        )
        
        self.provider = User.objects.create_user(
            username='provider',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
        
        self.booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
    
    def test_update_review_rating_triggers_recalculation(self):
        """Create review, update rating, verify rating recalculation triggered."""
        # Create initial review
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=3,
            comment='Average service'
        )
        
        # Verify initial ratings
        self.provider.refresh_from_db()
        self.service.refresh_from_db()
        
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('3.00'))
        self.assertEqual(self.service.rating_average, Decimal('3.00'))
        self.assertEqual(self.service.total_reviews, 1)
        
        # Update review rating
        self.client.force_authenticate(user=self.student)
        
        update_data = {
            'rating': 5,
            'comment': 'Actually excellent service!'
        }
        
        response = self.client.patch(f'/api/reviews/{review.id}/', update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify ratings recalculated
        self.provider.refresh_from_db()
        self.service.refresh_from_db()
        
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('5.00'))
        self.assertEqual(self.service.rating_average, Decimal('5.00'))
        self.assertEqual(self.service.total_reviews, 1)  # Count unchanged
    
    def test_delete_review_triggers_rating_recalculation(self):
        """Delete review, verify ratings recalculate correctly."""
        # Create two reviews
        review1 = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='Great service'
        )
        
        booking2 = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=2),
            pickup_location='789 Elm St',
            dropoff_location='321 Pine Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        review2 = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking2,
            rating=3,
            comment='Average service'
        )
        
        # Verify initial ratings (5+3)/2 = 4.00
        self.provider.refresh_from_db()
        self.service.refresh_from_db()
        
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('4.00'))
        self.assertEqual(self.service.rating_average, Decimal('4.00'))
        self.assertEqual(self.service.total_reviews, 2)
        
        # Delete first review
        self.client.force_authenticate(user=self.student)
        
        response = self.client.delete(f'/api/reviews/{review1.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify ratings recalculated (only review2 remains: 3.00)
        self.provider.refresh_from_db()
        self.service.refresh_from_db()
        
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('3.00'))
        self.assertEqual(self.service.rating_average, Decimal('3.00'))
        self.assertEqual(self.service.total_reviews, 1)
    
    def test_delete_all_reviews_sets_ratings_to_zero(self):
        """Delete all reviews, verify ratings set to 0.00."""
        # Create review
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='Great service'
        )
        
        # Verify initial ratings
        self.provider.refresh_from_db()
        self.service.refresh_from_db()
        
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('5.00'))
        self.assertEqual(self.service.rating_average, Decimal('5.00'))
        self.assertEqual(self.service.total_reviews, 1)
        
        # Delete review
        self.client.force_authenticate(user=self.student)
        
        response = self.client.delete(f'/api/reviews/{review.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify ratings reset to 0.00
        self.provider.refresh_from_db()
        self.service.refresh_from_db()
        
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('0.00'))
        self.assertEqual(self.service.rating_average, Decimal('0.00'))
        self.assertEqual(self.service.total_reviews, 0)


class ConcurrentReviewScenarioTests(TransactionTestCase):
    """Test concurrent review scenarios to ensure data integrity."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.student = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123',
            user_type='student'
        )
        
        self.provider = User.objects.create_user(
            username='provider',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
    
    def test_concurrent_review_submissions_maintain_integrity(self):
        """Multiple users submitting reviews simultaneously should maintain data integrity."""
        # Create multiple completed bookings
        bookings = []
        for i in range(5):
            booking = Booking.objects.create(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=timezone.now() + timedelta(days=i+1),
                pickup_location=f'{i} Main St',
                dropoff_location=f'{i} Oak Ave',
                total_price=Decimal('100.00'),
                status='completed'
            )
            bookings.append(booking)
        
        def create_review(booking, rating):
            """Create review in separate thread."""
            client = APIClient()
            client.force_authenticate(user=self.student)
            
            data = {
                'booking_id': booking.id,
                'rating': rating,
                'comment': f'Review for booking {booking.id}'
            }
            
            client.post('/api/reviews/', data, format='json')
        
        # Create reviews concurrently
        ratings = [5, 4, 5, 3, 4]
        threads = []
        
        for booking, rating in zip(bookings, ratings):
            thread = Thread(target=create_review, args=(booking, rating))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify all reviews created
        self.assertEqual(Review.objects.count(), 5)
        
        # Verify rating calculated correctly (5+4+5+3+4)/5 = 21/5 = 4.20
        self.provider.refresh_from_db()
        self.service.refresh_from_db()
        
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('4.20'))
        self.assertEqual(self.service.rating_average, Decimal('4.20'))
        self.assertEqual(self.service.total_reviews, 5)
    
    def test_concurrent_rating_updates_dont_corrupt_averages(self):
        """Concurrent rating updates should not corrupt averages."""
        # Create initial reviews
        bookings = []
        reviews = []
        
        for i in range(3):
            booking = Booking.objects.create(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=timezone.now() + timedelta(days=i+1),
                pickup_location=f'{i} Main St',
                dropoff_location=f'{i} Oak Ave',
                total_price=Decimal('100.00'),
                status='completed'
            )
            bookings.append(booking)
            
            review = Review.objects.create(
                reviewer=self.student,
                reviewee=self.provider,
                booking=booking,
                rating=3,
                comment=f'Initial review {i}'
            )
            reviews.append(review)
        
        # Verify initial rating (3+3+3)/3 = 3.00
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('3.00'))
        
        def update_review(review, new_rating):
            """Update review in separate thread."""
            client = APIClient()
            client.force_authenticate(user=self.student)
            
            data = {
                'rating': new_rating,
                'comment': f'Updated review {review.id}'
            }
            
            client.patch(f'/api/reviews/{review.id}/', data, format='json')
        
        # Update reviews concurrently
        new_ratings = [5, 4, 5]
        threads = []
        
        for review, new_rating in zip(reviews, new_ratings):
            thread = Thread(target=update_review, args=(review, new_rating))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify rating calculated correctly (5+4+5)/3 = 14/3 = 4.67
        self.provider.refresh_from_db()
        self.service.refresh_from_db()
        
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('4.67'))
        self.assertEqual(self.service.rating_average, Decimal('4.67'))


class DataConsistencyTests(TestCase):
    """Test data consistency across all related models."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.student = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123',
            user_type='student'
        )
        
        self.provider = User.objects.create_user(
            username='provider',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
    
    def test_reviews_remain_consistent_with_booking_data(self):
        """Reviews should remain consistent with booking data."""
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking,
            rating=5,
            comment='Great service'
        )
        
        # Verify review associations
        self.assertEqual(review.booking, booking)
        self.assertEqual(review.reviewer, booking.student)
        self.assertEqual(review.reviewee, booking.provider)
    
    def test_rating_averages_always_match_actual_review_data(self):
        """Rating averages should always match actual review data."""
        # Create multiple reviews
        ratings = [5, 4, 3, 5, 4]
        
        for i, rating in enumerate(ratings):
            booking = Booking.objects.create(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=timezone.now() + timedelta(days=i+1),
                pickup_location=f'{i} Main St',
                dropoff_location=f'{i} Oak Ave',
                total_price=Decimal('100.00'),
                status='completed'
            )
            
            Review.objects.create(
                reviewer=self.student,
                reviewee=self.provider,
                booking=booking,
                rating=rating,
                comment=f'Review {i+1}'
            )
        
        # Calculate expected average manually
        expected_avg = sum(ratings) / len(ratings)  # 21/5 = 4.2
        
        # Verify stored average matches calculation
        self.provider.refresh_from_db()
        self.service.refresh_from_db()
        
        # Calculate actual average from reviews
        actual_reviews = Review.objects.filter(reviewee=self.provider)
        actual_avg = sum(r.rating for r in actual_reviews) / actual_reviews.count()
        
        self.assertEqual(float(self.provider.avg_rating_as_provider), actual_avg)
        self.assertEqual(float(self.service.rating_average), actual_avg)
    
    def test_total_review_counts_match_actual_review_counts(self):
        """Total review counts should match actual review counts."""
        # Create reviews
        for i in range(7):
            booking = Booking.objects.create(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=timezone.now() + timedelta(days=i+1),
                pickup_location=f'{i} Main St',
                dropoff_location=f'{i} Oak Ave',
                total_price=Decimal('100.00'),
                status='completed'
            )
            
            Review.objects.create(
                reviewer=self.student,
                reviewee=self.provider,
                booking=booking,
                rating=4,
                comment=f'Review {i+1}'
            )
        
        # Verify counts match
        self.service.refresh_from_db()
        
        actual_count = Review.objects.filter(booking__service=self.service).count()
        self.assertEqual(self.service.total_reviews, actual_count)
        self.assertEqual(actual_count, 7)


class EdgeCaseTests(TestCase):
    """Test edge cases and boundary conditions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.student = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123',
            user_type='student'
        )
        
        self.provider = User.objects.create_user(
            username='provider',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
    
    def test_user_with_single_review(self):
        """User with single review should have correct rating."""
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking,
            rating=4,
            comment='Good service'
        )
        
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('4.00'))
    
    def test_service_with_no_reviews(self):
        """Service with no reviews should have 0.00 rating."""
        self.assertEqual(self.service.rating_average, Decimal('0.00'))
        self.assertEqual(self.service.total_reviews, 0)
    
    def test_service_with_all_five_star_reviews(self):
        """Service with all 5-star reviews should have 5.00 rating."""
        for i in range(10):
            booking = Booking.objects.create(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=timezone.now() + timedelta(days=i+1),
                pickup_location=f'{i} Main St',
                dropoff_location=f'{i} Oak Ave',
                total_price=Decimal('100.00'),
                status='completed'
            )
            
            Review.objects.create(
                reviewer=self.student,
                reviewee=self.provider,
                booking=booking,
                rating=5,
                comment='Perfect!'
            )
        
        self.service.refresh_from_db()
        self.assertEqual(self.service.rating_average, Decimal('5.00'))
        self.assertEqual(self.service.total_reviews, 10)
    
    def test_user_who_is_both_provider_and_student_with_reviews_in_both_roles(self):
        """User with reviews in both roles should have separate ratings."""
        # Create dual-role user
        dual_user = User.objects.create_user(
            username='dual',
            email='dual@test.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        
        dual_service = MovingService.objects.create(
            provider=dual_user,
            service_name='Dual Service',
            description='Service by dual user',
            base_price=Decimal('100.00')
        )
        
        # Review as provider (rating: 5)
        booking1 = Booking.objects.create(
            student=self.student,
            provider=dual_user,
            service=dual_service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        Review.objects.create(
            reviewer=self.student,
            reviewee=dual_user,
            booking=booking1,
            rating=5,
            comment='Great provider!'
        )
        
        # Review as student (rating: 2)
        booking2 = Booking.objects.create(
            student=dual_user,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=2),
            pickup_location='789 Elm St',
            dropoff_location='321 Pine Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        Review.objects.create(
            reviewer=self.provider,
            reviewee=dual_user,
            booking=booking2,
            rating=2,
            comment='Difficult student'
        )
        
        # Verify separate ratings
        dual_user.refresh_from_db()
        self.assertEqual(dual_user.avg_rating_as_provider, Decimal('5.00'))
        self.assertEqual(dual_user.avg_rating_as_student, Decimal('2.00'))
