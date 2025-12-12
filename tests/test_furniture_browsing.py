"""
Comprehensive test suite for Furniture Browsing Endpoint.

This test suite follows Test-Driven Development (TDD) principles.
Tests are written FIRST and designed to FAIL initially.
Implementation will be created to make these tests pass.

CRITICAL: These tests must NEVER be modified to make them pass.
Only the implementation code should be changed.

Test Coverage:
- Unauthenticated browsing access
- Filtering by category, condition, price range, seller, university
- Filtering by sold status (default excludes sold items)
- Search functionality (title and description)
- Sorting options (price, date, condition)
- Pagination (page size, total count, next/previous links)
- Query optimization (no N+1 problems)
- Edge cases (empty results, large datasets, invalid filters)
"""

from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from core.models import FurnitureImage, FurnitureItem

User = get_user_model()


# ============================================================================
# Helper Functions
# ============================================================================

def create_test_user(email, user_type='student', university_name='Test University', **kwargs):
    """Create a test user with given parameters."""
    return User.objects.create_user(
        username=email.split('@')[0],
        email=email,
        password='testpass123',
        user_type=user_type,
        university_name=university_name,
        **kwargs
    )


def create_test_image(filename='test.jpg', size=(100, 100), format='JPEG'):
    """Create a test image file."""
    file = BytesIO()
    image = Image.new('RGB', size, color='red')
    image.save(file, format)
    file.seek(0)
    return SimpleUploadedFile(
        filename,
        file.read(),
        content_type=f'image/{format.lower()}'
    )


def create_furniture_item(seller, title, price, category='furniture', condition='good', is_sold=False, **kwargs):
    """Create a furniture item with an image."""
    item = FurnitureItem.objects.create(
        seller=seller,
        title=title,
        description=kwargs.get('description', f'Description for {title}'),
        price=price,
        category=category,
        condition=condition,
        is_sold=is_sold
    )
    
    # Add at least one image
    FurnitureImage.objects.create(
        furniture_item=item,
        image=create_test_image(f'{title.replace(" ", "_")}.jpg'),
        order=0
    )
    
    return item


# ============================================================================
# Furniture Browsing Tests
# ============================================================================

