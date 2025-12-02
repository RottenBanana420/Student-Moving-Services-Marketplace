"""
Django admin configuration for custom User model.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin interface for User model.
    
    Extends Django's UserAdmin to include custom fields.
    """
    
    # Fields to display in the list view
    list_display = [
        'email',
        'username',
        'user_type',
        'university_name',
        'is_verified',
        'is_staff',
        'is_active',
        'created_at',
    ]
    
    # Fields to filter by in the sidebar
    list_filter = [
        'user_type',
        'is_verified',
        'is_staff',
        'is_superuser',
        'is_active',
        'created_at',
    ]
    
    # Fields to search
    search_fields = [
        'email',
        'username',
        'first_name',
        'last_name',
        'university_name',
    ]
    
    # Default ordering
    ordering = ['-created_at']
    
    # Fields to display in the detail view
    fieldsets = (
        (None, {
            'fields': ('username', 'password')
        }),
        (_('Personal Info'), {
            'fields': (
                'first_name',
                'last_name',
                'email',
                'phone_number',
                'university_name',
            )
        }),
        (_('User Type & Verification'), {
            'fields': ('user_type', 'is_verified', 'profile_image')
        }),
        (_('Permissions'), {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions',
            ),
            'classes': ('collapse',),
        }),
        (_('Important Dates'), {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    # Fields to display when adding a new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username',
                'email',
                'password1',
                'password2',
                'user_type',
                'university_name',
            ),
        }),
    )
    
    # Read-only fields
    readonly_fields = ['created_at', 'updated_at', 'last_login', 'date_joined']
    
    # Enable date hierarchy navigation
    date_hierarchy = 'created_at'
    
    # Number of items per page
    list_per_page = 25
    
    def get_readonly_fields(self, request, obj=None):
        """
        Make created_at and updated_at read-only.
        
        Args:
            request: HTTP request
            obj: User object (None when adding new user)
            
        Returns:
            list: Read-only field names
        """
        if obj:  # Editing an existing object
            return self.readonly_fields
        return []


# ============================================================================
# Furniture Marketplace Admin
# ============================================================================

from .models import FurnitureItem, FurnitureImage, FurnitureTransaction


class FurnitureImageInline(admin.TabularInline):
    """Inline admin for furniture images."""
    model = FurnitureImage
    extra = 1
    fields = ['image', 'order', 'uploaded_at']
    readonly_fields = ['uploaded_at']
    ordering = ['order']


@admin.register(FurnitureItem)
class FurnitureItemAdmin(admin.ModelAdmin):
    """Admin interface for FurnitureItem model."""
    
    list_display = [
        'title',
        'seller',
        'price',
        'condition',
        'category',
        'is_sold',
        'created_at',
    ]
    
    list_filter = [
        'is_sold',
        'condition',
        'category',
        'created_at',
    ]
    
    search_fields = [
        'title',
        'description',
        'seller__email',
        'seller__username',
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    ordering = ['-created_at']
    
    date_hierarchy = 'created_at'
    
    list_per_page = 25
    
    inlines = [FurnitureImageInline]
    
    fieldsets = (
        (None, {
            'fields': ('seller', 'title', 'description')
        }),
        (_('Pricing & Details'), {
            'fields': ('price', 'condition', 'category', 'is_sold')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(FurnitureImage)
class FurnitureImageAdmin(admin.ModelAdmin):
    """Admin interface for FurnitureImage model."""
    
    list_display = [
        'furniture_item',
        'order',
        'uploaded_at',
    ]
    
    list_filter = [
        'uploaded_at',
    ]
    
    search_fields = [
        'furniture_item__title',
    ]
    
    readonly_fields = ['uploaded_at']
    
    ordering = ['furniture_item', 'order']
    
    list_per_page = 50


@admin.register(FurnitureTransaction)
class FurnitureTransactionAdmin(admin.ModelAdmin):
    """Admin interface for FurnitureTransaction model."""
    
    list_display = [
        'id',
        'buyer',
        'seller',
        'furniture_item',
        'escrow_status',
        'transaction_date',
        'completed_at',
    ]
    
    list_filter = [
        'escrow_status',
        'transaction_date',
        'completed_at',
    ]
    
    search_fields = [
        'buyer__email',
        'buyer__username',
        'seller__email',
        'seller__username',
        'furniture_item__title',
    ]
    
    readonly_fields = ['transaction_date', 'created_at', 'updated_at', 'completed_at']
    
    ordering = ['-transaction_date']
    
    date_hierarchy = 'transaction_date'
    
    list_per_page = 25
    
    fieldsets = (
        (None, {
            'fields': ('buyer', 'seller', 'furniture_item')
        }),
        (_('Escrow Status'), {
            'fields': ('escrow_status', 'completed_at')
        }),
        (_('Timestamps'), {
            'fields': ('transaction_date', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


# ============================================================================
# Review Admin
# ============================================================================

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Admin interface for Review model."""
    
    list_display = [
        'id',
        'reviewer',
        'reviewee',
        'booking',
        'rating',
        'created_at',
    ]
    
    list_filter = [
        'rating',
        'created_at',
    ]
    
    search_fields = [
        'reviewer__email',
        'reviewer__username',
        'reviewee__email',
        'reviewee__username',
        'comment',
    ]
    
    readonly_fields = ['created_at']
    
    ordering = ['-created_at']
    
    date_hierarchy = 'created_at'
    
    list_per_page = 25
    
    fieldsets = (
        (None, {
            'fields': ('reviewer', 'reviewee', 'booking')
        }),
        (_('Review Content'), {
            'fields': ('rating', 'comment')
        }),
        (_('Timestamps'), {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

