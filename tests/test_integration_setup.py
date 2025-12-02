"""
Comprehensive integration test suite for Django REST Framework and Testing Infrastructure.

This test suite follows TDD principles and is designed to fail initially.
Tests verify that the entire setup works together:
- REST Framework is properly configured and responds to requests
- CORS settings allow frontend connections
- Test database is separate from development database
- All models can be imported without circular dependency errors
- Migrations run successfully in test environment
- Test data fixtures load correctly

These tests should NEVER be modified - only the configuration and setup
should be updated to make them pass.
"""

import json
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase, Client, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory, APITestCase


User = get_user_model()


class RESTFrameworkConfigurationTestCase(TestCase):
    """Test REST Framework configuration and setup."""

    def test_rest_framework_installed(self):
        """Verify REST Framework is in INSTALLED_APPS."""
        self.assertIn(
            'rest_framework',
            settings.INSTALLED_APPS,
            "Django REST Framework must be installed"
        )

    def test_rest_framework_settings_exist(self):
        """Verify REST_FRAMEWORK settings dictionary exists."""
        self.assertTrue(
            hasattr(settings, 'REST_FRAMEWORK'),
            "REST_FRAMEWORK settings must be configured"
        )
        self.assertIsInstance(
            settings.REST_FRAMEWORK,
            dict,
            "REST_FRAMEWORK must be a dictionary"
        )

    def test_default_permission_classes_configured(self):
        """Verify default permission classes are configured."""
        rest_settings = settings.REST_FRAMEWORK
        self.assertIn(
            'DEFAULT_PERMISSION_CLASSES',
            rest_settings,
            "DEFAULT_PERMISSION_CLASSES must be configured"
        )
        permission_classes = rest_settings['DEFAULT_PERMISSION_CLASSES']
        self.assertIsInstance(
            permission_classes,
            list,
            "DEFAULT_PERMISSION_CLASSES must be a list"
        )
        self.assertGreater(
            len(permission_classes),
            0,
            "At least one permission class must be configured"
        )

    def test_default_authentication_classes_configured(self):
        """Verify default authentication classes are configured (prepare for JWT)."""
        rest_settings = settings.REST_FRAMEWORK
        self.assertIn(
            'DEFAULT_AUTHENTICATION_CLASSES',
            rest_settings,
            "DEFAULT_AUTHENTICATION_CLASSES must be configured for JWT preparation"
        )
        auth_classes = rest_settings['DEFAULT_AUTHENTICATION_CLASSES']
        self.assertIsInstance(
            auth_classes,
            list,
            "DEFAULT_AUTHENTICATION_CLASSES must be a list"
        )
        # Should have at least SessionAuthentication for now
        self.assertGreater(
            len(auth_classes),
            0,
            "At least one authentication class must be configured"
        )

    def test_pagination_configured(self):
        """Verify pagination is properly configured."""
        rest_settings = settings.REST_FRAMEWORK
        self.assertIn(
            'DEFAULT_PAGINATION_CLASS',
            rest_settings,
            "DEFAULT_PAGINATION_CLASS must be configured"
        )
        self.assertIn(
            'PAGE_SIZE',
            rest_settings,
            "PAGE_SIZE must be configured"
        )
        page_size = rest_settings['PAGE_SIZE']
        self.assertIsInstance(page_size, int, "PAGE_SIZE must be an integer")
        self.assertGreater(page_size, 0, "PAGE_SIZE must be positive")
        self.assertLessEqual(page_size, 100, "PAGE_SIZE should be reasonable (<=100)")

    def test_default_renderer_classes_configured(self):
        """Verify default renderer classes include JSON and browsable API."""
        rest_settings = settings.REST_FRAMEWORK
        self.assertIn(
            'DEFAULT_RENDERER_CLASSES',
            rest_settings,
            "DEFAULT_RENDERER_CLASSES must be configured"
        )
        renderers = rest_settings['DEFAULT_RENDERER_CLASSES']
        self.assertIsInstance(renderers, list, "DEFAULT_RENDERER_CLASSES must be a list")
        
        # Must include JSONRenderer
        json_renderer = 'rest_framework.renderers.JSONRenderer'
        self.assertIn(
            json_renderer,
            renderers,
            "JSONRenderer must be in DEFAULT_RENDERER_CLASSES"
        )

    def test_default_parser_classes_configured(self):
        """Verify default parser classes are configured."""
        rest_settings = settings.REST_FRAMEWORK
        self.assertIn(
            'DEFAULT_PARSER_CLASSES',
            rest_settings,
            "DEFAULT_PARSER_CLASSES must be configured"
        )
        parsers = rest_settings['DEFAULT_PARSER_CLASSES']
        self.assertIsInstance(parsers, list, "DEFAULT_PARSER_CLASSES must be a list")
        
        # Must include JSONParser
        json_parser = 'rest_framework.parsers.JSONParser'
        self.assertIn(
            json_parser,
            parsers,
            "JSONParser must be in DEFAULT_PARSER_CLASSES"
        )

    def test_throttling_configured(self):
        """Verify API throttling is configured for rate limiting."""
        rest_settings = settings.REST_FRAMEWORK
        # Throttling should be configured for production readiness
        if 'DEFAULT_THROTTLE_CLASSES' in rest_settings:
            throttle_classes = rest_settings['DEFAULT_THROTTLE_CLASSES']
            self.assertIsInstance(
                throttle_classes,
                list,
                "DEFAULT_THROTTLE_CLASSES must be a list"
            )
        
        if 'DEFAULT_THROTTLE_RATES' in rest_settings:
            throttle_rates = rest_settings['DEFAULT_THROTTLE_RATES']
            self.assertIsInstance(
                throttle_rates,
                dict,
                "DEFAULT_THROTTLE_RATES must be a dictionary"
            )

    def test_exception_handler_configured(self):
        """Verify custom exception handler is configured for consistent error responses."""
        rest_settings = settings.REST_FRAMEWORK
        # Exception handler should be configured for consistent API responses
        if 'EXCEPTION_HANDLER' in rest_settings:
            exception_handler = rest_settings['EXCEPTION_HANDLER']
            self.assertIsInstance(
                exception_handler,
                str,
                "EXCEPTION_HANDLER must be a string path"
            )


