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

