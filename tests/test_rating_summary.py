"""
Comprehensive tests for user rating summary endpoint.

Tests statistical calculations, role-based metrics, rating distributions,
and edge cases. Following TDD principles - these tests are written FIRST
and should FAIL initially.
"""

import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import override_settings

from core.models import MovingService, Booking, Review

User = get_user_model()


@pytest.mark.django_db
class TestRatingSummaryEndpoint:
    """
    Test suite for GET /api/users/<user_id>/rating-summary/ endpoint.
    
    Tests comprehensive rating statistics including:
    - Overall averages and counts
    - Role-specific statistics (provider vs student)
    - Rating distributions
    - Additional metrics (dates, completion rates)
    - Comparison metrics (percentile, trends)
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
            provider=self.provider2,
            service_name='Premium Moving',
            description='Premium moving service',
            base_price=Decimal('200.00'),
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
    
    def test_rating_summary_for_user_with_reviews_shows_correct_averages(self):
        """
        Test that rating summary for user with reviews shows correct averages.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create reviews for provider (ratings: 5, 4, 3)
        booking1 = self._create_completed_booking(
            self.student, self.provider, self.service1
        )
        self._create_review(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking1,
            rating=5,
            comment='Excellent service!'
        )
        
        booking2 = self._create_completed_booking(
            self.student2, self.provider, self.service1
        )
        self._create_review(
            reviewer=self.student2,
            reviewee=self.provider,
            booking=booking2,
            rating=4,
            comment='Very good'
        )
        
        # Create another student for third review
        student3 = User.objects.create_user(
            username='student3',
            email='student3@test.com',
            password='testpass123',
            user_type='student'
        )
        booking3 = self._create_completed_booking(
            student3, self.provider, self.service1
        )
        self._create_review(
            reviewer=student3,
            reviewee=self.provider,
            booking=booking3,
            rating=3,
            comment='Average'
        )
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify overall average: (5 + 4 + 3) / 3 = 4.0
        assert 'overall_average_rating' in response.data
        assert float(response.data['overall_average_rating']) == 4.0
        
        # Verify total reviews
        assert response.data['total_reviews'] == 3
    
    def test_rating_summary_for_user_without_reviews_returns_appropriate_defaults(self):
        """
        Test that rating summary for user without reviews returns appropriate defaults.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        url = f'/api/users/{self.student.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify defaults
        assert response.data['overall_average_rating'] is None or response.data['overall_average_rating'] == 0
        assert response.data['total_reviews'] == 0
        assert response.data['as_provider']['total_reviews'] == 0
        assert response.data['as_student']['total_reviews'] == 0
    
    def test_summary_for_nonexistent_user_returns_404(self):
        """
        Test that summary for non-existent user returns 404.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        url = '/api/users/99999/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_unauthenticated_access_allowed(self):
        """
        Test that unauthenticated users can access rating summaries (public information).
        
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
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
    
    # ========================================================================
    # Statistical Accuracy Tests
    # ========================================================================
    
    def test_statistics_are_mathematically_correct(self):
        """
        Test that all statistics are mathematically correct.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create reviews with known ratings: 5, 5, 4, 3, 2
        ratings = [5, 5, 4, 3, 2]
        
        for i, rating in enumerate(ratings):
            student = User.objects.create_user(
                username=f'student_stat_{i}',
                email=f'student_stat_{i}@test.com',
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
                rating=rating,
                comment=f'Review {i}'
            )
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Expected average: (5 + 5 + 4 + 3 + 2) / 5 = 19 / 5 = 3.8
        expected_avg = 3.8
        assert abs(float(response.data['overall_average_rating']) - expected_avg) < 0.01
        
        # Verify total
        assert response.data['total_reviews'] == 5
    
    def test_rating_distribution_percentages_sum_to_100(self):
        """
        Test that rating distribution percentages sum to 100%.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create reviews: 2x5-star, 1x4-star, 1x3-star, 1x1-star
        ratings = [5, 5, 4, 3, 1]
        
        for i, rating in enumerate(ratings):
            student = User.objects.create_user(
                username=f'student_dist_{i}',
                email=f'student_dist_{i}@test.com',
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
                rating=rating,
                comment=f'Review {i}'
            )
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify distribution
        distribution = response.data['rating_distribution']
        
        # Count should be correct
        assert distribution['5_star'] == 2
        assert distribution['4_star'] == 1
        assert distribution['3_star'] == 1
        assert distribution['2_star'] == 0
        assert distribution['1_star'] == 1
        
        # Percentages should sum to 100
        percentages = [
            distribution['5_star_percentage'],
            distribution['4_star_percentage'],
            distribution['3_star_percentage'],
            distribution['2_star_percentage'],
            distribution['1_star_percentage']
        ]
        total_percentage = sum(percentages)
        assert abs(total_percentage - 100.0) < 0.01
    
    # ========================================================================
    # Role-Based Statistics Tests
    # ========================================================================
    
    def test_separate_role_statistics_are_accurate(self):
        """
        Test that separate role statistics (provider vs student) are accurate.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Provider receives reviews as provider (from students)
        booking1 = self._create_completed_booking(
            self.student, self.provider, self.service1
        )
        self._create_review(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking1,
            rating=5,
            comment='Great provider!'
        )
        
        booking2 = self._create_completed_booking(
            self.student2, self.provider, self.service1
        )
        self._create_review(
            reviewer=self.student2,
            reviewee=self.provider,
            booking=booking2,
            rating=4,
            comment='Good provider'
        )
        
        # Student receives review as student (from provider)
        booking3 = self._create_completed_booking(
            self.student, self.provider2, self.service2
        )
        self._create_review(
            reviewer=self.provider2,
            reviewee=self.student,
            booking=booking3,
            rating=3,
            comment='Average student'
        )
        
        # Test provider statistics
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Provider should have 2 reviews as provider, 0 as student
        assert response.data['as_provider']['total_reviews'] == 2
        assert response.data['as_provider']['average_rating'] == 4.5  # (5 + 4) / 2
        assert response.data['as_student']['total_reviews'] == 0
        
        # Test student statistics
        url = f'/api/users/{self.student.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Student should have 0 reviews as provider, 1 as student
        assert response.data['as_provider']['total_reviews'] == 0
        assert response.data['as_student']['total_reviews'] == 1
        assert response.data['as_student']['average_rating'] == 3.0
    
    def test_rating_distribution_separated_by_role(self):
        """
        Test that rating distribution is separated by role.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create provider reviews (5, 4)
        for i, rating in enumerate([5, 4]):
            student = User.objects.create_user(
                username=f'student_role_{i}',
                email=f'student_role_{i}@test.com',
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
                rating=rating,
                comment=f'Review {i}'
            )
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify provider role distribution
        provider_dist = response.data['as_provider']['rating_distribution']
        assert provider_dist['5_star'] == 1
        assert provider_dist['4_star'] == 1
        assert provider_dist['3_star'] == 0
        assert provider_dist['2_star'] == 0
        assert provider_dist['1_star'] == 0
        
        # Verify student role distribution (should be empty)
        student_dist = response.data['as_student']['rating_distribution']
        assert student_dist['5_star'] == 0
        assert student_dist['4_star'] == 0
    
    # ========================================================================
    # Additional Statistics Tests
    # ========================================================================
    
    def test_most_recent_and_first_review_dates_are_correct(self):
        """
        Test that most recent and first review dates are correct.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create reviews at different times
        old_date = timezone.now() - timedelta(days=30)
        recent_date = timezone.now() - timedelta(days=1)
        
        booking1 = self._create_completed_booking(
            self.student, self.provider, self.service1,
            booking_date=old_date
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
            booking_date=recent_date
        )
        review2 = self._create_review(
            reviewer=self.student2,
            reviewee=self.provider,
            booking=booking2,
            rating=4,
            comment='Recent review'
        )
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify dates
        assert 'most_recent_review_date' in response.data
        assert 'first_review_date' in response.data
        
        # Most recent should be review2's created_at
        # First should be review1's created_at
        # We can't check exact values due to auto_now_add, but we can verify they exist
        assert response.data['most_recent_review_date'] is not None
        assert response.data['first_review_date'] is not None
    
    def test_review_completion_rate_calculated_correctly(self):
        """
        Test that review completion rate is calculated correctly.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create 5 completed bookings for provider
        for i in range(5):
            student = User.objects.create_user(
                username=f'student_comp_{i}',
                email=f'student_comp_{i}@test.com',
                password='testpass123',
                user_type='student'
            )
            booking = self._create_completed_booking(
                student, self.provider, self.service1
            )
            
            # Only create reviews for 3 of them
            if i < 3:
                self._create_review(
                    reviewer=student,
                    reviewee=self.provider,
                    booking=booking,
                    rating=5,
                    comment=f'Review {i}'
                )
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify completion rate: 3 reviews / 5 completed bookings = 60%
        assert 'review_completion_rate' in response.data
        assert abs(response.data['review_completion_rate'] - 60.0) < 0.01
        
        # Verify counts
        assert response.data['completed_bookings_count'] == 5
        assert response.data['completed_bookings_with_reviews'] == 3
    
    def test_completed_bookings_count_excludes_non_completed_statuses(self):
        """
        Test that completed bookings count only includes completed bookings.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create bookings with different statuses
        for i, status_val in enumerate(['completed', 'completed', 'pending', 'confirmed', 'cancelled']):
            student = User.objects.create_user(
                username=f'student_status_{i}',
                email=f'student_status_{i}@test.com',
                password='testpass123',
                user_type='student'
            )
            booking = Booking.objects.create(
                student=student,
                provider=self.provider,
                service=self.service1,
                booking_date=timezone.now() - timedelta(days=7),
                pickup_location='123 Start St',
                dropoff_location='456 End Ave',
                total_price=self.service1.base_price,
                status=status_val
            )
            
            # Create reviews only for completed bookings
            if status_val == 'completed':
                self._create_review(
                    reviewer=student,
                    reviewee=self.provider,
                    booking=booking,
                    rating=5,
                    comment=f'Review {i}'
                )
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Should only count 2 completed bookings
        assert response.data['completed_bookings_count'] == 2
        assert response.data['completed_bookings_with_reviews'] == 2
        assert response.data['review_completion_rate'] == 100.0
    
    # ========================================================================
    # Comparison Metrics Tests
    # ========================================================================
    
    def test_percentile_ranking_for_providers(self):
        """
        Test percentile ranking compared to other providers.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create multiple providers with different ratings
        providers = []
        for i in range(10):
            provider = User.objects.create_user(
                username=f'provider_rank_{i}',
                email=f'provider_rank_{i}@test.com',
                password='testpass123',
                user_type='provider',
                is_verified=True
            )
            providers.append(provider)
            
            service = MovingService.objects.create(
                provider=provider,
                service_name=f'Service {i}',
                description='Test service',
                base_price=Decimal('100.00'),
                availability_status=True
            )
            
            # Give each provider a review with rating based on index
            # Ratings: 1, 2, 3, 4, 5, 5, 5, 5, 5, 5
            rating = min(i + 1, 5)
            
            student = User.objects.create_user(
                username=f'student_rank_{i}',
                email=f'student_rank_{i}@test.com',
                password='testpass123',
                user_type='student'
            )
            booking = self._create_completed_booking(student, provider, service)
            self._create_review(
                reviewer=student,
                reviewee=provider,
                booking=booking,
                rating=rating,
                comment=f'Review {i}'
            )
        
        # Test provider with rating 5 (should be in top percentile)
        url = f'/api/users/{providers[9].id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify percentile exists
        assert 'percentile_ranking' in response.data
        # Provider with rating 5 should be in high percentile (>= 50)
        assert response.data['percentile_ranking'] >= 50
    
    def test_trend_indicator_shows_improving_ratings(self):
        """
        Test trend indicator shows improving ratings over time.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create reviews with improving trend: 3, 4, 5
        ratings = [3, 4, 5]
        dates = [
            timezone.now() - timedelta(days=30),
            timezone.now() - timedelta(days=15),
            timezone.now() - timedelta(days=1)
        ]
        
        for i, (rating, date) in enumerate(zip(ratings, dates)):
            student = User.objects.create_user(
                username=f'student_trend_{i}',
                email=f'student_trend_{i}@test.com',
                password='testpass123',
                user_type='student'
            )
            booking = self._create_completed_booking(
                student, self.provider, self.service1,
                booking_date=date
            )
            self._create_review(
                reviewer=student,
                reviewee=self.provider,
                booking=booking,
                rating=rating,
                comment=f'Review {i}'
            )
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify trend indicator
        assert 'trend_indicator' in response.data
        assert response.data['trend_indicator'] == 'improving'
    
    def test_trend_indicator_shows_declining_ratings(self):
        """
        Test trend indicator shows declining ratings over time.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create reviews with declining trend: 5, 4, 3
        ratings = [5, 4, 3]
        dates = [
            timezone.now() - timedelta(days=30),
            timezone.now() - timedelta(days=15),
            timezone.now() - timedelta(days=1)
        ]
        
        for i, (rating, date) in enumerate(zip(ratings, dates)):
            student = User.objects.create_user(
                username=f'student_decline_{i}',
                email=f'student_decline_{i}@test.com',
                password='testpass123',
                user_type='student'
            )
            booking = self._create_completed_booking(
                student, self.provider, self.service1,
                booking_date=date
            )
            self._create_review(
                reviewer=student,
                reviewee=self.provider,
                booking=booking,
                rating=rating,
                comment=f'Review {i}'
            )
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify trend indicator
        assert 'trend_indicator' in response.data
        assert response.data['trend_indicator'] == 'declining'
    
    def test_trend_indicator_shows_stable_ratings(self):
        """
        Test trend indicator shows stable ratings over time.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create reviews with stable trend: 4, 4, 4
        for i in range(3):
            student = User.objects.create_user(
                username=f'student_stable_{i}',
                email=f'student_stable_{i}@test.com',
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
                rating=4,
                comment=f'Review {i}'
            )
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify trend indicator
        assert 'trend_indicator' in response.data
        assert response.data['trend_indicator'] == 'stable'
    
    # ========================================================================
    # Edge Case Tests
    # ========================================================================
    
    def test_calculations_handle_single_review(self):
        """
        Test that calculations handle edge case of single review.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        booking = self._create_completed_booking(
            self.student, self.provider, self.service1
        )
        self._create_review(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking,
            rating=5,
            comment='Only review'
        )
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify calculations work with single review
        assert response.data['overall_average_rating'] == 5.0
        assert response.data['total_reviews'] == 1
        assert response.data['rating_distribution']['5_star'] == 1
        assert response.data['rating_distribution']['5_star_percentage'] == 100.0
    
    def test_calculations_handle_all_same_ratings(self):
        """
        Test that calculations handle all reviews having same rating.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create 5 reviews all with rating 5
        for i in range(5):
            student = User.objects.create_user(
                username=f'student_same_{i}',
                email=f'student_same_{i}@test.com',
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
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify calculations
        assert response.data['overall_average_rating'] == 5.0
        assert response.data['total_reviews'] == 5
        assert response.data['rating_distribution']['5_star'] == 5
        assert response.data['rating_distribution']['5_star_percentage'] == 100.0
        assert response.data['rating_distribution']['4_star'] == 0
    
    def test_user_with_no_reviews_has_null_trend(self):
        """
        Test that user with no reviews has null/none trend indicator.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        url = f'/api/users/{self.student.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify trend is null or 'none' for user with no reviews
        assert response.data['trend_indicator'] in [None, 'none', 'stable']
    
    def test_user_with_insufficient_reviews_for_trend_analysis(self):
        """
        Test that user with only 1-2 reviews has appropriate trend handling.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create single review
        booking = self._create_completed_booking(
            self.student, self.provider, self.service1
        )
        self._create_review(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking,
            rating=5,
            comment='Only review'
        )
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # With only 1 review, trend should be 'stable' or 'none'
        assert response.data['trend_indicator'] in ['stable', 'none']
    
    # ========================================================================
    # Performance Tests
    # ========================================================================
    
    def test_aggregations_are_efficient_no_n_plus_1_queries(self):
        """
        Test that aggregations are efficient with no N+1 query problems.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create 20 reviews
        for i in range(20):
            student = User.objects.create_user(
                username=f'student_perf_{i}',
                email=f'student_perf_{i}@test.com',
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
                rating=(i % 5) + 1,  # Ratings 1-5
                comment=f'Review {i}'
            )
        
        # Count queries
        from django.test.utils import override_settings
        from django.db import connection, reset_queries
        
        reset_queries()
        
        with override_settings(DEBUG=True):
            url = f'/api/users/{self.provider.id}/rating-summary/'
            response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Should use aggregation queries, not individual queries per review
        # Maximum acceptable queries: ~10 (user lookup, aggregations, counts)
        num_queries = len(connection.queries)
        assert num_queries < 15, f"Too many queries: {num_queries}"
    
    def test_summaries_update_when_new_reviews_added(self):
        """
        Test that summaries update correctly when new reviews are added.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create initial review
        booking1 = self._create_completed_booking(
            self.student, self.provider, self.service1
        )
        self._create_review(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking1,
            rating=5,
            comment='First review'
        )
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['overall_average_rating'] == 5.0
        assert response.data['total_reviews'] == 1
        
        # Add another review
        booking2 = self._create_completed_booking(
            self.student2, self.provider, self.service1
        )
        self._create_review(
            reviewer=self.student2,
            reviewee=self.provider,
            booking=booking2,
            rating=3,
            comment='Second review'
        )
        
        # Get updated summary
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        # New average: (5 + 3) / 2 = 4.0
        assert response.data['overall_average_rating'] == 4.0
        assert response.data['total_reviews'] == 2
    
    # ========================================================================
    # Review Pattern Tests
    # ========================================================================
    
    def test_summary_with_all_high_ratings(self):
        """
        Test summary with all high ratings (4-5 stars).
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create reviews with ratings 4, 5, 5, 4, 5
        ratings = [4, 5, 5, 4, 5]
        
        for i, rating in enumerate(ratings):
            student = User.objects.create_user(
                username=f'student_high_{i}',
                email=f'student_high_{i}@test.com',
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
                rating=rating,
                comment=f'Review {i}'
            )
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Average: (4 + 5 + 5 + 4 + 5) / 5 = 23 / 5 = 4.6
        assert abs(float(response.data['overall_average_rating']) - 4.6) < 0.01
        
        # Distribution should show mostly high ratings
        dist = response.data['rating_distribution']
        assert dist['5_star'] == 3
        assert dist['4_star'] == 2
        assert dist['3_star'] == 0
        assert dist['2_star'] == 0
        assert dist['1_star'] == 0
    
    def test_summary_with_all_low_ratings(self):
        """
        Test summary with all low ratings (1-2 stars).
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create reviews with ratings 1, 2, 1, 2, 1
        ratings = [1, 2, 1, 2, 1]
        
        for i, rating in enumerate(ratings):
            student = User.objects.create_user(
                username=f'student_low_{i}',
                email=f'student_low_{i}@test.com',
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
                rating=rating,
                comment=f'Review {i}'
            )
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Average: (1 + 2 + 1 + 2 + 1) / 5 = 7 / 5 = 1.4
        assert abs(float(response.data['overall_average_rating']) - 1.4) < 0.01
        
        # Distribution should show mostly low ratings
        dist = response.data['rating_distribution']
        assert dist['5_star'] == 0
        assert dist['4_star'] == 0
        assert dist['3_star'] == 0
        assert dist['2_star'] == 2
        assert dist['1_star'] == 3
    
    def test_summary_with_mixed_ratings(self):
        """
        Test summary with mixed ratings across all levels.
        
        RED: This test should FAIL because the endpoint doesn't exist yet.
        """
        # Create reviews with ratings 1, 2, 3, 4, 5
        ratings = [1, 2, 3, 4, 5]
        
        for i, rating in enumerate(ratings):
            student = User.objects.create_user(
                username=f'student_mixed_{i}',
                email=f'student_mixed_{i}@test.com',
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
                rating=rating,
                comment=f'Review {i}'
            )
        
        url = f'/api/users/{self.provider.id}/rating-summary/'
        response = self.client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Average: (1 + 2 + 3 + 4 + 5) / 5 = 15 / 5 = 3.0
        assert abs(float(response.data['overall_average_rating']) - 3.0) < 0.01
        
        # Distribution should be even
        dist = response.data['rating_distribution']
        assert dist['5_star'] == 1
        assert dist['4_star'] == 1
        assert dist['3_star'] == 1
        assert dist['2_star'] == 1
        assert dist['1_star'] == 1
