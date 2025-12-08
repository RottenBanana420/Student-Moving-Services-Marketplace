"""
Comprehensive tests for service detail endpoint.

Following TDD approach - these tests are written first and will initially fail.
Implementation will be created to make these tests pass.
"""

from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from core.models import MovingService, Booking, Review
from datetime import timedelta

User = get_user_model()


class ServiceDetailEndpointTests(TestCase):
    """
    Test suite for GET /api/services/<id>/ endpoint.
    
    Tests verify:
    - Complete service detail retrieval
    - Provider information with rating summary
    - Service-specific statistics
    - Recent reviews
    - Edge cases (404, no reviews)
    - Query optimization
    - Public access
    """
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        
        # Create verified provider with complete profile
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider@example.com',
            password='testpass123',
            user_type='provider',
            is_verified=True,
            phone_number='+1234567890',
            university_name='Test University'
        )
        
        # Create student users for reviews
        self.student1 = User.objects.create_user(
            username='student1',
            email='student1@example.com',
            password='testpass123',
            user_type='student'
        )
        
        self.student2 = User.objects.create_user(
            username='student2',
            email='student2@example.com',
            password='testpass123',
            user_type='student'
        )
        
        self.student3 = User.objects.create_user(
            username='student3',
            email='student3@example.com',
            password='testpass123',
            user_type='student'
        )
        
        # Create a moving service
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Premium Moving Service',
            description='Professional moving service for students',
            base_price=Decimal('150.00'),
            availability_status=True
        )
    
    def _create_completed_booking_with_review(self, service, student, rating, comment):
        """
        Helper method to create a completed booking with a review.
        
        Args:
            service: MovingService instance
            student: Student User instance
            rating: Review rating (1-5)
            comment: Review comment text
            
        Returns:
            Review instance
        """
        # Create completed booking
        booking = Booking.objects.create(
            student=student,
            provider=service.provider,
            service=service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Test St',
            dropoff_location='456 Test Ave',
            total_price=service.base_price,
            status='completed'
        )
        
        # Create review for the booking
        review = Review.objects.create(
            reviewer=student,
            reviewee=service.provider,
            booking=booking,
            rating=rating,
            comment=comment
        )
        
        return review
    
    def test_retrieve_service_detail_success(self):
        """
        Test retrieving complete service details with all expected fields.
        
        Verifies:
        - 200 status code
        - All service fields present
        - Provider information included
        - Reviews included
        - Rating statistics present
        """
        # Create some reviews for the service
        self._create_completed_booking_with_review(
            self.service, self.student1, 5, 'Excellent service!'
        )
        self._create_completed_booking_with_review(
            self.service, self.student2, 4, 'Very good!'
        )
        
        # Make request
        url = f'/api/services/{self.service.id}/'
        response = self.client.get(url)
        
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Assert service fields
        self.assertEqual(response.data['id'], self.service.id)
        self.assertEqual(response.data['service_name'], 'Premium Moving Service')
        self.assertEqual(response.data['description'], 'Professional moving service for students')
        self.assertEqual(Decimal(response.data['base_price']), Decimal('150.00'))
        self.assertEqual(response.data['availability_status'], True)
        self.assertIn('created_at', response.data)
        self.assertIn('updated_at', response.data)
        
        # Assert provider information present
        self.assertIn('provider', response.data)
        
        # Assert reviews present
        self.assertIn('recent_reviews', response.data)
        
        # Assert rating statistics present
        self.assertIn('rating_average', response.data)
        self.assertIn('total_reviews', response.data)
        self.assertIn('rating_distribution', response.data)
    
    def test_retrieve_nonexistent_service_returns_404(self):
        """
        Test that requesting a non-existent service returns 404.
        """
        url = '/api/services/99999/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_provider_information_complete(self):
        """
        Test that provider information is complete and accurate.
        
        Verifies all provider fields:
        - id, email, phone_number, university_name
        - is_verified status
        - profile_image_url (if present)
        - provider_rating_average
        """
        # Create a review to generate provider rating
        self._create_completed_booking_with_review(
            self.service, self.student1, 5, 'Great!'
        )
        
        url = f'/api/services/{self.service.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        provider_data = response.data['provider']
        
        # Assert all provider fields present
        self.assertEqual(provider_data['id'], self.provider.id)
        self.assertEqual(provider_data['email'], 'provider@example.com')
        self.assertEqual(provider_data['phone_number'], '+1234567890')
        self.assertEqual(provider_data['university_name'], 'Test University')
        self.assertEqual(provider_data['is_verified'], True)
        self.assertIn('profile_image_url', provider_data)
        self.assertIn('provider_rating_average', provider_data)
    
    def test_reviews_included_and_formatted(self):
        """
        Test that reviews are included and properly formatted.
        
        Verifies each review has:
        - id, reviewer_name, rating, comment, created_at
        """
        # Create multiple reviews
        review1 = self._create_completed_booking_with_review(
            self.service, self.student1, 5, 'Excellent service!'
        )
        review2 = self._create_completed_booking_with_review(
            self.service, self.student2, 4, 'Very good!'
        )
        
        url = f'/api/services/{self.service.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        reviews = response.data['recent_reviews']
        
        # Assert reviews present
        self.assertGreaterEqual(len(reviews), 2)
        
        # Assert review structure
        for review in reviews:
            self.assertIn('id', review)
            self.assertIn('reviewer_name', review)
            self.assertIn('rating', review)
            self.assertIn('comment', review)
            self.assertIn('created_at', review)
            
            # Verify rating is in valid range
            self.assertGreaterEqual(review['rating'], 1)
            self.assertLessEqual(review['rating'], 5)
    
    def test_rating_statistics_calculated_correctly(self):
        """
        Test that rating statistics are calculated correctly.
        
        Creates reviews with different ratings and verifies:
        - rating_average is correct
        - total_reviews is correct
        - rating_distribution shows correct counts
        """
        # Create reviews with specific ratings
        # 2x 5-star, 1x 4-star, 1x 3-star
        self._create_completed_booking_with_review(
            self.service, self.student1, 5, 'Perfect!'
        )
        self._create_completed_booking_with_review(
            self.service, self.student2, 5, 'Excellent!'
        )
        
        # Create another student for third review
        student4 = User.objects.create_user(
            username='student4',
            email='student4@example.com',
            password='testpass123',
            user_type='student'
        )
        self._create_completed_booking_with_review(
            self.service, self.student3, 4, 'Very good!'
        )
        
        student5 = User.objects.create_user(
            username='student5',
            email='student5@example.com',
            password='testpass123',
            user_type='student'
        )
        self._create_completed_booking_with_review(
            self.service, student4, 3, 'Good!'
        )
        
        url = f'/api/services/{self.service.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Calculate expected average: (5+5+4+3) / 4 = 4.25
        expected_average = Decimal('4.25')
        actual_average = Decimal(str(response.data['rating_average']))
        
        self.assertEqual(actual_average, expected_average)
        self.assertEqual(response.data['total_reviews'], 4)
        
        # Verify rating distribution
        distribution = response.data['rating_distribution']
        self.assertEqual(distribution['5'], 2)
        self.assertEqual(distribution['4'], 1)
        self.assertEqual(distribution['3'], 1)
        self.assertEqual(distribution['2'], 0)
        self.assertEqual(distribution['1'], 0)
    
    def test_service_with_no_reviews(self):
        """
        Test that services with no reviews display properly.
        
        Verifies:
        - recent_reviews is empty list
        - rating_average is 0.00
        - total_reviews is 0
        - rating_distribution shows all zeros
        """
        url = f'/api/services/{self.service.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Assert empty reviews
        self.assertEqual(response.data['recent_reviews'], [])
        
        # Assert zero statistics
        self.assertEqual(Decimal(str(response.data['rating_average'])), Decimal('0.00'))
        self.assertEqual(response.data['total_reviews'], 0)
        
        # Assert all-zero distribution
        distribution = response.data['rating_distribution']
        self.assertEqual(distribution['5'], 0)
        self.assertEqual(distribution['4'], 0)
        self.assertEqual(distribution['3'], 0)
        self.assertEqual(distribution['2'], 0)
        self.assertEqual(distribution['1'], 0)
    
    def test_provider_rating_summary(self):
        """
        Test that provider rating aggregates across all their services.
        
        Creates multiple services for the same provider with different ratings
        and verifies provider_rating_average reflects all services.
        """
        # Create second service for same provider
        service2 = MovingService.objects.create(
            provider=self.provider,
            service_name='Economy Moving Service',
            description='Budget-friendly moving',
            base_price=Decimal('100.00'),
            availability_status=True
        )
        
        # Add reviews to first service (5-star)
        self._create_completed_booking_with_review(
            self.service, self.student1, 5, 'Perfect!'
        )
        
        # Add reviews to second service (3-star)
        self._create_completed_booking_with_review(
            service2, self.student2, 3, 'Okay'
        )
        
        # Request first service detail
        url = f'/api/services/{self.service.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Provider rating should be average of both services: (5+3)/2 = 4.0
        provider_rating = Decimal(str(response.data['provider']['provider_rating_average']))
        expected_rating = Decimal('4.00')
        
        self.assertEqual(provider_rating, expected_rating)
    
    def test_recent_reviews_limited(self):
        """
        Test that recent reviews are limited to most recent 10.
        
        Creates 15 reviews and verifies only 10 most recent are returned.
        """
        # Create 15 students and reviews
        students = []
        for i in range(15):
            student = User.objects.create_user(
                username=f'student_review_{i}',
                email=f'studentreview{i}@example.com',  # Unique email
                password='testpass123',
                user_type='student'
            )
            students.append(student)
            
            # Create review with slight time difference
            self._create_completed_booking_with_review(
                self.service, student, 5, f'Review {i}'
            )
        
        url = f'/api/services/{self.service.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        reviews = response.data['recent_reviews']
        
        # Should return at most 10 reviews
        self.assertLessEqual(len(reviews), 10)
        
        # Verify reviews are ordered by most recent first
        if len(reviews) > 1:
            for i in range(len(reviews) - 1):
                current_date = reviews[i]['created_at']
                next_date = reviews[i + 1]['created_at']
                # Current should be >= next (most recent first)
                self.assertGreaterEqual(current_date, next_date)
    
    def test_unauthenticated_access_allowed(self):
        """
        Test that unauthenticated users can access service details.
        
        This is a public endpoint for marketplace browsing.
        """
        # Ensure client is not authenticated
        self.client.force_authenticate(user=None)
        
        url = f'/api/services/{self.service.id}/'
        response = self.client.get(url)
        
        # Should succeed without authentication
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_query_optimization_no_n_plus_1(self):
        """
        Test that the endpoint doesn't have N+1 query problems.
        
        Verifies database queries are optimized with select_related
        and prefetch_related.
        """
        # Create reviews to ensure related data is fetched
        self._create_completed_booking_with_review(
            self.service, self.student1, 5, 'Great!'
        )
        self._create_completed_booking_with_review(
            self.service, self.student2, 4, 'Good!'
        )
        
        url = f'/api/services/{self.service.id}/'
        
        # Count queries
        from django.test.utils import override_settings
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should use minimal queries (typically 3-5):
        # 1. Fetch service with provider (select_related)
        # 2. Prefetch provider's services for rating calculation
        # 3. Prefetch reviews through bookings
        # 4-5. Possible additional queries for aggregations
        
        num_queries = len(context.captured_queries)
        
        # Assert reasonable query count (should be <= 10 with optimizations)
        self.assertLessEqual(
            num_queries, 10,
            f"Too many queries ({num_queries}). Possible N+1 problem. "
            f"Queries: {[q['sql'] for q in context.captured_queries]}"
        )
