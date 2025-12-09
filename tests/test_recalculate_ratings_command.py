from decimal import Decimal
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from core.models import User, MovingService, Review, Booking


class RecalculateRatingsCommandTests(TestCase):
    def setUp(self):
        # Create users
        self.student1 = User.objects.create_user(
            username='student1', email='s1@test.com', password='password', user_type='student'
        )
        self.student2 = User.objects.create_user(
            username='student2', email='s2@test.com', password='password', user_type='student'
        )
        self.provider1 = User.objects.create_user(
            username='provider1', email='p1@test.com', password='password', user_type='provider', is_verified=True
        )
        self.provider2 = User.objects.create_user(
            username='provider2', email='p2@test.com', password='password', user_type='provider', is_verified=True
        )

        # Create services
        self.service1 = MovingService.objects.create(
            provider=self.provider1,
            service_name='Service 1',
            description='Desc 1',
            base_price=Decimal('100.00'),
            rating_average=Decimal('0.00'),
            total_reviews=0
        )
        self.service2 = MovingService.objects.create(
            provider=self.provider2,
            service_name='Service 2',
            description='Desc 2',
            base_price=Decimal('150.00'),
            rating_average=Decimal('0.00'),
            total_reviews=0
        )

        # Create bookings and reviews for Service 1
        # Review 1: 5 stars
        b1 = Booking.objects.create(
            student=self.student1,
            provider=self.provider1,
            service=self.service1,
            booking_date=timezone.now(),
            status='completed',
            total_price=Decimal('200.00'),
            pickup_location='Loc A',
            dropoff_location='Loc B'
        )
        Review.objects.create(
            reviewer=self.student1,
            reviewee=self.provider1,
            booking=b1,
            rating=5,
            comment='Great!'
        )

        # Review 2: 3 stars
        b2 = Booking.objects.create(
            student=self.student2,
            provider=self.provider1,
            service=self.service1,
            booking_date=timezone.now() + timezone.timedelta(days=1),
            status='completed',
            total_price=Decimal('200.00'),
            pickup_location='Loc C',
            dropoff_location='Loc D'
        )
        Review.objects.create(
            reviewer=self.student2,
            reviewee=self.provider1,
            booking=b2,
            rating=3,
            comment='Okay'
        )

        # Service 1 Actual Stats: Avg = 4.0, Count = 2
        # Provider 1 Actual Stats: Avg as Provider = 4.0

        # Create booking and review for Service 2
        # Review 3: 4 stars
        b3 = Booking.objects.create(
            student=self.student1,
            provider=self.provider2,
            service=self.service2,
            booking_date=timezone.now() + timezone.timedelta(days=2),
            status='completed',
            total_price=Decimal('150.00'),
            pickup_location='Loc E',
            dropoff_location='Loc F'
        )
        Review.objects.create(
            reviewer=self.student1,
            reviewee=self.provider2,
            booking=b3,
            rating=4,
            comment='Good'
        )
        # Service 2 Actual Stats: Avg = 4.0, Count = 1
        # Provider 2 Actual Stats: Avg as Provider = 4.0

        # Corrupt data intentionally
        self.service1.rating_average = Decimal('1.00')
        self.service1.total_reviews = 99
        self.service1.save()

        self.provider1.avg_rating_as_provider = Decimal('1.00')
        self.provider1.save()

    def test_recalculate_ratings_services_and_users(self):
        """Test full recalculation of services and users."""
        call_command('recalculate_ratings')

        self.service1.refresh_from_db()
        self.provider1.refresh_from_db()
        self.service2.refresh_from_db()
        self.provider2.refresh_from_db()

        # Service 1: (5 + 3) / 2 = 4.0
        self.assertEqual(self.service1.rating_average, Decimal('4.00'))
        self.assertEqual(self.service1.total_reviews, 2)

        # Provider 1: Derived from service ratings or reviews received?
        # Based on implementation plan: "Average of their services' ratings" or "Average of ratings received"
        # User model doc says: "Average rating when acting as a service provider"
        # Usually this is aggregated from reviews where they are reviewee.
        # Reviews for P1: 5, 3 -> Avg 4.0
        self.assertEqual(self.provider1.avg_rating_as_provider, Decimal('4.00'))

        # Service 2: 4.0, Count 1
        self.assertEqual(self.service2.rating_average, Decimal('4.00'))
        self.assertEqual(self.service2.total_reviews, 1)

    def test_dry_run_does_not_change_data(self):
        """Test that --dry-run flag does not persist changes."""
        call_command('recalculate_ratings', dry_run=True)

        self.service1.refresh_from_db()
        self.provider1.refresh_from_db()

        # Check values remain corrupted
        self.assertEqual(self.service1.rating_average, Decimal('1.00'))
        self.assertEqual(self.service1.total_reviews, 99)
        self.assertEqual(self.provider1.avg_rating_as_provider, Decimal('1.00'))

    def test_services_only_flag(self):
        """Test processing only services."""
        call_command('recalculate_ratings', services_only=True)

        self.service1.refresh_from_db()
        self.provider1.refresh_from_db()

        # Service should be corrected
        self.assertEqual(self.service1.rating_average, Decimal('4.00'))
        
        # User should REMAIN corrupted
        self.assertEqual(self.provider1.avg_rating_as_provider, Decimal('1.00'))

    def test_users_only_flag(self):
        """Test processing only users."""
        call_command('recalculate_ratings', users_only=True)

        self.service1.refresh_from_db()
        self.provider1.refresh_from_db()

        # Service should REMAIN corrupted
        self.assertEqual(self.service1.rating_average, Decimal('1.00'))
        
        # User should be corrected
        self.assertEqual(self.provider1.avg_rating_as_provider, Decimal('4.00'))
