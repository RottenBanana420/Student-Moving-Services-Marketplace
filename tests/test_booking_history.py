"""
Comprehensive tests for booking history endpoint.

Following TDD principles:
1. Tests written FIRST to define requirements
2. Tests must FAIL initially (RED phase)
3. Implementation written to make tests pass (GREEN phase)
4. Never modify tests - fix implementation instead

Tests verify:
- Authentication and authorization
- User-specific data isolation (students vs providers)
- Filtering by status, date range, upcoming/past
- Sorting options
- Pagination
- Edge cases
- Query optimization
"""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from rest_framework.test import APIClient
from rest_framework import status
from core.models import MovingService, Booking

User = get_user_model()


@pytest.fixture
def api_client():
    """Fixture for API client."""
    return APIClient()


@pytest.fixture
def student_user(db):
    """Fixture for student user."""
    return User.objects.create_user(
        username='student@test.com',
        email='student@test.com',
        password='TestPass123!',
        user_type='student',
        university_name='Test University'
    )


@pytest.fixture
def another_student_user(db):
    """Fixture for another student user."""
    return User.objects.create_user(
        username='student2@test.com',
        email='student2@test.com',
        password='TestPass123!',
        user_type='student',
        university_name='Test University'
    )


@pytest.fixture
def provider_user(db):
    """Fixture for provider user."""
    return User.objects.create_user(
        username='provider@test.com',
        email='provider@test.com',
        password='TestPass123!',
        user_type='provider',
        university_name='Test University',
        is_verified=True
    )


@pytest.fixture
def another_provider_user(db):
    """Fixture for another provider user."""
    return User.objects.create_user(
        username='provider2@test.com',
        email='provider2@test.com',
        password='TestPass123!',
        user_type='provider',
        university_name='Test University',
        is_verified=True
    )


@pytest.fixture
def moving_service(db, provider_user):
    """Fixture for moving service."""
    return MovingService.objects.create(
        provider=provider_user,
        service_name='Test Moving Service',
        description='Test description',
        base_price=Decimal('100.00'),
        availability_status=True
    )


@pytest.fixture
def another_moving_service(db, another_provider_user):
    """Fixture for another moving service."""
    return MovingService.objects.create(
        provider=another_provider_user,
        service_name='Another Moving Service',
        description='Another description',
        base_price=Decimal('150.00'),
        availability_status=True
    )


@pytest.mark.django_db
class TestBookingHistoryAuthentication:
    """Test authentication requirements for booking history endpoint."""
    
    def test_unauthenticated_access_returns_401(self, api_client):
        """Verify endpoint requires authentication."""
        url = '/api/bookings/my-bookings/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestBookingHistoryAuthorization:
    """Test authorization and data isolation for booking history endpoint."""
    
    def test_students_see_only_their_bookings(
        self, api_client, student_user, another_student_user, 
        provider_user, moving_service
    ):
        """Students should only see bookings they created."""
        # Create bookings for student_user
        booking1 = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            status='pending',
            total_price=Decimal('100.00')
        )
        
        booking2 = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() + timedelta(days=2),
            pickup_location='789 Pine St',
            dropoff_location='321 Elm Ave',
            status='confirmed',
            total_price=Decimal('150.00')
        )
        
        # Create booking for another_student_user (should NOT be visible)
        booking3 = Booking.objects.create(
            student=another_student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() + timedelta(days=3),
            pickup_location='111 Maple St',
            dropoff_location='222 Cedar Ave',
            status='pending',
            total_price=Decimal('200.00')
        )
        
        # Authenticate as student_user
        api_client.force_authenticate(user=student_user)
        
        url = '/api/bookings/my-bookings/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert len(response.data['results']) == 2
        
        # Verify only student_user's bookings are returned
        booking_ids = [b['id'] for b in response.data['results']]
        assert booking1.id in booking_ids
        assert booking2.id in booking_ids
        assert booking3.id not in booking_ids
    
    def test_providers_see_only_their_service_bookings(
        self, api_client, student_user, provider_user, 
        another_provider_user, moving_service, another_moving_service
    ):
        """Providers should only see bookings for their services."""
        # Create bookings for provider_user's service
        booking1 = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            status='pending',
            total_price=Decimal('100.00')
        )
        
        booking2 = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() + timedelta(days=2),
            pickup_location='789 Pine St',
            dropoff_location='321 Elm Ave',
            status='confirmed',
            total_price=Decimal('150.00')
        )
        
        # Create booking for another_provider_user's service (should NOT be visible)
        booking3 = Booking.objects.create(
            student=student_user,
            provider=another_provider_user,
            service=another_moving_service,
            booking_date=timezone.now() + timedelta(days=3),
            pickup_location='111 Maple St',
            dropoff_location='222 Cedar Ave',
            status='pending',
            total_price=Decimal('200.00')
        )
        
        # Authenticate as provider_user
        api_client.force_authenticate(user=provider_user)
        
        url = '/api/bookings/my-bookings/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert len(response.data['results']) == 2
        
        # Verify only provider_user's service bookings are returned
        booking_ids = [b['id'] for b in response.data['results']]
        assert booking1.id in booking_ids
        assert booking2.id in booking_ids
        assert booking3.id not in booking_ids
    
    def test_users_cannot_see_other_users_bookings(
        self, api_client, student_user, another_student_user,
        provider_user, moving_service
    ):
        """Verify strict data isolation between users."""
        # Create booking for another_student_user
        booking = Booking.objects.create(
            student=another_student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            status='pending',
            total_price=Decimal('100.00')
        )
        
        # Authenticate as student_user (different user)
        api_client.force_authenticate(user=student_user)
        
        url = '/api/bookings/my-bookings/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert len(response.data['results']) == 0  # Should see no bookings


