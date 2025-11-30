"""
Comprehensive test suite for MovingService model.

These tests are designed to FAIL until the MovingService model is properly implemented.
Following TDD principles: write tests first, then implement code to pass them.
NEVER modify these tests - only fix the model implementation.
"""

from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from django.utils import timezone


User = get_user_model()


class MovingServiceModelBasicTests(TestCase):
    """Test basic MovingService model creation and fields."""
    
    def setUp(self):
        """Set up test fixtures."""
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
    
    def test_moving_service_creation(self):
        """Creating a valid MovingService should succeed."""
        from core.models import MovingService
        
        service = MovingService.objects.create(
            provider=self.provider,
            service_name='Campus Moving Service',
            description='Professional moving service for students',
            base_price=Decimal('50.00'),
            availability_status=True
        )
        
        self.assertIsNotNone(service.id)
        self.assertEqual(service.provider, self.provider)
        self.assertEqual(service.service_name, 'Campus Moving Service')
        self.assertEqual(service.base_price, Decimal('50.00'))
        self.assertTrue(service.availability_status)
    
    def test_service_name_required(self):
        """Creating service without service_name must raise error."""
        from core.models import MovingService
        
        with self.assertRaises((ValidationError, IntegrityError)):
            service = MovingService(
                provider=self.provider,
                description='Test description',
                base_price=Decimal('50.00')
            )
            service.full_clean()
    
    def test_description_required(self):
        """Creating service without description must raise error."""
        from core.models import MovingService
        
        with self.assertRaises((ValidationError, IntegrityError)):
            service = MovingService(
                provider=self.provider,
                service_name='Test Service',
                base_price=Decimal('50.00')
            )
            service.full_clean()
    
    def test_base_price_required(self):
        """Creating service without base_price must raise error."""
        from core.models import MovingService
        
        with self.assertRaises((ValidationError, IntegrityError)):
            service = MovingService(
                provider=self.provider,
                service_name='Test Service',
                description='Test description'
            )
            service.full_clean()


class MovingServiceProviderValidationTests(TestCase):
    """Test that only providers can create services."""
    
    def setUp(self):
        """Set up test fixtures."""
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
    
    def test_only_providers_can_create_services(self):
        """Students attempting to create services must raise ValidationError."""
        from core.models import MovingService
        
        with self.assertRaises(ValidationError):
            service = MovingService(
                provider=self.student,  # Student, not provider
                service_name='Invalid Service',
                description='This should fail',
                base_price=Decimal('50.00')
            )
            service.full_clean()
    
    def test_provider_can_create_service(self):
        """Providers should be able to create services."""
        from core.models import MovingService
        
        service = MovingService.objects.create(
            provider=self.provider,
            service_name='Valid Service',
            description='This should succeed',
            base_price=Decimal('50.00')
        )
        
        self.assertIsNotNone(service.id)


class MovingServicePriceValidationTests(TestCase):
    """Test price field validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
    
    def test_negative_price_rejected(self):
        """Negative prices must raise ValidationError."""
        from core.models import MovingService
        
        with self.assertRaises(ValidationError):
            service = MovingService(
                provider=self.provider,
                service_name='Test Service',
                description='Test description',
                base_price=Decimal('-10.00')
            )
            service.full_clean()
    
    def test_zero_price_rejected(self):
        """Zero price must raise ValidationError."""
        from core.models import MovingService
        
        with self.assertRaises(ValidationError):
            service = MovingService(
                provider=self.provider,
                service_name='Test Service',
                description='Test description',
                base_price=Decimal('0.00')
            )
            service.full_clean()
    
    def test_decimal_precision(self):
        """Price should handle decimal precision correctly."""
        from core.models import MovingService
        
        service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Service',
            description='Test description',
            base_price=Decimal('99.99')
        )
        
        self.assertEqual(service.base_price, Decimal('99.99'))
    
    def test_large_price_accepted(self):
        """Large but valid prices should be accepted."""
        from core.models import MovingService
        
        service = MovingService.objects.create(
            provider=self.provider,
            service_name='Premium Service',
            description='Expensive service',
            base_price=Decimal('9999.99')
        )
        
        self.assertEqual(service.base_price, Decimal('9999.99'))


class MovingServiceFieldConstraintsTests(TestCase):
    """Test field length and constraint validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
    
    def test_service_name_max_length(self):
        """Service name exceeding max length must raise ValidationError."""
        from core.models import MovingService
        
        long_name = 'A' * 201  # Assuming max_length=200
        
        with self.assertRaises(ValidationError):
            service = MovingService(
                provider=self.provider,
                service_name=long_name,
                description='Test description',
                base_price=Decimal('50.00')
            )
            service.full_clean()
    
    def test_service_name_empty_string(self):
        """Empty service name must raise ValidationError."""
        from core.models import MovingService
        
        with self.assertRaises(ValidationError):
            service = MovingService(
                provider=self.provider,
                service_name='',
                description='Test description',
                base_price=Decimal('50.00')
            )
            service.full_clean()
    
    def test_description_empty_string(self):
        """Empty description must raise ValidationError."""
        from core.models import MovingService
        
        with self.assertRaises(ValidationError):
            service = MovingService(
                provider=self.provider,
                service_name='Test Service',
                description='',
                base_price=Decimal('50.00')
            )
            service.full_clean()


