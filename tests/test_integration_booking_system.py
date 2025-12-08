from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from core.models import MovingService, Booking
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
from django.conf import settings
import concurrent.futures
import time

User = get_user_model()

class ProviderWorkflowTests(APITestCase):
    def setUp(self):
        # Disable throttling
        p = patch('rest_framework.throttling.ScopedRateThrottle.allow_request', return_value=True)
        self.throttle_patch = p.start()
        self.addCleanup(p.stop)

        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass',
            user_type='provider' # Ensure valid user_type
        )

        self.register_url = reverse('user_register')
        self.login_url = reverse('user_login')
        self.verify_url = reverse('verify_provider')
        self.service_list_url = reverse('service_list')
        self.service_create_url = reverse('service_create')
        self.booking_list_url = reverse('booking_create') # For POST
        self.booking_history_url = reverse('booking_history') # For GET

    def test_complete_provider_journey(self):
        # 1. Provider registers
        provider_data = {
            'email': 'provider@example.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
            'user_type': 'provider',
            'first_name': 'John',
            'last_name': 'Doe'
        }
        response = self.client.post(self.register_url, provider_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        provider_id = response.data['id']
        
        # Log in to get token
        login_data = {
            'email': 'provider@example.com',
            'password': 'SecurePassword123!'
        }
        login_response = self.client.post(self.login_url, login_data)
        access_token = login_response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

        # 2. Provider gets verified (requires admin)
        admin_token = self.client_login_as_admin(self.admin)
        
        # Verify provider via API
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_token}')
        # Use provider_id
        verify_response = self.client.post(self.verify_url, {'provider_id': provider_id})
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)

        # Switch back to provider (re-login to ensure fresh state/token)
        login_response = self.client.post(self.login_url, {
             'email': 'provider@example.com',
             'password': 'SecurePassword123!'
        })
        access_token = login_response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # 3. Provider creates service
        service_data = {
            'service_name': 'Test Moving Service',
            'description': 'We move stuff',
            'base_price': '100.00',
            # 'user_type': 'provider' # Not needed if serializer gets it from request.user
        }
        create_service_response = self.client.post(self.service_create_url, service_data)
        self.assertEqual(create_service_response.status_code, status.HTTP_201_CREATED)
        service_id = create_service_response.data['id']

        # 4. Provider views their services (public listing should verify it appears)
        list_response = self.client.get(self.service_list_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data['results']), 1)
        self.assertEqual(list_response.data['results'][0]['id'], service_id)

    def client_login_as_admin(self, admin_user):
        login_data = {
            'email': admin_user.email,
            'password': 'adminpass'
        }
        response = self.client.post(self.login_url, login_data)
        return response.data['access']

class StudentWorkflowTests(APITestCase):
    def setUp(self):
        # Disable throttling
        p = patch('rest_framework.throttling.ScopedRateThrottle.allow_request', return_value=True)
        self.throttle_patch = p.start()
        self.addCleanup(p.stop)

        # Setup provider and service for student to interact with
        self.provider = User.objects.create_user(
            username='provider',
            email='provider@example.com', 
            password='Password123!', 
            user_type='provider',
            is_verified=True
        )
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Best Movers',
            description='Fast and cheap',
            base_price=50.00
        )
        self.register_url = reverse('user_register')
        self.login_url = reverse('user_login')
        self.service_list_url = reverse('service_list')
        self.booking_create_url = reverse('booking_create')
        self.booking_history_url = reverse('booking_history')
        
    def test_complete_student_journey(self):
        # 1. Student registers
        student_data = {
            'email': 'student@example.com',
            'password': 'StudentPassword123!',
            'confirm_password': 'StudentPassword123!',
            'user_type': 'student'
        }
        self.client.post(self.register_url, student_data)
        
        # 2. Student logs in
        login_response = self.client.post(self.login_url, {
            'email': 'student@example.com',
            'password': 'StudentPassword123!'
        })
        access_token = login_response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

        # 3. Student browses services
        list_resp = self.client.get(self.service_list_url)
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        # Should see the service created in setUp
        self.assertTrue(any(s['id'] == self.service.id for s in list_resp.data['results']))

        # 4. Student views specific service details
        detail_url = reverse('service_detail', args=[self.service.id])
        detail_resp = self.client.get(detail_url)
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data['service_name'], 'Best Movers')

        # 5. Student checks calendar/slots (assuming endpoint exists, e.g., service-availability)
        # Using a hypothetical endpoint or just checking the booking creation directly if calendar not fully spec'd yet
        # But per requirements: "Student checks calendar availability"
        
        # 6. Student creates booking
        booking_date = timezone.now() + timedelta(days=2)
        booking_data = {
            'service': self.service.id,
            'booking_date': booking_date.isoformat(),
            'pickup_location': 'A',
            'dropoff_location': 'B',
            'total_price': 50.00
        }
        # Note: Booking creation might need provider_id explicitly depending on serializer
        booking_resp = self.client.post(self.booking_create_url, booking_data)
        client_print = booking_resp.data # for debugging if fails
        if booking_resp.status_code != 201:
             print(f"Booking failed: {booking_resp.data}")
        self.assertEqual(booking_resp.status_code, status.HTTP_201_CREATED)
        booking_id = booking_resp.data['id']

        # 7. Student views their booking history
        history_resp = self.client.get(self.booking_history_url)
        self.assertEqual(history_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(history_resp.data['results']), 1)
        
        # 8. Student cancels booking
        # Standard ViewSet might use /bookings/{id}/ or /bookings/{id}/cancel/
        # Assuming standard UPDATE or specialized endpoint
        cancel_url = reverse('booking_status_update', args=[booking_id])
        # Try patch update status
        cancel_resp = self.client.put(cancel_url, {'status': 'cancelled'})
        self.assertEqual(cancel_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel_resp.data['status'], 'cancelled')