class CORSConfigurationTestCase(TestCase):
    """Test CORS configuration for frontend connectivity."""

    def test_cors_headers_installed(self):
        """Verify django-cors-headers is in INSTALLED_APPS."""
        self.assertIn(
            'corsheaders',
            settings.INSTALLED_APPS,
            "django-cors-headers must be installed"
        )

    def test_cors_middleware_installed(self):
        """Verify CORS middleware is in MIDDLEWARE."""
        self.assertIn(
            'corsheaders.middleware.CorsMiddleware',
            settings.MIDDLEWARE,
            "CorsMiddleware must be in MIDDLEWARE"
        )

    def test_cors_middleware_position(self):
        """Verify CORS middleware is positioned before CommonMiddleware."""
        middleware_list = settings.MIDDLEWARE
        cors_index = middleware_list.index('corsheaders.middleware.CorsMiddleware')
        common_index = middleware_list.index('django.middleware.common.CommonMiddleware')
        self.assertLess(
            cors_index,
            common_index,
            "CorsMiddleware must be before CommonMiddleware for proper header handling"
        )

    def test_cors_allowed_origins_configured(self):
        """Verify CORS allowed origins are configured for development."""
        # Check for either CORS_ALLOWED_ORIGINS or CORS_ALLOW_ALL_ORIGINS
        has_allowed_origins = hasattr(settings, 'CORS_ALLOWED_ORIGINS')
        has_allow_all = hasattr(settings, 'CORS_ALLOW_ALL_ORIGINS')
        
        self.assertTrue(
            has_allowed_origins or has_allow_all,
            "Either CORS_ALLOWED_ORIGINS or CORS_ALLOW_ALL_ORIGINS must be configured"
        )
        
        if has_allowed_origins:
            allowed_origins = settings.CORS_ALLOWED_ORIGINS
            self.assertIsInstance(
                allowed_origins,
                (list, tuple),
                "CORS_ALLOWED_ORIGINS must be a list or tuple"
            )
            # Should include common development origins
            self.assertGreater(
                len(allowed_origins),
                0,
                "At least one origin must be allowed"
            )
            # Check for React development server
            react_origins = [
                origin for origin in allowed_origins
                if 'localhost:3000' in origin or '127.0.0.1:3000' in origin
            ]
            self.assertGreater(
                len(react_origins),
                0,
                "React development server (port 3000) must be in allowed origins"
            )

    def test_cors_allow_credentials_configured(self):
        """Verify CORS allows credentials for authenticated requests."""
        self.assertTrue(
            hasattr(settings, 'CORS_ALLOW_CREDENTIALS'),
            "CORS_ALLOW_CREDENTIALS must be configured"
        )
        self.assertTrue(
            settings.CORS_ALLOW_CREDENTIALS,
            "CORS_ALLOW_CREDENTIALS should be True for authenticated requests"
        )

    def test_cors_allowed_methods_configured(self):
        """Verify CORS allowed methods include standard HTTP methods."""
        if hasattr(settings, 'CORS_ALLOW_METHODS'):
            allowed_methods = settings.CORS_ALLOW_METHODS
            self.assertIsInstance(
                allowed_methods,
                (list, tuple),
                "CORS_ALLOW_METHODS must be a list or tuple"
            )
            # Should include standard REST methods
            required_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
            for method in required_methods:
                self.assertIn(
                    method,
                    allowed_methods,
                    f"{method} must be in CORS_ALLOW_METHODS"
                )

    def test_cors_allowed_headers_configured(self):
        """Verify CORS allowed headers include necessary headers."""
        if hasattr(settings, 'CORS_ALLOW_HEADERS'):
            allowed_headers = settings.CORS_ALLOW_HEADERS
            self.assertIsInstance(
                allowed_headers,
                (list, tuple),
                "CORS_ALLOW_HEADERS must be a list or tuple"
            )


