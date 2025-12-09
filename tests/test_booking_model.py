"""
Comprehensive test suite for Booking model.

These tests are designed to FAIL until the Booking model is properly implemented.
Following TDD principles: write tests first, then implement code to pass them.
NEVER modify these tests - only fix the model implementation.
"""

from decimal import Decimal
from datetime import datetime, timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from django.utils import timezone


User = get_user_model()


class BookingModelBasicTests(TestCase):
    """Test basic Booking model creation and fields."""
    
    def setUp(self):
        """Set up test fixtures."""
        from core.models import MovingService
        
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
        
        self.student = User.objects.create_user(
            username='student1',
            email='student@test.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Campus Moving Service',
            description='Professional moving service',
            base_price=Decimal('50.00')
        )
    
    def test_booking_creation(self):
        """Creating a valid Booking should succeed."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=booking_date,
            pickup_location='123 Campus St',
            dropoff_location='456 Dorm Ave',
            status='pending',
            total_price=Decimal('50.00')
        )
        
        self.assertIsNotNone(booking.id)
        self.assertEqual(booking.student, self.student)
        self.assertEqual(booking.provider, self.provider)
        self.assertEqual(booking.service, self.service)
        self.assertEqual(booking.status, 'pending')
    
    def test_student_required(self):
        """Creating booking without student must raise error."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        with self.assertRaises((ValidationError, IntegrityError)):
            booking = Booking(
                provider=self.provider,
                service=self.service,
                booking_date=booking_date,
                pickup_location='123 Campus St',
                dropoff_location='456 Dorm Ave',
                total_price=Decimal('50.00')
            )
            booking.save()
    
    def test_provider_required(self):
        """Creating booking without provider must raise error."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        with self.assertRaises((ValidationError, IntegrityError)):
            booking = Booking(
                student=self.student,
                service=self.service,
                booking_date=booking_date,
                pickup_location='123 Campus St',
                dropoff_location='456 Dorm Ave',
                total_price=Decimal('50.00')
            )
            booking.save()
    
    def test_service_required(self):
        """Creating booking without service must raise error."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        with self.assertRaises((ValidationError, IntegrityError)):
            booking = Booking(
                student=self.student,
                provider=self.provider,
                booking_date=booking_date,
                pickup_location='123 Campus St',
                dropoff_location='456 Dorm Ave',
                total_price=Decimal('50.00')
            )
            booking.save()


class BookingUserTypeValidationTests(TestCase):
    """Test that bookings properly link students and providers."""
    
    def setUp(self):
        """Set up test fixtures."""
        from core.models import MovingService
        
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
        
        self.student = User.objects.create_user(
            username='student1',
            email='student@test.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Campus Moving Service',
            description='Professional moving service',
            base_price=Decimal('50.00')
        )
    
    def test_student_must_be_student_type(self):
        """Booking student field must be a user with user_type='student'."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        with self.assertRaises(ValidationError):
            booking = Booking(
                student=self.provider,  # Provider, not student
                provider=self.provider,
                service=self.service,
                booking_date=booking_date,
                pickup_location='123 Campus St',
                dropoff_location='456 Dorm Ave',
                total_price=Decimal('50.00')
            )
            booking.full_clean()
    
    def test_provider_must_be_provider_type(self):
        """Booking provider field must be a user with user_type='provider'."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        with self.assertRaises(ValidationError):
            booking = Booking(
                student=self.student,
                provider=self.student,  # Student, not provider
                service=self.service,
                booking_date=booking_date,
                pickup_location='123 Campus St',
                dropoff_location='456 Dorm Ave',
                total_price=Decimal('50.00')
            )
            booking.full_clean()


