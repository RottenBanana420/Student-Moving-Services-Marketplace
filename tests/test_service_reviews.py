
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status
from core.models import MovingService, Booking, Review

User = get_user_model()

class ServiceReviewsRetrievalTests(TestCase):
    """Test suite for retrieving service reviews."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        # Create provider
        self.provider = User.objects.create_user(
            username='provider',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )

        # Create service
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Moving Service',
            description='Test description',
            base_price=Decimal('100.00')
        )

        # Create students
        self.student1 = User.objects.create_user(
            username='student1',
            email='student1@test.com',
            password='testpass123',
            user_type='student'
        )
        self.student2 = User.objects.create_user(
            username='student2',
            email='student2@test.com',
            password='testpass123',
            user_type='student'
        )

        # Create bookings for this service
        self.booking1 = Booking.objects.create(
            student=self.student1,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() - timedelta(days=5),
            pickup_location='Loc A',
            dropoff_location='Loc B',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        self.booking2 = Booking.objects.create(
            student=self.student2,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() - timedelta(days=2),
            pickup_location='Loc C',
            dropoff_location='Loc D',
            total_price=Decimal('100.00'),
            status='completed'
        )

        # Create reviews
        self.review1 = Review.objects.create(
            reviewer=self.student1,
            reviewee=self.provider,
            booking=self.booking1,
            rating=5,
            comment="Great service!",
            created_at=timezone.now() - timedelta(days=4)
        )
        
        self.review2 = Review.objects.create(
            reviewer=self.student2,
            reviewee=self.provider,
            booking=self.booking2,
            rating=3,
            comment="Okay service.",
            created_at=timezone.now() - timedelta(days=1)
        )
        
        # Ensure created_at ordering (review2 is newer)
        # We manually update created_at because auto_now_add doesn't let us set it easily on create in some DBs,
        # but Django usually respects it if we set it. However, to be safe:
        Review.objects.filter(id=self.review1.id).update(created_at=timezone.now() - timedelta(days=4))
        Review.objects.filter(id=self.review2.id).update(created_at=timezone.now() - timedelta(days=1))


    def test_retrieve_reviews_success(self):
        """Should retrieve reviews for the service."""
        response = self.client.get(f'/api/reviews/service/{self.service.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check standard pagination structure
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 2)
        
        # Check ordering (newest first)
        results = response.data['results']
        self.assertEqual(results[0]['id'], self.review2.id)
        self.assertEqual(results[1]['id'], self.review1.id)

    def test_unauthenticated_access(self):
        """Unauthenticated users should be able to view reviews."""
        self.client.logout()
        response = self.client.get(f'/api/reviews/service/{self.service.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_reviews_only_for_specified_service(self):
        """Should not show reviews for other services."""
        # Create another service and review
        other_service = MovingService.objects.create(
            provider=self.provider,
            service_name='Other Service',
            description='Desc',
            base_price=Decimal('200.00')
        )
        other_booking = Booking.objects.create(
            student=self.student1,
            provider=self.provider,
            service=other_service,
            booking_date=timezone.now(),
            pickup_location='X',
            dropoff_location='Y',
            total_price=Decimal('200.00'),
            status='completed'
        )
        Review.objects.create(
            reviewer=self.student1,
            reviewee=self.provider,
            booking=other_booking,
            rating=4,
            comment="Other review"
        )
        
        response = self.client.get(f'/api/reviews/service/{self.service.id}/')
        self.assertEqual(len(response.data['results']), 2) # Still 2, not 3

    def test_non_existent_service(self):
        """Should return 404 for non-existent service."""
        response = self.client.get('/api/reviews/service/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_serializer_structure(self):
        """Verify serializer fields."""
        response = self.client.get(f'/api/reviews/service/{self.service.id}/')
        review_data = response.data['results'][0]
        
        self.assertIn('rating', review_data)
        self.assertIn('comment', review_data)
        self.assertIn('created_at', review_data)
        self.assertIn('reviewer', review_data)
        
        # Check reviewer details
        reviewer = review_data['reviewer']
        self.assertIn('full_name', reviewer) # Assuming we want name/email or something displayable
        self.assertIn('university_name', reviewer) 
        self.assertIn('user_type', reviewer)
        
        # Check confirmation
        self.assertEqual(review_data['is_verified_booking'], True) # Implicit by review existence on completed booking? Or field?

    def test_statistics_inclusion(self):
        """Response should include rating statistics."""
        response = self.client.get(f'/api/reviews/service/{self.service.id}/')
        
        self.assertIn('statistics', response.data)
        stats = response.data['statistics']
        self.assertEqual(stats['total_reviews'], 2)
        self.assertEqual(float(stats['average_rating']), 4.0) # (5+3)/2
        self.assertEqual(stats['rating_distribution']['5'], 1)
        self.assertEqual(stats['rating_distribution']['3'], 1)
        self.assertEqual(stats['rating_distribution']['1'], 0)

    def test_zero_reviews(self):
        """Service with no reviews should return empty list and zero stats."""
        # Create new service
        new_service = MovingService.objects.create(
            provider=self.provider,
            service_name='New Service',
            description='Desc',
            base_price=Decimal('50.00')
        )
        
        response = self.client.get(f'/api/reviews/service/{new_service.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)
        
        stats = response.data['statistics']
        self.assertEqual(stats['total_reviews'], 0)
        self.assertEqual(stats['average_rating'], 0)
        for i in range(1, 6):
            self.assertEqual(stats['rating_distribution'][str(i)], 0)


class ServiceReviewsFilteringTests(TestCase):
    """Test filtering and ordering of reviews."""
    
    def setUp(self):
        self.client = APIClient()
        self.provider = User.objects.create_user(
            username='provider', email='p@test.com', password='p', user_type='provider'
        )
        self.service = MovingService.objects.create(
            provider=self.provider, service_name='S', description='D', base_price=10
        )
        self.student = User.objects.create_user(
            username='student', email='s@test.com', password='p', user_type='student'
        )
        
        # Create reviews with different ratings
        for i in range(1, 6):
            booking = Booking.objects.create(
                student=self.student, provider=self.provider, service=self.service,
                booking_date=timezone.now(), pickup_location='A', dropoff_location='B',
                total_price=10, status='completed'
            )
            Review.objects.create(
                reviewer=self.student, reviewee=self.provider, booking=booking,
                rating=i, comment=f"Rating {i}"
            )

    def test_filter_by_rating(self):
        """Filter reviews by rating."""
        response = self.client.get(f'/api/reviews/service/{self.service.id}/?rating=5')
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['rating'], 5)

    def test_ordering_lowest_rating(self):
        """Order by rating ascending."""
        response = self.client.get(f'/api/reviews/service/{self.service.id}/?ordering=rating')
        results = response.data['results']
        self.assertEqual(results[0]['rating'], 1)
        self.assertEqual(results[-1]['rating'], 5)

    def test_ordering_highest_rating(self):
        """Order by rating descending."""
        response = self.client.get(f'/api/reviews/service/{self.service.id}/?ordering=-rating')
        results = response.data['results']
        self.assertEqual(results[0]['rating'], 5)
        self.assertEqual(results[-1]['rating'], 1)

