"""
Tests for Django signals that automatically recalculate ratings.

Following TDD principles: These tests are written BEFORE signal implementation.
All tests should FAIL initially, then pass after signal implementation.
"""

import threading
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TransactionTestCase
from django.utils import timezone
from core.models import MovingService, Booking, Review

User = get_user_model()


class ReviewSignalTests(TransactionTestCase):
    """
    Test suite for review signal functionality.
    
    Uses TransactionTestCase for proper database visibility across threads
    and to test transaction behavior correctly.
    """
    
    def setUp(self):
        """Set up test data for each test."""
        # Create student user
        self.student = User.objects.create_user(
            username='student1',
            email='student1@test.com',
            password='testpass123',
            user_type='student'
        )
        
        # Create provider user
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider1@test.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        
        # Create moving service
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Moving Service',
            description='A test service',
            base_price=Decimal('100.00'),
            availability_status=True
        )
        
        # Create completed booking
        self.booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() - timezone.timedelta(days=1),
            pickup_location='123 Test St',
            dropoff_location='456 Test Ave',
            total_price=Decimal('100.00'),
            status='completed'
        )
    
    def test_creating_review_triggers_signal_and_updates_ratings(self):
        """
        Test that creating a review triggers signal and updates both user and service ratings.
        
        Expected behavior:
        - Review creation should trigger post_save signal
        - Provider's avg_rating_as_provider should be updated
        - Service's rating_average should be updated
        - Service's total_reviews should be incremented
        """
        # Verify initial state
        self.provider.refresh_from_db()
        self.service.refresh_from_db()
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('0.00'))
        self.assertEqual(self.service.rating_average, Decimal('0.00'))
        self.assertEqual(self.service.total_reviews, 0)
        
        # Create review
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=4,
            comment='Great service!'
        )
        
        # Refresh from database to get updated values
        self.provider.refresh_from_db()
        self.service.refresh_from_db()
        
        # Verify ratings were updated
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('4.00'))
        self.assertEqual(self.service.rating_average, Decimal('4.00'))
        self.assertEqual(self.service.total_reviews, 1)
    
    def test_single_review_calculates_correct_average(self):
        """
        Test that a single review results in average equal to that review's rating.
        
        Edge case: First review should set average to exactly that rating.
        """
        # Create review with rating of 5
        Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='Excellent!'
        )
        
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('5.00'))
    
    def test_multiple_reviews_calculate_correct_average(self):
        """
        Test that multiple reviews calculate accurate average.
        
        Mathematical accuracy test: (5 + 3 + 4) / 3 = 4.00
        """
        # Create second student and booking for additional reviews
        student2 = User.objects.create_user(
            username='student2',
            email='student2@test.com',
            password='testpass123',
            user_type='student'
        )
        
        booking2 = Booking.objects.create(
            student=student2,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() - timezone.timedelta(days=2),
            pickup_location='789 Test Rd',
            dropoff_location='101 Test Blvd',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        student3 = User.objects.create_user(
            username='student3',
            email='student3@test.com',
            password='testpass123',
            user_type='student'
        )
        
        booking3 = Booking.objects.create(
            student=student3,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() - timezone.timedelta(days=3),
            pickup_location='202 Test Ln',
            dropoff_location='303 Test Way',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        # Create three reviews: 5, 3, 4 -> average should be 4.00
        Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='Excellent!'
        )
        
        Review.objects.create(
            reviewer=student2,
            reviewee=self.provider,
            booking=booking2,
            rating=3,
            comment='Good'
        )
        
        Review.objects.create(
            reviewer=student3,
            reviewee=self.provider,
            booking=booking3,
            rating=4,
            comment='Very good'
        )
        
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('4.00'))
    
    def test_service_rating_average_updates_correctly(self):
        """
        Test that service rating_average field updates correctly.
        """
        # Create review
        Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=4,
            comment='Great service!'
        )
        
        self.service.refresh_from_db()
        self.assertEqual(self.service.rating_average, Decimal('4.00'))
    
    def test_service_total_reviews_increments_correctly(self):
        """
        Test that service total_reviews counter increments correctly.
        """
        # Verify initial count
        self.service.refresh_from_db()
        self.assertEqual(self.service.total_reviews, 0)
        
        # Create first review
        Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=4,
            comment='Great service!'
        )
        
        self.service.refresh_from_db()
        self.assertEqual(self.service.total_reviews, 1)
        
        # Create second review
        student2 = User.objects.create_user(
            username='student2',
            email='student2@test.com',
            password='testpass123',
            user_type='student'
        )
        
        booking2 = Booking.objects.create(
            student=student2,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() - timezone.timedelta(days=2),
            pickup_location='789 Test Rd',
            dropoff_location='101 Test Blvd',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        Review.objects.create(
            reviewer=student2,
            reviewee=self.provider,
            booking=booking2,
            rating=5,
            comment='Excellent!'
        )
        
        self.service.refresh_from_db()
        self.assertEqual(self.service.total_reviews, 2)
    
    def test_concurrent_review_submissions_update_ratings_without_corruption(self):
        """
        Test that concurrent review submissions don't cause race conditions.
        
        This test uses threading to simulate concurrent review creation.
        With proper locking (select_for_update) and retry logic, all reviews should be counted
        and the final average should be mathematically correct.
        """
        import time
        from django.db.utils import OperationalError
        
        # Create multiple students and bookings
        students = []
        bookings = []
        
        for i in range(5):
            student = User.objects.create_user(
                username=f'concurrent_student{i}',
                email=f'concurrent{i}@test.com',
                password='testpass123',
                user_type='student'
            )
            students.append(student)
            
            booking = Booking.objects.create(
                student=student,
                provider=self.provider,
                service=self.service,
                booking_date=timezone.now() - timezone.timedelta(days=i+1),
                pickup_location=f'{i} Test St',
                dropoff_location=f'{i+1} Test Ave',
                total_price=Decimal('100.00'),
                status='completed'
            )
            bookings.append(booking)
        
        # Function to create review in thread with retry logic
        def create_review_with_retry(student, booking, rating):
            max_retries = 5
            retry_delay = 0.05  # 50ms
            
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        Review.objects.create(
                            reviewer=student,
                            reviewee=self.provider,
                            booking=booking,
                            rating=rating,
                            comment=f'Review from {student.username}'
                        )
                    # Success - break out of retry loop
                    break
                except OperationalError as e:
                    if 'Deadlock' in str(e) or '1213' in str(e):
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            print(f"Max retries exceeded for {student.username}: {e}")
                            raise
                    else:
                        print(f"Non-deadlock error for {student.username}: {e}")
                        raise
                except Exception as e:
                    print(f"Error creating review for {student.username}: {e}")
                    raise
        
        # Create threads to submit reviews concurrently
        # Ratings: 5, 4, 3, 4, 4 -> average should be 4.00
        ratings = [5, 4, 3, 4, 4]
        threads = []
        
        for i in range(5):
            thread = threading.Thread(
                target=create_review_with_retry,
                args=(students[i], bookings[i], ratings[i])
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all reviews were created
        review_count = Review.objects.filter(reviewee=self.provider).count()
        self.assertEqual(review_count, 5)
        
        # Verify ratings are correct
        self.provider.refresh_from_db()
        self.service.refresh_from_db()
        
        # Average of [5, 4, 3, 4, 4] = 20/5 = 4.00
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('4.00'))
        self.assertEqual(self.service.rating_average, Decimal('4.00'))
        self.assertEqual(self.service.total_reviews, 5)
    
    def test_signal_handles_division_by_zero_gracefully(self):
        """
        Test that signal handles first review without errors.
        
        Edge case: When there are no previous reviews, avoid division by zero.
        """
        # Verify no reviews exist
        self.assertEqual(Review.objects.filter(reviewee=self.provider).count(), 0)
        
        # Create first review - should not raise any errors
        try:
            Review.objects.create(
                reviewer=self.student,
                reviewee=self.provider,
                booking=self.booking,
                rating=5,
                comment='First review!'
            )
        except Exception as e:
            self.fail(f"Signal raised exception on first review: {e}")
        
        # Verify rating was set correctly
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('5.00'))
    
    def test_ratings_update_for_provider_role(self):
        """
        Test that provider ratings update when provider is reviewed.
        
        When a student reviews a provider, the provider's avg_rating_as_provider
        should be updated, not avg_rating_as_student.
        """
        # Create review where student reviews provider
        Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=4,
            comment='Good provider!'
        )
        
        self.provider.refresh_from_db()
        
        # Provider's provider rating should be updated
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('4.00'))
        
        # Provider's student rating should remain 0
        self.assertEqual(self.provider.avg_rating_as_student, Decimal('0.00'))
    
    def test_ratings_update_for_student_role(self):
        """
        Test that student ratings update when student is reviewed.
        
        When a provider reviews a student, the student's avg_rating_as_student
        should be updated, not avg_rating_as_provider.
        """
        # Create a booking where provider can review student
        # (In real scenario, this might be for a different service type)
        # For this test, we'll create a reverse review
        
        # Create another completed booking
        booking2 = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() - timezone.timedelta(days=2),
            pickup_location='789 Test Rd',
            dropoff_location='101 Test Blvd',
            total_price=Decimal('100.00'),
            status='completed'
        )
        
        # Provider reviews student
        Review.objects.create(
            reviewer=self.provider,
            reviewee=self.student,
            booking=booking2,
            rating=5,
            comment='Great student!'
        )
        
        self.student.refresh_from_db()
        
        # Student's student rating should be updated
        self.assertEqual(self.student.avg_rating_as_student, Decimal('5.00'))
        
        # Student's provider rating should remain 0
        self.assertEqual(self.student.avg_rating_as_provider, Decimal('0.00'))
    
    def test_rating_calculation_with_all_fives(self):
        """
        Test mathematical accuracy: all 5-star reviews should average to 5.00.
        """
        # Create multiple students and bookings
        for i in range(3):
            student = User.objects.create_user(
                username=f'student_five_{i}',
                email=f'five{i}@test.com',
                password='testpass123',
                user_type='student'
            )
            
            booking = Booking.objects.create(
                student=student,
                provider=self.provider,
                service=self.service,
                booking_date=timezone.now() - timezone.timedelta(days=i+1),
                pickup_location=f'{i} Test St',
                dropoff_location=f'{i+1} Test Ave',
                total_price=Decimal('100.00'),
                status='completed'
            )
            
            Review.objects.create(
                reviewer=student,
                reviewee=self.provider,
                booking=booking,
                rating=5,
                comment='Perfect!'
            )
        
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('5.00'))
    
    def test_rating_calculation_with_all_ones(self):
        """
        Test mathematical accuracy: all 1-star reviews should average to 1.00.
        """
        # Create multiple students and bookings
        for i in range(3):
            student = User.objects.create_user(
                username=f'student_one_{i}',
                email=f'one{i}@test.com',
                password='testpass123',
                user_type='student'
            )
            
            booking = Booking.objects.create(
                student=student,
                provider=self.provider,
                service=self.service,
                booking_date=timezone.now() - timezone.timedelta(days=i+1),
                pickup_location=f'{i} Test St',
                dropoff_location=f'{i+1} Test Ave',
                total_price=Decimal('100.00'),
                status='completed'
            )
            
            Review.objects.create(
                reviewer=student,
                reviewee=self.provider,
                booking=booking,
                rating=1,
                comment='Poor service'
            )
        
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('1.00'))
    
    def test_rating_calculation_with_mixed_ratings(self):
        """
        Test mathematical accuracy with mixed ratings.
        
        Ratings: [5, 3, 4, 2] -> (5+3+4+2)/4 = 14/4 = 3.50
        """
        ratings = [5, 3, 4, 2]
        
        for i, rating in enumerate(ratings):
            student = User.objects.create_user(
                username=f'student_mixed_{i}',
                email=f'mixed{i}@test.com',
                password='testpass123',
                user_type='student'
            )
            
            booking = Booking.objects.create(
                student=student,
                provider=self.provider,
                service=self.service,
                booking_date=timezone.now() - timezone.timedelta(days=i+1),
                pickup_location=f'{i} Test St',
                dropoff_location=f'{i+1} Test Ave',
                total_price=Decimal('100.00'),
                status='completed'
            )
            
            Review.objects.create(
                reviewer=student,
                reviewee=self.provider,
                booking=booking,
                rating=rating,
                comment=f'Rating: {rating}'
            )
        
        self.provider.refresh_from_db()
        self.service.refresh_from_db()
        
        # Average should be 3.50
        self.assertEqual(self.provider.avg_rating_as_provider, Decimal('3.50'))
        self.assertEqual(self.service.rating_average, Decimal('3.50'))
