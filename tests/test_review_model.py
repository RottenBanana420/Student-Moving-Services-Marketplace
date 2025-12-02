"""
Comprehensive test suite for Review model.

These tests are designed to FAIL until the Review model is properly implemented.
Following TDD principles: write tests first, then implement code to pass them.
NEVER modify these tests - only fix the model implementation.
"""

from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from core.models import MovingService, Booking, Review


User = get_user_model()


class ReviewModelRatingValidationTests(TestCase):
    """Test rating field validation for 1-5 range."""
    
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
            user_type='provider'
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Moving Service',
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
    
    def test_rating_zero_raises_validation_error(self):
        """Rating of 0 must raise ValidationError."""
        with self.assertRaises(ValidationError):
            review = Review(
                reviewer=self.student,
                reviewee=self.provider,
                booking=self.booking,
                rating=0,
                comment='Test comment'
            )
            review.full_clean()
    
    def test_rating_six_raises_validation_error(self):
        """Rating of 6 must raise ValidationError."""
        with self.assertRaises(ValidationError):
            review = Review(
                reviewer=self.student,
                reviewee=self.provider,
                booking=self.booking,
                rating=6,
                comment='Test comment'
            )
            review.full_clean()
    
    def test_rating_negative_raises_validation_error(self):
        """Negative rating must raise ValidationError."""
        with self.assertRaises(ValidationError):
            review = Review(
                reviewer=self.student,
                reviewee=self.provider,
                booking=self.booking,
                rating=-1,
                comment='Test comment'
            )
            review.full_clean()
    
    def test_rating_one_is_valid(self):
        """Rating of 1 should be accepted."""
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=1,
            comment='Poor service'
        )
        self.assertEqual(review.rating, 1)
    
    def test_rating_five_is_valid(self):
        """Rating of 5 should be accepted."""
        # Create a new booking for this test
        booking2 = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=2),
            pickup_location='789 Elm St',
            dropoff_location='321 Pine Ave',
            total_price=Decimal('150.00'),
            status='completed'
        )
        
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking2,
            rating=5,
            comment='Excellent service!'
        )
        self.assertEqual(review.rating, 5)
    
    def test_rating_three_is_valid(self):
        """Rating of 3 (mid-range) should be accepted."""
        # Create a new booking for this test
        booking3 = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=3),
            pickup_location='111 Maple St',
            dropoff_location='222 Birch Ave',
            total_price=Decimal('120.00'),
            status='completed'
        )
        
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking3,
            rating=3,
            comment='Average service'
        )
        self.assertEqual(review.rating, 3)


class ReviewModelUniqueConstraintTests(TestCase):
    """Test unique constraint preventing duplicate reviews per booking."""
    
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
            user_type='provider'
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Moving Service',
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
    
    def test_duplicate_review_for_same_booking_raises_integrity_error(self):
        """Creating two reviews for the same booking must raise IntegrityError."""
        Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='First review'
        )
        
        # Attempting to create another review for the same booking should fail
        with self.assertRaises(IntegrityError):
            Review.objects.create(
                reviewer=self.provider,
                reviewee=self.student,
                booking=self.booking,
                rating=4,
                comment='Second review'
            )
    
    def test_different_bookings_can_have_reviews(self):
        """Different bookings should be able to have their own reviews."""
        booking2 = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=2),
            pickup_location='789 Elm St',
            dropoff_location='321 Pine Ave',
            total_price=Decimal('150.00'),
            status='completed'
        )
        
        review1 = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='First booking review'
        )
        
        review2 = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking2,
            rating=4,
            comment='Second booking review'
        )
        
        self.assertNotEqual(review1.booking, review2.booking)
        self.assertEqual(Review.objects.count(), 2)
    
    def test_same_users_can_review_each_other_on_different_bookings(self):
        """Same users can review each other on different bookings."""
        # Create two different bookings
        booking2 = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=2),
            pickup_location='789 Elm St',
            dropoff_location='321 Pine Ave',
            total_price=Decimal('150.00'),
            status='completed'
        )
        
        # Student reviews provider on first booking
        review1 = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='Great provider!'
        )
        
        # Student reviews provider on second booking
        review2 = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking2,
            rating=4,
            comment='Good again!'
        )
        
        self.assertEqual(Review.objects.count(), 2)