class FurnitureBrowsingBasicTests(TestCase):
    """Test suite for basic furniture browsing functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.url = '/api/furniture/'
        
        # Create test users
        self.seller1 = create_test_user('seller1@test.com', university_name='University A')
        self.seller2 = create_test_user('seller2@test.com', university_name='University B')
        
        # Create test furniture items
        self.item1 = create_furniture_item(
            self.seller1, 'Comfortable Sofa', Decimal('150.00'),
            category='furniture', condition='good'
        )
        self.item2 = create_furniture_item(
            self.seller2, 'Study Desk', Decimal('75.00'),
            category='furniture', condition='like_new'
        )
        self.item3 = create_furniture_item(
            self.seller1, 'Office Chair', Decimal('50.00'),
            category='furniture', condition='fair', is_sold=True
        )
    
    def test_unauthenticated_users_can_browse_furniture(self):
        """Test that unauthenticated users can browse furniture listings."""
        # No authentication credentials
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_browsing_returns_all_unsold_furniture_by_default(self):
        """Test that browsing returns only unsold furniture by default."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # Only unsold items
        
        # Verify sold item is not included
        titles = [item['title'] for item in response.data['results']]
        self.assertIn('Comfortable Sofa', titles)
        self.assertIn('Study Desk', titles)
        self.assertNotIn('Office Chair', titles)
    
    def test_browsing_returns_correct_furniture_details(self):
        """Test that browsing returns all required furniture details."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item_data = response.data['results'][0]
        
        # Verify all required fields are present
        self.assertIn('id', item_data)
        self.assertIn('title', item_data)
        self.assertIn('description', item_data)
        self.assertIn('price', item_data)
        self.assertIn('condition', item_data)
        self.assertIn('category', item_data)
        self.assertIn('is_sold', item_data)
        self.assertIn('created_at', item_data)
        self.assertIn('seller', item_data)
        self.assertIn('primary_image', item_data)
        self.assertIn('listing_age', item_data)
    
    def test_browsing_returns_seller_information(self):
        """Test that browsing returns seller information correctly."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item_data = response.data['results'][0]
        
        # Verify seller information
        self.assertIn('seller', item_data)
        seller_data = item_data['seller']
        self.assertIn('id', seller_data)
        self.assertIn('email', seller_data)
        self.assertIn('university_name', seller_data)
    
    def test_browsing_returns_primary_image_url(self):
        """Test that browsing returns primary image URL."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item_data = response.data['results'][0]
        
        # Verify primary image is present and is a URL
        self.assertIn('primary_image', item_data)
        self.assertIsNotNone(item_data['primary_image'])
        self.assertTrue(item_data['primary_image'].startswith('http'))


class FurnitureFilteringTests(TestCase):
    """Test suite for furniture filtering functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.url = '/api/furniture/'
        
        # Create test users
        self.seller1 = create_test_user('seller1@test.com', university_name='University A')
        self.seller2 = create_test_user('seller2@test.com', university_name='University B')
        
        # Create diverse furniture items
        create_furniture_item(self.seller1, 'Wooden Desk', Decimal('100.00'), category='furniture', condition='good')
        create_furniture_item(self.seller1, 'Office Chair', Decimal('50.00'), category='furniture', condition='fair')
        create_furniture_item(self.seller2, 'Laptop', Decimal('500.00'), category='electronics', condition='like_new')
        create_furniture_item(self.seller2, 'Textbook', Decimal('30.00'), category='books', condition='good')
        create_furniture_item(self.seller1, 'Winter Jacket', Decimal('40.00'), category='clothing', condition='new')
        create_furniture_item(self.seller1, 'Sold Sofa', Decimal('200.00'), category='furniture', condition='good', is_sold=True)
    
    def test_filter_by_category_shows_only_matching_items(self):
        """Test filtering by category returns only items in that category."""
        response = self.client.get(self.url, {'category': 'furniture'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # 2 unsold furniture items
        
        for item in response.data['results']:
            self.assertEqual(item['category'], 'furniture')
    
    def test_filter_by_condition_shows_only_matching_items(self):
        """Test filtering by condition returns only items with that condition."""
        response = self.client.get(self.url, {'condition': 'good'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for item in response.data['results']:
            self.assertEqual(item['condition'], 'good')
    
    def test_filter_by_price_range_minimum_only(self):
        """Test filtering by minimum price only."""
        response = self.client.get(self.url, {'min_price': '100'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for item in response.data['results']:
            self.assertGreaterEqual(Decimal(item['price']), Decimal('100.00'))
    
    def test_filter_by_price_range_maximum_only(self):
        """Test filtering by maximum price only."""
        response = self.client.get(self.url, {'max_price': '50'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for item in response.data['results']:
            self.assertLessEqual(Decimal(item['price']), Decimal('50.00'))
    
    def test_filter_by_price_range_both_min_and_max(self):
        """Test filtering by both minimum and maximum price."""
        response = self.client.get(self.url, {'min_price': '40', 'max_price': '100'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for item in response.data['results']:
            price = Decimal(item['price'])
            self.assertGreaterEqual(price, Decimal('40.00'))
            self.assertLessEqual(price, Decimal('100.00'))
    
    def test_filter_by_seller_id(self):
        """Test filtering by seller ID."""
        response = self.client.get(self.url, {'seller': self.seller1.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for item in response.data['results']:
            self.assertEqual(item['seller']['id'], self.seller1.id)
    
    def test_filter_by_university(self):
        """Test filtering by university name."""
        response = self.client.get(self.url, {'university': 'University A'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for item in response.data['results']:
            self.assertEqual(item['seller']['university_name'], 'University A')
    
    def test_sold_items_excluded_by_default(self):
        """Test that sold items are excluded by default."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for item in response.data['results']:
            self.assertFalse(item['is_sold'])
    
    def test_include_sold_items_when_explicitly_requested(self):
        """Test that sold items are included when explicitly requested."""
        response = self.client.get(self.url, {'include_sold': 'true'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should include both sold and unsold items
        sold_items = [item for item in response.data['results'] if item['is_sold']]
        self.assertGreater(len(sold_items), 0)
    
    def test_multiple_filters_work_together(self):
        """Test that multiple filters can be applied together."""
        response = self.client.get(self.url, {
            'category': 'furniture',
            'condition': 'good',
            'min_price': '50'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for item in response.data['results']:
            self.assertEqual(item['category'], 'furniture')
            self.assertEqual(item['condition'], 'good')
            self.assertGreaterEqual(Decimal(item['price']), Decimal('50.00'))


class FurnitureSearchTests(TestCase):
    """Test suite for furniture search functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.url = '/api/furniture/'
        
        seller = create_test_user('seller@test.com')
        
        # Create items with searchable content
        create_furniture_item(
            seller, 'Comfortable Leather Sofa', Decimal('150.00'),
            description='A very comfortable 3-seater leather sofa in excellent condition.'
        )
        create_furniture_item(
            seller, 'Modern Study Desk', Decimal('75.00'),
            description='Perfect desk for studying with built-in storage.'
        )
        create_furniture_item(
            seller, 'Ergonomic Office Chair', Decimal('50.00'),
            description='Comfortable chair with lumbar support.'
        )
    
    def test_search_by_title_keywords(self):
        """Test searching by title keywords."""
        response = self.client.get(self.url, {'search': 'sofa'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertIn('Sofa', response.data['results'][0]['title'])
    
    def test_search_by_description_keywords(self):
        """Test searching by description keywords."""
        response = self.client.get(self.url, {'search': 'storage'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertIn('storage', response.data['results'][0]['description'].lower())
    
    def test_search_is_case_insensitive(self):
        """Test that search is case-insensitive."""
        response_lower = self.client.get(self.url, {'search': 'comfortable'})
        response_upper = self.client.get(self.url, {'search': 'COMFORTABLE'})
        response_mixed = self.client.get(self.url, {'search': 'CoMfOrTaBlE'})
        
        self.assertEqual(response_lower.status_code, status.HTTP_200_OK)
        self.assertEqual(response_upper.status_code, status.HTTP_200_OK)
        self.assertEqual(response_mixed.status_code, status.HTTP_200_OK)
        
        # All should return the same results
        self.assertEqual(len(response_lower.data['results']), len(response_upper.data['results']))
        self.assertEqual(len(response_lower.data['results']), len(response_mixed.data['results']))
    
    def test_search_partial_match_support(self):
        """Test that search supports partial matching."""
        response = self.client.get(self.url, {'search': 'comf'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should match both "Comfortable Leather Sofa" and "Ergonomic Office Chair" (comfortable in description)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_search_returns_empty_when_no_matches(self):
        """Test that search returns empty results when no matches found."""
        response = self.client.get(self.url, {'search': 'nonexistent'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)


class FurnitureSortingTests(TestCase):
    """Test suite for furniture sorting functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.url = '/api/furniture/'
        
        seller = create_test_user('seller@test.com')
        
        # Create items with different prices and conditions
        self.item1 = create_furniture_item(seller, 'Item A', Decimal('100.00'), condition='good')
        self.item2 = create_furniture_item(seller, 'Item B', Decimal('50.00'), condition='like_new')
        self.item3 = create_furniture_item(seller, 'Item C', Decimal('200.00'), condition='fair')
    
    def test_sort_by_price_ascending(self):
        """Test sorting by price in ascending order."""
        response = self.client.get(self.url, {'ordering': 'price'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prices = [Decimal(item['price']) for item in response.data['results']]
        self.assertEqual(prices, sorted(prices))
    
    def test_sort_by_price_descending(self):
        """Test sorting by price in descending order."""
        response = self.client.get(self.url, {'ordering': '-price'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prices = [Decimal(item['price']) for item in response.data['results']]
        self.assertEqual(prices, sorted(prices, reverse=True))
    
    def test_sort_by_date_newest_first(self):
        """Test sorting by creation date (newest first)."""
        response = self.client.get(self.url, {'ordering': '-created_at'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Most recently created should be first
        self.assertEqual(response.data['results'][0]['title'], 'Item C')
    
    def test_sort_by_date_oldest_first(self):
        """Test sorting by creation date (oldest first)."""
        response = self.client.get(self.url, {'ordering': 'created_at'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # First created should be first
        self.assertEqual(response.data['results'][0]['title'], 'Item A')
    
    def test_default_sort_is_newest_first(self):
        """Test that default sorting is newest first."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Most recently created should be first
        self.assertEqual(response.data['results'][0]['title'], 'Item C')


class FurniturePaginationTests(TestCase):
    """Test suite for furniture pagination functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.url = '/api/furniture/'
        
        seller = create_test_user('seller@test.com')
        
        # Create 25 items to test pagination (default page size is 20)
        for i in range(25):
            create_furniture_item(seller, f'Item {i}', Decimal('100.00'))
    
    def test_results_are_paginated(self):
        """Test that results are paginated."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
    
    def test_pagination_limits_results_per_page(self):
        """Test that pagination limits results to page size."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['results']), 20)
    
    def test_pagination_includes_total_count(self):
        """Test that pagination includes total count of items."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 25)
    
    def test_pagination_provides_next_page_link(self):
        """Test that pagination provides next page link when available."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['next'])
    
    def test_pagination_second_page_works(self):
        """Test that second page returns remaining items."""
        response = self.client.get(self.url, {'page': 2})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)  # Remaining 5 items
    
    def test_large_dataset_paginates_correctly(self):
        """Test that large datasets paginate correctly."""
        # Already have 25 items from setUp
        response_page1 = self.client.get(self.url, {'page': 1})
        response_page2 = self.client.get(self.url, {'page': 2})
        
        self.assertEqual(response_page1.status_code, status.HTTP_200_OK)
        self.assertEqual(response_page2.status_code, status.HTTP_200_OK)
        
        # Verify no duplicate items between pages
        page1_ids = {item['id'] for item in response_page1.data['results']}
        page2_ids = {item['id'] for item in response_page2.data['results']}
        self.assertEqual(len(page1_ids & page2_ids), 0)


class FurnitureQueryOptimizationTests(TestCase):
    """Test suite for query optimization (N+1 prevention)."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.url = '/api/furniture/'
        
        # Create multiple sellers and items
        for i in range(10):
            seller = create_test_user(f'seller{i}@test.com', university_name=f'University {i}')
            create_furniture_item(seller, f'Item {i}', Decimal('100.00'))
    
    def test_no_n_plus_1_queries_for_seller_information(self):
        """Test that seller information doesn't cause N+1 queries."""
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should use select_related for seller, so queries should be minimal
        # Expected: 1 for furniture items + seller (select_related), 1 for images (prefetch_related), 1 for count
        self.assertLessEqual(len(context.captured_queries), 5)
    
    def test_no_n_plus_1_queries_for_images(self):
        """Test that images don't cause N+1 queries."""
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Access all primary images
            for item in response.data['results']:
                _ = item['primary_image']
        
        # Should use prefetch_related for images
        self.assertLessEqual(len(context.captured_queries), 5)
    
    def test_query_optimization_with_large_dataset(self):
        """Test query optimization with larger dataset."""
        # Create more items
        seller = create_test_user('bulk_seller@test.com')
        for i in range(50):
            create_furniture_item(seller, f'Bulk Item {i}', Decimal('100.00'))
        
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Query count should remain constant regardless of dataset size
        self.assertLessEqual(len(context.captured_queries), 5)


class FurnitureEdgeCasesTests(TestCase):
    """Test suite for edge cases."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.url = '/api/furniture/'
    
    def test_empty_results_when_no_furniture_exists(self):
        """Test that empty results are returned when no furniture exists."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)
        self.assertEqual(response.data['count'], 0)
    
    def test_empty_results_when_all_furniture_is_sold(self):
        """Test that empty results are returned when all furniture is sold."""
        seller = create_test_user('seller@test.com')
        create_furniture_item(seller, 'Sold Item 1', Decimal('100.00'), is_sold=True)
        create_furniture_item(seller, 'Sold Item 2', Decimal('100.00'), is_sold=True)
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)
    
    def test_invalid_filter_values_return_empty_results(self):
        """Test that invalid filter values return empty results."""
        seller = create_test_user('seller@test.com')
        create_furniture_item(seller, 'Item', Decimal('100.00'))
        
        response = self.client.get(self.url, {'category': 'nonexistent_category'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)
    
    def test_invalid_page_number_returns_404(self):
        """Test that invalid page number returns 404."""
        seller = create_test_user('seller@test.com')
        create_furniture_item(seller, 'Item', Decimal('100.00'))
        
        response = self.client.get(self.url, {'page': 999})
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