class BookingStatusValidationTests(TestCase):
    """Test status field validation and transitions."""
    
    def setUp(self):
        """Set up test fixtures."""
        from core.models import MovingService
        
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
        
        self.student = User.objects.create_user(
            username='student1',
            email='student@test.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Campus Moving Service',
            description='Professional moving service',
            base_price=Decimal('50.00')
        )
    
    def test_status_defaults_to_pending(self):
        """New bookings should have status='pending' by default."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=booking_date,
            pickup_location='123 Campus St',
            dropoff_location='456 Dorm Ave',
            total_price=Decimal('50.00')
        )
        
        self.assertEqual(booking.status, 'pending')
    
    def test_valid_status_choices(self):
        """All valid status choices should be accepted."""
        from core.models import Booking
        
        valid_statuses = ['pending', 'confirmed', 'completed', 'cancelled']
        booking_date = timezone.now() + timedelta(days=1)
        
        for idx, status in enumerate(valid_statuses):
            # Use different times to avoid uniqueness constraint violations
            # Use 4 hour intervals to safely clear any overlap windows
            current_booking_date = booking_date + timedelta(hours=idx * 4)
            
            booking = Booking.objects.create(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=current_booking_date,
                pickup_location=f'{idx} Campus St',
                dropoff_location=f'{idx} Dorm Ave',
                status=status,
                total_price=Decimal('50.00')
            )
            self.assertEqual(booking.status, status)
    
    def test_invalid_status_rejected(self):
        """Invalid status values must raise ValidationError."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        with self.assertRaises(ValidationError):
            booking = Booking(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=booking_date,
                pickup_location='123 Campus St',
                dropoff_location='456 Dorm Ave',
                status='invalid_status',
                total_price=Decimal('50.00')
            )
            booking.full_clean()
    
    def test_cannot_complete_from_pending(self):
        """Cannot transition from pending to completed without confirming first."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=booking_date,
            pickup_location='123 Campus St',
            dropoff_location='456 Dorm Ave',
            status='pending',
            total_price=Decimal('50.00')
        )
        
        with self.assertRaises(ValidationError):
            booking.status = 'completed'
            booking.full_clean()
    
    def test_cannot_modify_completed_booking(self):
        """Cannot change status once booking is completed."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=booking_date,
            pickup_location='123 Campus St',
            dropoff_location='456 Dorm Ave',
            status='completed',
            total_price=Decimal('50.00')
        )
        
        with self.assertRaises(ValidationError):
            booking.status = 'cancelled'
            booking.full_clean()
    
    def test_cannot_modify_cancelled_booking(self):
        """Cannot change status once booking is cancelled."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=booking_date,
            pickup_location='123 Campus St',
            dropoff_location='456 Dorm Ave',
            status='cancelled',
            total_price=Decimal('50.00')
        )
        
        with self.assertRaises(ValidationError):
            booking.status = 'confirmed'
            booking.full_clean()


class BookingPriceValidationTests(TestCase):
    """Test price field validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        from core.models import MovingService
        
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
        
        self.student = User.objects.create_user(
            username='student1',
            email='student@test.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Campus Moving Service',
            description='Professional moving service',
            base_price=Decimal('50.00')
        )
    
    def test_negative_price_rejected(self):
        """Negative total_price must raise ValidationError."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        with self.assertRaises(ValidationError):
            booking = Booking(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=booking_date,
                pickup_location='123 Campus St',
                dropoff_location='456 Dorm Ave',
                total_price=Decimal('-10.00')
            )
            booking.full_clean()
    
    def test_zero_price_rejected(self):
        """Zero total_price must raise ValidationError."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        with self.assertRaises(ValidationError):
            booking = Booking(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=booking_date,
                pickup_location='123 Campus St',
                dropoff_location='456 Dorm Ave',
                total_price=Decimal('0.00')
            )
            booking.full_clean()
    
    def test_decimal_precision(self):
        """Price should handle decimal precision correctly."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=booking_date,
            pickup_location='123 Campus St',
            dropoff_location='456 Dorm Ave',
            total_price=Decimal('99.99')
        )
        
        self.assertEqual(booking.total_price, Decimal('99.99'))


class BookingLocationValidationTests(TestCase):
    """Test location field validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        from core.models import MovingService
        
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
        
        self.student = User.objects.create_user(
            username='student1',
            email='student@test.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Campus Moving Service',
            description='Professional moving service',
            base_price=Decimal('50.00')
        )
    
    def test_pickup_location_required(self):
        """Creating booking without pickup_location must raise error."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        with self.assertRaises(ValidationError):
            booking = Booking(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=booking_date,
                dropoff_location='456 Dorm Ave',
                total_price=Decimal('50.00')
            )
            booking.full_clean()
    
    def test_dropoff_location_required(self):
        """Creating booking without dropoff_location must raise error."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        with self.assertRaises(ValidationError):
            booking = Booking(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=booking_date,
                pickup_location='123 Campus St',
                total_price=Decimal('50.00')
            )
            booking.full_clean()
    
    def test_empty_pickup_location_rejected(self):
        """Empty pickup_location must raise ValidationError."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        with self.assertRaises(ValidationError):
            booking = Booking(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=booking_date,
                pickup_location='',
                dropoff_location='456 Dorm Ave',
                total_price=Decimal('50.00')
            )
            booking.full_clean()
    
    def test_empty_dropoff_location_rejected(self):
        """Empty dropoff_location must raise ValidationError."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        with self.assertRaises(ValidationError):
            booking = Booking(
                student=self.student,
                provider=self.provider,
                service=self.service,
                booking_date=booking_date,
                pickup_location='123 Campus St',
                dropoff_location='',
                total_price=Decimal('50.00')
            )
            booking.full_clean()


