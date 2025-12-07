"""
Comprehensive Service Creation Security Tests

This test suite is designed to FAIL initially and validate service creation implementation.
Tests cover authentication, authorization, validation, business rules, and security edge cases.

CRITICAL: These tests should NEVER be modified to make them pass.
Only the implementation (permissions, serializers, views) should be updated.
"""

import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from core.models import MovingService

User = get_user_model()


@pytest.fixture
def api_client():
    """Provide API client for testing."""
    return APIClient()


@pytest.fixture
def verified_provider(db):
    """Create a verified provider user."""
    return User.objects.create_user(
        username='verified_provider',
        email='verified_provider@example.com',
        password='ProviderPass123!',
        first_name='Verified',
        last_name='Provider',
        user_type='provider',
        is_staff=False,
        is_active=True,
        is_verified=True
    )


@pytest.fixture
def unverified_provider(db):
    """Create an unverified provider user."""
    return User.objects.create_user(
        username='unverified_provider',
        email='unverified@example.com',
        password='ProviderPass123!',
        first_name='Unverified',
        last_name='Provider',
        user_type='provider',
        is_staff=False,
        is_active=True,
        is_verified=False
    )


@pytest.fixture
def student_user(db):
    """Create a student user."""
    return User.objects.create_user(
        username='student_user',
        email='student@example.com',
        password='StudentPass123!',
        first_name='Student',
        last_name='User',
        user_type='student',
        is_staff=False,
        is_active=True,
        is_verified=False
    )


def get_auth_header(user):
    """Generate JWT authentication header for a user."""
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    return f'Bearer {access_token}'