class MovingServiceRatingFieldsTests(TestCase):
    """Test rating and review count fields."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
    
    def test_rating_average_defaults_to_zero(self):
        """New services should have rating_average=0."""
        from core.models import MovingService
        
        service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Service',
            description='Test description',
            base_price=Decimal('50.00')
        )
        
        self.assertEqual(service.rating_average, Decimal('0.00'))
    
    def test_total_reviews_defaults_to_zero(self):
        """New services should have total_reviews=0."""
        from core.models import MovingService
        
        service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Service',
            description='Test description',
            base_price=Decimal('50.00')
        )
        
        self.assertEqual(service.total_reviews, 0)
    
    def test_rating_average_range_validation(self):
        """Rating average must be between 0 and 5."""
        from core.models import MovingService
        
        # Test invalid rating > 5
        with self.assertRaises(ValidationError):
            service = MovingService(
                provider=self.provider,
                service_name='Test Service',
                description='Test description',
                base_price=Decimal('50.00'),
                rating_average=Decimal('5.5')
            )
            service.full_clean()
        
        # Test invalid negative rating
        with self.assertRaises(ValidationError):
            service = MovingService(
                provider=self.provider,
                service_name='Test Service',
                description='Test description',
                base_price=Decimal('50.00'),
                rating_average=Decimal('-1.0')
            )
            service.full_clean()
    
    def test_total_reviews_negative_rejected(self):
        """Negative total_reviews must raise ValidationError."""
        from core.models import MovingService
        
        with self.assertRaises(ValidationError):
            service = MovingService(
                provider=self.provider,
                service_name='Test Service',
                description='Test description',
                base_price=Decimal('50.00'),
                total_reviews=-1
            )
            service.full_clean()


class MovingServiceForeignKeyTests(TestCase):
    """Test foreign key relationships and cascade behavior."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
    
    def test_provider_required(self):
        """Creating service without provider must raise error."""
        from core.models import MovingService
        
        with self.assertRaises((ValidationError, IntegrityError)):
            service = MovingService(
                service_name='Test Service',
                description='Test description',
                base_price=Decimal('50.00')
            )
            service.save()
    
    def test_cascade_delete_on_provider_deletion(self):
        """Deleting provider should delete associated services."""
        from core.models import MovingService
        
        service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Service',
            description='Test description',
            base_price=Decimal('50.00')
        )
        
        service_id = service.id
        self.provider.delete()
        
        # Service should be deleted
        with self.assertRaises(MovingService.DoesNotExist):
            MovingService.objects.get(id=service_id)


class MovingServiceTimestampTests(TestCase):
    """Test timestamp fields."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
    
    def test_created_at_auto_set(self):
        """created_at should be automatically set on creation."""
        from core.models import MovingService
        
        before_creation = timezone.now()
        
        service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Service',
            description='Test description',
            base_price=Decimal('50.00')
        )
        
        after_creation = timezone.now()
        
        self.assertIsNotNone(service.created_at)
        self.assertGreaterEqual(service.created_at, before_creation)
        self.assertLessEqual(service.created_at, after_creation)
    
    def test_updated_at_auto_update(self):
        """updated_at should change when model is updated."""
        from core.models import MovingService
        
        service = MovingService.objects.create(
            provider=self.provider,
            service_name='Test Service',
            description='Test description',
            base_price=Decimal('50.00')
        )
        
        original_updated_at = service.updated_at
        
        import time
        time.sleep(0.1)
        
        service.base_price = Decimal('75.00')
        service.save()
        service.refresh_from_db()
        
        self.assertGreater(service.updated_at, original_updated_at)


class MovingServiceStringRepresentationTests(TestCase):
    """Test string representation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.provider = User.objects.create_user(
            username='provider1',
            email='provider@test.com',
            password='testpass123',
            user_type='provider',
            university_name='Test University'
        )
    
    def test_str_method(self):
        """__str__ should return meaningful representation."""
        from core.models import MovingService
        
        service = MovingService.objects.create(
            provider=self.provider,
            service_name='Campus Moving Service',
            description='Test description',
            base_price=Decimal('50.00')
        )
        
        str_repr = str(service)
        self.assertIn('Campus Moving Service', str_repr)