class BookingForeignKeyTests(TestCase):
    """Test foreign key relationships and cascade behavior."""
    
    def setUp(self):
        """Set up test fixtures."""
        from core.models import MovingService
        
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
        
        self.student = User.objects.create_user(
            username='student1',
            email='student@test.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Campus Moving Service',
            description='Professional moving service',
            base_price=Decimal('50.00')
        )
    
    def test_cascade_delete_on_service_deletion(self):
        """Deleting service should delete associated bookings."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=booking_date,
            pickup_location='123 Campus St',
            dropoff_location='456 Dorm Ave',
            total_price=Decimal('50.00')
        )
        
        booking_id = booking.id
        self.service.delete()
        
        # Booking should be deleted
        with self.assertRaises(Booking.DoesNotExist):
            Booking.objects.get(id=booking_id)
    
    def test_cascade_delete_on_student_deletion(self):
        """Deleting student should delete their bookings."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=booking_date,
            pickup_location='123 Campus St',
            dropoff_location='456 Dorm Ave',
            total_price=Decimal('50.00')
        )
        
        booking_id = booking.id
        self.student.delete()
        
        # Booking should be deleted
        with self.assertRaises(Booking.DoesNotExist):
            Booking.objects.get(id=booking_id)
    
    def test_cascade_delete_on_provider_deletion(self):
        """Deleting provider should delete bookings where they are the provider."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=booking_date,
            pickup_location='123 Campus St',
            dropoff_location='456 Dorm Ave',
            total_price=Decimal('50.00')
        )
        
        booking_id = booking.id
        self.provider.delete()
        
        # Booking should be deleted
        with self.assertRaises(Booking.DoesNotExist):
            Booking.objects.get(id=booking_id)


class BookingTimestampTests(TestCase):
    """Test timestamp fields."""
    
    def setUp(self):
        """Set up test fixtures."""
        from core.models import MovingService
        
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
        
        self.student = User.objects.create_user(
            username='student1',
            email='student@test.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Campus Moving Service',
            description='Professional moving service',
            base_price=Decimal('50.00')
        )
    
    def test_created_at_auto_set(self):
        """created_at should be automatically set on creation."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        before_creation = timezone.now()
        
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=booking_date,
            pickup_location='123 Campus St',
            dropoff_location='456 Dorm Ave',
            total_price=Decimal('50.00')
        )
        
        after_creation = timezone.now()
        
        self.assertIsNotNone(booking.created_at)
        self.assertGreaterEqual(booking.created_at, before_creation)
        self.assertLessEqual(booking.created_at, after_creation)
    
    def test_updated_at_auto_update(self):
        """updated_at should change when model is updated."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=booking_date,
            pickup_location='123 Campus St',
            dropoff_location='456 Dorm Ave',
            total_price=Decimal('50.00')
        )
        
        original_updated_at = booking.updated_at
        
        import time
        time.sleep(0.1)
        
        booking.pickup_location = '789 New St'
        booking.save()
        booking.refresh_from_db()
        
        self.assertGreater(booking.updated_at, original_updated_at)


class BookingStringRepresentationTests(TestCase):
    """Test string representation."""
    
    def setUp(self):
        """Set up test fixtures."""
        from core.models import MovingService
        
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
        
        self.student = User.objects.create_user(
            username='student1',
            email='student@test.com',
            password='testpass123',
            user_type='student',
            university_name='Test University'
        )
        
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Campus Moving Service',
            description='Professional moving service',
            base_price=Decimal('50.00')
        )
    
    def test_str_method(self):
        """__str__ should return meaningful representation."""
        from core.models import Booking
        
        booking_date = timezone.now() + timedelta(days=1)
        
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=self.service,
            booking_date=booking_date,
            pickup_location='123 Campus St',
            dropoff_location='456 Dorm Ave',
            total_price=Decimal('50.00')
        )
        
        str_repr = str(booking)
        # Should contain student email or service name
        self.assertTrue(
            'student@test.com' in str_repr or 'Campus Moving Service' in str_repr,
            f"String representation '{str_repr}' should contain student or service info"
        )
