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


class IsStudent(permissions.BasePermission):
    """
    Permission class that allows only students to access the endpoint.
    
    This permission checks if the authenticated user has user_type='student'.
    Returns 403 Forbidden for non-student users (providers).
    
    Usage:
        class MyView(APIView):
            permission_classes = [IsAuthenticated, IsStudent]
    """
    
    message = 'Only students can create bookings.'
    
    def has_permission(self, request, view):
        """
        Check if user is authenticated and is a student.
        
        Args:
            request: HTTP request object
            view: View being accessed
            
        Returns:
            bool: True if user is student, False otherwise
        """
        # User must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # User must be a student
        if not hasattr(request.user, 'user_type') or request.user.user_type != 'student':
            return False
        
        return True


class CanUpdateBookingStatus(permissions.BasePermission):
    """
    Permission class for booking status updates with role-based authorization.
    
    Authorization rules:
    - Providers can: confirm, complete (their own bookings only)
    - Students can: cancel (their own bookings only)
    - Providers can: cancel (their own bookings only)
    - Users cannot modify other users' bookings
    
    This permission implements object-level permissions via has_object_permission().
    
    Usage:
        class BookingStatusUpdateView(APIView):
            permission_classes = [IsAuthenticated, CanUpdateBookingStatus]
    """
    
    message = 'You do not have permission to update this booking status.'
    
    def has_permission(self, request, view):
        """
        Check if user is authenticated.
        
        Args:
            request: HTTP request object
            view: View being accessed
            
        Returns:
            bool: True if user is authenticated, False otherwise
        """
        # User must be authenticated
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can update the specific booking's status.
        
        Validates:
        1. User is either the student or provider of the booking
        2. User has permission for the specific status transition
        
        Args:
            request: HTTP request object
            view: View being accessed
            obj: Booking instance
            
        Returns:
            bool: True if user can update this booking, False otherwise
        """
        # Get the requested new status from request data
        new_status = request.data.get('status')
        
        # User must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user is the student of this booking
        is_student = obj.student_id == request.user.id
        
        # Check if user is the provider of this booking
        is_provider = obj.provider_id == request.user.id
        
        # User must be either student or provider
        if not is_student and not is_provider:
            self.message = 'You do not have permission to modify this booking.'
            return False
        
        # Authorization based on role and requested status
        if new_status == 'confirmed':
            # Only providers can confirm
            if not is_provider:
                self.message = 'Only providers can confirm bookings.'
                return False
            return True
        
        elif new_status == 'completed':
            # Only providers can complete
            if not is_provider:
                self.message = 'Only providers can complete bookings.'
                return False
            return True
        
        elif new_status == 'cancelled':
            # Both students and providers can cancel their own bookings
            if is_student or is_provider:
                return True
            return False
        
        # For all other statuses (including 'pending'), allow through
        # Let the serializer's state machine validation handle invalid transitions
        # This ensures we return 400 (validation error) instead of 403 (permission denied)
        return True