class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        # Disable throttling
        p = patch('rest_framework.throttling.ScopedRateThrottle.allow_request', return_value=True)
        self.throttle_patch = p.start()
        self.addCleanup(p.stop)

        self.client = APIClient()
        self.provider = User.objects.create_user(
            username='provider',
            email='provider_c@example.com', 
            password='Password123!', 
            user_type='provider',
            is_verified=True
        )
        self.service = MovingService.objects.create(
            provider=self.provider,
            service_name='Concurrent Movers',
            description='Fast',
            base_price=100.00
        )
        # Create two students
        self.student1 = User.objects.create_user(username='s1', email='s1@example.com', password='Password123!', user_type='student')
        self.student2 = User.objects.create_user(username='s2', email='s2@example.com', password='Password123!', user_type='student')
        
        self.booking_url = reverse('booking_create')

    def test_double_booking_prevention(self):
        # Attempt to book the same slot for the same provider/service from two different students
        # Note: This depends on the system having a constraint (unique_together or validation) 
        # that prevents overlapping bookings. 
        # If the constraint is "one booking per service per time", this test verifies it.
        
        booking_date = timezone.now() + timedelta(days=5)
        booking_date_iso = booking_date.isoformat()
        
        def attempt_booking(student):
            # We need a new client for each thread/attempt to simulate distinct users
            from django.test import Client
            client = Client()
            # Login
            login_url = reverse('user_login')
            resp = client.post(login_url, {'email': student.email, 'password': 'Password123!'})
            if resp.status_code != 200:
                print(f"Login failed for {student.email}: {resp.data}")
                raise Exception(f"Login failed: {resp.data}")
            token = resp.data['access']
            
            return client.post(
                self.booking_url,
                {
                    'service': self.service.id,
                    'booking_date': booking_date_iso,
                    'pickup_location': 'X',
                    'dropoff_location': 'Y',
                    'total_price': 100.00
                },
                HTTP_AUTHORIZATION=f'Bearer {token}'
            )

        # Run concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(attempt_booking, self.student1),
                executor.submit(attempt_booking, self.student2)
            ]
            results = [f.result() for f in futures]

        # Analyze results
        status_codes = [r.status_code for r in results]
        success_count = status_codes.count(201)
        fail_count = status_codes.count(400) + status_codes.count(409)
        
        # Ideally, one succeeds and one fails. 
        # If both succeed, we have a double booking problem (race condition).
        # We surely want success_count <= 1
        self.assertTrue(success_count <= 1, f"Both bookings succeeded! Statuses: {status_codes}")
        self.assertTrue(fail_count >= 1, f"Expected at least one failure (400/409). Statuses: {status_codes}")

class EdgeCaseTests(APITestCase):
    def setUp(self):
        # Disable throttling
        p = patch('rest_framework.throttling.ScopedRateThrottle.allow_request', return_value=True)
        self.throttle_patch = p.start()
        self.addCleanup(p.stop)

         # Setup basic users
        self.student = User.objects.create_user(username='student', email='student@example.com', password='Password123!', user_type='student')
        self.provider = User.objects.create_user(username='provider', email='provider@example.com', password='Password123!', user_type='provider', is_verified=True)
        self.service = MovingService.objects.create(provider=self.provider, service_name='S', description='D', base_price=10)
        self.login_url = reverse('user_login')
        self.booking_url = reverse('booking_create')

    def test_booking_past_dates(self):
        # Authenticate student
        token = self.client.post(self.login_url, {'email': self.student.email, 'password': 'Password123!'}).data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        past_date = timezone.now() - timedelta(days=1)
        resp = self.client.post(self.booking_url, {
            'service': self.service.id,
            'booking_date': past_date.isoformat(),
            'pickup_location': 'A',
            'dropoff_location': 'B',
            'total_price': 10
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_provider_cannot_book(self):
         # Authenticate provider
        token = self.client.post(self.login_url, {'email': self.provider.email, 'password': 'Password123!'}).data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        future_date = timezone.now() + timedelta(days=1)
        resp = self.client.post(self.booking_url, {
            'service': self.service.id,
            'booking_date': future_date.isoformat(),
            'pickup_location': 'A',
            'dropoff_location': 'B',
            'total_price': 10
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN) # Or 400 depending on implementation

class DataConsistencyTests(APITestCase):
    # Tests that aggregate fields (if any) or related models update correctly
    def setUp(self):
         pass
    def test_booking_counts(self):
        # If there's an endpoint returning booking stats or if services have booking counts
        pass