class ReviewModelForeignKeyTests(TestCase):
    """Test foreign key relationships and cascade behavior."""
    
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
            user_type='provider'
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Moving Service',
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
    
    def test_reviewer_foreign_key_relationship(self):
        """Reviewer foreign key should link to User model."""
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='Test comment'
        )
        
        self.assertEqual(review.reviewer, self.student)
        self.assertIn(review, self.student.reviews_given.all())
    
    def test_reviewee_foreign_key_relationship(self):
        """Reviewee foreign key should link to User model."""
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='Test comment'
        )
        
        self.assertEqual(review.reviewee, self.provider)
        self.assertIn(review, self.provider.reviews_received.all())
    
    def test_booking_foreign_key_relationship(self):
        """Booking foreign key should link to Booking model."""
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='Test comment'
        )
        
        self.assertEqual(review.booking, self.booking)
        self.assertIn(review, self.booking.reviews.all())
    
    def test_cascade_deletion_when_reviewer_deleted(self):
        """Review should be deleted when reviewer is deleted."""
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='Test comment'
        )
        
        review_id = review.id
        self.student.delete()
        
        with self.assertRaises(Review.DoesNotExist):
            Review.objects.get(id=review_id)
    
    def test_cascade_deletion_when_reviewee_deleted(self):
        """Review should be deleted when reviewee is deleted."""
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='Test comment'
        )
        
        review_id = review.id
        self.provider.delete()
        
        with self.assertRaises(Review.DoesNotExist):
            Review.objects.get(id=review_id)
    
    def test_cascade_deletion_when_booking_deleted(self):
        """Review should be deleted when booking is deleted."""
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='Test comment'
        )
        
        review_id = review.id
        self.booking.delete()
        
        with self.assertRaises(Review.DoesNotExist):
            Review.objects.get(id=review_id)


class ReviewModelValidationTests(TestCase):
    """Test model validation logic."""
    
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
            user_type='provider'
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Moving Service',
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
    
    def test_reviewer_and_reviewee_cannot_be_same_user(self):
        """Reviewer and reviewee must be different users."""
        with self.assertRaises(ValidationError):
            review = Review(
                reviewer=self.student,
                reviewee=self.student,  # Same as reviewer
                booking=self.booking,
                rating=5,
                comment='Test comment'
            )
            review.full_clean()
    
    def test_booking_must_be_completed_status(self):
        """Only completed bookings can be reviewed."""
        pending_booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=2),
            pickup_location='789 Elm St',
            dropoff_location='321 Pine Ave',
            total_price=Decimal('150.00'),
            status='pending'
        )
        
        with self.assertRaises(ValidationError):
            review = Review(
                reviewer=self.student,
                reviewee=self.provider,
                booking=pending_booking,
                rating=5,
                comment='Test comment'
            )
            review.full_clean()
    
    def test_reviewer_must_be_from_booking(self):
        """Reviewer must be either student or provider from the booking."""
        other_user = User.objects.create_user(
            username='other',
            email='other@test.com',
            password='testpass123',
            user_type='student'
        )
        
        with self.assertRaises(ValidationError):
            review = Review(
                reviewer=other_user,  # Not part of the booking
                reviewee=self.provider,
                booking=self.booking,
                rating=5,
                comment='Test comment'
            )
            review.full_clean()
    
    def test_reviewee_must_be_other_party_in_booking(self):
        """Reviewee must be the other party in the booking."""
        other_user = User.objects.create_user(
            username='other',
            email='other@test.com',
            password='testpass123',
            user_type='provider'
        )
        
        with self.assertRaises(ValidationError):
            review = Review(
                reviewer=self.student,
                reviewee=other_user,  # Not the provider in the booking
                booking=self.booking,
                rating=5,
                comment='Test comment'
            )
            review.full_clean()
    
    def test_comment_cannot_be_empty(self):
        """Comment field cannot be empty."""
        with self.assertRaises(ValidationError):
            review = Review(
                reviewer=self.student,
                reviewee=self.provider,
                booking=self.booking,
                rating=5,
                comment=''
            )
            review.full_clean()
    
    def test_comment_cannot_be_whitespace_only(self):
        """Comment cannot be only whitespace."""
        with self.assertRaises(ValidationError):
            review = Review(
                reviewer=self.student,
                reviewee=self.provider,
                booking=self.booking,
                rating=5,
                comment='   \n\t   '
            )
            review.full_clean()


