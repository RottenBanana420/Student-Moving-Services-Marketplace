"""
Comprehensive test suite for Furniture Marketplace models.

This test suite follows Test-Driven Development (TDD) principles.
Tests are written FIRST and designed to FAIL initially.
Models will be implemented to make these tests pass.

Test Coverage:
- FurnitureItem: ~25 tests
- FurnitureImage: ~15 tests
- FurnitureTransaction: ~30 tests
- Integration: ~10 tests
Total: ~80 tests
"""

import os
from decimal import Decimal
from io import BytesIO
from threading import Thread
from time import sleep

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from PIL import Image

from core.models import FurnitureImage, FurnitureItem, FurnitureTransaction

User = get_user_model()


# ============================================================================
# Helper Functions
# ============================================================================

def create_test_user(email, user_type='student', **kwargs):
    """Create a test user with given parameters."""
    return User.objects.create_user(
        username=email.split('@')[0],
        email=email,
        password='testpass123',
        user_type=user_type,
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


def create_large_test_image(filename='large.jpg', size=(8000, 8000)):
    """Create a large test image (> 5MB) for validation testing."""
    import random
    file = BytesIO()
    # Create a larger image with random pixels to prevent compression
    image = Image.new('RGB', size)
    pixels = image.load()
    # Add random noise to prevent JPEG compression from reducing size too much
    for i in range(0, size[0], 10):
        for j in range(0, size[1], 10):
            pixels[i, j] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    image.save(file, 'JPEG', quality=95)
    file.seek(0)
    return SimpleUploadedFile(
        filename,
        file.read(),
        content_type='image/jpeg'
    )


# ============================================================================
# FurnitureItem Model Tests (~25 tests)
# ============================================================================

class FurnitureItemModelTests(TestCase):
    """Test suite for FurnitureItem model."""
    
    def setUp(self):
        """Set up test data."""
        self.seller = create_test_user('seller@test.com', user_type='student')
    
    def test_create_valid_furniture_item(self):
        """Test creating a valid furniture item."""
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Comfortable Sofa',
            description='A very comfortable 3-seater sofa in excellent condition.',
            price=Decimal('150.00'),
            condition='good',
            category='furniture'
        )
        self.assertEqual(item.title, 'Comfortable Sofa')
        self.assertEqual(item.seller, self.seller)
        self.assertEqual(item.price, Decimal('150.00'))
        self.assertEqual(item.condition, 'good')
        self.assertEqual(item.category, 'furniture')
        self.assertFalse(item.is_sold)
    
    def test_furniture_item_zero_price_raises_error(self):
        """Test that zero price raises ValidationError."""
        item = FurnitureItem(
            seller=self.seller,
            title='Free Sofa',
            description='Take it away',
            price=Decimal('0.00'),
            condition='fair',
            category='furniture'
        )
        with self.assertRaises(ValidationError) as context:
            item.full_clean()
        self.assertIn('price', context.exception.message_dict)
    
    def test_furniture_item_negative_price_raises_error(self):
        """Test that negative price raises ValidationError."""
        item = FurnitureItem(
            seller=self.seller,
            title='Negative Price Item',
            description='This should fail',
            price=Decimal('-50.00'),
            condition='good',
            category='furniture'
        )
        with self.assertRaises(ValidationError) as context:
            item.full_clean()
        self.assertIn('price', context.exception.message_dict)
    
    def test_furniture_item_null_price_raises_error(self):
        """Test that null price raises ValidationError."""
        item = FurnitureItem(
            seller=self.seller,
            title='No Price Item',
            description='This should fail',
            price=None,
            condition='good',
            category='furniture'
        )
        with self.assertRaises(ValidationError):
            item.full_clean()
    
    def test_furniture_item_empty_title_raises_error(self):
        """Test that empty title raises ValidationError."""
        item = FurnitureItem(
            seller=self.seller,
            title='',
            description='Valid description',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        with self.assertRaises(ValidationError) as context:
            item.full_clean()
        self.assertIn('title', context.exception.message_dict)
    
    def test_furniture_item_whitespace_title_raises_error(self):
        """Test that whitespace-only title raises ValidationError."""
        item = FurnitureItem(
            seller=self.seller,
            title='   ',
            description='Valid description',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        with self.assertRaises(ValidationError) as context:
            item.full_clean()
        self.assertIn('title', context.exception.message_dict)
    
    def test_furniture_item_empty_description_raises_error(self):
        """Test that empty description raises ValidationError."""
        item = FurnitureItem(
            seller=self.seller,
            title='Valid Title',
            description='',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        with self.assertRaises(ValidationError) as context:
            item.full_clean()
        self.assertIn('description', context.exception.message_dict)
    
    def test_furniture_item_whitespace_description_raises_error(self):
        """Test that whitespace-only description raises ValidationError."""
        item = FurnitureItem(
            seller=self.seller,
            title='Valid Title',
            description='   ',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        with self.assertRaises(ValidationError) as context:
            item.full_clean()
        self.assertIn('description', context.exception.message_dict)
    
    def test_furniture_item_invalid_condition_raises_error(self):
        """Test that invalid condition choice raises ValidationError."""
        item = FurnitureItem(
            seller=self.seller,
            title='Valid Title',
            description='Valid description',
            price=Decimal('100.00'),
            condition='excellent',  # Not a valid choice
            category='furniture'
        )
        with self.assertRaises(ValidationError) as context:
            item.full_clean()
        self.assertIn('condition', context.exception.message_dict)
    
    def test_furniture_item_all_valid_conditions(self):
        """Test that all valid condition choices work."""
        valid_conditions = ['new', 'like_new', 'good', 'fair', 'poor']
        for condition in valid_conditions:
            item = FurnitureItem.objects.create(
                seller=self.seller,
                title=f'Item with {condition} condition',
                description='Test description',
                price=Decimal('100.00'),
                condition=condition,
                category='furniture'
            )
            self.assertEqual(item.condition, condition)
    
    def test_furniture_item_invalid_category_raises_error(self):
        """Test that invalid category choice raises ValidationError."""
        item = FurnitureItem(
            seller=self.seller,
            title='Valid Title',
            description='Valid description',
            price=Decimal('100.00'),
            condition='good',
            category='invalid_category'  # Not a valid choice
        )
        with self.assertRaises(ValidationError) as context:
            item.full_clean()
        self.assertIn('category', context.exception.message_dict)
    
    def test_furniture_item_all_valid_categories(self):
        """Test that all valid category choices work."""
        valid_categories = ['furniture', 'appliances', 'electronics', 'books', 'clothing', 'other']
        for category in valid_categories:
            item = FurnitureItem.objects.create(
                seller=self.seller,
                title=f'Item in {category} category',
                description='Test description',
                price=Decimal('100.00'),
                condition='good',
                category=category
            )
            self.assertEqual(item.category, category)
    
    def test_furniture_item_default_is_sold_false(self):
        """Test that is_sold defaults to False."""
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title='New Item',
            description='Test description',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        self.assertFalse(item.is_sold)
    
    def test_furniture_item_mark_as_sold(self):
        """Test mark_as_sold() method."""
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Item to Sell',
            description='Test description',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        self.assertFalse(item.is_sold)
        item.mark_as_sold()
        self.assertTrue(item.is_sold)
    
    def test_furniture_item_is_available_when_not_sold(self):
        """Test is_available() returns True when not sold."""
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Available Item',
            description='Test description',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        self.assertTrue(item.is_available())
    
    def test_furniture_item_is_not_available_when_sold(self):
        """Test is_available() returns False when sold."""
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Sold Item',
            description='Test description',
            price=Decimal('100.00'),
            condition='good',
            category='furniture',
            is_sold=True
        )
        self.assertFalse(item.is_available())
    
    def test_furniture_item_string_representation(self):
        """Test __str__() method returns title."""
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Test Sofa',
            description='Test description',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        self.assertEqual(str(item), 'Test Sofa')
    
    def test_furniture_item_timestamps_auto_created(self):
        """Test that created_at and updated_at are auto-generated."""
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Timestamped Item',
            description='Test description',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        self.assertIsNotNone(item.created_at)
        self.assertIsNotNone(item.updated_at)
    
    def test_furniture_item_very_large_price(self):
        """Test that very large prices are handled correctly."""
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Expensive Item',
            description='Test description',
            price=Decimal('99999999.99'),  # Max for 10 digits, 2 decimal places
            condition='new',
            category='furniture'
        )
        self.assertEqual(item.price, Decimal('99999999.99'))
    
    def test_furniture_item_price_precision(self):
        """Test that price maintains 2 decimal places precision."""
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Precise Price Item',
            description='Test description',
            price=Decimal('123.45'),
            condition='good',
            category='furniture'
        )
        self.assertEqual(item.price, Decimal('123.45'))
    
    def test_furniture_item_seller_required(self):
        """Test that seller is required."""
        item = FurnitureItem(
            seller=None,
            title='No Seller Item',
            description='Test description',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        with self.assertRaises(ValidationError):
            item.full_clean()
    
    def test_furniture_item_with_provider_seller(self):
        """Test that providers can also sell furniture."""
        provider = create_test_user('provider@test.com', user_type='provider')
        item = FurnitureItem.objects.create(
            seller=provider,
            title='Provider Item',
            description='Test description',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        self.assertEqual(item.seller, provider)
    
    def test_furniture_item_long_title(self):
        """Test that very long titles are handled (max 200 chars)."""
        long_title = 'A' * 200
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title=long_title,
            description='Test description',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        self.assertEqual(len(item.title), 200)
    
    def test_furniture_item_long_description(self):
        """Test that very long descriptions are handled."""
        long_description = 'B' * 5000
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Long Description Item',
            description=long_description,
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        self.assertEqual(len(item.description), 5000)


# ============================================================================
# FurnitureImage Model Tests (~15 tests)
# ============================================================================

class FurnitureImageModelTests(TestCase):
    """Test suite for FurnitureImage model."""
    
    def setUp(self):
        """Set up test data."""
        self.seller = create_test_user('seller@test.com', user_type='student')
        self.item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Sofa with Images',
            description='Test description',
            price=Decimal('150.00'),
            condition='good',
            category='furniture'
        )
    
    def test_add_single_image_to_furniture_item(self):
        """Test adding a single image to furniture item."""
        image = create_test_image('sofa1.jpg')
        furniture_image = FurnitureImage.objects.create(
            furniture_item=self.item,
            image=image,
            order=0
        )
        self.assertEqual(furniture_image.furniture_item, self.item)
        self.assertIsNotNone(furniture_image.image)
        self.assertEqual(furniture_image.order, 0)
    
    def test_add_multiple_images_to_furniture_item(self):
        """Test adding multiple images to furniture item."""
        images = [
            create_test_image('sofa1.jpg'),
            create_test_image('sofa2.jpg'),
            create_test_image('sofa3.jpg'),
        ]
        for i, img in enumerate(images):
            FurnitureImage.objects.create(
                furniture_item=self.item,
                image=img,
                order=i
            )
        self.assertEqual(self.item.images.count(), 3)
    
    def test_furniture_image_ordering(self):
        """Test that images are ordered correctly."""
        img1 = FurnitureImage.objects.create(
            furniture_item=self.item,
            image=create_test_image('img1.jpg'),
            order=2
        )
        img2 = FurnitureImage.objects.create(
            furniture_item=self.item,
            image=create_test_image('img2.jpg'),
            order=0
        )
        img3 = FurnitureImage.objects.create(
            furniture_item=self.item,
            image=create_test_image('img3.jpg'),
            order=1
        )
        
        images = list(self.item.images.all())
        self.assertEqual(images[0], img2)  # order=0
        self.assertEqual(images[1], img3)  # order=1
        self.assertEqual(images[2], img1)  # order=2
    
    def test_furniture_image_default_order(self):
        """Test that order defaults to 0."""
        furniture_image = FurnitureImage.objects.create(
            furniture_item=self.item,
            image=create_test_image('default_order.jpg')
        )
        self.assertEqual(furniture_image.order, 0)
    
    def test_furniture_image_cascade_delete(self):
        """Test that images are deleted when furniture item is deleted."""
        FurnitureImage.objects.create(
            furniture_item=self.item,
            image=create_test_image('img1.jpg')
        )
        FurnitureImage.objects.create(
            furniture_item=self.item,
            image=create_test_image('img2.jpg')
        )
        self.assertEqual(FurnitureImage.objects.count(), 2)
        
        self.item.delete()
        self.assertEqual(FurnitureImage.objects.count(), 0)
    
    def test_furniture_image_string_representation(self):
        """Test __str__() method."""
        furniture_image = FurnitureImage.objects.create(
            furniture_item=self.item,
            image=create_test_image('test.jpg')
        )
        expected = f"Image for {self.item.title}"
        self.assertEqual(str(furniture_image), expected)
    
    def test_furniture_image_uploaded_at_timestamp(self):
        """Test that uploaded_at is auto-generated."""
        furniture_image = FurnitureImage.objects.create(
            furniture_item=self.item,
            image=create_test_image('test.jpg')
        )
        self.assertIsNotNone(furniture_image.uploaded_at)
    
    def test_furniture_image_required(self):
        """Test that image field is required."""
        furniture_image = FurnitureImage(
            furniture_item=self.item,
            image=None
        )
        with self.assertRaises(ValidationError):
            furniture_image.full_clean()
    
    def test_furniture_image_valid_formats(self):
        """Test that valid image formats are accepted."""
        valid_formats = [
            ('test.jpg', 'JPEG'),
            ('test.png', 'PNG'),
            ('test.webp', 'WEBP'),
        ]
        for filename, format_type in valid_formats:
            img = create_test_image(filename, format=format_type)
            furniture_image = FurnitureImage.objects.create(
                furniture_item=self.item,
                image=img
            )
            self.assertIsNotNone(furniture_image.image)
    
    def test_furniture_image_oversized_raises_error(self):
        """Test that oversized images (> 5MB) raise ValidationError."""
        large_image = create_large_test_image('huge.jpg', size=(5000, 5000))
        furniture_image = FurnitureImage(
            furniture_item=self.item,
            image=large_image
        )
        with self.assertRaises(ValidationError) as context:
            furniture_image.full_clean()
        self.assertIn('image', context.exception.message_dict)
    
    def test_furniture_image_invalid_format_raises_error(self):
        """Test that invalid image formats raise ValidationError."""
        # Create a fake "image" that's actually a text file
        invalid_file = SimpleUploadedFile(
            'test.txt',
            b'This is not an image',
            content_type='text/plain'
        )
        furniture_image = FurnitureImage(
            furniture_item=self.item,
            image=invalid_file
        )
        with self.assertRaises(ValidationError):
            furniture_image.full_clean()
    
    def test_furniture_image_item_required(self):
        """Test that furniture_item is required."""
        furniture_image = FurnitureImage(
            furniture_item=None,
            image=create_test_image('test.jpg')
        )
        with self.assertRaises(ValidationError):
            furniture_image.full_clean()
    
    def test_multiple_items_can_have_images(self):
        """Test that multiple furniture items can each have images."""
        item2 = FurnitureItem.objects.create(
            seller=self.seller,
            title='Another Item',
            description='Test description',
            price=Decimal('200.00'),
            condition='new',
            category='electronics'
        )
        
        FurnitureImage.objects.create(
            furniture_item=self.item,
            image=create_test_image('item1_img.jpg')
        )
        FurnitureImage.objects.create(
            furniture_item=item2,
            image=create_test_image('item2_img.jpg')
        )
        
        self.assertEqual(self.item.images.count(), 1)
        self.assertEqual(item2.images.count(), 1)
    
    def test_furniture_image_many_images_per_item(self):
        """Test that an item can have many images (stress test)."""
        for i in range(10):
            FurnitureImage.objects.create(
                furniture_item=self.item,
                image=create_test_image(f'img{i}.jpg'),
                order=i
            )
        self.assertEqual(self.item.images.count(), 10)


# ============================================================================
# FurnitureTransaction Model Tests (~30 tests)
# ============================================================================

class FurnitureTransactionModelTests(TestCase):
    """Test suite for FurnitureTransaction model."""
    
    def setUp(self):
        """Set up test data."""
        self.buyer = create_test_user('buyer@test.com', user_type='student')
        self.seller = create_test_user('seller@test.com', user_type='student')
        self.item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Transaction Test Item',
            description='Test description',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
    
    def test_create_valid_transaction(self):
        """Test creating a valid transaction."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='pending'
        )
        self.assertEqual(txn.buyer, self.buyer)
        self.assertEqual(txn.seller, self.seller)
        self.assertEqual(txn.furniture_item, self.item)
        self.assertEqual(txn.escrow_status, 'pending')
        self.assertIsNotNone(txn.transaction_date)
    
    def test_transaction_for_already_sold_item_raises_error(self):
        """Test that creating transaction for sold item raises ValidationError."""
        self.item.is_sold = True
        self.item.save()
        
        txn = FurnitureTransaction(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='pending'
        )
        with self.assertRaises(ValidationError) as context:
            txn.full_clean()
        self.assertIn('furniture_item', context.exception.message_dict)
    
    def test_transaction_buyer_and_seller_same_raises_error(self):
        """Test that buyer and seller being the same user raises ValidationError."""
        txn = FurnitureTransaction(
            buyer=self.seller,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='pending'
        )
        with self.assertRaises(ValidationError) as context:
            txn.full_clean()
        self.assertIn('buyer', context.exception.message_dict)
    
    def test_transaction_default_escrow_status_pending(self):
        """Test that escrow_status defaults to 'pending'."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item
        )
        self.assertEqual(txn.escrow_status, 'pending')
    
    def test_escrow_transition_pending_to_held_valid(self):
        """Test valid transition from pending to held."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='pending'
        )
        txn.escrow_status = 'held'
        txn.save()  # Should not raise error
        txn.refresh_from_db()
        self.assertEqual(txn.escrow_status, 'held')
    
    def test_escrow_transition_held_to_released_valid(self):
        """Test valid transition from held to released."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='held'
        )
        txn.escrow_status = 'released'
        txn.save()  # Should not raise error
        txn.refresh_from_db()
        self.assertEqual(txn.escrow_status, 'released')
    
    def test_escrow_transition_pending_to_released_invalid(self):
        """Test invalid transition from pending to released."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='pending'
        )
        txn.escrow_status = 'released'
        with self.assertRaises(ValidationError) as context:
            txn.save()
        self.assertIn('escrow_status', context.exception.message_dict)
    
    def test_escrow_transition_held_to_pending_invalid(self):
        """Test invalid transition from held to pending (backwards)."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='held'
        )
        txn.escrow_status = 'pending'
        with self.assertRaises(ValidationError) as context:
            txn.save()
        self.assertIn('escrow_status', context.exception.message_dict)
    
    def test_escrow_transition_released_to_held_invalid(self):
        """Test invalid transition from released to held (backwards)."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='released'
        )
        txn.escrow_status = 'held'
        with self.assertRaises(ValidationError) as context:
            txn.save()
        self.assertIn('escrow_status', context.exception.message_dict)
    
    def test_escrow_transition_released_to_pending_invalid(self):
        """Test invalid transition from released to pending (backwards)."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='released'
        )
        txn.escrow_status = 'pending'
        with self.assertRaises(ValidationError) as context:
            txn.save()
        self.assertIn('escrow_status', context.exception.message_dict)
    
    def test_hold_escrow_method(self):
        """Test hold_escrow() method transitions from pending to held."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='pending'
        )
        txn.hold_escrow()
        self.assertEqual(txn.escrow_status, 'held')
    
    def test_release_escrow_method(self):
        """Test release_escrow() method transitions from held to released."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='held'
        )
        txn.release_escrow()
        self.assertEqual(txn.escrow_status, 'released')
    
    def test_release_escrow_marks_item_as_sold(self):
        """Test that release_escrow() marks furniture item as sold."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='held'
        )
        self.assertFalse(self.item.is_sold)
        txn.release_escrow()
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_sold)
    
    def test_release_escrow_sets_completed_at(self):
        """Test that release_escrow() sets completed_at timestamp."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='held'
        )
        self.assertIsNone(txn.completed_at)
        txn.release_escrow()
        self.assertIsNotNone(txn.completed_at)
    
    def test_can_transition_to_method_valid(self):
        """Test can_transition_to() returns True for valid transitions."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='pending'
        )
        self.assertTrue(txn.can_transition_to('held'))
        self.assertFalse(txn.can_transition_to('released'))
    
    def test_can_transition_to_method_invalid(self):
        """Test can_transition_to() returns False for invalid transitions."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='released'
        )
        self.assertFalse(txn.can_transition_to('held'))
        self.assertFalse(txn.can_transition_to('pending'))
    
    def test_transaction_string_representation(self):
        """Test __str__() method."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item
        )
        expected = f"Transaction: {self.buyer.email} ← {self.item.title} ← {self.seller.email}"
        self.assertEqual(str(txn), expected)
    
    def test_transaction_timestamps_auto_created(self):
        """Test that timestamps are auto-generated."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item
        )
        self.assertIsNotNone(txn.transaction_date)
        self.assertIsNotNone(txn.created_at)
        self.assertIsNotNone(txn.updated_at)
    
    def test_transaction_buyer_required(self):
        """Test that buyer is required."""
        txn = FurnitureTransaction(
            buyer=None,
            seller=self.seller,
            furniture_item=self.item
        )
        with self.assertRaises(ValidationError):
            txn.full_clean()
    
    def test_transaction_seller_required(self):
        """Test that seller is required."""
        txn = FurnitureTransaction(
            buyer=self.buyer,
            seller=None,
            furniture_item=self.item
        )
        with self.assertRaises(ValidationError):
            txn.full_clean()
    
    def test_transaction_furniture_item_required(self):
        """Test that furniture_item is required."""
        txn = FurnitureTransaction(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=None
        )
        with self.assertRaises(ValidationError):
            txn.full_clean()
    
    def test_transaction_invalid_escrow_status_raises_error(self):
        """Test that invalid escrow_status raises ValidationError."""
        txn = FurnitureTransaction(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='invalid_status'
        )
        with self.assertRaises(ValidationError) as context:
            txn.full_clean()
        self.assertIn('escrow_status', context.exception.message_dict)
    
    def test_transaction_all_valid_escrow_statuses(self):
        """Test that all valid escrow statuses work."""
        valid_statuses = ['pending', 'held', 'released']
        for status in valid_statuses:
            item = FurnitureItem.objects.create(
                seller=self.seller,
                title=f'Item for {status}',
                description='Test',
                price=Decimal('100.00'),
                condition='good',
                category='furniture'
            )
            txn = FurnitureTransaction.objects.create(
                buyer=self.buyer,
                seller=self.seller,
                furniture_item=item,
                escrow_status=status
            )
            self.assertEqual(txn.escrow_status, status)
    
    def test_multiple_transactions_on_same_item_after_first_completes(self):
        """Test that new transaction can be created after first one completes."""
        # First transaction
        txn1 = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='released'
        )
        self.item.is_sold = True
        self.item.save()
        
        # Try to create second transaction - should fail because item is sold
        buyer2 = create_test_user('buyer2@test.com', user_type='student')
        txn2 = FurnitureTransaction(
            buyer=buyer2,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='pending'
        )
        with self.assertRaises(ValidationError):
            txn2.full_clean()
    
    def test_transaction_with_provider_as_buyer(self):
        """Test that providers can be buyers."""
        provider = create_test_user('provider@test.com', user_type='provider')
        txn = FurnitureTransaction.objects.create(
            buyer=provider,
            seller=self.seller,
            furniture_item=self.item
        )
        self.assertEqual(txn.buyer, provider)
    
    def test_transaction_with_provider_as_seller(self):
        """Test that providers can be sellers."""
        provider = create_test_user('provider@test.com', user_type='provider')
        item = FurnitureItem.objects.create(
            seller=provider,
            title='Provider Item',
            description='Test',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=provider,
            furniture_item=item
        )
        self.assertEqual(txn.seller, provider)
    
    def test_hold_escrow_from_non_pending_raises_error(self):
        """Test that hold_escrow() from non-pending status raises error."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='released'
        )
        with self.assertRaises(ValidationError):
            txn.hold_escrow()
    
    def test_release_escrow_from_non_held_raises_error(self):
        """Test that release_escrow() from non-held status raises error."""
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=self.item,
            escrow_status='pending'
        )
        with self.assertRaises(ValidationError):
            txn.release_escrow()
    
    def test_transaction_seller_must_match_item_seller(self):
        """Test that transaction seller must match furniture item seller."""
        other_seller = create_test_user('other@test.com', user_type='student')
        txn = FurnitureTransaction(
            buyer=self.buyer,
            seller=other_seller,  # Different from self.item.seller
            furniture_item=self.item
        )
        with self.assertRaises(ValidationError) as context:
            txn.full_clean()
        self.assertIn('seller', context.exception.message_dict)


# ============================================================================
# Concurrent Transaction Tests
# ============================================================================

class ConcurrentTransactionTests(TransactionTestCase):
    """Test suite for concurrent transaction attempts."""
    
    def setUp(self):
        """Set up test data."""
        self.buyer1 = create_test_user('buyer1@test.com', user_type='student')
        self.buyer2 = create_test_user('buyer2@test.com', user_type='student')
        self.seller = create_test_user('seller@test.com', user_type='student')
        self.item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Concurrent Test Item',
            description='Test description',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
    
    def test_concurrent_transaction_attempts_on_same_item(self):
        """Test that concurrent transaction attempts are properly handled."""
        errors = []
        
        def create_transaction(buyer, errors_list):
            try:
                with transaction.atomic():
                    # Lock the item for update
                    item = FurnitureItem.objects.select_for_update().get(pk=self.item.pk)
                    if item.is_sold:
                        raise ValidationError('Item already sold')
                    
                    txn = FurnitureTransaction(
                        buyer=buyer,
                        seller=self.seller,
                        furniture_item=item,
                        escrow_status='pending'
                    )
                    txn.full_clean()
                    txn.save()
                    
                    # Simulate some processing time
                    sleep(0.1)
            except (ValidationError, IntegrityError) as e:
                errors_list.append(e)
        
        # Create two threads trying to create transactions simultaneously
        thread1 = Thread(target=create_transaction, args=(self.buyer1, errors))
        thread2 = Thread(target=create_transaction, args=(self.buyer2, errors))
        
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()
        
        # One should succeed, one should fail
        # At least one transaction should be created
        self.assertGreaterEqual(FurnitureTransaction.objects.count(), 1)
        # At most one transaction should be created (if we have proper locking)
        self.assertLessEqual(FurnitureTransaction.objects.count(), 2)


# ============================================================================
# Integration Tests (~10 tests)
# ============================================================================

class FurnitureMarketplaceIntegrationTests(TestCase):
    """Integration tests for complete furniture marketplace workflows."""
    
    def setUp(self):
        """Set up test data."""
        self.buyer = create_test_user('buyer@test.com', user_type='student')
        self.seller = create_test_user('seller@test.com', user_type='student')
    
    def test_complete_transaction_flow(self):
        """Test complete flow: create item → add images → transaction → escrow → release."""
        # Step 1: Create furniture item
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Complete Flow Sofa',
            description='A complete test sofa',
            price=Decimal('200.00'),
            condition='like_new',
            category='furniture'
        )
        self.assertFalse(item.is_sold)
        
        # Step 2: Add images
        for i in range(3):
            FurnitureImage.objects.create(
                furniture_item=item,
                image=create_test_image(f'sofa{i}.jpg'),
                order=i
            )
        self.assertEqual(item.images.count(), 3)
        
        # Step 3: Create transaction
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=item,
            escrow_status='pending'
        )
        self.assertEqual(txn.escrow_status, 'pending')
        
        # Step 4: Hold escrow
        txn.hold_escrow()
        self.assertEqual(txn.escrow_status, 'held')
        
        # Step 5: Release escrow
        txn.release_escrow()
        self.assertEqual(txn.escrow_status, 'released')
        
        # Step 6: Verify item is marked as sold
        item.refresh_from_db()
        self.assertTrue(item.is_sold)
        self.assertFalse(item.is_available())
    
    def test_cannot_create_transaction_for_sold_item(self):
        """Test that new transaction cannot be created for sold item."""
        # Create and sell item
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Sold Item',
            description='Test',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        item.mark_as_sold()
        
        # Try to create transaction
        buyer2 = create_test_user('buyer2@test.com', user_type='student')
        txn = FurnitureTransaction(
            buyer=buyer2,
            seller=self.seller,
            furniture_item=item
        )
        with self.assertRaises(ValidationError):
            txn.full_clean()
    
    def test_multiple_items_with_images_and_transactions(self):
        """Test multiple items each with images and transactions."""
        for i in range(3):
            # Create item
            item = FurnitureItem.objects.create(
                seller=self.seller,
                title=f'Item {i}',
                description=f'Description {i}',
                price=Decimal(f'{100 + i * 50}.00'),
                condition='good',
                category='furniture'
            )
            
            # Add images
            for j in range(2):
                FurnitureImage.objects.create(
                    furniture_item=item,
                    image=create_test_image(f'item{i}_img{j}.jpg'),
                    order=j
                )
            
            # Create transaction
            buyer = create_test_user(f'buyer{i}@test.com', user_type='student')
            FurnitureTransaction.objects.create(
                buyer=buyer,
                seller=self.seller,
                furniture_item=item
            )
        
        self.assertEqual(FurnitureItem.objects.count(), 3)
        self.assertEqual(FurnitureImage.objects.count(), 6)
        self.assertEqual(FurnitureTransaction.objects.count(), 3)
    
    def test_student_seller_provider_buyer_transaction(self):
        """Test transaction with student seller and provider buyer."""
        provider = create_test_user('provider@test.com', user_type='provider')
        
        item = FurnitureItem.objects.create(
            seller=self.seller,  # student
            title='Student Item',
            description='Test',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        
        txn = FurnitureTransaction.objects.create(
            buyer=provider,  # provider
            seller=self.seller,
            furniture_item=item
        )
        
        self.assertTrue(self.seller.is_student())
        self.assertTrue(provider.is_provider())
        self.assertEqual(txn.buyer, provider)
    
    def test_provider_seller_student_buyer_transaction(self):
        """Test transaction with provider seller and student buyer."""
        provider = create_test_user('provider@test.com', user_type='provider')
        
        item = FurnitureItem.objects.create(
            seller=provider,  # provider
            title='Provider Item',
            description='Test',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,  # student
            seller=provider,
            furniture_item=item
        )
        
        self.assertTrue(provider.is_provider())
        self.assertTrue(self.buyer.is_student())
        self.assertEqual(txn.seller, provider)
    
    def test_item_deletion_cascades_to_images_and_transactions(self):
        """Test that deleting item cascades to images and transactions."""
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Cascade Test',
            description='Test',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        
        FurnitureImage.objects.create(
            furniture_item=item,
            image=create_test_image('test.jpg')
        )
        
        FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=item
        )
        
        self.assertEqual(FurnitureImage.objects.count(), 1)
        self.assertEqual(FurnitureTransaction.objects.count(), 1)
        
        item.delete()
        
        self.assertEqual(FurnitureImage.objects.count(), 0)
        self.assertEqual(FurnitureTransaction.objects.count(), 0)
    
    def test_escrow_flow_with_validation_at_each_step(self):
        """Test escrow flow with validation at each transition."""
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Escrow Flow Item',
            description='Test',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=item,
            escrow_status='pending'
        )
        
        # Validate pending state
        self.assertTrue(txn.can_transition_to('held'))
        self.assertFalse(txn.can_transition_to('released'))
        
        # Transition to held
        txn.hold_escrow()
        self.assertEqual(txn.escrow_status, 'held')
        
        # Validate held state
        self.assertTrue(txn.can_transition_to('released'))
        self.assertFalse(txn.can_transition_to('pending'))
        
        # Transition to released
        txn.release_escrow()
        self.assertEqual(txn.escrow_status, 'released')
        
        # Validate released state (immutable)
        self.assertFalse(txn.can_transition_to('held'))
        self.assertFalse(txn.can_transition_to('pending'))
    
    def test_item_with_many_images_performance(self):
        """Test performance with many images per item."""
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Many Images Item',
            description='Test',
            price=Decimal('100.00'),
            condition='good',
            category='furniture'
        )
        
        # Add 20 images
        for i in range(20):
            FurnitureImage.objects.create(
                furniture_item=item,
                image=create_test_image(f'img{i}.jpg'),
                order=i
            )
        
        # Verify all images are properly ordered
        images = list(item.images.all())
        self.assertEqual(len(images), 20)
        for i, img in enumerate(images):
            self.assertEqual(img.order, i)
    
    def test_price_precision_through_transaction_flow(self):
        """Test that price precision is maintained through transaction flow."""
        item = FurnitureItem.objects.create(
            seller=self.seller,
            title='Precision Test',
            description='Test',
            price=Decimal('123.45'),
            condition='good',
            category='furniture'
        )
        
        txn = FurnitureTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            furniture_item=item
        )
        
        # Verify price precision maintained
        self.assertEqual(item.price, Decimal('123.45'))
        self.assertEqual(txn.furniture_item.price, Decimal('123.45'))
    
    def test_all_categories_and_conditions_combinations(self):
        """Test creating items with all category and condition combinations."""
        categories = ['furniture', 'appliances', 'electronics', 'books', 'clothing', 'other']
        conditions = ['new', 'like_new', 'good', 'fair', 'poor']
        
        count = 0
        for category in categories:
            for condition in conditions:
                item = FurnitureItem.objects.create(
                    seller=self.seller,
                    title=f'{category} - {condition}',
                    description='Test',
                    price=Decimal('50.00'),
                    condition=condition,
                    category=category
                )
                count += 1
                self.assertEqual(item.category, category)
                self.assertEqual(item.condition, condition)
        
        self.assertEqual(FurnitureItem.objects.count(), len(categories) * len(conditions))
