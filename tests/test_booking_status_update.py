"""
Comprehensive tests for booking status update endpoint.

Following Test-Driven Development (TDD) approach:
1. All tests are designed to fail initially
2. Implementation will be created to make tests pass
3. Tests will NOT be modified - only implementation code

Test Coverage:
- Valid status transitions
- Invalid status transitions (terminal states)
- Authorization rules (providers vs students)
- Business logic (completion date validation)
- Authentication requirements
- Edge cases (404, concurrent updates, validation)
"""

import threading
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import MovingService, Booking

User = get_user_model()


class BookingStatusUpdateTestCase(TestCase):
    """Test suite for booking status update endpoint."""
    
    def setUp(self):
        """Set up test fixtures for each test."""
        self.client = APIClient()
        
        # Create student user
        self.student_user = User.objects.create_user(
            username='student',
            email='student@example.com',
            password='testpass123',
            user_type='student'
        )
        
        # Create provider user
        self.provider_user = User.objects.create_user(
            username='provider',
            email='provider@example.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        
        # Create another student for cross-user tests
        self.other_student = User.objects.create_user(
            username='otherstudent',
            email='otherstudent@example.com',
            password='testpass123',
            user_type='student'
        )
        
        # Create another provider for cross-provider tests
        self.other_provider = User.objects.create_user(
            username='otherprovider',
            email='otherprovider@example.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        
        # Create moving service
        self.service = MovingService.objects.create(
            provider=self.provider_user,
            service_name='Test Moving Service',
            description='Test description',
            base_price=Decimal('100.00'),
            availability_status=True
        )
        
        # Create another service for other provider
        self.other_service = MovingService.objects.create(
            provider=self.other_provider,
            service_name='Other Moving Service',
            description='Other description',
            base_price=Decimal('150.00'),
            availability_status=True
        )
        
        # Generate JWT tokens
        self.student_token = str(RefreshToken.for_user(self.student_user).access_token)
        self.provider_token = str(RefreshToken.for_user(self.provider_user).access_token)
        self.other_student_token = str(RefreshToken.for_user(self.other_student).access_token)
        self.other_provider_token = str(RefreshToken.for_user(self.other_provider).access_token)
    
    def _create_booking(self, student, service, booking_date=None, status='pending'):
        """Helper method to create a booking."""
        if booking_date is None:
            booking_date = timezone.now() + timedelta(days=7)
        
        return Booking.objects.create(
            student=student,
            provider=service.provider,
            service=service,
            booking_date=booking_date,
            pickup_location='123 Pickup St',
            dropoff_location='456 Dropoff Ave',
            status=status,
            total_price=service.base_price
        )
    
    # ========================================================================
    # Valid Transition Tests
    # ========================================================================
    
    def test_provider_can_confirm_pending_booking(self):
        """Test that provider can confirm their pending booking."""
        booking = self._create_booking(self.student_user, self.service)
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'confirmed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'confirmed')
        
        # Verify database was updated
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'confirmed')
    
    def test_provider_can_complete_confirmed_booking(self):
        """Test that provider can complete confirmed booking after booking date."""
        # Create booking in the past
        past_date = timezone.now() - timedelta(hours=1)
        booking = self._create_booking(
            self.student_user, 
            self.service, 
            booking_date=past_date,
            status='confirmed'
        )
        
        url = f'/api/bookings/{booking.id}/status/'
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'completed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'completed')
    
    def test_student_can_cancel_pending_booking(self):
        """Test that student can cancel their pending booking."""
        booking = self._create_booking(self.student_user, self.service)
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token}')
        response = self.client.put(url, {'status': 'cancelled'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'cancelled')
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')
    
    def test_student_can_cancel_confirmed_booking(self):
        """Test that student can cancel their confirmed booking."""
        booking = self._create_booking(
            self.student_user, 
            self.service, 
            status='confirmed'
        )
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token}')
        response = self.client.put(url, {'status': 'cancelled'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'cancelled')
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')
    
    def test_provider_can_cancel_pending_booking(self):
        """Test that provider can cancel pending booking."""
        booking = self._create_booking(self.student_user, self.service)
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'cancelled'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'cancelled')
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')
    
    def test_provider_can_cancel_confirmed_booking(self):
        """Test that provider can cancel confirmed booking."""
        booking = self._create_booking(
            self.student_user, 
            self.service, 
            status='confirmed'
        )
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'cancelled'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'cancelled')
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')
    
    # ========================================================================
    # Invalid Transition Tests
    # ========================================================================
    
    def test_cannot_transition_completed_to_pending(self):
        """Test that completed bookings cannot transition to pending."""
        past_date = timezone.now() - timedelta(hours=1)
        booking = self._create_booking(
            self.student_user, 
            self.service, 
            booking_date=past_date,
            status='completed'
        )
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'pending'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data)
        self.assertIn('completed', str(response.data['status']).lower())
        
        # Verify status didn't change
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'completed')
    
    def test_cannot_transition_completed_to_confirmed(self):
        """Test that completed bookings cannot transition to confirmed."""
        past_date = timezone.now() - timedelta(hours=1)
        booking = self._create_booking(
            self.student_user, 
            self.service, 
            booking_date=past_date,
            status='completed'
        )
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'confirmed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data)
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'completed')
    
    def test_cannot_transition_completed_to_cancelled(self):
        """Test that completed bookings cannot transition to cancelled."""
        past_date = timezone.now() - timedelta(hours=1)
        booking = self._create_booking(
            self.student_user, 
            self.service, 
            booking_date=past_date,
            status='completed'
        )
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'cancelled'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data)
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'completed')
    
    def test_cannot_transition_cancelled_to_pending(self):
        """Test that cancelled bookings cannot transition to pending."""
        booking = self._create_booking(
            self.student_user, 
            self.service, 
            status='cancelled'
        )
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'pending'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data)
        self.assertIn('cancelled', str(response.data['status']).lower())
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')
    
    def test_cannot_transition_cancelled_to_confirmed(self):
        """Test that cancelled bookings cannot transition to confirmed."""
        booking = self._create_booking(
            self.student_user, 
            self.service, 
            status='cancelled'
        )
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'confirmed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data)
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')
    
    def test_cannot_transition_cancelled_to_completed(self):
        """Test that cancelled bookings cannot transition to completed."""
        booking = self._create_booking(
            self.student_user, 
            self.service, 
            status='cancelled'
        )
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'completed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data)
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')
    
    def test_cannot_transition_pending_to_completed(self):
        """Test that pending bookings cannot skip to completed (must confirm first)."""
        booking = self._create_booking(self.student_user, self.service)
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'completed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data)
        self.assertIn('confirm', str(response.data['status']).lower())
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'pending')
    
    # ========================================================================
    # Authorization Tests
    # ========================================================================
    
    def test_provider_can_confirm_own_booking(self):
        """Test that provider can confirm bookings for their service."""
        booking = self._create_booking(self.student_user, self.service)
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'confirmed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'confirmed')
    
    def test_provider_can_complete_own_booking(self):
        """Test that provider can complete bookings for their service."""
        past_date = timezone.now() - timedelta(hours=1)
        booking = self._create_booking(
            self.student_user, 
            self.service, 
            booking_date=past_date,
            status='confirmed'
        )
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'completed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')
    
    def test_student_cannot_confirm_booking(self):
        """Test that students cannot confirm bookings (403 Forbidden)."""
        booking = self._create_booking(self.student_user, self.service)
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token}')
        response = self.client.put(url, {'status': 'confirmed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify status didn't change
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'pending')
    
    def test_student_cannot_complete_booking(self):
        """Test that students cannot complete bookings (403 Forbidden)."""
        past_date = timezone.now() - timedelta(hours=1)
        booking = self._create_booking(
            self.student_user, 
            self.service, 
            booking_date=past_date,
            status='confirmed'
        )
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token}')
        response = self.client.put(url, {'status': 'completed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'confirmed')
    
    def test_provider_cannot_modify_other_provider_booking(self):
        """Test that providers cannot modify other providers' bookings (403)."""
        # Create booking with other provider's service
        booking = self._create_booking(self.student_user, self.other_service)
        url = f'/api/bookings/{booking.id}/status/'
        
        # Try to confirm with wrong provider
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'confirmed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'pending')
    
    def test_student_cannot_modify_other_student_booking(self):
        """Test that students cannot modify other students' bookings (403)."""
        # Create booking with other student
        booking = self._create_booking(self.other_student, self.service)
        url = f'/api/bookings/{booking.id}/status/'
        
        # Try to cancel with wrong student
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token}')
        response = self.client.put(url, {'status': 'cancelled'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'pending')
    
    # ========================================================================
    # Business Logic Tests
    # ========================================================================
    
    def test_cannot_complete_before_booking_date(self):
        """Test that bookings cannot be completed before the booking date."""
        # Create booking in the future
        future_date = timezone.now() + timedelta(days=1)
        booking = self._create_booking(
            self.student_user, 
            self.service, 
            booking_date=future_date,
            status='confirmed'
        )
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'completed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data)
        self.assertIn('date', str(response.data['status']).lower())
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'confirmed')
    
    def test_can_complete_on_booking_date(self):
        """Test that bookings can be completed on the booking date."""
        # Create booking at current time (within a few seconds)
        current_date = timezone.now()
        booking = self._create_booking(
            self.student_user, 
            self.service, 
            booking_date=current_date,
            status='confirmed'
        )
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'completed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')
    
    def test_can_complete_after_booking_date(self):
        """Test that bookings can be completed after the booking date."""
        past_date = timezone.now() - timedelta(days=1)
        booking = self._create_booking(
            self.student_user, 
            self.service, 
            booking_date=past_date,
            status='confirmed'
        )
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'completed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')
    
    # ========================================================================
    # Authentication Tests
    # ========================================================================
    
    def test_unauthenticated_request_returns_401(self):
        """Test that requests without authentication return 401."""
        booking = self._create_booking(self.student_user, self.service)
        url = f'/api/bookings/{booking.id}/status/'
        
        # No authentication
        response = self.client.put(url, {'status': 'confirmed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Verify status didn't change
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'pending')
    
    def test_invalid_token_returns_401(self):
        """Test that requests with invalid token return 401."""
        booking = self._create_booking(self.student_user, self.service)
        url = f'/api/bookings/{booking.id}/status/'
        
        # Invalid token
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid_token_here')
        response = self.client.put(url, {'status': 'confirmed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'pending')
    
    # ========================================================================
    # Edge Case Tests
    # ========================================================================
    
    def test_nonexistent_booking_returns_404(self):
        """Test that updating non-existent booking returns 404."""
        url = '/api/bookings/99999/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'confirmed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    
    def test_missing_status_field_returns_400(self):
        """Test that missing status field returns validation error."""
        booking = self._create_booking(self.student_user, self.service)
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data)
    
    def test_invalid_status_value_returns_400(self):
        """Test that invalid status value returns validation error."""
        booking = self._create_booking(self.student_user, self.service)
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'invalid_status'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data)
    
    def test_status_update_logs_timestamp(self):
        """Test that status updates modify the updated_at timestamp."""
        booking = self._create_booking(self.student_user, self.service)
        original_updated_at = booking.updated_at
        url = f'/api/bookings/{booking.id}/status/'
        
        # Wait a moment to ensure timestamp difference
        import time
        time.sleep(0.1)
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'confirmed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        booking.refresh_from_db()
        self.assertGreater(booking.updated_at, original_updated_at)
    
    # ========================================================================
    # Response Validation Tests
    # ========================================================================
    
    def test_successful_update_returns_complete_booking(self):
        """Test that successful update returns complete booking details."""
        booking = self._create_booking(self.student_user, self.service)
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'confirmed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify response structure
        self.assertIn('id', response.data)
        self.assertIn('status', response.data)
        self.assertIn('booking_date', response.data)
        self.assertIn('pickup_location', response.data)
        self.assertIn('dropoff_location', response.data)
        self.assertIn('total_price', response.data)
        self.assertIn('student', response.data)
        self.assertIn('provider', response.data)
        self.assertIn('service', response.data)
        
        # Verify correct values
        self.assertEqual(response.data['id'], booking.id)
        self.assertEqual(response.data['status'], 'confirmed')
    
    def test_response_includes_updated_timestamp(self):
        """Test that response includes the updated timestamp."""
        booking = self._create_booking(self.student_user, self.service)
        url = f'/api/bookings/{booking.id}/status/'
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.provider_token}')
        response = self.client.put(url, {'status': 'confirmed'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('updated_at', response.data)
        
        # Verify timestamp is recent (within last minute)
        from django.utils.dateparse import parse_datetime
        updated_at = parse_datetime(response.data['updated_at'])
        time_diff = timezone.now() - updated_at
        self.assertLess(time_diff.total_seconds(), 60)

class BookingStatusUpdateConcurrencyTests(TransactionTestCase):
    """Test suite for concurrent booking status updates."""
    
    def setUp(self):
        """Set up test fixtures for each test."""
        self.client = APIClient()
        
        # Create student user
        self.student_user = User.objects.create_user(
            username='student_conc',
            email='student_conc@example.com',
            password='testpass123',
            user_type='student'
        )
        
        # Create provider user
        self.provider_user = User.objects.create_user(
            username='provider_conc',
            email='provider_conc@example.com',
            password='testpass123',
            user_type='provider',
            is_verified=True
        )
        
        # Create moving service
        self.service = MovingService.objects.create(
            provider=self.provider_user,
            service_name='Test Moving Service Conc',
            description='Test description',
            base_price=Decimal('100.00'),
            availability_status=True
        )
        
        # Generate JWT tokens
        self.student_token = str(RefreshToken.for_user(self.student_user).access_token)
        self.provider_token = str(RefreshToken.for_user(self.provider_user).access_token)
    
    def _create_booking(self, student, service, booking_date=None, status='pending'):
        """Helper method to create a booking."""
        if booking_date is None:
            booking_date = timezone.now() + timedelta(days=7)
        
        return Booking.objects.create(
            student=student,
            provider=service.provider,
            service=service,
            booking_date=booking_date,
            pickup_location='123 Pickup St',
            dropoff_location='456 Dropoff Ave',
            status=status,
            total_price=service.base_price
        )

    def test_concurrent_status_updates(self):
        """Test that concurrent status updates are handled safely."""
        booking = self._create_booking(self.student_user, self.service)
        url = f'/api/bookings/{booking.id}/status/'
        
        results = []
        
        def update_status(token, new_status):
            """Helper function to update status in a thread."""
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            response = client.put(url, {'status': new_status}, format='json')
            results.append(response.status_code)
        
        # Create threads for concurrent updates
        thread1 = threading.Thread(
            target=update_status, 
            args=(self.provider_token, 'confirmed')
        )
        thread2 = threading.Thread(
            target=update_status, 
            args=(self.student_token, 'cancelled')
        )
        
        # Start both threads
        thread1.start()
        thread2.start()
        
        # Wait for completion
        thread1.join()
        thread2.join()
        
        # At least one should succeed
        self.assertIn(status.HTTP_200_OK, results)
        
        # Verify booking is in a valid state
        booking.refresh_from_db()
        self.assertIn(booking.status, ['confirmed', 'cancelled'])