class ReviewModelEdgeCaseTests(TestCase):
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
            user_type='provider'
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Moving Service',
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
    
    def test_provider_reviewing_student(self):
        """Provider should be able to review student."""
        review = Review.objects.create(
            reviewer=self.provider,
            reviewee=self.student,
            booking=self.booking,
            rating=4,
            comment='Good student, easy to work with'
        )
        
        self.assertEqual(review.reviewer, self.provider)
        self.assertEqual(review.reviewee, self.student)
    
    def test_student_reviewing_provider(self):
        """Student should be able to review provider."""
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='Excellent provider!'
        )
        
        self.assertEqual(review.reviewer, self.student)
        self.assertEqual(review.reviewee, self.provider)
    
    def test_very_long_comment(self):
        """Very long comments (10,000+ characters) should be accepted."""
        long_comment = 'A' * 10000
        
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment=long_comment
        )
        
        self.assertEqual(len(review.comment), 10000)
    
    def test_comment_with_special_characters_and_unicode(self):
        """Comments with special characters and unicode should be accepted."""
        special_comments = [
            'Great service! 😊👍',
            'Très bon service!',
            '非常好的服务！',
            'Отличный сервис!',
            '<script>alert("XSS")</script>',
            "'; DROP TABLE reviews; --",
        ]
        
        for idx, comment in enumerate(special_comments):
            # Create a new booking for each review
            booking = Booking.objects.create(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=timezone.now() + timedelta(days=idx+2),
                pickup_location=f'{idx} Main St',
                dropoff_location=f'{idx} Oak Ave',
                total_price=Decimal('100.00'),
                status='completed'
            )
            
            review = Review.objects.create(
                reviewer=self.student,
                reviewee=self.provider,
                booking=booking,
                rating=5,
                comment=comment
            )
            
            self.assertEqual(review.comment, comment)
    
    def test_review_creation_with_pending_booking_fails(self):
        """Creating review for pending booking should fail."""
        pending_booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=2),
            pickup_location='789 Elm St',
            dropoff_location='321 Pine Ave',
            total_price=Decimal('150.00'),
            status='pending'
        )
        
        with self.assertRaises(ValidationError):
            review = Review(
                reviewer=self.student,
                reviewee=self.provider,
                booking=pending_booking,
                rating=5,
                comment='Test comment'
            )
            review.full_clean()
    
    def test_review_creation_with_cancelled_booking_fails(self):
        """Creating review for cancelled booking should fail."""
        cancelled_booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=2),
            pickup_location='789 Elm St',
            dropoff_location='321 Pine Ave',
            total_price=Decimal('150.00'),
            status='cancelled'
        )
        
        with self.assertRaises(ValidationError):
            review = Review(
                reviewer=self.student,
                reviewee=self.provider,
                booking=cancelled_booking,
                rating=5,
                comment='Test comment'
            )
            review.full_clean()
    
    def test_review_creation_with_confirmed_booking_fails(self):
        """Creating review for confirmed (not completed) booking should fail."""
        confirmed_booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.now() + timedelta(days=2),
            pickup_location='789 Elm St',
            dropoff_location='321 Pine Ave',
            total_price=Decimal('150.00'),
            status='confirmed'
        )
        
        with self.assertRaises(ValidationError):
            review = Review(
                reviewer=self.student,
                reviewee=self.provider,
                booking=confirmed_booking,
                rating=5,
                comment='Test comment'
            )
            review.full_clean()


class ReviewModelStringRepresentationTests(TestCase):
    """Test string representation."""
    
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
            user_type='provider'
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Moving Service',
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
    
    def test_str_method_returns_expected_format(self):
        """__str__ should return meaningful representation."""
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='Excellent service!'
        )
        
        str_repr = str(review)
        
        # Should contain reviewer email, reviewee email, and rating
        self.assertIn('student@test.com', str_repr)
        self.assertIn('provider@test.com', str_repr)
        self.assertIn('5', str_repr)
    
    def test_string_includes_all_key_information(self):
        """String representation should include reviewer, reviewee, and rating."""
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=3,
            comment='Average service'
        )
        
        str_repr = str(review)
        
        # Verify all key components are present
        self.assertTrue(
            'student@test.com' in str_repr or 'student' in str_repr,
            "String should contain reviewer information"
        )
        self.assertTrue(
            'provider@test.com' in str_repr or 'provider' in str_repr,
            "String should contain reviewee information"
        )
        self.assertIn('3', str_repr, "String should contain rating")


class ReviewModelTimestampTests(TestCase):
    """Test timestamp fields."""
    
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
            user_type='provider'
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Moving Service',
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
    
    def test_created_at_auto_set(self):
        """created_at should be automatically set on creation."""
        before_creation = timezone.now()
        
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='Test comment'
        )
        
        after_creation = timezone.now()
        
        self.assertIsNotNone(review.created_at)
        self.assertGreaterEqual(review.created_at, before_creation)
        self.assertLessEqual(review.created_at, after_creation)
    
    def test_created_at_immutable(self):
        """created_at should not change on update."""
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=self.booking,
            rating=5,
            comment='Original comment'
        )
        
        original_created_at = review.created_at
        
        # Wait a moment and update
        import time
        time.sleep(0.1)
        
        review.comment = 'Updated comment'
        review.save()
        review.refresh_from_db()
        
        self.assertEqual(review.created_at, original_created_at)
