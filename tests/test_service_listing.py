"""
Comprehensive test suite for service listing endpoint.

Tests cover:
- Basic listing functionality
- Filtering (availability, price range, rating, university)
- Sorting (price, rating, date)
- Pagination
- Query optimization (N+1 prevention)
- Edge cases and error handling
- Public access (no authentication required)
"""

import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.db import connection
from django.test.utils import override_settings

from core.models import MovingService

User = get_user_model()


@pytest.mark.django_db
class ServiceListingTests(TestCase):
    """Test suite for service listing endpoint."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.url = reverse('service_list')
        
        # Create test providers with different universities
        self.provider1 = User.objects.create_user(
            username='provider1',
            email='provider1@test.com',
            password='TestPass123!',
            user_type='provider',
            university_name='Harvard University',
            is_verified=True
        )
        
        self.provider2 = User.objects.create_user(
            username='provider2',
            email='provider2@test.com',
            password='TestPass123!',
            user_type='provider',
            university_name='MIT',
            is_verified=False
        )
        
        self.provider3 = User.objects.create_user(
            username='provider3',
            email='provider3@test.com',
            password='TestPass123!',
            user_type='provider',
            university_name='Stanford University',
            is_verified=True
        )
        
        # Create test services with varying attributes
        self.service1 = MovingService.objects.create(
            provider=self.provider1,
            service_name='Budget Moving Service',
            description='Affordable moving for students',
            base_price=Decimal('50.00'),
            availability_status=True,
            rating_average=Decimal('4.50'),
            total_reviews=10
        )
        
        self.service2 = MovingService.objects.create(
            provider=self.provider1,
            service_name='Premium Moving Service',
            description='High-end moving with packing',
            base_price=Decimal('200.00'),
            availability_status=True,
            rating_average=Decimal('4.80'),
            total_reviews=25
        )
        
        self.service3 = MovingService.objects.create(
            provider=self.provider2,
            service_name='MIT Student Movers',
            description='Quick and efficient moving',
            base_price=Decimal('100.00'),
            availability_status=False,  # Not available
            rating_average=Decimal('3.50'),
            total_reviews=5
        )
        
        self.service4 = MovingService.objects.create(
            provider=self.provider3,
            service_name='Stanford Express Moving',
            description='Fast moving service',
            base_price=Decimal('150.00'),
            availability_status=True,
            rating_average=Decimal('4.20'),
            total_reviews=15
        )
        
        self.service5 = MovingService.objects.create(
            provider=self.provider3,
            service_name='Economy Moving',
            description='Low-cost moving option',
            base_price=Decimal('75.00'),
            availability_status=True,
            rating_average=Decimal('3.80'),
            total_reviews=8
        )
    
    # ========================================================================
    # Basic Functionality Tests
    # ========================================================================
    
    def test_listing_returns_all_services_no_filters(self):
        """Test that listing returns all services when no filters are applied."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 5)
    
    def test_listing_works_without_authentication(self):
        """Test that listing endpoint is publicly accessible."""
        # Ensure client is not authenticated
        self.client.force_authenticate(user=None)
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_empty_results_when_no_services_exist(self):
        """Test that endpoint returns empty results when no services exist."""
        # Delete all services
        MovingService.objects.all().delete()
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)
        self.assertEqual(response.data['count'], 0)
    
    def test_response_includes_service_details(self):
        """Test that response includes all required service details."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        service_data = response.data['results'][0]
        
        # Check service fields
        self.assertIn('id', service_data)
        self.assertIn('service_name', service_data)
        self.assertIn('description', service_data)
        self.assertIn('base_price', service_data)
        self.assertIn('availability_status', service_data)
        self.assertIn('rating_average', service_data)
        self.assertIn('total_reviews', service_data)
        self.assertIn('created_at', service_data)
        
        # Check provider fields
        self.assertIn('provider', service_data)
        provider_data = service_data['provider']
        self.assertIn('id', provider_data)
        self.assertIn('email', provider_data)
        self.assertIn('university_name', provider_data)
        self.assertIn('is_verified', provider_data)
    
    # ========================================================================
    # Filtering Tests
    # ========================================================================
    
    def test_availability_filter_shows_only_available_services(self):
        """Test filtering by availability status shows only available services."""
        response = self.client.get(self.url, {'available': 'true'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 4)
        
        # Verify all returned services are available
        for service in response.data['results']:
            self.assertTrue(service['availability_status'])
    
    def test_availability_filter_false_shows_unavailable_services(self):
        """Test filtering by availability=false shows only unavailable services."""
        response = self.client.get(self.url, {'available': 'false'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['service_name'], 'MIT Student Movers')
    
    def test_price_range_filter_minimum_price(self):
        """Test filtering by minimum price."""
        response = self.client.get(self.url, {'min_price': '100'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return services with price >= 100 (service2, service3, service4)
        self.assertEqual(len(response.data['results']), 3)
        
        for service in response.data['results']:
            self.assertGreaterEqual(Decimal(service['base_price']), Decimal('100.00'))
    
    def test_price_range_filter_maximum_price(self):
        """Test filtering by maximum price."""
        response = self.client.get(self.url, {'max_price': '100'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return services with price <= 100 (service1, service3, service5)
        self.assertEqual(len(response.data['results']), 3)
        
        for service in response.data['results']:
            self.assertLessEqual(Decimal(service['base_price']), Decimal('100.00'))
    
    def test_price_range_filter_both_min_and_max(self):
        """Test filtering with both minimum and maximum price."""
        response = self.client.get(self.url, {'min_price': '75', 'max_price': '150'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return services with 75 <= price <= 150 (service3, service4, service5)
        self.assertEqual(len(response.data['results']), 3)
        
        for service in response.data['results']:
            price = Decimal(service['base_price'])
            self.assertGreaterEqual(price, Decimal('75.00'))
            self.assertLessEqual(price, Decimal('150.00'))
    
    def test_rating_filter_excludes_low_rated_services(self):
        """Test filtering by minimum rating."""
        response = self.client.get(self.url, {'min_rating': '4.0'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return services with rating >= 4.0 (service1, service2, service4)
        self.assertEqual(len(response.data['results']), 3)
        
        for service in response.data['results']:
            self.assertGreaterEqual(Decimal(service['rating_average']), Decimal('4.00'))
    
    def test_university_filter_shows_only_specific_university(self):
        """Test filtering by provider university."""
        response = self.client.get(self.url, {'university': 'Harvard'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return services from Harvard provider (service1, service2)
        self.assertEqual(len(response.data['results']), 2)
        
        for service in response.data['results']:
            self.assertIn('Harvard', service['provider']['university_name'])
    
    def test_university_filter_case_insensitive(self):
        """Test that university filter is case-insensitive."""
        response = self.client.get(self.url, {'university': 'stanford'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return services from Stanford provider (service4, service5)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_multiple_filters_work_together(self):
        """Test that multiple filters can be applied simultaneously."""
        response = self.client.get(self.url, {
            'available': 'true',
            'min_price': '50',
            'max_price': '150',
            'min_rating': '4.0'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return service1 and service4
        self.assertEqual(len(response.data['results']), 2)
        
        for service in response.data['results']:
            self.assertTrue(service['availability_status'])
            price = Decimal(service['base_price'])
            self.assertGreaterEqual(price, Decimal('50.00'))
            self.assertLessEqual(price, Decimal('150.00'))
            self.assertGreaterEqual(Decimal(service['rating_average']), Decimal('4.00'))
    
    # ========================================================================
    # Sorting Tests
    # ========================================================================
    
    def test_sorting_by_price_ascending(self):
        """Test sorting by price in ascending order."""
        response = self.client.get(self.url, {'ordering': 'price'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        
        # Verify prices are in ascending order
        prices = [Decimal(s['base_price']) for s in results]
        self.assertEqual(prices, sorted(prices))
        
        # First should be cheapest (service1 - $50)
        self.assertEqual(results[0]['service_name'], 'Budget Moving Service')
    
    def test_sorting_by_price_descending(self):
        """Test sorting by price in descending order."""
        response = self.client.get(self.url, {'ordering': '-price'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        
        # Verify prices are in descending order
        prices = [Decimal(s['base_price']) for s in results]
        self.assertEqual(prices, sorted(prices, reverse=True))
        
        # First should be most expensive (service2 - $200)
        self.assertEqual(results[0]['service_name'], 'Premium Moving Service')
    
    def test_sorting_by_rating_highest_first(self):
        """Test sorting by rating with highest first."""
        response = self.client.get(self.url, {'ordering': '-rating'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        
        # Verify ratings are in descending order
        ratings = [Decimal(s['rating_average']) for s in results]
        self.assertEqual(ratings, sorted(ratings, reverse=True))
        
        # First should be highest rated (service2 - 4.80)
        self.assertEqual(results[0]['service_name'], 'Premium Moving Service')
    
    def test_sorting_by_creation_date_newest_first(self):
        """Test sorting by creation date with newest first."""
        response = self.client.get(self.url, {'ordering': '-date'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        
        # Verify dates are in descending order (newest first)
        # Since we created them in order, service5 should be first
        self.assertEqual(results[0]['service_name'], 'Economy Moving')
    
    def test_default_sorting_by_rating_then_price(self):
        """Test default sorting is by rating (desc) then price (asc)."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        
        # First should be highest rated (service2 - 4.80)
        self.assertEqual(results[0]['service_name'], 'Premium Moving Service')
        
        # Among same ratings, cheaper should come first
        # service1 (4.50) should come before service4 (4.20)
        service_names = [s['service_name'] for s in results]
        self.assertLess(
            service_names.index('Budget Moving Service'),
            service_names.index('Stanford Express Moving')
        )
    
    # ========================================================================
    # Pagination Tests
    # ========================================================================
    
    def test_pagination_limits_response_size(self):
        """Test that pagination limits the number of results returned."""
        response = self.client.get(self.url, {'page_size': '2'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        self.assertEqual(response.data['count'], 5)  # Total count
    
    def test_pagination_metadata_includes_count_next_previous(self):
        """Test that pagination metadata includes count, next, and previous."""
        response = self.client.get(self.url, {'page_size': '2', 'page': '1'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        self.assertIn('results', response.data)
        
        self.assertEqual(response.data['count'], 5)
        self.assertIsNotNone(response.data['next'])  # Has next page
        self.assertIsNone(response.data['previous'])  # First page
    
    def test_pagination_second_page(self):
        """Test accessing second page of results."""
        response = self.client.get(self.url, {'page_size': '2', 'page': '2'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        self.assertIsNotNone(response.data['previous'])  # Has previous page
    
    def test_custom_page_size_via_query_parameter(self):
        """Test that page size can be customized via query parameter."""
        response = self.client.get(self.url, {'page_size': '3'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)
    
    def test_default_page_size_is_20(self):
        """Test that default page size is 20 when not specified."""
        # Create 25 services to test pagination
        for i in range(20):
            MovingService.objects.create(
                provider=self.provider1,
                service_name=f'Service {i}',
                description='Test service',
                base_price=Decimal('100.00'),
                availability_status=True
            )
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 20)
        self.assertEqual(response.data['count'], 25)
    
    # ========================================================================
    # Performance Tests (N+1 Query Prevention)
    # ========================================================================
    
    def test_provider_information_included_without_n_plus_1_queries(self):
        """Test that provider information is loaded efficiently without N+1 queries."""
        # Reset queries
        connection.queries_log.clear()
        
        with self.assertNumQueries(2):  # 1 for count, 1 for services with provider (select_related optimization)
            response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify provider data is included
        for service in response.data['results']:
            self.assertIn('provider', service)
            self.assertIsNotNone(service['provider']['email'])
    
    def test_queryset_optimization_with_select_related(self):
        """Test that queryset uses select_related for provider."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify all services have provider data without additional queries
        for service in response.data['results']:
            self.assertIn('provider', service)
            self.assertIn('email', service['provider'])
            self.assertIn('university_name', service['provider'])
            self.assertIn('is_verified', service['provider'])
    
    # ========================================================================
    # Edge Cases and Error Handling
    # ========================================================================
    
    def test_filtering_with_impossible_criteria_returns_empty(self):
        """Test that impossible filter criteria (min_price > max_price) returns error or empty."""
        response = self.client.get(self.url, {'min_price': '200', 'max_price': '100'})
        
        # Should either return 400 error or empty results
        # We'll implement validation to return 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_filtering_with_no_matching_results(self):
        """Test filtering that results in no matches."""
        response = self.client.get(self.url, {'min_price': '1000'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)
        self.assertEqual(response.data['count'], 0)
    
    def test_invalid_query_parameters_handled_gracefully(self):
        """Test that invalid query parameters are handled gracefully."""
        response = self.client.get(self.url, {'min_price': 'invalid'})
        
        # Should return 400 error with helpful message
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_negative_price_filter_handled_gracefully(self):
        """Test that negative price values are handled appropriately."""
        response = self.client.get(self.url, {'min_price': '-50'})
        
        # Should return 400 error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_invalid_page_number_handled_gracefully(self):
        """Test that invalid page numbers are handled gracefully."""
        response = self.client.get(self.url, {'page': '999'})
        
        # Should return 404 or empty results
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_invalid_ordering_parameter_ignored(self):
        """Test that invalid ordering parameters are ignored or return error."""
        response = self.client.get(self.url, {'ordering': 'invalid_field'})
        
        # Should either ignore and use default, or return 400
        # We'll implement to return 400 for invalid fields
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    # ========================================================================
    # HTTP Method Tests
    # ========================================================================
    
    def test_only_get_method_allowed_for_listing(self):
        """Test that only GET method is allowed for listing endpoint."""
        # POST should work for creation (different functionality)
        # But PUT, PATCH, DELETE should not be allowed on list endpoint
        
        response = self.client.put(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        
        response = self.client.patch(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