@pytest.mark.django_db
class TestBookingHistoryFiltering:
    """Test filtering options for booking history endpoint."""
    
    def test_filter_by_status_pending(
        self, api_client, student_user, provider_user, moving_service
    ):
        """Filter bookings by pending status."""
        # Create bookings with different statuses
        pending_booking = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            status='pending',
            total_price=Decimal('100.00')
        )
        
        confirmed_booking = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() + timedelta(days=2),
            pickup_location='789 Pine St',
            dropoff_location='321 Elm Ave',
            status='confirmed',
            total_price=Decimal('150.00')
        )
        
        api_client.force_authenticate(user=student_user)
        
        url = '/api/bookings/my-bookings/?status=pending'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == pending_booking.id
        assert response.data['results'][0]['status'] == 'pending'
    
    def test_filter_by_status_confirmed(
        self, api_client, student_user, provider_user, moving_service
    ):
        """Filter bookings by confirmed status."""
        pending_booking = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            status='pending',
            total_price=Decimal('100.00')
        )
        
        confirmed_booking = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() + timedelta(days=2),
            pickup_location='789 Pine St',
            dropoff_location='321 Elm Ave',
            status='confirmed',
            total_price=Decimal('150.00')
        )
        
        api_client.force_authenticate(user=student_user)
        
        url = '/api/bookings/my-bookings/?status=confirmed'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == confirmed_booking.id
        assert response.data['results'][0]['status'] == 'confirmed'
    
    def test_filter_by_status_completed(
        self, api_client, student_user, provider_user, moving_service
    ):
        """Filter bookings by completed status."""
        pending_booking = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() - timedelta(days=2),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            status='pending',
            total_price=Decimal('100.00')
        )
        
        completed_booking = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() - timedelta(days=1),
            pickup_location='789 Pine St',
            dropoff_location='321 Elm Ave',
            status='completed',
            total_price=Decimal('150.00')
        )
        
        api_client.force_authenticate(user=student_user)
        
        url = '/api/bookings/my-bookings/?status=completed'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == completed_booking.id
        assert response.data['results'][0]['status'] == 'completed'
    
    def test_filter_by_status_cancelled(
        self, api_client, student_user, provider_user, moving_service
    ):
        """Filter bookings by cancelled status."""
        pending_booking = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            status='pending',
            total_price=Decimal('100.00')
        )
        
        cancelled_booking = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() + timedelta(days=2),
            pickup_location='789 Pine St',
            dropoff_location='321 Elm Ave',
            status='cancelled',
            total_price=Decimal('150.00')
        )
        
        api_client.force_authenticate(user=student_user)
        
        url = '/api/bookings/my-bookings/?status=cancelled'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == cancelled_booking.id
        assert response.data['results'][0]['status'] == 'cancelled'
    
    def test_filter_by_date_range(
        self, api_client, student_user, provider_user, moving_service
    ):
        """Filter bookings within specific date range."""
        now = timezone.now()
        
        # Booking before range
        booking1 = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=now - timedelta(days=10),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            status='completed',
            total_price=Decimal('100.00')
        )
        
        # Booking within range
        booking2 = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=now + timedelta(days=5),
            pickup_location='789 Pine St',
            dropoff_location='321 Elm Ave',
            status='confirmed',
            total_price=Decimal('150.00')
        )
        
        # Booking after range
        booking3 = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=now + timedelta(days=20),
            pickup_location='111 Maple St',
            dropoff_location='222 Cedar Ave',
            status='pending',
            total_price=Decimal('200.00')
        )
        
        api_client.force_authenticate(user=student_user)
        
        start_date = (now + timedelta(days=1)).strftime('%Y-%m-%d')
        end_date = (now + timedelta(days=15)).strftime('%Y-%m-%d')
        url = f'/api/bookings/my-bookings/?start_date={start_date}&end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == booking2.id
    
    def test_filter_upcoming_bookings(
        self, api_client, student_user, provider_user, moving_service
    ):
        """Filter for upcoming bookings only."""
        now = timezone.now()
        
        # Past booking
        past_booking = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=now - timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            status='completed',
            total_price=Decimal('100.00')
        )
        
        # Future booking
        future_booking = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=now + timedelta(days=1),
            pickup_location='789 Pine St',
            dropoff_location='321 Elm Ave',
            status='confirmed',
            total_price=Decimal('150.00')
        )
        
        api_client.force_authenticate(user=student_user)
        
        url = '/api/bookings/my-bookings/?upcoming=true'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == future_booking.id
    
    def test_filter_past_bookings(
        self, api_client, student_user, provider_user, moving_service
    ):
        """Filter for past bookings only."""
        now = timezone.now()
        
        # Past booking
        past_booking = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=now - timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            status='completed',
            total_price=Decimal('100.00')
        )
        
        # Future booking
        future_booking = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=now + timedelta(days=1),
            pickup_location='789 Pine St',
            dropoff_location='321 Elm Ave',
            status='confirmed',
            total_price=Decimal('150.00')
        )
        
        api_client.force_authenticate(user=student_user)
        
        url = '/api/bookings/my-bookings/?past=true'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == past_booking.id