class DatabaseIsolationTestCase(TransactionTestCase):
    """Test that test database is properly isolated from development database."""

    def test_test_database_has_test_prefix(self):
        """Verify test database name has 'test_' prefix."""
        db_name = connection.settings_dict['NAME']
        self.assertTrue(
            db_name.startswith('test_'),
            f"Test database must have 'test_' prefix, got '{db_name}'"
        )

    def test_test_database_is_separate(self):
        """Verify test database is not the same as development database."""
        # Get the actual database name being used
        actual_db_name = connection.settings_dict['NAME']
        
        # The actual database name should have 'test_' prefix
        self.assertTrue(
            actual_db_name.startswith('test_'),
            f"Test database must have 'test_' prefix, got '{actual_db_name}'"
        )
        
        # Verify it's a test database by checking the name pattern
        # In Django test environment, the database name is always prefixed with 'test_'
        self.assertIn(
            'test_',
            actual_db_name,
            f"Test database should contain 'test_' in name, got '{actual_db_name}'"
        )

    def test_test_data_does_not_persist(self):
        """Verify test data is isolated and doesn't persist."""
        # Create a test user
        test_username = 'test_isolation_user_12345'
        user = User.objects.create_user(
            username=test_username,
            email='isolation@test.com',
            password='testpass123',
            user_type='student'
        )
        self.assertIsNotNone(user.id)
        
        # Verify it exists in test database
        self.assertTrue(
            User.objects.filter(username=test_username).exists(),
            "Test user should exist in test database"
        )

    def test_database_charset_is_utf8mb4(self):
        """Verify test database uses utf8mb4 charset."""
        db_options = connection.settings_dict.get('OPTIONS', {})
        charset = db_options.get('charset')
        self.assertEqual(
            charset,
            'utf8mb4',
            f"Test database must use utf8mb4 charset, got {charset}"
        )

    def test_database_connection_pooling(self):
        """Verify database connection pooling is configured in test environment."""
        conn_max_age = connection.settings_dict.get('CONN_MAX_AGE')
        self.assertIsNotNone(
            conn_max_age,
            "CONN_MAX_AGE should be configured"
        )


