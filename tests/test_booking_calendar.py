"""
Comprehensive test suite for booking calendar endpoint.

Tests cover:
- Date range filtering (within range, outside range, boundaries)
- Provider and service filtering
- Status filtering
- Calendar data structure and organization
- Available slot calculation
- Edge cases (past dates, future dates, empty results)
- Query optimization
- Authentication (public access)

Following TDD approach: Tests are written first and will fail until implementation is complete.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import MovingService, Booking

User = get_user_model()


@pytest.fixture
def api_client():
    """Return API client for testing."""
    return APIClient()


@pytest.fixture
def student_user(db):
    """Create a student user for testing."""
    return User.objects.create_user(
        email='student@test.com',
        username='student',
        password='TestPass123!',
        user_type='student',
        university_name='Test University'
    )


@pytest.fixture
def another_student(db):
    """Create another student user for testing."""
    return User.objects.create_user(
        email='student2@test.com',
        username='student2',
        password='TestPass123!',
        user_type='student',
        university_name='Test University'
    )


@pytest.fixture
def provider_user(db):
    """Create a provider user for testing."""
    return User.objects.create_user(
        email='provider@test.com',
        username='provider',
        password='TestPass123!',
        user_type='provider',
        is_verified=True,
        university_name='Test University'
    )


@pytest.fixture
def another_provider(db):
    """Create another provider user for testing."""
    return User.objects.create_user(
        email='provider2@test.com',
        username='provider2',
        password='TestPass123!',
        user_type='provider',
        is_verified=True,
        university_name='Another University'
    )


@pytest.fixture
def moving_service(db, provider_user):
    """Create a moving service for testing."""
    return MovingService.objects.create(
        provider=provider_user,
        service_name='Test Moving Service',
        description='Test description for moving service',
        base_price=Decimal('100.00'),
        availability_status=True
    )


@pytest.fixture
def another_service(db, another_provider):
    """Create another moving service for testing."""
    return MovingService.objects.create(
        provider=another_provider,
        service_name='Another Moving Service',
        description='Another test description',
        base_price=Decimal('150.00'),
        availability_status=True
    )


@pytest.fixture
def student_token(student_user):
    """Generate JWT token for student user."""
    refresh = RefreshToken.for_user(student_user)
    return str(refresh.access_token)


def create_booking(student, service, booking_date, status='pending'):
    """Helper function to create a booking."""
    return Booking.objects.create(
        student=student,
        provider=service.provider,
        service=service,
        booking_date=booking_date,
        pickup_location='123 Main St, Test City',
        dropoff_location='456 Oak Ave, Test City',
        status=status,
        total_price=service.base_price
    )


@pytest.mark.django_db
class TestCalendarDateRangeFiltering:
    """Test date range filtering for calendar endpoint."""
    
    def test_calendar_shows_bookings_within_date_range(
        self, api_client, student_user, moving_service
    ):
        """Test that calendar shows only bookings within specified date range."""
        # Create bookings at different dates
        base_date = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        
        # Booking 1: Within range (day 2)
        booking1 = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=2)
        )
        
        # Booking 2: Within range (day 5)
        booking2 = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=5)
        )
        
        # Booking 3: Outside range (day 10)
        booking3 = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=10)
        )
        
        # Request calendar for days 1-7
        start_date = (base_date + timedelta(days=1)).date()
        end_date = (base_date + timedelta(days=7)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'days' in response.data
        
        # Collect all booking IDs from response
        booking_ids = []
        for day in response.data['days']:
            for booking in day['bookings']:
                booking_ids.append(booking['id'])
        
        # Should include bookings 1 and 2, but not 3
        assert booking1.id in booking_ids
        assert booking2.id in booking_ids
        assert booking3.id not in booking_ids
    
    def test_calendar_excludes_bookings_outside_date_range(
        self, api_client, student_user, moving_service
    ):
        """Test that calendar excludes bookings outside the specified date range."""
        base_date = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        
        # Booking before range
        create_booking(
            student_user, moving_service,
            base_date - timedelta(days=1)
        )
        
        # Booking after range
        create_booking(
            student_user, moving_service,
            base_date + timedelta(days=10)
        )
        
        # Request calendar for days 1-7
        start_date = (base_date + timedelta(days=1)).date()
        end_date = (base_date + timedelta(days=7)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Count total bookings in response
        total_bookings = sum(len(day['bookings']) for day in response.data['days'])
        assert total_bookings == 0
    
    def test_calendar_handles_single_day_range(
        self, api_client, student_user, moving_service
    ):
        """Test that calendar works for single day date range."""
        base_date = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        target_date = base_date + timedelta(days=2)
        
        # Create booking on target date
        booking = create_booking(student_user, moving_service, target_date)
        
        # Request calendar for single day
        date_str = target_date.date()
        url = f'/api/bookings/calendar/?start_date={date_str}&end_date={date_str}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['days']) == 1
        assert response.data['days'][0]['bookings'][0]['id'] == booking.id
    
    def test_calendar_handles_month_boundaries(
        self, api_client, student_user, moving_service
    ):
        """Test that calendar correctly handles month boundaries."""
        # Create booking at end of month and beginning of next month
        base_date = timezone.now().replace(day=28, hour=10, minute=0, second=0, microsecond=0)
        
        booking1 = create_booking(
            student_user, moving_service,
            base_date
        )
        
        booking2 = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=5)  # Will cross into next month
        )
        
        # Request calendar spanning month boundary
        start_date = base_date.date()
        end_date = (base_date + timedelta(days=7)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Collect all booking IDs
        booking_ids = []
        for day in response.data['days']:
            for booking in day['bookings']:
                booking_ids.append(booking['id'])
        
        assert booking1.id in booking_ids
        assert booking2.id in booking_ids
    
    def test_calendar_requires_start_date_parameter(self, api_client):
        """Test that calendar returns error when start_date is missing."""
        end_date = timezone.now().date()
        url = f'/api/bookings/calendar/?end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'start_date' in str(response.data).lower()
    
    def test_calendar_requires_end_date_parameter(self, api_client):
        """Test that calendar returns error when end_date is missing."""
        start_date = timezone.now().date()
        url = f'/api/bookings/calendar/?start_date={start_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'end_date' in str(response.data).lower()
    
    def test_calendar_rejects_invalid_date_format(self, api_client):
        """Test that calendar returns error for invalid date format."""
        url = '/api/bookings/calendar/?start_date=invalid&end_date=2025-12-31'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_calendar_rejects_end_date_before_start_date(self, api_client):
        """Test that calendar returns error when end_date is before start_date."""
        start_date = timezone.now().date()
        end_date = start_date - timedelta(days=7)
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'end_date' in str(response.data).lower() or 'start_date' in str(response.data).lower()


@pytest.mark.django_db
class TestCalendarProviderFiltering:
    """Test provider filtering for calendar endpoint."""
    
    def test_calendar_filters_by_provider(
        self, api_client, student_user, another_student,
        provider_user, another_provider, moving_service, another_service
    ):
        """Test that calendar filters bookings by specific provider."""
        base_date = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        
        # Create bookings for different providers
        booking1 = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=2)
        )
        
        booking2 = create_booking(
            another_student, another_service,
            base_date + timedelta(days=3)
        )
        
        # Request calendar filtered by first provider
        start_date = (base_date + timedelta(days=1)).date()
        end_date = (base_date + timedelta(days=7)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}&provider_id={provider_user.id}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Collect all booking IDs
        booking_ids = []
        for day in response.data['days']:
            for booking in day['bookings']:
                booking_ids.append(booking['id'])
        
        # Should only include booking1 (provider_user's booking)
        assert booking1.id in booking_ids
        assert booking2.id not in booking_ids
    
    def test_calendar_without_provider_filter_shows_all(
        self, api_client, student_user, another_student,
        provider_user, another_provider, moving_service, another_service
    ):
        """Test that calendar without provider filter shows all bookings."""
        base_date = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        
        # Create bookings for different providers
        booking1 = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=2)
        )
        
        booking2 = create_booking(
            another_student, another_service,
            base_date + timedelta(days=3)
        )
        
        # Request calendar without provider filter
        start_date = (base_date + timedelta(days=1)).date()
        end_date = (base_date + timedelta(days=7)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Collect all booking IDs
        booking_ids = []
        for day in response.data['days']:
            for booking in day['bookings']:
                booking_ids.append(booking['id'])
        
        # Should include both bookings
        assert booking1.id in booking_ids
        assert booking2.id in booking_ids
    
    def test_calendar_returns_400_for_nonexistent_provider(self, api_client):
        """Test that calendar returns 400 for non-existent provider."""
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=7)
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}&provider_id=99999'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'provider' in str(response.data).lower()


@pytest.mark.django_db
class TestCalendarServiceFiltering:
    """Test service filtering for calendar endpoint."""
    
    def test_calendar_filters_by_service(
        self, api_client, student_user, another_student,
        moving_service, another_service
    ):
        """Test that calendar filters bookings by specific service."""
        base_date = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        
        # Create bookings for different services
        booking1 = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=2)
        )
        
        booking2 = create_booking(
            another_student, another_service,
            base_date + timedelta(days=3)
        )
        
        # Request calendar filtered by first service
        start_date = (base_date + timedelta(days=1)).date()
        end_date = (base_date + timedelta(days=7)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}&service_id={moving_service.id}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Collect all booking IDs
        booking_ids = []
        for day in response.data['days']:
            for booking in day['bookings']:
                booking_ids.append(booking['id'])
        
        # Should only include booking1
        assert booking1.id in booking_ids
        assert booking2.id not in booking_ids


@pytest.mark.django_db
class TestCalendarStatusFiltering:
    """Test status filtering for calendar endpoint."""
    
    def test_calendar_filters_by_status(
        self, api_client, student_user, moving_service
    ):
        """Test that calendar filters bookings by status."""
        base_date = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        
        # Create bookings with different statuses
        booking_pending = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=2),
            status='pending'
        )
        
        booking_confirmed = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=3),
            status='confirmed'
        )
        
        booking_completed = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=4),
            status='completed'
        )
        
        booking_cancelled = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=5),
            status='cancelled'
        )
        
        # Request calendar filtered by confirmed status only
        start_date = (base_date + timedelta(days=1)).date()
        end_date = (base_date + timedelta(days=7)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}&status=confirmed'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Collect all booking IDs
        booking_ids = []
        for day in response.data['days']:
            for booking in day['bookings']:
                booking_ids.append(booking['id'])
        
        # Should only include confirmed booking
        assert booking_confirmed.id in booking_ids
        assert booking_pending.id not in booking_ids
        assert booking_completed.id not in booking_ids
        assert booking_cancelled.id not in booking_ids
    
    def test_calendar_supports_multiple_status_values(
        self, api_client, student_user, moving_service
    ):
        """Test that calendar supports filtering by multiple status values."""
        base_date = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        
        # Create bookings with different statuses
        booking_pending = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=2),
            status='pending'
        )
        
        booking_confirmed = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=3),
            status='confirmed'
        )
        
        booking_completed = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=4),
            status='completed'
        )
        
        # Request calendar filtered by pending and confirmed
        start_date = (base_date + timedelta(days=1)).date()
        end_date = (base_date + timedelta(days=7)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}&status=pending,confirmed'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Collect all booking IDs
        booking_ids = []
        for day in response.data['days']:
            for booking in day['bookings']:
                booking_ids.append(booking['id'])
        
        # Should include pending and confirmed, but not completed
        assert booking_pending.id in booking_ids
        assert booking_confirmed.id in booking_ids
        assert booking_completed.id not in booking_ids
    
    def test_calendar_defaults_to_active_bookings(
        self, api_client, student_user, moving_service
    ):
        """Test that calendar defaults to showing active bookings (pending, confirmed)."""
        base_date = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        
        # Create bookings with different statuses
        booking_pending = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=2),
            status='pending'
        )
        
        booking_confirmed = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=3),
            status='confirmed'
        )
        
        booking_completed = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=4),
            status='completed'
        )
        
        booking_cancelled = create_booking(
            student_user, moving_service,
            base_date + timedelta(days=5),
            status='cancelled'
        )
        
        # Request calendar without status filter
        start_date = (base_date + timedelta(days=1)).date()
        end_date = (base_date + timedelta(days=7)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Collect all booking IDs
        booking_ids = []
        for day in response.data['days']:
            for booking in day['bookings']:
                booking_ids.append(booking['id'])
        
        # Should include pending and confirmed by default
        assert booking_pending.id in booking_ids
        assert booking_confirmed.id in booking_ids
        # Should NOT include completed or cancelled by default
        assert booking_completed.id not in booking_ids
        assert booking_cancelled.id not in booking_ids


@pytest.mark.django_db
class TestCalendarDataStructure:
    """Test calendar data structure and organization."""
    
    def test_calendar_organizes_bookings_by_date(
        self, api_client, student_user, moving_service
    ):
        """Test that calendar organizes bookings by date in chronological order."""
        base_date = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        
        # Create bookings on different dates
        create_booking(student_user, moving_service, base_date + timedelta(days=5))
        create_booking(student_user, moving_service, base_date + timedelta(days=2))
        create_booking(student_user, moving_service, base_date + timedelta(days=4))
        
        start_date = (base_date + timedelta(days=1)).date()
        end_date = (base_date + timedelta(days=7)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'days' in response.data
        
        # Verify days are in chronological order
        dates = [day['date'] for day in response.data['days']]
        assert dates == sorted(dates)
    
    def test_calendar_includes_booking_details(
        self, api_client, student_user, moving_service
    ):
        """Test that each booking includes complete details."""
        base_date = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        booking = create_booking(student_user, moving_service, base_date + timedelta(days=2))
        
        start_date = (base_date + timedelta(days=1)).date()
        end_date = (base_date + timedelta(days=7)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Find the booking in response
        booking_data = None
        for day in response.data['days']:
            for b in day['bookings']:
                if b['id'] == booking.id:
                    booking_data = b
                    break
        
        assert booking_data is not None
        assert 'id' in booking_data
        assert 'service_name' in booking_data
        assert 'service_id' in booking_data
        assert 'student_email' in booking_data
        assert 'provider_email' in booking_data
        assert 'booking_date' in booking_data
        assert 'status' in booking_data
        assert 'total_price' in booking_data
    
    def test_calendar_shows_available_slots(
        self, api_client, student_user, moving_service
    ):
        """Test that calendar shows available time slots."""
        base_date = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        
        # Create one booking
        create_booking(student_user, moving_service, base_date + timedelta(days=2, hours=10))
        
        start_date = (base_date + timedelta(days=1)).date()
        end_date = (base_date + timedelta(days=7)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check that days have available_slots field
        for day in response.data['days']:
            assert 'available_slots' in day
            assert isinstance(day['available_slots'], list)
    
    def test_calendar_marks_fully_booked_days(
        self, api_client, student_user, moving_service
    ):
        """Test that calendar marks fully booked days."""
        base_date = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        
        start_date = (base_date + timedelta(days=1)).date()
        end_date = (base_date + timedelta(days=7)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check that days have is_fully_booked field
        for day in response.data['days']:
            assert 'is_fully_booked' in day
            assert isinstance(day['is_fully_booked'], bool)
    
    def test_calendar_shows_empty_days_correctly(
        self, api_client, student_user, moving_service
    ):
        """Test that calendar displays days with no bookings correctly."""
        base_date = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        
        # Don't create any bookings
        start_date = (base_date + timedelta(days=1)).date()
        end_date = (base_date + timedelta(days=7)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'days' in response.data
        
        # All days should have empty bookings list
        for day in response.data['days']:
            assert len(day['bookings']) == 0
            assert day['is_fully_booked'] is False


@pytest.mark.django_db
class TestCalendarEdgeCases:
    """Test edge cases for calendar endpoint."""
    
    def test_calendar_handles_past_dates(
        self, api_client, student_user, moving_service
    ):
        """Test that calendar handles past dates correctly."""
        past_date = timezone.now() - timedelta(days=30)
        
        # Create booking in the past
        create_booking(student_user, moving_service, past_date)
        
        start_date = (past_date - timedelta(days=1)).date()
        end_date = (past_date + timedelta(days=1)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_calendar_handles_far_future_dates(self, api_client):
        """Test that calendar handles far future dates."""
        future_date = timezone.now() + timedelta(days=365)
        
        start_date = future_date.date()
        end_date = (future_date + timedelta(days=7)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_calendar_limits_date_range_to_90_days(self, api_client):
        """Test that calendar limits date range to prevent performance issues."""
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=91)  # Exceeds 90-day limit
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'date range' in str(response.data).lower() or '90' in str(response.data)
    
    def test_calendar_returns_empty_when_no_bookings(self, api_client):
        """Test that calendar returns empty results when no bookings exist."""
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=7)
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'days' in response.data


@pytest.mark.django_db
class TestCalendarAuthentication:
    """Test authentication requirements for calendar endpoint."""
    
    def test_unauthenticated_users_can_access_calendar(self, api_client):
        """Test that unauthenticated users can access calendar (public access)."""
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=7)
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        
        # No authentication credentials
        response = api_client.get(url)
        
        # Should allow access (public endpoint)
        assert response.status_code == status.HTTP_200_OK
    
    def test_authenticated_users_can_access_calendar(
        self, api_client, student_token
    ):
        """Test that authenticated users can access calendar."""
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=7)
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {student_token}')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestCalendarQueryOptimization:
    """Test query optimization for calendar endpoint."""
    
    def test_calendar_uses_select_related(
        self, api_client, student_user, moving_service, django_assert_num_queries
    ):
        """Test that calendar uses select_related to minimize queries."""
        base_date = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        
        # Create multiple bookings
        for i in range(5):
            create_booking(
                student_user, moving_service,
                base_date + timedelta(days=i+1)
            )
        
        start_date = base_date.date()
        end_date = (base_date + timedelta(days=7)).date()
        
        url = f'/api/bookings/calendar/?start_date={start_date}&end_date={end_date}'
        
        # Query count should be minimal (not N+1)
        # Expected: 1 query for bookings with select_related
        with django_assert_num_queries(1):
            response = api_client.get(url)
            assert response.status_code == status.HTTP_200_OK