@pytest.mark.django_db
class TestBookingHistorySorting:
    """Test sorting options for booking history endpoint."""
    
    def test_sort_by_booking_date_desc(
        self, api_client, student_user, provider_user, moving_service
    ):
        """Sort by booking date descending (most recent first) - default."""
        now = timezone.now()
        
        booking1 = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=now + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            status='pending',
            total_price=Decimal('100.00')
        )
        
        booking2 = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=now + timedelta(days=5),
            pickup_location='789 Pine St',
            dropoff_location='321 Elm Ave',
            status='confirmed',
            total_price=Decimal('150.00')
        )
        
        booking3 = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=now + timedelta(days=3),
            pickup_location='111 Maple St',
            dropoff_location='222 Cedar Ave',
            status='pending',
            total_price=Decimal('200.00')
        )
        
        api_client.force_authenticate(user=student_user)
        
        # Test default sorting (no sort parameter)
        url = '/api/bookings/my-bookings/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 3
        # Should be sorted by booking_date descending (most recent first)
        assert response.data['results'][0]['id'] == booking2.id  # Day 5
        assert response.data['results'][1]['id'] == booking3.id  # Day 3
        assert response.data['results'][2]['id'] == booking1.id  # Day 1
    
    def test_sort_by_booking_date_asc(
        self, api_client, student_user, provider_user, moving_service
    ):
        """Sort by booking date ascending (upcoming first)."""
        now = timezone.now()
        
        booking1 = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=now + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            status='pending',
            total_price=Decimal('100.00')
        )
        
        booking2 = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=now + timedelta(days=5),
            pickup_location='789 Pine St',
            dropoff_location='321 Elm Ave',
            status='confirmed',
            total_price=Decimal('150.00')
        )
        
        booking3 = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=now + timedelta(days=3),
            pickup_location='111 Maple St',
            dropoff_location='222 Cedar Ave',
            status='pending',
            total_price=Decimal('200.00')
        )
        
        api_client.force_authenticate(user=student_user)
        
        url = '/api/bookings/my-bookings/?sort=booking_date_asc'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 3
        # Should be sorted by booking_date ascending (upcoming first)
        assert response.data['results'][0]['id'] == booking1.id  # Day 1
        assert response.data['results'][1]['id'] == booking3.id  # Day 3
        assert response.data['results'][2]['id'] == booking2.id  # Day 5


@pytest.mark.django_db
class TestBookingHistoryPagination:
    """Test pagination for booking history endpoint."""
    
    def test_pagination_works_correctly(
        self, api_client, student_user, provider_user, moving_service
    ):
        """Verify pagination with 20 items per page."""
        now = timezone.now()
        
        # Create 25 bookings
        for i in range(25):
            Booking.objects.create(
                student=student_user,
                provider=provider_user,
                service=moving_service,
                booking_date=now + timedelta(days=i),
                pickup_location=f'{i} Main St',
                dropoff_location=f'{i} Oak Ave',
                status='pending',
                total_price=Decimal('100.00')
            )
        
        api_client.force_authenticate(user=student_user)
        
        # Test first page
        url = '/api/bookings/my-bookings/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert 'count' in response.data
        assert 'next' in response.data
        assert 'previous' in response.data
        assert len(response.data['results']) == 20
        assert response.data['count'] == 25
        assert response.data['next'] is not None
        assert response.data['previous'] is None
        
        # Test second page
        url = '/api/bookings/my-bookings/?page=2'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 5
        assert response.data['count'] == 25
        assert response.data['next'] is None
        assert response.data['previous'] is not None
    
    def test_pagination_returns_total_count(
        self, api_client, student_user, provider_user, moving_service
    ):
        """Verify total count is returned in pagination."""
        now = timezone.now()
        
        # Create 15 bookings
        for i in range(15):
            Booking.objects.create(
                student=student_user,
                provider=provider_user,
                service=moving_service,
                booking_date=now + timedelta(days=i),
                pickup_location=f'{i} Main St',
                dropoff_location=f'{i} Oak Ave',
                status='pending',
                total_price=Decimal('100.00')
            )
        
        api_client.force_authenticate(user=student_user)
        
        url = '/api/bookings/my-bookings/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 15