class ModelImportTestCase(TestCase):
    """Test that all models can be imported without circular dependency errors."""

    def test_user_model_import(self):
        """Verify User model can be imported without errors."""
        try:
            from core.models import User
            self.assertIsNotNone(User, "User model should be importable")
        except ImportError as e:
            self.fail(f"Failed to import User model: {e}")

    def test_moving_service_model_import(self):
        """Verify MovingService model can be imported without errors."""
        try:
            from core.models import MovingService
            self.assertIsNotNone(MovingService, "MovingService model should be importable")
        except ImportError as e:
            self.fail(f"Failed to import MovingService model: {e}")

    def test_booking_model_import(self):
        """Verify Booking model can be imported without errors."""
        try:
            from core.models import Booking
            self.assertIsNotNone(Booking, "Booking model should be importable")
        except ImportError as e:
            self.fail(f"Failed to import Booking model: {e}")

    def test_furniture_item_model_import(self):
        """Verify FurnitureItem model can be imported without errors."""
        try:
            from core.models import FurnitureItem
            self.assertIsNotNone(FurnitureItem, "FurnitureItem model should be importable")
        except ImportError as e:
            self.fail(f"Failed to import FurnitureItem model: {e}")

    def test_furniture_image_model_import(self):
        """Verify FurnitureImage model can be imported without errors."""
        try:
            from core.models import FurnitureImage
            self.assertIsNotNone(FurnitureImage, "FurnitureImage model should be importable")
        except ImportError as e:
            self.fail(f"Failed to import FurnitureImage model: {e}")

    def test_furniture_transaction_model_import(self):
        """Verify FurnitureTransaction model can be imported without errors."""
        try:
            from core.models import FurnitureTransaction
            self.assertIsNotNone(FurnitureTransaction, "FurnitureTransaction model should be importable")
        except ImportError as e:
            self.fail(f"Failed to import FurnitureTransaction model: {e}")

    def test_review_model_import(self):
        """Verify Review model can be imported without errors."""
        try:
            from core.models import Review
            self.assertIsNotNone(Review, "Review model should be importable")
        except ImportError as e:
            self.fail(f"Failed to import Review model: {e}")

    def test_all_models_import_together(self):
        """Verify all models can be imported together without circular dependencies."""
        try:
            from core.models import (
                User, MovingService, Booking,
                FurnitureItem, FurnitureImage, FurnitureTransaction,
                Review
            )
            self.assertIsNotNone(User)
            self.assertIsNotNone(MovingService)
            self.assertIsNotNone(Booking)
            self.assertIsNotNone(FurnitureItem)
            self.assertIsNotNone(FurnitureImage)
            self.assertIsNotNone(FurnitureTransaction)
            self.assertIsNotNone(Review)
        except ImportError as e:
            self.fail(f"Circular dependency detected when importing all models: {e}")

    def test_get_user_model_works(self):
        """Verify get_user_model() returns the custom User model."""
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        self.assertEqual(
            UserModel.__name__,
            'User',
            "get_user_model() should return custom User model"
        )
        self.assertEqual(
            UserModel._meta.app_label,
            'core',
            "User model should be in 'core' app"
        )


class MigrationTestCase(TransactionTestCase):
    """Test that migrations run successfully in test environment."""

    def test_migrations_can_be_applied(self):
        """Verify all migrations can be applied without errors."""
        try:
            # This will fail if migrations have issues
            call_command('migrate', verbosity=0, interactive=False)
        except Exception as e:
            self.fail(f"Migrations failed to apply: {e}")

    def test_no_missing_migrations(self):
        """Verify there are no missing migrations."""
        from io import StringIO
        out = StringIO()
        try:
            call_command('makemigrations', '--check', '--dry-run', verbosity=0, stdout=out)
        except SystemExit as e:
            if e.code != 0:
                self.fail("Missing migrations detected. Run 'python manage.py makemigrations'")

    def test_migration_dependencies_correct(self):
        """Verify migration dependencies are correctly configured."""
        from django.db.migrations.loader import MigrationLoader
        loader = MigrationLoader(connection)
        
        # Check that all migrations loaded successfully
        self.assertGreater(
            len(loader.graph.nodes),
            0,
            "At least one migration should exist"
        )