# ============================================================================
# 1. SUCCESSFUL SERVICE CREATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestSuccessfulServiceCreation:
    """Test successful service creation scenarios."""
    
    def test_verified_provider_can_create_service(self, api_client, verified_provider):
        """Verified provider should be able to create a service."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        data = {
            'service_name': 'Premium Moving Service',
            'description': 'Professional moving service for students',
            'base_price': '150.00',
            'availability_status': True
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify service was created in database
        assert MovingService.objects.filter(
            provider=verified_provider,
            service_name='Premium Moving Service'
        ).exists()
    
    def test_service_creation_returns_correct_data_structure(self, api_client, verified_provider):
        """Service creation should return complete service details."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        data = {
            'service_name': 'Budget Moving',
            'description': 'Affordable moving service',
            'base_price': '75.50'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'id' in response.data
        assert 'service_name' in response.data
        assert 'description' in response.data
        assert 'base_price' in response.data
        assert 'availability_status' in response.data
        assert 'rating_average' in response.data
        assert 'total_reviews' in response.data
        assert 'provider' in response.data
        assert 'created_at' in response.data
        
        # Verify data values
        assert response.data['service_name'] == 'Budget Moving'
        assert response.data['description'] == 'Affordable moving service'
        assert Decimal(str(response.data['base_price'])) == Decimal('75.50')
    
    def test_auto_populated_fields_are_set_correctly(self, api_client, verified_provider):
        """Auto-populated fields should be initialized correctly."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        data = {
            'service_name': 'Express Moving',
            'description': 'Fast and reliable moving service',
            'base_price': '200.00'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify auto-populated fields
        assert response.data['provider'] == verified_provider.id
        assert Decimal(str(response.data['rating_average'])) == Decimal('0.00')
        assert response.data['total_reviews'] == 0
        assert response.data['id'] is not None
        assert response.data['created_at'] is not None
    
    def test_availability_status_defaults_to_true(self, api_client, verified_provider):
        """Availability status should default to True if not provided."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        data = {
            'service_name': 'Default Availability Service',
            'description': 'Testing default availability',
            'base_price': '100.00'
            # availability_status not provided
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['availability_status'] is True
    
    def test_concurrent_service_creation_by_same_provider(self, api_client, verified_provider):
        """Provider should be able to create multiple services."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        services_data = [
            {
                'service_name': 'Service 1',
                'description': 'First service',
                'base_price': '100.00'
            },
            {
                'service_name': 'Service 2',
                'description': 'Second service',
                'base_price': '150.00'
            },
            {
                'service_name': 'Service 3',
                'description': 'Third service',
                'base_price': '200.00'
            }
        ]
        
        for service_data in services_data:
            response = api_client.post(url, service_data, format='json')
            assert response.status_code == status.HTTP_201_CREATED
        
        # Verify all services were created
        assert MovingService.objects.filter(provider=verified_provider).count() == 3


# ============================================================================
# 2. AUTHENTICATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestAuthenticationRequirements:
    """Test authentication requirements for service creation."""
    
    def test_unauthenticated_request_returns_401(self, api_client):
        """Request without authentication should return 401."""
        url = reverse('service_create')
        
        data = {
            'service_name': 'Unauthorized Service',
            'description': 'This should fail',
            'base_price': '100.00'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Verify no service was created
        assert MovingService.objects.count() == 0
    
    def test_invalid_jwt_token_returns_401(self, api_client):
        """Request with invalid JWT token should return 401."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION='Bearer invalid_token_here')
        
        data = {
            'service_name': 'Invalid Token Service',
            'description': 'This should fail',
            'base_price': '100.00'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert MovingService.objects.count() == 0
    
    def test_malformed_auth_header_returns_401(self, api_client):
        """Request with malformed authorization header should return 401."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION='InvalidFormat')
        
        data = {
            'service_name': 'Malformed Auth Service',
            'description': 'This should fail',
            'base_price': '100.00'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ============================================================================
# 3. AUTHORIZATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestAuthorizationRequirements:
    """Test authorization requirements (verified provider-only access)."""
    
    def test_student_cannot_create_service(self, api_client, student_user):
        """Student user should receive 403 when attempting to create service."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(student_user))
        
        data = {
            'service_name': 'Student Service',
            'description': 'Students cannot create services',
            'base_price': '100.00'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert MovingService.objects.count() == 0
    
    def test_unverified_provider_cannot_create_service(self, api_client, unverified_provider):
        """Unverified provider should receive 403 when attempting to create service."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(unverified_provider))
        
        data = {
            'service_name': 'Unverified Provider Service',
            'description': 'Unverified providers cannot create services',
            'base_price': '100.00'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert MovingService.objects.count() == 0
    
    def test_only_verified_providers_can_create_services(self, api_client, verified_provider, unverified_provider, student_user):
        """Only verified providers should be able to create services."""
        url = reverse('service_create')
        
        data = {
            'service_name': 'Test Service',
            'description': 'Testing authorization',
            'base_price': '100.00'
        }
        
        # Verified provider should succeed
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        response_verified = api_client.post(url, data, format='json')
        assert response_verified.status_code == status.HTTP_201_CREATED
        
        # Unverified provider should fail
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(unverified_provider))
        response_unverified = api_client.post(url, data, format='json')
        assert response_unverified.status_code == status.HTTP_403_FORBIDDEN
        
        # Student should fail
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(student_user))
        response_student = api_client.post(url, data, format='json')
        assert response_student.status_code == status.HTTP_403_FORBIDDEN
        
        # Only one service should be created (by verified provider)
        assert MovingService.objects.count() == 1
        assert MovingService.objects.first().provider == verified_provider


# ============================================================================
# 4. VALIDATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestValidationRules:
    """Test input validation and error handling."""
    
    def test_missing_required_fields_returns_400(self, api_client, verified_provider):
        """Request with missing required fields should return 400."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        # Missing service_name
        data1 = {
            'description': 'Missing service name',
            'base_price': '100.00'
        }
        response1 = api_client.post(url, data1, format='json')
        assert response1.status_code == status.HTTP_400_BAD_REQUEST
        assert 'service_name' in str(response1.data).lower()
        
        # Missing description
        data2 = {
            'service_name': 'Missing Description Service',
            'base_price': '100.00'
        }
        response2 = api_client.post(url, data2, format='json')
        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        assert 'description' in str(response2.data).lower()
        
        # Missing base_price
        data3 = {
            'service_name': 'Missing Price Service',
            'description': 'Missing base price'
        }
        response3 = api_client.post(url, data3, format='json')
        assert response3.status_code == status.HTTP_400_BAD_REQUEST
        assert 'base_price' in str(response3.data).lower() or 'price' in str(response3.data).lower()
    
    def test_negative_price_returns_validation_error(self, api_client, verified_provider):
        """Negative base price should return validation error."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        data = {
            'service_name': 'Negative Price Service',
            'description': 'Testing negative price validation',
            'base_price': '-50.00'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_message = str(response.data).lower()
        assert 'price' in error_message or 'positive' in error_message or 'greater' in error_message
    
    def test_zero_price_returns_validation_error(self, api_client, verified_provider):
        """Zero base price should return validation error."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        data = {
            'service_name': 'Zero Price Service',
            'description': 'Testing zero price validation',
            'base_price': '0.00'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_message = str(response.data).lower()
        assert 'price' in error_message or 'positive' in error_message or 'greater' in error_message
    
    def test_excessively_long_service_name_returns_validation_error(self, api_client, verified_provider):
        """Service name exceeding max length should return validation error."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        # Create a name longer than 200 characters
        long_name = 'A' * 201
        
        data = {
            'service_name': long_name,
            'description': 'Testing max length validation',
            'base_price': '100.00'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_message = str(response.data).lower()
        assert 'service_name' in error_message or 'name' in error_message or 'length' in error_message or 'characters' in error_message
    
    def test_empty_service_name_returns_validation_error(self, api_client, verified_provider):
        """Empty service name should return validation error."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        empty_names = ['', '   ', '\t', '\n']
        
        for empty_name in empty_names:
            data = {
                'service_name': empty_name,
                'description': 'Testing empty name validation',
                'base_price': '100.00'
            }
            response = api_client.post(url, data, format='json')
            assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_empty_description_returns_validation_error(self, api_client, verified_provider):
        """Empty description should return validation error."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        empty_descriptions = ['', '   ', '\t', '\n']
        
        for empty_desc in empty_descriptions:
            data = {
                'service_name': 'Valid Service Name',
                'description': empty_desc,
                'base_price': '100.00'
            }
            response = api_client.post(url, data, format='json')
            assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_invalid_price_format_returns_validation_error(self, api_client, verified_provider):
        """Invalid price format should return validation error."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        invalid_prices = ['abc', 'null', '', 'one hundred']
        
        for invalid_price in invalid_prices:
            data = {
                'service_name': 'Invalid Price Service',
                'description': 'Testing invalid price format',
                'base_price': invalid_price
            }
            response = api_client.post(url, data, format='json')
            assert response.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# 5. BUSINESS RULES TESTS
# ============================================================================

@pytest.mark.django_db
class TestBusinessRules:
    """Test business rules and auto-population logic."""
    
    def test_provider_field_auto_set_to_authenticated_user(self, api_client, verified_provider):
        """Provider field should be automatically set to authenticated user."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        data = {
            'service_name': 'Auto Provider Service',
            'description': 'Testing auto provider assignment',
            'base_price': '100.00'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify provider is set correctly
        service = MovingService.objects.get(id=response.data['id'])
        assert service.provider == verified_provider
        assert response.data['provider'] == verified_provider.id
    
    def test_rating_average_initialized_to_zero(self, api_client, verified_provider):
        """Rating average should be initialized to 0.0 for new services."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        data = {
            'service_name': 'Zero Rating Service',
            'description': 'Testing rating initialization',
            'base_price': '100.00'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert Decimal(str(response.data['rating_average'])) == Decimal('0.00')
        
        service = MovingService.objects.get(id=response.data['id'])
        assert service.rating_average == Decimal('0.00')
    
    def test_total_reviews_initialized_to_zero(self, api_client, verified_provider):
        """Total reviews should be initialized to 0 for new services."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        data = {
            'service_name': 'Zero Reviews Service',
            'description': 'Testing reviews initialization',
            'base_price': '100.00'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['total_reviews'] == 0
        
        service = MovingService.objects.get(id=response.data['id'])
        assert service.total_reviews == 0
    
    def test_created_service_has_auto_generated_id(self, api_client, verified_provider):
        """Created service should have an auto-generated ID."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        data = {
            'service_name': 'Auto ID Service',
            'description': 'Testing auto ID generation',
            'base_price': '100.00'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'id' in response.data
        assert response.data['id'] is not None
        assert isinstance(response.data['id'], int)
        assert response.data['id'] > 0


# ============================================================================
# 6. HTTP METHODS TESTS
# ============================================================================

@pytest.mark.django_db
class TestHTTPMethods:
    """Test HTTP method restrictions."""
    
    def test_only_post_method_allowed(self, api_client, verified_provider):
        """Only POST method should be allowed for service creation."""
        url = reverse('service_create')
        api_client.credentials(HTTP_AUTHORIZATION=get_auth_header(verified_provider))
        
        # Test GET
        response_get = api_client.get(url)
        assert response_get.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        
        # Test PUT
        data = {
            'service_name': 'PUT Service',
            'description': 'Testing PUT method',
            'base_price': '100.00'
        }
        response_put = api_client.put(url, data, format='json')
        assert response_put.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        
        # Test PATCH
        response_patch = api_client.patch(url, data, format='json')
        assert response_patch.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        
        # Test DELETE
        response_delete = api_client.delete(url)
        assert response_delete.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        
        # POST should work
        response_post = api_client.post(url, data, format='json')
        assert response_post.status_code == status.HTTP_201_CREATED
