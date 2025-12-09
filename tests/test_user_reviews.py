"""
Comprehensive tests for user reviews endpoint.

Tests bidirectional review retrieval, filtering, statistics, and pagination.
Following TDD principles - these tests are written FIRST and should FAIL initially.
"""

import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from core.models import MovingService, Booking, Review

User = get_user_model()


@pytest.mark.django_db
class TestUserReviewsEndpoint:
    """
    Test suite for GET /api/reviews/user/<user_id>/ endpoint.
    
    Tests bidirectional review display:
    - Reviews received as a provider (from students)
    - Reviews received as a student (from providers)
    """
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data for all tests."""
        self.client = APIClient()
        
        # Create users
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        
        self.student = User.objects.create_user(
            username='student1',
            email='student@test.com',
            password='testpass123',
            user_type='student'
        )
        
        
        # Create a user who is both provider and student (dual role)
        # Note: In the current model, a user can only have ONE user_type.
        # To test bidirectional reviews, we create a provider who receives reviews as a provider,
        # and a separate student user to simulate the "student" context.
        self.dual_user = User.objects.create_user(
            username='dualuser',
            email='dual@test.com',
            password='testpass123',
            user_type='provider',  # Primary type
            is_verified=True
        )
        
        # Create a student user to test the "student" context for dual-role scenario
        # This student will book services and receive reviews as a student
        self.dual_student = User.objects.create_user(
            username='dualstudent',
            email='dualstudent@test.com',
            password='testpass123',
            user_type='student'
        )
        
        # Create additional users for reviews
        self.student2 = User.objects.create_user(
            username='student2',
            email='student2@test.com',
            password='testpass123',
            user_type='student'
        )
        
        self.provider2 = User.objects.create_user(
            username='provider2',
            email='provider2@test.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        
        # Create services
        self.service1 = MovingService.objects.create(
            provider=self.provider,
            service_name='Basic Moving',
            description='Basic moving service',
            base_price=Decimal('100.00'),
            availability_status=True
        )
        
        self.service2 = MovingService.objects.create(
            provider=self.dual_user,
            service_name='Premium Moving',
            description='Premium moving service',
            base_price=Decimal('200.00'),
            availability_status=True
        )
        
        self.service3 = MovingService.objects.create(
            provider=self.provider2,
            service_name='Express Moving',
            description='Express moving service',
            base_price=Decimal('150.00'),
            availability_status=True
        )
    
    def _create_completed_booking(self, student, provider, service, booking_date=None):
        """Helper to create a completed booking."""
        if booking_date is None:
            booking_date = timezone.now() - timedelta(days=7)
        
        booking = Booking.objects.create(
            student=student,
            provider=provider,
            service=service,
            booking_date=booking_date,
            pickup_location='123 Start St',
            dropoff_location='456 End Ave',
            total_price=service.base_price,
            status='completed'
        )
        return booking
    
    def _create_review(self, reviewer, reviewee, booking, rating, comment):
        """Helper to create a review."""
        review = Review.objects.create(
            reviewer=reviewer,
            reviewee=reviewee,
            booking=booking,
            rating=rating,
            comment=comment
        )
        return review
    
    # ========================================================================
    # Basic Functionality Tests
    # ========================================================================
    
    def test_retrieve_reviews_for_existing_user_returns_correct_reviews(self):
        """
        Test that retrieving reviews for an existing user returns correct reviews.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create completed bookings
        booking1 = self._create_completed_booking(
            self.student, self.provider, self.service1
        )
        booking2 = self._create_completed_booking(
            self.student2, self.provider, self.service1
        )
        
        # Create reviews for provider (provider receives these)
        review1 = self._create_review(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking1,
            rating=5,
            comment='Excellent service!'
        )
        review2 = self._create_review(
            reviewer=self.student2,
            reviewee=self.provider,
            booking=booking2,
            rating=4,
            comment='Very good service'
        )
        
        # Retrieve reviews for provider
        url = f'/api/reviews/user/{self.provider.id}/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert len(response.data['results']) == 2
        
        # Verify review data
        review_ids = [r['id'] for r in response.data['results']]
        assert review1.id in review_ids
        assert review2.id in review_ids
    
    def test_user_with_no_reviews_returns_empty_result(self):
        """
        Test that a user with no reviews returns an empty result.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        url = f'/api/reviews/user/{self.student.id}/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert len(response.data['results']) == 0
        assert response.data['count'] == 0
    
    def test_retrieving_reviews_for_nonexistent_user_returns_404(self):
        """
        Test that retrieving reviews for a non-existent user returns 404.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        url = '/api/reviews/user/99999/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_unauthenticated_access_works(self):
        """
        Test that unauthenticated users can access reviews (public information).
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create a review
        booking = self._create_completed_booking(
            self.student, self.provider, self.service1
        )
        self._create_review(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking,
            rating=5,
            comment='Great!'
        )
        
        # Access without authentication
        url = f'/api/reviews/user/{self.provider.id}/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
    
    # ========================================================================
    # Bidirectional Review Tests
    # ========================================================================
    
    def test_reviews_are_separated_by_user_role(self):
        """
        Test that reviews are properly separated by user role (provider vs student).
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create bookings where dual_user acts as provider
        booking1 = self._create_completed_booking(
            self.student, self.dual_user, self.service2
        )
        # Create booking where dual_student acts as student
        booking2 = self._create_completed_booking(
            self.dual_student, self.provider2, self.service3
        )
        
        # Review for dual_user as provider (from student)
        review1 = self._create_review(
            reviewer=self.student,
            reviewee=self.dual_user,
            booking=booking1,
            rating=5,
            comment='Great provider!'
        )
        
        # Review for dual_student as student (from provider)
        review2 = self._create_review(
            reviewer=self.provider2,
            reviewee=self.dual_student,
            booking=booking2,
            rating=4,
            comment='Good student!'
        )
        
        # Retrieve reviews for dual_user (provider reviews)
        url = f'/api/reviews/user/{self.dual_user.id}/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1  # Only provider review
        
        # Verify review has context field indicating role
        assert 'review_context' in response.data['results'][0]
        assert response.data['results'][0]['review_context'] == 'as_provider'
        
        # Retrieve reviews for dual_student (student reviews)
        url = f'/api/reviews/user/{self.dual_student.id}/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1  # Only student review
        assert response.data['results'][0]['review_context'] == 'as_student'
    
    def test_reviews_show_correct_reviewer_information(self):
        """
        Test that reviews display correct reviewer information.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        booking = self._create_completed_booking(
            self.student, self.provider, self.service1
        )
        review = self._create_review(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking,
            rating=5,
            comment='Excellent!'
        )
        
        url = f'/api/reviews/user/{self.provider.id}/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        review_data = response.data['results'][0]
        
        # Verify reviewer information
        assert 'reviewer' in review_data
        assert review_data['reviewer']['id'] == self.student.id
        assert review_data['reviewer']['email'] == self.student.email
        assert review_data['reviewer']['user_type'] == 'student'
    
    def test_reviews_display_context_appropriately(self):
        """
        Test that reviews display appropriate context (service name for provider reviews).
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        booking = self._create_completed_booking(
            self.student, self.provider, self.service1
        )
        review = self._create_review(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking,
            rating=5,
            comment='Great service!'
        )
        
        url = f'/api/reviews/user/{self.provider.id}/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        review_data = response.data['results'][0]
        
        # For provider reviews, should include service name
        assert 'service_name' in review_data
        assert review_data['service_name'] == self.service1.service_name
        assert review_data['review_context'] == 'as_provider'
    
    def test_users_who_are_both_providers_and_students_with_reviews_in_both_roles(self):
        """
        Test users who have reviews in both provider and student roles.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # dual_user receives review as provider
        booking1 = self._create_completed_booking(
            self.student, self.dual_user, self.service2
        )
        review1 = self._create_review(
            reviewer=self.student,
            reviewee=self.dual_user,
            booking=booking1,
            rating=5,
            comment='Great provider!'
        )
        
        # dual_student receives review as student
        booking2 = self._create_completed_booking(
            self.dual_student, self.provider2, self.service3
        )
        review2 = self._create_review(
            reviewer=self.provider2,
            reviewee=self.dual_student,
            booking=booking2,
            rating=3,
            comment='Average student'
        )
        
        # Test dual_user (provider) - should only have provider reviews
        url = f'/api/reviews/user/{self.dual_user.id}/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['review_context'] == 'as_provider'
        
        # Test dual_student - should only have student reviews
        url = f'/api/reviews/user/{self.dual_student.id}/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['review_context'] == 'as_student'
    
    # ========================================================================
    # Statistics Tests
    # ========================================================================
    
    def test_statistics_are_calculated_accurately_for_each_role(self):
        """
        Test that statistics are calculated accurately for each role.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create reviews for dual_user as provider
        booking1 = self._create_completed_booking(
            self.student, self.dual_user, self.service2
        )
        self._create_review(
            reviewer=self.student,
            reviewee=self.dual_user,
            booking=booking1,
            rating=5,
            comment='Excellent provider!'
        )
        
        booking2 = self._create_completed_booking(
            self.student2, self.dual_user, self.service2
        )
        self._create_review(
            reviewer=self.student2,
            reviewee=self.dual_user,
            booking=booking2,
            rating=4,
            comment='Good provider'
        )
        
        # Create review for dual_student as student
        booking3 = self._create_completed_booking(
            self.dual_student, self.provider2, self.service3
        )
        self._create_review(
            reviewer=self.provider2,
            reviewee=self.dual_student,
            booking=booking3,
            rating=3,
            comment='Average student'
        )
        
        # Test dual_user (provider) statistics
        url = f'/api/reviews/user/{self.dual_user.id}/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'statistics' in response.data
        
        stats = response.data['statistics']
        
        # Provider statistics for dual_user
        assert 'as_provider' in stats
        assert stats['as_provider']['average_rating'] == 4.5  # (5 + 4) / 2
        assert stats['as_provider']['total_reviews'] == 2
        assert 'rating_distribution' in stats['as_provider']
        
        # Student statistics should be empty for dual_user (they're a provider)
        assert 'as_student' in stats
        assert stats['as_student']['total_reviews'] == 0
        
        # Test dual_student statistics
        url = f'/api/reviews/user/{self.dual_student.id}/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        stats = response.data['statistics']
        
        # Student statistics for dual_student
        assert 'as_student' in stats
        assert stats['as_student']['average_rating'] == 3.0
        assert stats['as_student']['total_reviews'] == 1
        assert 'rating_distribution' in stats['as_student']
    
    # ========================================================================
    # Filtering Tests
    # ========================================================================
    
    def test_filtering_by_role_works_correctly(self):
        """
        Test that filtering by role (provider/student) works correctly.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create reviews for dual_user in both roles
        booking1 = self._create_completed_booking(
            self.student, self.dual_user, self.service2
        )
        self._create_review(
            reviewer=self.student,
            reviewee=self.dual_user,
            booking=booking1,
            rating=5,
            comment='Great provider!'
        )
        
        booking2 = self._create_completed_booking(
            self.dual_student, self.provider2, self.service3
        )
        self._create_review(
            reviewer=self.provider2,
            reviewee=self.dual_student,
            booking=booking2,
            rating=3,
            comment='Average student'
        )
        
        # Filter for provider reviews only
        url = f'/api/reviews/user/{self.dual_user.id}/?role=provider'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['review_context'] == 'as_provider'
        
        # Filter for student reviews only (using dual_student)
        url = f'/api/reviews/user/{self.dual_student.id}/?role=student'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['review_context'] == 'as_student'
    
    def test_sort_by_date_newest_first_by_default(self):
        """
        Test that reviews are sorted by date (newest first) by default.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create reviews at different times
        booking1 = self._create_completed_booking(
            self.student, self.provider, self.service1,
            booking_date=timezone.now() - timedelta(days=10)
        )
        review1 = self._create_review(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking1,
            rating=5,
            comment='First review'
        )
        
        booking2 = self._create_completed_booking(
            self.student2, self.provider, self.service1,
            booking_date=timezone.now() - timedelta(days=5)
        )
        review2 = self._create_review(
            reviewer=self.student2,
            reviewee=self.provider,
            booking=booking2,
            rating=4,
            comment='Second review'
        )
        
        url = f'/api/reviews/user/{self.provider.id}/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        reviews = response.data['results']
        
        # Newest should be first
        assert reviews[0]['id'] == review2.id
        assert reviews[1]['id'] == review1.id
    
    def test_sort_by_rating_highest_first(self):
        """
        Test sorting by rating (highest first).
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create reviews with different ratings
        booking1 = self._create_completed_booking(
            self.student, self.provider, self.service1
        )
        review1 = self._create_review(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking1,
            rating=3,
            comment='Average'
        )
        
        booking2 = self._create_completed_booking(
            self.student2, self.provider, self.service1
        )
        review2 = self._create_review(
            reviewer=self.student2,
            reviewee=self.provider,
            booking=booking2,
            rating=5,
            comment='Excellent'
        )
        
        url = f'/api/reviews/user/{self.provider.id}/?sort=rating_desc'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        reviews = response.data['results']
        
        # Highest rating first
        assert reviews[0]['rating'] == 5
        assert reviews[1]['rating'] == 3
    
    def test_sort_by_rating_lowest_first(self):
        """
        Test sorting by rating (lowest first).
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create reviews with different ratings
        booking1 = self._create_completed_booking(
            self.student, self.provider, self.service1
        )
        review1 = self._create_review(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking1,
            rating=5,
            comment='Excellent'
        )
        
        booking2 = self._create_completed_booking(
            self.student2, self.provider, self.service1
        )
        review2 = self._create_review(
            reviewer=self.student2,
            reviewee=self.provider,
            booking=booking2,
            rating=2,
            comment='Poor'
        )
        
        url = f'/api/reviews/user/{self.provider.id}/?sort=rating_asc'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        reviews = response.data['results']
        
        # Lowest rating first
        assert reviews[0]['rating'] == 2
        assert reviews[1]['rating'] == 5
    
    def test_filter_by_rating_threshold(self):
        """
        Test filtering by minimum rating threshold.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create reviews with different ratings
        booking1 = self._create_completed_booking(
            self.student, self.provider, self.service1
        )
        self._create_review(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking1,
            rating=5,
            comment='Excellent'
        )
        
        booking2 = self._create_completed_booking(
            self.student2, self.provider, self.service1
        )
        self._create_review(
            reviewer=self.student2,
            reviewee=self.provider,
            booking=booking2,
            rating=3,
            comment='Average'
        )
        
        # Filter for ratings >= 4
        url = f'/api/reviews/user/{self.provider.id}/?min_rating=4'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['rating'] >= 4
    
    # ========================================================================
    # Pagination Tests
    # ========================================================================
    
    def test_pagination_handles_large_review_counts(self):
        """
        Test that pagination works correctly for users with many reviews.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create 15 reviews for provider
        for i in range(15):
            student = User.objects.create_user(
                username=f'student_bulk_{i}',
                email=f'student_bulk_{i}@test.com',
                password='testpass123',
                user_type='student'
            )
            booking = self._create_completed_booking(
                student, self.provider, self.service1
            )
            self._create_review(
                reviewer=student,
                reviewee=self.provider,
                booking=booking,
                rating=5,
                comment=f'Review {i}'
            )
        
        # Get first page (default page size should be 10)
        url = f'/api/reviews/user/{self.provider.id}/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert 'count' in response.data
        assert 'next' in response.data
        assert 'previous' in response.data
        
        assert response.data['count'] == 15
        assert len(response.data['results']) == 10  # Default page size
        assert response.data['next'] is not None
        assert response.data['previous'] is None
        
        # Get second page
        url = f'/api/reviews/user/{self.provider.id}/?page=2'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 5  # Remaining reviews
        assert response.data['next'] is None
        assert response.data['previous'] is not None