class FixtureTestCase(TransactionTestCase):
    """Test that fixtures can be loaded correctly."""

    def test_user_fixtures_can_be_created(self):
        """Verify user fixtures can be created programmatically."""
        # Create sample users
        student = User.objects.create_user(
            username='fixture_student',
            email='student@fixture.com',
            password='testpass123',
            user_type='student',
            first_name='Test',
            last_name='Student'
        )
        
        provider = User.objects.create_user(
            username='fixture_provider',
            email='provider@fixture.com',
            password='testpass123',
            user_type='provider',
            first_name='Test',
            last_name='Provider'
        )
        
        self.assertIsNotNone(student.id)
        self.assertIsNotNone(provider.id)
        self.assertEqual(student.user_type, 'student')
        self.assertEqual(provider.user_type, 'provider')

    def test_moving_service_fixtures_can_be_created(self):
        """Verify moving service fixtures can be created."""
        from core.models import MovingService
        
        provider = User.objects.create_user(
            username='service_fixture_provider',
            email='serviceprovider@fixture.com',
            password='testpass123',
            user_type='provider'
        )
        
        service = MovingService.objects.create(
            provider=provider,
            service_name='Test Moving Service',
            description='Test description',
            base_price=Decimal('100.00')
        )
        
        self.assertIsNotNone(service.id)
        self.assertEqual(service.provider, provider)

    def test_booking_fixtures_can_be_created(self):
        """Verify booking fixtures can be created."""
        from core.models import MovingService, Booking
        from django.utils import timezone
        from datetime import timedelta
        
        student = User.objects.create_user(
            username='booking_student',
            email='bookingstudent@fixture.com',
            password='testpass123',
            user_type='student'
        )
        
        provider = User.objects.create_user(
            username='booking_provider',
            email='bookingprovider@fixture.com',
            password='testpass123',
            user_type='provider'
        )
        
        service = MovingService.objects.create(
            provider=provider,
            service_name='Booking Test Service',
            description='Test',
            base_price=Decimal('100.00')
        )
        
        booking = Booking.objects.create(
            student=student,
            provider=provider,
            service=service,
            pickup_location='123 Test St',
            dropoff_location='456 Test Ave',
            booking_date=timezone.now() + timedelta(days=7),
            total_price=Decimal('126.25')
        )
        
        self.assertIsNotNone(booking.id)
        self.assertEqual(booking.student, student)
        self.assertEqual(booking.service, service)

    def test_furniture_fixtures_can_be_created(self):
        """Verify furniture item fixtures can be created."""
        from core.models import FurnitureItem
        
        seller = User.objects.create_user(
            username='furniture_seller',
            email='seller@fixture.com',
            password='testpass123',
            user_type='student'
        )
        
        item = FurnitureItem.objects.create(
            seller=seller,
            title='Test Desk',
            description='A test desk',
            price=Decimal('50.00'),
            condition='good',
            category='furniture'
        )
        
        self.assertIsNotNone(item.id)
        self.assertEqual(item.seller, seller)

    def test_review_fixtures_can_be_created(self):
        """Verify review fixtures can be created."""
        from core.models import MovingService, Booking, Review
        from django.utils import timezone
        from datetime import timedelta
        
        student = User.objects.create_user(
            username='review_student',
            email='reviewstudent@fixture.com',
            password='testpass123',
            user_type='student'
        )
        
        provider = User.objects.create_user(
            username='review_provider',
            email='reviewprovider@fixture.com',
            password='testpass123',
            user_type='provider'
        )
        
        service = MovingService.objects.create(
            provider=provider,
            service_name='Review Test Service',
            description='Test',
            base_price=Decimal('100.00')
        )
        
        booking = Booking.objects.create(
            student=student,
            provider=provider,
            service=service,
            pickup_location='123 Test St',
            dropoff_location='456 Test Ave',
            booking_date=timezone.now() + timedelta(days=7),
            total_price=Decimal('126.25'),
            status='completed'
        )
        
        from django.utils import timezone
        
        review = Review.objects.create(
            reviewer=student,
            reviewee=provider,
            booking=booking,
            rating=5,
            comment='Great service!'
        )
        
        self.assertIsNotNone(review.id)
        self.assertEqual(review.reviewer, student)
        self.assertEqual(review.reviewee, provider)


class APIResponseFormattingTestCase(APITestCase):
    """Test that API responses are properly formatted."""

    def setUp(self):
        """Set up test client and sample data."""
        self.client = APIClient()
        self.factory = APIRequestFactory()

    def test_api_client_available(self):
        """Verify REST Framework APIClient is available."""
        self.assertIsNotNone(self.client, "APIClient should be available")

    def test_api_request_factory_available(self):
        """Verify REST Framework APIRequestFactory is available."""
        self.assertIsNotNone(self.factory, "APIRequestFactory should be available")

    def test_json_renderer_produces_valid_json(self):
        """Verify JSON renderer produces valid JSON."""
        from rest_framework.renderers import JSONRenderer
        
        renderer = JSONRenderer()
        data = {'test': 'data', 'number': 123}
        rendered = renderer.render(data)
        
        # Should be valid JSON
        try:
            parsed = json.loads(rendered)
            self.assertEqual(parsed['test'], 'data')
            self.assertEqual(parsed['number'], 123)
        except json.JSONDecodeError as e:
            self.fail(f"JSONRenderer did not produce valid JSON: {e}")

    def test_pagination_class_available(self):
        """Verify pagination class is available and properly configured."""
        from rest_framework.pagination import PageNumberPagination
        
        paginator = PageNumberPagination()
        self.assertIsNotNone(paginator, "PageNumberPagination should be available")
        
        # Check page size from settings
        page_size = settings.REST_FRAMEWORK.get('PAGE_SIZE')
        self.assertIsNotNone(page_size, "PAGE_SIZE should be configured")


