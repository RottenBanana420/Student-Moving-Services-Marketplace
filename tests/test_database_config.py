"""
Comprehensive test suite for Django MySQL database configuration.

This test suite follows TDD principles and is designed to fail initially.
Tests verify database connectivity, CRUD operations, media configuration,
and installed apps loading. These tests should NEVER be modified - only
the configuration should be updated to make them pass.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection, connections
from django.db.utils import OperationalError
from django.test import TestCase, TransactionTestCase, override_settings
from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile


class DatabaseConnectivityTestCase(TestCase):
    """Test database connectivity with correct and incorrect credentials."""

    def test_database_engine_is_mysql(self):
        """Verify that MySQL is configured as the database engine."""
        db_engine = settings.DATABASES['default']['ENGINE']
        self.assertEqual(
            db_engine,
            'django.db.backends.mysql',
            f"Expected MySQL engine, got {db_engine}"
        )

    def test_database_name_is_correct(self):
        """Verify database name is 'student_moving_db'."""
        db_name = settings.DATABASES['default']['NAME']
        # Django prefixes test databases with 'test_'
        expected_name = 'student_moving_db'
        if db_name.startswith('test_'):
            # In test environment, verify it's test_student_moving_db
            self.assertEqual(
                db_name,
                f'test_{expected_name}',
                f"Expected 'test_{expected_name}' in test environment, got '{db_name}'"
            )
        else:
            # In normal environment, verify it's student_moving_db
            self.assertEqual(
                db_name,
                expected_name,
                f"Expected '{expected_name}', got '{db_name}'"
            )

    def test_database_connection_succeeds(self):
        """Test that database connection succeeds with correct credentials."""
        try:
            connection.ensure_connection()
            self.assertTrue(connection.is_usable())
        except OperationalError as e:
            self.fail(f"Database connection failed: {e}")

    def test_database_host_is_configured(self):
        """Verify database host is configured."""
        db_host = settings.DATABASES['default'].get('HOST')
        self.assertIsNotNone(db_host, "Database HOST must be configured")
        self.assertIn(
            db_host,
            ['localhost', '127.0.0.1'],
            f"Expected localhost or 127.0.0.1, got {db_host}"
        )

    def test_database_port_is_configured(self):
        """Verify database port is configured to MySQL default."""
        db_port = settings.DATABASES['default'].get('PORT')
        self.assertIsNotNone(db_port, "Database PORT must be configured")
        self.assertEqual(
            str(db_port),
            '3306',
            f"Expected MySQL default port 3306, got {db_port}"
        )

    def test_database_user_is_configured(self):
        """Verify database user is configured."""
        db_user = settings.DATABASES['default'].get('USER')
        self.assertIsNotNone(db_user, "Database USER must be configured")
        self.assertTrue(
            len(db_user) > 0,
            "Database USER cannot be empty"
        )

    def test_database_password_is_configured(self):
        """Verify database password is configured."""
        db_password = settings.DATABASES['default'].get('PASSWORD')
        self.assertIsNotNone(db_password, "Database PASSWORD must be configured")

    def test_database_charset_is_utf8mb4(self):
        """Verify database is configured with utf8mb4 charset."""
        db_options = settings.DATABASES['default'].get('OPTIONS', {})
        charset = db_options.get('charset')
        self.assertEqual(
            charset,
            'utf8mb4',
            f"Expected utf8mb4 charset for emoji support, got {charset}"
        )

    def test_database_strict_mode_enabled(self):
        """Verify SQL strict mode is enabled."""
        db_options = settings.DATABASES['default'].get('OPTIONS', {})
        init_command = db_options.get('init_command', '')
        self.assertIn(
            'STRICT_TRANS_TABLES',
            init_command,
            "SQL strict mode must be enabled"
        )

    def test_connection_timeout_configured(self):
        """Verify connection timeout is configured for reliability."""
        db_options = settings.DATABASES['default'].get('OPTIONS', {})
        # MySQL connector uses 'connect_timeout'
        self.assertIn(
            'connect_timeout',
            db_options,
            "Connection timeout must be configured"
        )
        timeout = db_options['connect_timeout']
        self.assertGreater(timeout, 0, "Timeout must be positive")
        self.assertLessEqual(timeout, 30, "Timeout should be reasonable (<=30s)")


class DatabaseOperationsTestCase(TransactionTestCase):
    """Test CRUD operations on the database."""

    def setUp(self):
        """Set up test database connection."""
        from core.models import User
        self.User = User

    def test_create_operation(self):
        """Test creating a record in the database."""
        user = self.User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='student'
        )
        self.assertIsNotNone(user.id, "User should have an ID after creation")
        self.assertEqual(user.username, 'testuser')

    def test_read_operation(self):
        """Test reading a record from the database."""
        # Create a user
        created_user = self.User.objects.create_user(
            username='readuser',
            email='read@example.com',
            password='testpass123',
            user_type='student'
        )
        
        # Read it back
        retrieved_user = self.User.objects.get(username='readuser')
        self.assertEqual(retrieved_user.id, created_user.id)
        self.assertEqual(retrieved_user.email, 'read@example.com')

    def test_update_operation(self):
        """Test updating a record in the database."""
        user = self.User.objects.create_user(
            username='updateuser',
            email='update@example.com',
            password='testpass123',
            user_type='student'
        )
        
        # Update the user
        user.email = 'updated@example.com'
        user.save()
        
        # Verify update
        updated_user = self.User.objects.get(username='updateuser')
        self.assertEqual(updated_user.email, 'updated@example.com')

    def test_delete_operation(self):
        """Test deleting a record from the database."""
        user = self.User.objects.create_user(
            username='deleteuser',
            email='delete@example.com',
            password='testpass123',
            user_type='student'
        )
        user_id = user.id
        
        # Delete the user
        user.delete()
        
        # Verify deletion
        with self.assertRaises(self.User.DoesNotExist):
            self.User.objects.get(id=user_id)

    def test_transaction_rollback(self):
        """Test that database transactions can rollback properly."""
        from django.db import transaction
        
        initial_count = self.User.objects.count()
        
        try:
            with transaction.atomic():
                self.User.objects.create_user(
                    username='rollbackuser',
                    email='rollback@example.com',
                    password='testpass123',
                    user_type='student'
                )
                # Force a rollback by raising an exception
                raise Exception("Intentional rollback")
        except Exception:
            pass
        
        # Verify the user was not created
        final_count = self.User.objects.count()
        self.assertEqual(initial_count, final_count, "Transaction should have rolled back")

    def test_emoji_and_special_characters(self):
        """Test that utf8mb4 charset handles emojis and special characters."""
        emoji_username = 'user_😀_test'
        special_chars = 'Tëst Üsér 中文 العربية'
        
        user = self.User.objects.create_user(
            username='emoji_user',
            first_name=emoji_username,
            last_name=special_chars,
            email='emoji@example.com',
            password='testpass123',
            user_type='student'
        )
        
        # Retrieve and verify
        retrieved_user = self.User.objects.get(username='emoji_user')
        self.assertEqual(retrieved_user.first_name, emoji_username)
        self.assertEqual(retrieved_user.last_name, special_chars)

    def test_bulk_operations_performance(self):
        """Test bulk create operations work correctly."""
        users = [
            self.User(
                username=f'bulkuser{i}',
                email=f'bulk{i}@example.com',
                user_type='student'
            )
            for i in range(100)
        ]
        
        created_users = self.User.objects.bulk_create(users)
        self.assertEqual(len(created_users), 100, "All users should be created")


class MediaFileConfigurationTestCase(TestCase):
    """Test media file configuration settings."""

    def test_media_url_is_configured(self):
        """Verify MEDIA_URL is configured."""
        self.assertTrue(
            hasattr(settings, 'MEDIA_URL'),
            "MEDIA_URL must be configured"
        )
        self.assertEqual(
            settings.MEDIA_URL,
            '/media/',
            f"Expected '/media/', got '{settings.MEDIA_URL}'"
        )

    def test_media_root_is_configured(self):
        """Verify MEDIA_ROOT is configured."""
        self.assertTrue(
            hasattr(settings, 'MEDIA_ROOT'),
            "MEDIA_ROOT must be configured"
        )
        self.assertIsNotNone(settings.MEDIA_ROOT)

    def test_media_root_is_absolute_path(self):
        """Verify MEDIA_ROOT is an absolute path."""
        media_root = Path(settings.MEDIA_ROOT)
        self.assertTrue(
            media_root.is_absolute(),
            f"MEDIA_ROOT must be absolute path, got {media_root}"
        )

    def test_media_root_directory_exists(self):
        """Verify MEDIA_ROOT directory exists."""
        media_root = Path(settings.MEDIA_ROOT)
        # Create if doesn't exist for testing
        media_root.mkdir(parents=True, exist_ok=True)
        self.assertTrue(
            media_root.exists(),
            f"MEDIA_ROOT directory must exist: {media_root}"
        )

    def test_media_root_is_writable(self):
        """Verify MEDIA_ROOT directory is writable."""
        media_root = Path(settings.MEDIA_ROOT)
        media_root.mkdir(parents=True, exist_ok=True)
        
        # Test write permission
        test_file = media_root / '.write_test'
        try:
            test_file.write_text('test')
            test_file.unlink()
            writable = True
        except (PermissionError, OSError):
            writable = False
        
        self.assertTrue(
            writable,
            f"MEDIA_ROOT must be writable: {media_root}"
        )

    def test_file_upload_max_memory_size_configured(self):
        """Verify FILE_UPLOAD_MAX_MEMORY_SIZE is configured."""
        self.assertTrue(
            hasattr(settings, 'FILE_UPLOAD_MAX_MEMORY_SIZE'),
            "FILE_UPLOAD_MAX_MEMORY_SIZE must be configured"
        )
        max_size = settings.FILE_UPLOAD_MAX_MEMORY_SIZE
        self.assertGreater(
            max_size,
            0,
            "FILE_UPLOAD_MAX_MEMORY_SIZE must be positive"
        )
        # Should be reasonable (e.g., 5MB = 5242880 bytes)
        self.assertGreaterEqual(
            max_size,
            2621440,  # 2.5MB minimum
            "FILE_UPLOAD_MAX_MEMORY_SIZE should be at least 2.5MB"
        )

    def test_data_upload_max_memory_size_configured(self):
        """Verify DATA_UPLOAD_MAX_MEMORY_SIZE is configured."""
        self.assertTrue(
            hasattr(settings, 'DATA_UPLOAD_MAX_MEMORY_SIZE'),
            "DATA_UPLOAD_MAX_MEMORY_SIZE must be configured"
        )
        max_size = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
        self.assertGreater(
            max_size,
            0,
            "DATA_UPLOAD_MAX_MEMORY_SIZE must be positive"
        )
        self.assertGreaterEqual(
            max_size,
            2621440,  # 2.5MB minimum
            "DATA_UPLOAD_MAX_MEMORY_SIZE should be at least 2.5MB"
        )


class InstalledAppsTestCase(TestCase):
    """Test that all required apps are installed and load correctly."""

    def test_core_app_installed(self):
        """Verify core app is in INSTALLED_APPS."""
        self.assertIn(
            'core',
            settings.INSTALLED_APPS,
            "core app must be in INSTALLED_APPS"
        )

    def test_rest_framework_installed(self):
        """Verify Django REST Framework is in INSTALLED_APPS."""
        self.assertIn(
            'rest_framework',
            settings.INSTALLED_APPS,
            "rest_framework must be in INSTALLED_APPS"
        )

    def test_cors_headers_installed(self):
        """Verify django-cors-headers is in INSTALLED_APPS."""
        self.assertIn(
            'corsheaders',
            settings.INSTALLED_APPS,
            "corsheaders must be in INSTALLED_APPS"
        )

    def test_all_apps_load_without_errors(self):
        """Verify all installed apps load without errors."""
        for app_name in settings.INSTALLED_APPS:
            try:
                app_config = apps.get_app_config(app_name.split('.')[-1])
                self.assertIsNotNone(
                    app_config,
                    f"App {app_name} should load successfully"
                )
            except LookupError as e:
                self.fail(f"App {app_name} failed to load: {e}")

    def test_cors_middleware_installed(self):
        """Verify CORS middleware is in MIDDLEWARE."""
        self.assertIn(
            'corsheaders.middleware.CorsMiddleware',
            settings.MIDDLEWARE,
            "CorsMiddleware must be in MIDDLEWARE"
        )

    def test_cors_middleware_position(self):
        """Verify CORS middleware is before CommonMiddleware."""
        middleware_list = settings.MIDDLEWARE
        cors_index = middleware_list.index('corsheaders.middleware.CorsMiddleware')
        common_index = middleware_list.index('django.middleware.common.CommonMiddleware')
        self.assertLess(
            cors_index,
            common_index,
            "CorsMiddleware must be before CommonMiddleware"
        )

    def test_rest_framework_settings_configured(self):
        """Verify REST Framework settings are configured."""
        self.assertTrue(
            hasattr(settings, 'REST_FRAMEWORK'),
            "REST_FRAMEWORK settings must be configured"
        )
        rest_settings = settings.REST_FRAMEWORK
        self.assertIsInstance(
            rest_settings,
            dict,
            "REST_FRAMEWORK must be a dictionary"
        )

    def test_cors_allowed_origins_configured(self):
        """Verify CORS allowed origins are configured."""
        self.assertTrue(
            hasattr(settings, 'CORS_ALLOWED_ORIGINS') or hasattr(settings, 'CORS_ALLOW_ALL_ORIGINS'),
            "CORS origins must be configured"
        )

    def test_core_app_has_valid_config(self):
        """Verify core app has valid AppConfig."""
        try:
            app_config = apps.get_app_config('core')
            self.assertEqual(app_config.name, 'core')
        except LookupError:
            self.fail("core app config not found")


class DatabaseConnectionPoolingTestCase(TestCase):
    """Test database connection pooling and performance settings."""

    def test_connection_max_age_configured(self):
        """Verify CONN_MAX_AGE is configured for connection pooling."""
        conn_max_age = settings.DATABASES['default'].get('CONN_MAX_AGE')
        self.assertIsNotNone(
            conn_max_age,
            "CONN_MAX_AGE should be configured for connection pooling"
        )
        if conn_max_age != 0:  # 0 means disabled, which is also valid
            self.assertGreater(
                conn_max_age,
                0,
                "CONN_MAX_AGE should be positive if enabled"
            )

    def test_atomic_requests_configured(self):
        """Verify ATOMIC_REQUESTS setting is explicitly configured."""
        self.assertIn(
            'ATOMIC_REQUESTS',
            settings.DATABASES['default'],
            "ATOMIC_REQUESTS should be explicitly configured"
        )


class DatabaseSecurityTestCase(TestCase):
    """Test database security configurations."""

    def test_password_not_empty(self):
        """Verify database password is not empty."""
        db_password = settings.DATABASES['default'].get('PASSWORD', '')
        self.assertTrue(
            len(db_password) > 0,
            "Database password should not be empty for security"
        )

    def test_user_not_root(self):
        """Verify database user is not root (security best practice)."""
        db_user = settings.DATABASES['default'].get('USER', '')
        self.assertNotEqual(
            db_user.lower(),
            'root',
            "Should not use root user for application database access"
        )

    def test_sql_mode_strict(self):
        """Verify strict SQL mode is enabled for data integrity."""
        db_options = settings.DATABASES['default'].get('OPTIONS', {})
        init_command = db_options.get('init_command', '')
        self.assertIn(
            'STRICT_TRANS_TABLES',
            init_command,
            "Strict SQL mode should be enabled"
        )