@pytest.mark.django_db
class TestBookingHistoryEdgeCases:
    """Test edge cases for booking history endpoint."""
    
    def test_user_with_no_bookings(
        self, api_client, student_user
    ):
        """User with no bookings should get empty result set."""
        api_client.force_authenticate(user=student_user)
        
        url = '/api/bookings/my-bookings/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert len(response.data['results']) == 0
        assert response.data['count'] == 0
    
    def test_user_with_one_booking(
        self, api_client, student_user, provider_user, moving_service
    ):
        """User with one booking should get single result."""
        booking = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            status='pending',
            total_price=Decimal('100.00')
        )
        
        api_client.force_authenticate(user=student_user)
        
        url = '/api/bookings/my-bookings/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['count'] == 1
        assert response.data['results'][0]['id'] == booking.id
    
    def test_user_with_many_bookings(
        self, api_client, student_user, provider_user, moving_service
    ):
        """User with many bookings should get paginated results."""
        now = timezone.now()
        
        # Create 30 bookings
        for i in range(30):
            Booking.objects.create(
                student=student_user,
                provider=provider_user,
                service=moving_service,
                booking_date=now + timedelta(days=i),
                pickup_location=f'{i} Main St',
                dropoff_location=f'{i} Oak Ave',
                status='pending',
                total_price=Decimal('100.00')
            )
        
        api_client.force_authenticate(user=student_user)
        
        url = '/api/bookings/my-bookings/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 20  # First page
        assert response.data['count'] == 30
        assert response.data['next'] is not None


@pytest.mark.django_db
class TestBookingHistoryResponseStructure:
    """Test response structure and serialization."""
    
    def test_response_includes_complete_booking_details(
        self, api_client, student_user, provider_user, moving_service
    ):
        """Verify response includes all required booking fields."""
        booking = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            status='pending',
            total_price=Decimal('100.00')
        )
        
        api_client.force_authenticate(user=student_user)
        
        url = '/api/bookings/my-bookings/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        
        booking_data = response.data['results'][0]
        
        # Verify all required fields are present
        assert 'id' in booking_data
        assert 'booking_date' in booking_data
        assert 'pickup_location' in booking_data
        assert 'dropoff_location' in booking_data
        assert 'status' in booking_data
        assert 'total_price' in booking_data
        assert 'created_at' in booking_data
        assert 'updated_at' in booking_data
        assert 'service' in booking_data
        
        # Verify service details are nested
        assert 'id' in booking_data['service']
        assert 'service_name' in booking_data['service']
        assert 'description' in booking_data['service']
        assert 'base_price' in booking_data['service']
    
    def test_student_sees_provider_information(
        self, api_client, student_user, provider_user, moving_service
    ):
        """Students should see provider information in their bookings."""
        booking = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            status='pending',
            total_price=Decimal('100.00')
        )
        
        api_client.force_authenticate(user=student_user)
        
        url = '/api/bookings/my-bookings/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        booking_data = response.data['results'][0]
        
        # Students should see provider info
        assert 'provider' in booking_data
        assert 'id' in booking_data['provider']
        assert 'email' in booking_data['provider']
        assert 'university_name' in booking_data['provider']
        assert 'is_verified' in booking_data['provider']
        
        # Should NOT see student info (that's themselves)
        assert 'student' not in booking_data
    
    def test_provider_sees_student_information(
        self, api_client, student_user, provider_user, moving_service
    ):
        """Providers should see student information in their bookings."""
        booking = Booking.objects.create(
            student=student_user,
            provider=provider_user,
            service=moving_service,
            booking_date=timezone.now() + timedelta(days=1),
            pickup_location='123 Main St',
            dropoff_location='456 Oak Ave',
            status='pending',
            total_price=Decimal('100.00')
        )
        
        api_client.force_authenticate(user=provider_user)
        
        url = '/api/bookings/my-bookings/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        booking_data = response.data['results'][0]
        
        # Providers should see student info
        assert 'student' in booking_data
        assert 'id' in booking_data['student']
        assert 'email' in booking_data['student']
        assert 'university_name' in booking_data['student']
        
        # Should NOT see provider info (that's themselves)
        assert 'provider' not in booking_data