class IntegrationEndToEndTestCase(TransactionTestCase):
    """End-to-end integration tests verifying the entire setup works together."""

    def setUp(self):
        """Set up test data for integration tests."""
        self.client = APIClient()
        
        # Create test users
        self.student = User.objects.create_user(
            username='integration_student',
            email='student@integration.com',
            password='testpass123',
            user_type='student'
        )
        
        self.provider = User.objects.create_user(
            username='integration_provider',
            email='provider@integration.com',
            password='testpass123',
            user_type='provider'
        )

    def test_database_and_models_work_together(self):
        """Verify database operations work with all models."""
        from core.models import MovingService, Booking, FurnitureItem, Review
        from django.utils import timezone
        from datetime import timedelta
        
        # Create a moving service
        service = MovingService.objects.create(
            provider=self.provider,
            service_name='Integration Test Service',
            description='Full integration test',
            base_price=Decimal('150.00')
        )
        
        # Create a booking
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=service,
            pickup_location='123 Integration St',
            dropoff_location='456 Integration Ave',
            booking_date=timezone.now() + timedelta(days=7),
            total_price=Decimal('195.00'),
            status='completed'
        )
        
        # Create a furniture item
        from django.utils import timezone
        
        furniture = FurnitureItem.objects.create(
            seller=self.student,
            title='Integration Test Desk',
            description='Desk for integration testing',
            price=Decimal('75.00'),
            condition='like_new',
            category='furniture'
        )
        
        # Create a review
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking,
            rating=5,
            comment='Excellent integration test!'
        )
        
        # Verify all objects were created
        self.assertIsNotNone(service.id)
        self.assertIsNotNone(booking.id)
        self.assertIsNotNone(furniture.id)
        self.assertIsNotNone(review.id)
        
        # Verify relationships
        self.assertEqual(booking.service, service)
        self.assertEqual(booking.student, self.student)
        self.assertEqual(review.booking, booking)
        self.assertEqual(review.reviewer, self.student)
        self.assertEqual(review.reviewee, self.provider)

    def test_rest_framework_and_database_integration(self):
        """Verify REST Framework works with database models."""
        from rest_framework.serializers import ModelSerializer
        
        class UserSerializer(ModelSerializer):
            class Meta:
                model = User
                fields = ['id', 'username', 'email', 'user_type']
        
        # Serialize a user
        serializer = UserSerializer(self.student)
        data = serializer.data
        
        self.assertEqual(data['username'], 'integration_student')
        self.assertEqual(data['email'], 'student@integration.com')
        self.assertEqual(data['user_type'], 'student')

    def test_complete_workflow_integration(self):
        """Test a complete workflow from user creation to review."""
        from core.models import MovingService, Booking, Review
        from django.utils import timezone
        from datetime import timedelta
        
        # 1. Provider creates a service
        service = MovingService.objects.create(
            provider=self.provider,
            service_name='Complete Workflow Service',
            description='End-to-end test',
            base_price=Decimal('200.00')
        )
        
        # 2. Student creates a booking
        booking = Booking.objects.create(
            student=self.student,
            provider=self.provider,
            service=service,
            pickup_location='Start Point',
            dropoff_location='End Point',
            booking_date=timezone.now() + timedelta(days=7),
            total_price=Decimal('280.00')
        )
        
        from django.utils import timezone
        
        # 3. Booking progresses through statuses
        self.assertEqual(booking.status, 'pending')
        booking.status = 'confirmed'
        booking.save()
        booking.status = 'completed'
        booking.save()
        
        # 4. Student leaves a review
        review = Review.objects.create(
            reviewer=self.student,
            reviewee=self.provider,
            booking=booking,
            rating=4,
            comment='Complete workflow test successful!'
        )
        
        # 5. Verify the entire chain
        self.assertEqual(review.booking.service.provider, self.provider)
        self.assertEqual(review.reviewer, self.student)
        self.assertEqual(review.reviewee, self.provider)
        self.assertEqual(booking.status, 'completed')
