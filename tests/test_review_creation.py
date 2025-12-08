"""
Comprehensive test suite for Review Creation Endpoint.

These tests are designed to FAIL until the endpoint is properly implemented.
Following TDD principles: write tests first, then implement code to pass them.
NEVER modify these tests - only fix the implementation.
"""

from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status
from threading import Thread
from multiprocessing import Process, Queue
import time

from core.models import MovingService, Booking, Review


User = get_user_model()


class ReviewCreationValidDataTests(TestCase):
    """Test successful review creation with valid data."""
    
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
            service_name='Test Moving Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
        
        self.completed_booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
    
    def test_student_can_create_review_for_completed_booking(self):
        """Student should be able to review completed booking."""
        self.client.force_authenticate(user=self.student)
        
        data = {
            'booking_id': self.completed_booking.id,
            'rating': 5,
            'comment': 'Excellent service!'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['rating'], 5)
        self.assertEqual(response.data['comment'], 'Excellent service!')
        self.assertEqual(response.data['reviewer']['id'], self.student.id)
        self.assertEqual(response.data['reviewee']['id'], self.provider.id)
        self.assertEqual(response.data['booking']['id'], self.completed_booking.id)
        
        # Verify review was created in database
        self.assertEqual(Review.objects.count(), 1)
        review = Review.objects.first()
        self.assertEqual(review.reviewer, self.student)
        self.assertEqual(review.reviewee, self.provider)
        self.assertEqual(review.rating, 5)
    
    def test_provider_can_create_review_for_completed_booking(self):
        """Provider should be able to review completed booking."""
        self.client.force_authenticate(user=self.provider)
        
        data = {
            'booking_id': self.completed_booking.id,
            'rating': 4,
            'comment': 'Good student, easy to work with'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['rating'], 4)
        self.assertEqual(response.data['reviewer']['id'], self.provider.id)
        self.assertEqual(response.data['reviewee']['id'], self.student.id)
        
        # Verify review was created in database
        review = Review.objects.first()
        self.assertEqual(review.reviewer, self.provider)
        self.assertEqual(review.reviewee, self.student)
    
    def test_review_response_includes_complete_details(self):
        """Review response should include all relevant details."""
        self.client.force_authenticate(user=self.student)
        
        data = {
            'booking_id': self.completed_booking.id,
            'rating': 5,
            'comment': 'Great service!'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify response structure
        self.assertIn('id', response.data)
        self.assertIn('rating', response.data)
        self.assertIn('comment', response.data)
        self.assertIn('reviewer', response.data)
        self.assertIn('reviewee', response.data)
        self.assertIn('booking', response.data)
        self.assertIn('created_at', response.data)
        
        # Verify reviewer details
        self.assertIn('id', response.data['reviewer'])
        self.assertIn('email', response.data['reviewer'])
        
        # Verify reviewee details
        self.assertIn('id', response.data['reviewee'])
        self.assertIn('email', response.data['reviewee'])


class ReviewCreationRatingValidationTests(TestCase):
    """Test rating field validation for 1-5 range."""
    
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
            service_name='Test Moving Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
        
        self.completed_booking = Booking.objects.create(
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
    
    def test_rating_zero_returns_validation_error(self):
        """Rating of 0 must return 400 with validation error."""
        data = {
            'booking_id': self.completed_booking.id,
            'rating': 0,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rating', response.data)
        self.assertEqual(Review.objects.count(), 0)
    
    def test_rating_six_returns_validation_error(self):
        """Rating of 6 must return 400 with validation error."""
        data = {
            'booking_id': self.completed_booking.id,
            'rating': 6,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rating', response.data)
        self.assertEqual(Review.objects.count(), 0)
    
    def test_rating_negative_returns_validation_error(self):
        """Negative rating must return 400 with validation error."""
        data = {
            'booking_id': self.completed_booking.id,
            'rating': -1,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rating', response.data)
        self.assertEqual(Review.objects.count(), 0)
    
    def test_missing_rating_returns_validation_error(self):
        """Missing rating field must return 400 with validation error."""
        data = {
            'booking_id': self.completed_booking.id,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rating', response.data)
        self.assertEqual(Review.objects.count(), 0)
    
    def test_non_integer_rating_returns_validation_error(self):
        """Non-integer rating must return 400 with validation error."""
        data = {
            'booking_id': self.completed_booking.id,
            'rating': 'five',
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rating', response.data)
        self.assertEqual(Review.objects.count(), 0)
    
    def test_float_rating_returns_validation_error(self):
        """Float rating must return 400 with validation error."""
        data = {
            'booking_id': self.completed_booking.id,
            'rating': 4.5,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rating', response.data)
        self.assertEqual(Review.objects.count(), 0)


class ReviewCreationBookingStatusValidationTests(TestCase):
    """Test booking status validation - only completed bookings can be reviewed."""
    
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
            service_name='Test Moving Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
        
        self.client.force_authenticate(user=self.student)
    
    def test_pending_booking_cannot_be_reviewed(self):
        """Review for pending booking must return 400."""
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
        
        data = {
            'booking_id': pending_booking.id,
            'rating': 5,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 0)
    
    def test_confirmed_booking_cannot_be_reviewed(self):
        """Review for confirmed booking must return 400."""
        confirmed_booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='confirmed'
        )
        
        data = {
            'booking_id': confirmed_booking.id,
            'rating': 5,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 0)
    
    def test_cancelled_booking_cannot_be_reviewed(self):
        """Review for cancelled booking must return 400."""
        cancelled_booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='cancelled'
        )
        
        data = {
            'booking_id': cancelled_booking.id,
            'rating': 5,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 0)


class ReviewCreationAuthorizationTests(TestCase):
    """Test authorization - only booking participants can review."""
    
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
            service_name='Test Moving Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
        
        self.completed_booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
    
    def test_non_participant_cannot_review_booking(self):
        """User who didn't participate in booking must get 403 Forbidden."""
        self.client.force_authenticate(user=self.other_user)
        
        data = {
            'booking_id': self.completed_booking.id,
            'rating': 5,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Review.objects.count(), 0)


class ReviewCreationDuplicatePreventionTests(TestCase):
    """Test duplicate review prevention."""
    
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
            service_name='Test Moving Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
        
        self.completed_booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
    
    def test_duplicate_review_for_same_booking_returns_error(self):
        """Creating duplicate review for same booking must return 400 with descriptive error."""
        self.client.force_authenticate(user=self.student)
        
        data = {
            'booking_id': self.completed_booking.id,
            'rating': 5,
            'comment': 'First review'
        }
        
        # First review should succeed
        response1 = self.client.post('/api/reviews/', data, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Second review for same booking should fail
        data['comment'] = 'Second review'
        response2 = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already been reviewed', str(response2.data).lower())
        
        # Verify only one review exists
        self.assertEqual(Review.objects.count(), 1)


class ReviewCreationConcurrentDuplicateTests(TransactionTestCase):
    """Test concurrent duplicate review attempts."""
    
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
            service_name='Test Moving Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
        
        self.completed_booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
    
    def test_concurrent_duplicate_review_attempts(self):
        """Concurrent duplicate review attempts should result in only one review."""
        results = []
        
        def create_review():
            """Create review in separate thread."""
            client = APIClient()
            client.force_authenticate(user=self.student)
            
            data = {
                'booking_id': self.completed_booking.id,
                'rating': 5,
                'comment': 'Concurrent review'
            }
            
            response = client.post('/api/reviews/', data, format='json')
            results.append(response.status_code)
        
        # Create multiple threads attempting to create review simultaneously
        threads = [Thread(target=create_review) for _ in range(5)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify only one review was created
        self.assertEqual(Review.objects.count(), 1)
        
        # Verify at least one request succeeded
        self.assertIn(status.HTTP_201_CREATED, results)
        
        # Verify other requests failed with 400
        failed_requests = [r for r in results if r == status.HTTP_400_BAD_REQUEST]
        self.assertGreater(len(failed_requests), 0)


class ReviewCreationAuthenticationTests(TestCase):
    """Test authentication requirement."""
    
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
            service_name='Test Moving Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
        
        self.completed_booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
    
    def test_unauthenticated_request_returns_401(self):
        """Unauthenticated request must return 401 Unauthorized."""
        data = {
            'booking_id': self.completed_booking.id,
            'rating': 5,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Review.objects.count(), 0)


class ReviewCreationEdgeCaseTests(TestCase):
    """Test edge cases and error handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        
        self.student = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123',
            user_type='student'
        )
        
        self.client.force_authenticate(user=self.student)
    
    def test_non_existent_booking_returns_404(self):
        """Non-existent booking ID must return 404 Not Found."""
        data = {
            'booking_id': 99999,
            'rating': 5,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Review.objects.count(), 0)
    
    def test_invalid_booking_id_format_returns_400(self):
        """Invalid booking ID format must return 400."""
        data = {
            'booking_id': 'invalid',
            'rating': 5,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('booking_id', response.data)
        self.assertEqual(Review.objects.count(), 0)
    
    def test_missing_booking_id_returns_400(self):
        """Missing booking_id field must return 400."""
        data = {
            'rating': 5,
            'comment': 'Test comment'
        }
        
        response = self.client.post('/api/reviews/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('booking_id', response.data)
        self.assertEqual(Review.objects.count(), 0)
