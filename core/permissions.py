"""
Custom permission classes for Student Moving Services Marketplace.
"""

from rest_framework import permissions


class IsStaffUser(permissions.BasePermission):
    """
    Permission class that allows only staff users to access the endpoint.
    
    This permission checks if the authenticated user has is_staff=True.
    Returns 403 Forbidden for non-staff users.
    
    Usage:
        class MyView(APIView):
            permission_classes = [IsAuthenticated, IsStaffUser]
    """
    
    message = 'You do not have permission to perform this action. Staff privileges required.'
    
    def has_permission(self, request, view):
        """
        Check if user is authenticated and has staff privileges.
        
        Args:
            request: HTTP request object
            view: View being accessed
            
        Returns:
            bool: True if user is staff, False otherwise
        """
        # User must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # User must have staff privileges
        return request.user.is_staff


class IsVerifiedProvider(permissions.BasePermission):
    """
    Permission class that allows only verified providers to access the endpoint.
    
    This permission checks if the authenticated user:
    1. Has user_type='provider'
    2. Has is_verified=True
    
    Returns 403 Forbidden for:
    - Non-provider users (students)
    - Unverified providers
    
    Usage:
        class MyView(APIView):
            permission_classes = [IsAuthenticated, IsVerifiedProvider]
    """
    
    message = 'You do not have permission to perform this action. Only verified providers can create services.'
    
    def has_permission(self, request, view):
        """
        Check if user is authenticated, is a provider, and is verified.
        
        Args:
            request: HTTP request object
            view: View being accessed
            
        Returns:
            bool: True if user is verified provider, False otherwise
        """
        # User must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # User must be a provider
        if not hasattr(request.user, 'user_type') or request.user.user_type != 'provider':
            return False
        
        # Provider must be verified
        if not hasattr(request.user, 'is_verified') or not request.user.is_verified:
            return False
        
        return True
