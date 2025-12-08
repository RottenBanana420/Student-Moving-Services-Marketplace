"""
Custom views for Student Moving Services Marketplace.
"""

import logging
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from .serializers import (
    EmailTokenObtainPairSerializer,
    UserRegistrationSerializer,
    LoginSerializer,
    TokenRefreshSerializer
)

User = get_user_model()
logger = logging.getLogger(__name__)


class EmailTokenObtainPairView(TokenObtainPairView):
    """
    Custom view to use email-based authentication instead of username.
    """
    serializer_class = EmailTokenObtainPairSerializer


class UserRegistrationView(generics.CreateAPIView):
    """
    API endpoint for user registration.
    
    Accepts POST requests with user registration data.
    Returns created user data (excluding password) on success.
    Handles concurrent registration attempts with database-level uniqueness.
    """
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        """
        Handle user registration with proper error handling.
        Catches IntegrityError for concurrent duplicate email attempts.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
                headers=headers
            )
        except IntegrityError as e:
            # Handle database-level uniqueness constraint violations
            # This catches concurrent registration attempts with the same email
            if 'email' in str(e).lower() or 'unique' in str(e).lower():
                return Response(
                    {'email': ['A user with that email already exists.']},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Re-raise if it's a different integrity error
            raise


class LoginView(APIView):
    """
    API endpoint for user login with JWT token generation.
    
    Security features:
    - Rate limiting: 5 attempts per minute per IP
    - Generic error messages to prevent user enumeration
    - Failed login attempt logging for security monitoring
    - SQL injection protection via Django ORM
    - Case-insensitive email lookup
    
    POST /api/auth/login/
    Request body: {"email": "user@example.com", "password": "password123"}
    
    Success response (200):
    {
        "access": "<jwt_access_token>",
        "refresh": "<jwt_refresh_token>",
        "user": {
            "id": 1,
            "email": "user@example.com",
            "user_type": "student",
            "is_verified": false
        }
    }
    
    Error response (401): {"detail": "Invalid credentials"}
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'
    serializer_class = LoginSerializer
    
    def get_client_ip(self, request):
        """
        Get client IP address from request.
        Handles proxy headers for accurate IP detection.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def post(self, request, *args, **kwargs):
        """
        Handle login request with comprehensive security measures.
        """
        # Validate request data
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        # Normalize email to lowercase for case-insensitive lookup
        email = email.lower().strip()
        
        # Get client IP for logging
        client_ip = self.get_client_ip(request)
        
        try:
            # Attempt to retrieve user by email (case-insensitive)
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # User doesn't exist - log and return generic error
            logger.warning(
                f"Failed login attempt for non-existent user. "
                f"Email: {email}, IP: {client_ip}"
            )
            return Response(
                {'detail': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Verify password
        if not user.check_password(password):
            # Wrong password - log and return generic error
            logger.warning(
                f"Failed login attempt with incorrect password. "
                f"Email: {email}, IP: {client_ip}"
            )
            return Response(
                {'detail': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if user account is active
        if not user.is_active:
            # Inactive account - log and return generic error
            logger.warning(
                f"Failed login attempt for inactive account. "
                f"Email: {email}, IP: {client_ip}"
            )
            return Response(
                {'detail': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Authentication successful - generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        # Log successful login
        logger.info(
            f"Successful login. Email: {email}, IP: {client_ip}"
        )
        
        # Prepare user data (exclude sensitive information)
        user_data = {
            'id': user.id,
            'email': user.email,
            'user_type': user.user_type,
            'is_verified': user.is_verified,
        }
        
        # Return tokens and user information
        return Response({
            'access': access_token,
            'refresh': refresh_token,
            'user': user_data
        }, status=status.HTTP_200_OK)


class CustomTokenRefreshView(APIView):
    """
    API endpoint for refreshing JWT access tokens.
    
    Security features:
    - Rate limiting: 10 requests per minute per IP
    - Refresh token validation (signature, expiration, type)
    - Blacklist checking (tokens blacklisted after logout)
    - Token rotation (new refresh token issued)
    - Old refresh token automatically blacklisted
    - Comprehensive logging for security monitoring
    
    POST /api/auth/refresh/
    Request body: {"refresh": "<jwt_refresh_token>"}
    
    Success response (200):
    {
        "access": "<new_jwt_access_token>",
        "refresh": "<new_jwt_refresh_token>"  # If rotation enabled
    }
    
    Error responses:
    - 400: Invalid request format (missing refresh field)
    - 401: Invalid, expired, or blacklisted refresh token
    - 429: Rate limit exceeded (too many refresh attempts)
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'refresh'
    serializer_class = TokenRefreshSerializer
    
    def get_client_ip(self, request):
        """
        Get client IP address from request.
        Handles proxy headers for accurate IP detection.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def post(self, request, *args, **kwargs):
        """
        Handle token refresh request with comprehensive security measures.
        """
        # Validate request data
        serializer = TokenRefreshSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        refresh_token_str = serializer.validated_data['refresh']
        client_ip = self.get_client_ip(request)
        
        try:
            # Create RefreshToken instance from string
            # This validates:
            # - Token signature
            # - Token expiration
            # - Token format
            # - Blacklist status (if CHECK_REVOKE_TOKEN is True)
            refresh_token = RefreshToken(refresh_token_str)
            
            # Verify it's actually a refresh token (not access token)
            if refresh_token.get('token_type') != 'refresh':
                logger.warning(
                    f"Token refresh attempt with non-refresh token. IP: {client_ip}"
                )
                return Response(
                    {'detail': 'Token has wrong type'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Generate new access token
            access_token = str(refresh_token.access_token)
            
            # Prepare response data
            response_data = {
                'access': access_token
            }
            
            # If token rotation is enabled, include new refresh token
            # The settings have ROTATE_REFRESH_TOKENS=True and BLACKLIST_AFTER_ROTATION=True
            # So we need to manually handle rotation
            from django.conf import settings as django_settings
            if django_settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS', False):
                # Get user_id from the refresh token
                user_id = refresh_token.get('user_id')
                
                # Blacklist the old refresh token
                if django_settings.SIMPLE_JWT.get('BLACKLIST_AFTER_ROTATION', False):
                    try:
                        refresh_token.blacklist()
                    except AttributeError:
                        # Blacklist not available
                        pass
                
                # Generate new refresh token for the user
                User = get_user_model()
                try:
                    user = User.objects.get(id=user_id)
                    new_refresh = RefreshToken.for_user(user)
                    response_data['refresh'] = str(new_refresh)
                except User.DoesNotExist:
                    # User doesn't exist, but we already generated access token
                    # This shouldn't happen in normal flow
                    pass
            
            # Log successful refresh
            logger.info(
                f"Successful token refresh. IP: {client_ip}"
            )
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except TokenError as e:
            # Token is invalid, expired, or blacklisted
            logger.warning(
                f"Failed token refresh attempt. Error: {str(e)}, IP: {client_ip}"
            )
            return Response(
                {'detail': str(e)},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            # Unexpected error
            logger.error(
                f"Unexpected error during token refresh. Error: {str(e)}, IP: {client_ip}"
            )
            return Response(
                {'detail': 'Token refresh failed'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class UserProfileView(APIView):
    """
    API endpoint for retrieving and updating authenticated user's profile.
    
    Security features:
    - Requires JWT authentication
    - Supports GET (retrieve), PUT (full update), and PATCH (partial update)
    - Users can only access/update their own profile
    - Excludes sensitive data (password, permissions, etc.)
    - Validates all input data
    - Handles file uploads for profile images
    
    GET /api/auth/profile/
    Headers: Authorization: Bearer <access_token>
    
    Success response (200):
    {
        "id": 1,
        "email": "user@example.com",
        "phone_number": "+1234567890",
        "university_name": "Example University",
        "user_type": "student",
        "is_verified": false,
        "profile_image_url": "http://localhost:8000/media/profile_images/1/photo.jpg",
        "created_at": "2025-12-06T20:00:00Z"
    }
    
    PUT /api/auth/profile/
    PATCH /api/auth/profile/
    Headers: Authorization: Bearer <access_token>
    Body: {
        "phone_number": "+1234567890",
        "university_name": "New University",
        "profile_image": <file>  # Optional
    }
    
    Error responses:
    - 401: Missing, invalid, or expired JWT token
    - 400: Invalid data (validation errors)
    - 404: Authenticated user no longer exists in database (edge case)
    - 405: Method not allowed (only GET, PUT, PATCH supported)
    """
    permission_classes = [AllowAny]  # Will be overridden by authentication
    
    def get(self, request, *args, **kwargs):
        """
        Retrieve the authenticated user's profile.
        
        The authentication is handled by DRF's authentication classes.
        If authentication fails, DRF will automatically return 401.
        """
        # Check if user is authenticated
        # DRF's JWTAuthentication will set request.user if token is valid
        if not request.user or not request.user.is_authenticated:
            return Response(
                {'detail': 'Authentication credentials were not provided.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Edge case: Check if user still exists in database
        # This handles the case where a user was deleted but token is still valid
        try:
            user = User.objects.get(id=request.user.id)
        except User.DoesNotExist:
            logger.warning(
                f"Profile access attempt for non-existent user. "
                f"User ID: {request.user.id}"
            )
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Serialize and return user profile
        from .serializers import UserProfileSerializer
        serializer = UserProfileSerializer(user, context={'request': request})
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request, *args, **kwargs):
        """
        Full update of authenticated user's profile.
        
        All updatable fields should be provided (phone_number, university_name).
        Profile image is optional.
        """
        return self._update_profile(request, partial=False)
    
    def patch(self, request, *args, **kwargs):
        """
        Partial update of authenticated user's profile.
        
        Only provided fields will be updated.
        """
        return self._update_profile(request, partial=True)
    
    def _update_profile(self, request, partial=False):
        """
        Internal method to handle profile updates (PUT/PATCH).
        
        Args:
            request: HTTP request
            partial: If True, allows partial updates (PATCH). If False, requires all fields (PUT).
            
        Returns:
            Response: Updated profile data or error
        """
        # Check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            return Response(
                {'detail': 'Authentication credentials were not provided.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Get user from database
        try:
            user = User.objects.get(id=request.user.id)
        except User.DoesNotExist:
            logger.warning(
                f"Profile update attempt for non-existent user. "
                f"User ID: {request.user.id}"
            )
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Use update serializer for validation and update
        from .serializers import UserProfileUpdateSerializer
        serializer = UserProfileUpdateSerializer(
            user,
            data=request.data,
            partial=partial,
            context={'request': request}
        )
        
        if serializer.is_valid():
            # Save the updated profile
            serializer.save()
            
            # Return updated profile using the read serializer
            from .serializers import UserProfileSerializer
            response_serializer = UserProfileSerializer(user, context={'request': request})
            
            logger.info(
                f"Profile updated successfully. "
                f"User ID: {user.id}, Email: {user.email}, "
                f"Partial: {partial}"
            )
            
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        else:
            # Return validation errors
            logger.warning(
                f"Profile update validation failed. "
                f"User ID: {user.id}, Errors: {serializer.errors}"
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def post(self, request, *args, **kwargs):
        """POST method not allowed."""
        return Response(
            {'detail': 'Method "POST" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def delete(self, request, *args, **kwargs):
        """DELETE method not allowed."""
        return Response(
            {'detail': 'Method "DELETE" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


class ProviderVerificationView(APIView):
    """
    Admin-only endpoint for verifying provider accounts.
    
    Security features:
    - Requires JWT authentication (IsAuthenticated)
    - Requires staff privileges (IsStaffUser - is_staff=True)
    - Validates target user is a provider
    - Logs all verification actions for audit trail
    - Returns appropriate error codes (401, 403, 404, 400)
    - Idempotent operation (can verify already-verified providers)
    
    POST /api/auth/verify-provider/
    Headers: Authorization: Bearer <access_token>
    Request body: {"provider_id": 123}
    
    Success response (200):
    {
        "id": 123,
        "email": "provider@example.com",
        "user_type": "provider",
        "is_verified": true,
        "phone_number": "+1234567890",
        "university_name": "Example University",
        "created_at": "2025-12-06T20:00:00Z",
        "updated_at": "2025-12-07T08:30:00Z"
    }
    
    Error responses:
    - 401: Missing, invalid, or expired JWT token
    - 403: Authenticated but not staff user
    - 404: Target provider doesn't exist
    - 400: Invalid request (missing provider_id, target is not a provider, etc.)
    - 405: Method not allowed (only POST supported)
    """
    permission_classes = [AllowAny]  # Will check manually for better error messages
    
    def get_client_ip(self, request):
        """
        Get client IP address from request.
        Handles proxy headers for accurate IP detection.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def post(self, request, *args, **kwargs):
        """
        Handle provider verification request.
        
        Steps:
        1. Verify user is authenticated
        2. Verify user has staff privileges
        3. Validate request data (provider_id)
        4. Verify target user exists and is a provider
        5. Update is_verified to True
        6. Log verification action
        7. Return updated provider information
        """
        # Step 1: Check authentication
        if not request.user or not request.user.is_authenticated:
            return Response(
                {'detail': 'Authentication credentials were not provided.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Step 2: Check staff privileges
        if not request.user.is_staff:
            logger.warning(
                f"Non-staff user attempted provider verification. "
                f"User: {request.user.email}, IP: {self.get_client_ip(request)}"
            )
            return Response(
                {'detail': 'You do not have permission to perform this action. Staff privileges required.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Step 3: Validate request data
        from .serializers import ProviderVerificationRequestSerializer
        request_serializer = ProviderVerificationRequestSerializer(data=request.data)
        
        if not request_serializer.is_valid():
            return Response(
                request_serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        provider_id = request_serializer.validated_data['provider_id']
        
        # Step 4: Get target provider user
        try:
            provider_user = User.objects.get(id=provider_id)
        except User.DoesNotExist:
            logger.warning(
                f"Provider verification attempted for non-existent user. "
                f"Provider ID: {provider_id}, Admin: {request.user.email}, "
                f"IP: {self.get_client_ip(request)}"
            )
            return Response(
                {'detail': f'User with ID {provider_id} does not exist.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate user is a provider (should be caught by serializer, but double-check)
        if provider_user.user_type != 'provider':
            logger.warning(
                f"Verification attempted on non-provider user. "
                f"User ID: {provider_id}, User Type: {provider_user.user_type}, "
                f"Admin: {request.user.email}, IP: {self.get_client_ip(request)}"
            )
            return Response(
                {'detail': f'User with ID {provider_id} is not a provider. Only provider accounts can be verified.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Step 5: Update is_verified to True (idempotent operation)
        was_already_verified = provider_user.is_verified
        provider_user.is_verified = True
        provider_user.save(update_fields=['is_verified', 'updated_at'])
        
        # Step 6: Log verification action for audit trail
        logger.info(
            f"Provider verification {'confirmed' if was_already_verified else 'completed'}. "
            f"Provider: {provider_user.email} (ID: {provider_user.id}), "
            f"Admin: {request.user.email} (ID: {request.user.id}), "
            f"IP: {self.get_client_ip(request)}, "
            f"Already Verified: {was_already_verified}"
        )
        
        # Step 7: Return updated provider information
        from .serializers import ProviderVerificationResponseSerializer
        response_serializer = ProviderVerificationResponseSerializer(provider_user)
        
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    def get(self, request, *args, **kwargs):
        """GET method not allowed."""
        return Response(
            {'detail': 'Method "GET" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def put(self, request, *args, **kwargs):
        """PUT method not allowed."""
        return Response(
            {'detail': 'Method "PUT" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def patch(self, request, *args, **kwargs):
        """PATCH method not allowed."""
        return Response(
            {'detail': 'Method "PATCH" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def delete(self, request, *args, **kwargs):
        """DELETE method not allowed."""
        return Response(
            {'detail': 'Method "DELETE" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


class ServiceCreateView(APIView):
    """
    API endpoint for creating moving services.
    
    Security features:
    - Requires JWT authentication (IsAuthenticated)
    - Requires verified provider status (IsVerifiedProvider)
    - Auto-populates provider field from authenticated user
    - Validates all input fields
    - Initializes rating_average to 0.0 and total_reviews to 0
    - Logs service creation for audit trail
    
    POST /api/services/
    Headers: Authorization: Bearer <access_token>
    Request body: {
        "service_name": "Premium Moving Service",
        "description": "Professional moving service for students",
        "base_price": "150.00",
        "availability_status": true  # Optional, defaults to true
    }
    
    Success response (201):
    {
        "id": 1,
        "service_name": "Premium Moving Service",
        "description": "Professional moving service for students",
        "base_price": "150.00",
        "availability_status": true,
        "provider": 1,
        "rating_average": "0.00",
        "total_reviews": 0,
        "created_at": "2025-12-07T12:00:00Z",
        "updated_at": "2025-12-07T12:00:00Z"
    }
    
    Error responses:
    - 401: Missing, invalid, or expired JWT token
    - 403: Non-provider or unverified provider attempting to create service
    - 400: Invalid data (validation errors)
    - 405: Method not allowed (only POST supported)
    """
    permission_classes = [AllowAny]  # Will check manually for better error messages
    
    def get_client_ip(self, request):
        """
        Get client IP address from request.
        Handles proxy headers for accurate IP detection.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def post(self, request, *args, **kwargs):
        """
        Handle service creation request.
        
        Steps:
        1. Verify user is authenticated
        2. Verify user is a verified provider
        3. Validate request data
        4. Create service with auto-populated fields
        5. Log creation action
        6. Return created service details
        """
        # Step 1: Check authentication
        if not request.user or not request.user.is_authenticated:
            return Response(
                {'detail': 'Authentication credentials were not provided.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Step 2: Check if user is a verified provider
        from .permissions import IsVerifiedProvider
        permission = IsVerifiedProvider()
        
        if not permission.has_permission(request, self):
            # Determine specific reason for denial
            if not hasattr(request.user, 'user_type') or request.user.user_type != 'provider':
                logger.warning(
                    f"Non-provider user attempted service creation. "
                    f"User: {request.user.email}, User Type: {getattr(request.user, 'user_type', 'unknown')}, "
                    f"IP: {self.get_client_ip(request)}"
                )
                return Response(
                    {'detail': 'You do not have permission to perform this action. Only verified providers can create services.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            elif not hasattr(request.user, 'is_verified') or not request.user.is_verified:
                logger.warning(
                    f"Unverified provider attempted service creation. "
                    f"User: {request.user.email}, Is Verified: {getattr(request.user, 'is_verified', False)}, "
                    f"IP: {self.get_client_ip(request)}"
                )
                return Response(
                    {'detail': 'You do not have permission to perform this action. Only verified providers can create services.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Step 3: Validate request data
        from .serializers import MovingServiceCreateSerializer
        serializer = MovingServiceCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Step 4: Create service
        service = serializer.save()
        
        # Step 5: Log creation action
        logger.info(
            f"Service created successfully. "
            f"Service ID: {service.id}, Service Name: {service.service_name}, "
            f"Provider: {request.user.email} (ID: {request.user.id}), "
            f"IP: {self.get_client_ip(request)}"
        )
        
        # Step 6: Return created service details
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    def get(self, request, *args, **kwargs):
        """GET method not allowed."""
        return Response(
            {'detail': 'Method "GET" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def put(self, request, *args, **kwargs):
        """PUT method not allowed."""
        return Response(
            {'detail': 'Method "PUT" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def patch(self, request, *args, **kwargs):
        """PATCH method not allowed."""
        return Response(
            {'detail': 'Method "PATCH" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def delete(self, request, *args, **kwargs):
        """DELETE method not allowed."""
        return Response(
            {'detail': 'Method "DELETE" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )



# ============================================================================
# Service Listing View
# ============================================================================

class ServiceListView(APIView):
    """
    API endpoint for listing moving services with filtering, sorting, and pagination.
    
    Public endpoint - no authentication required.
    
    Features:
    - Public access (AllowAny permission)
    - Filtering by availability, price range, rating, university
    - Sorting by price, rating, creation date
    - Pagination with configurable page size
    - Query optimization with select_related to prevent N+1 queries
    
    Query Parameters:
    - available: Filter by availability status (true/false)
    - min_price: Minimum price filter (decimal)
    - max_price: Maximum price filter (decimal)
    - min_rating: Minimum rating filter (decimal, 0-5)
    - university: Filter by provider university (case-insensitive partial match)
    - ordering: Sort field (price, -price, rating, -rating, date, -date)
    - page: Page number for pagination
    - page_size: Number of results per page (default: 20, max: 100)
    
    Returns:
    - 200 OK: Paginated list of services with provider information
    - 400 Bad Request: Invalid query parameters
    - 404 Not Found: Invalid page number
    """
    
    permission_classes = [AllowAny]
    
    def get(self, request, *args, **kwargs):
        """
        Handle GET request for service listing.
        
        Implements filtering, sorting, and pagination with query optimization.
        """
        from decimal import Decimal, InvalidOperation
        from django.core.paginator import Paginator, EmptyPage
        from core.models import MovingService
        from core.serializers import ServiceListSerializer
        
        try:
            # Start with all services, optimized with select_related
            queryset = MovingService.objects.select_related('provider').all()
            
            # ================================================================
            # Filtering
            # ================================================================
            
            # Filter by availability
            available = request.query_params.get('available')
            if available is not None:
                if available.lower() == 'true':
                    queryset = queryset.filter(availability_status=True)
                elif available.lower() == 'false':
                    queryset = queryset.filter(availability_status=False)
                else:
                    return Response(
                        {'error': 'Invalid value for "available". Must be "true" or "false".'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Filter by price range
            min_price = request.query_params.get('min_price')
            max_price = request.query_params.get('max_price')
            
            if min_price is not None:
                try:
                    min_price_decimal = Decimal(min_price)
                    if min_price_decimal < 0:
                        return Response(
                            {'error': 'Minimum price cannot be negative.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    queryset = queryset.filter(base_price__gte=min_price_decimal)
                except (ValueError, InvalidOperation):
                    return Response(
                        {'error': 'Invalid value for "min_price". Must be a valid number.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            if max_price is not None:
                try:
                    max_price_decimal = Decimal(max_price)
                    if max_price_decimal < 0:
                        return Response(
                            {'error': 'Maximum price cannot be negative.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    queryset = queryset.filter(base_price__lte=max_price_decimal)
                except (ValueError, InvalidOperation):
                    return Response(
                        {'error': 'Invalid value for "max_price". Must be a valid number.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Validate min_price <= max_price
            if min_price is not None and max_price is not None:
                try:
                    if Decimal(min_price) > Decimal(max_price):
                        return Response(
                            {'error': 'Minimum price cannot be greater than maximum price.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                except (ValueError, InvalidOperation):
                    pass  # Already handled above
            
            # Filter by minimum rating
            min_rating = request.query_params.get('min_rating')
            if min_rating is not None:
                try:
                    min_rating_decimal = Decimal(min_rating)
                    if min_rating_decimal < 0 or min_rating_decimal > 5:
                        return Response(
                            {'error': 'Minimum rating must be between 0 and 5.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    queryset = queryset.filter(rating_average__gte=min_rating_decimal)
                except (ValueError, InvalidOperation):
                    return Response(
                        {'error': 'Invalid value for "min_rating". Must be a valid number.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Filter by university (case-insensitive partial match)
            university = request.query_params.get('university')
            if university:
                queryset = queryset.filter(provider__university_name__icontains=university)
            
            # ================================================================
            # Sorting
            # ================================================================
            
            ordering = request.query_params.get('ordering', None)
            
            # Define valid ordering fields
            valid_orderings = {
                'price': 'base_price',
                '-price': '-base_price',
                'rating': '-rating_average',  # Higher ratings first
                '-rating': '-rating_average',  # Explicit descending
                'date': '-created_at',  # Newest first
                '-date': '-created_at',  # Explicit descending
            }
            
            if ordering:
                if ordering not in valid_orderings:
                    return Response(
                        {
                            'error': f'Invalid ordering field "{ordering}". Valid options: {", ".join(valid_orderings.keys())}'
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
                queryset = queryset.order_by(valid_orderings[ordering])
            else:
                # Default sorting: rating (desc) then price (asc)
                queryset = queryset.order_by('-rating_average', 'base_price')
            
            # ================================================================
            # Pagination
            # ================================================================
            
            # Get page size from query params (default: 20, max: 100)
            try:
                page_size = int(request.query_params.get('page_size', 20))
                if page_size < 1:
                    page_size = 20
                elif page_size > 100:
                    page_size = 100
            except ValueError:
                page_size = 20
            
            # Get page number
            try:
                page_number = int(request.query_params.get('page', 1))
                if page_number < 1:
                    page_number = 1
            except ValueError:
                page_number = 1
            
            # Create paginator
            paginator = Paginator(queryset, page_size)
            
            try:
                page_obj = paginator.page(page_number)
            except EmptyPage:
                return Response(
                    {'error': f'Invalid page number. Page {page_number} does not exist.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Serialize the results
            serializer = ServiceListSerializer(
                page_obj.object_list,
                many=True,
                context={'request': request}
            )
            
            # Build pagination response
            response_data = {
                'count': paginator.count,
                'next': None,
                'previous': None,
                'results': serializer.data
            }
            
            # Add next page URL
            if page_obj.has_next():
                next_page = page_obj.next_page_number()
                response_data['next'] = request.build_absolute_uri(
                    f"{request.path}?page={next_page}&page_size={page_size}"
                )
            
            # Add previous page URL
            if page_obj.has_previous():
                prev_page = page_obj.previous_page_number()
                response_data['previous'] = request.build_absolute_uri(
                    f"{request.path}?page={prev_page}&page_size={page_size}"
                )
            
            logger.info(
                f"Service listing retrieved: {len(serializer.data)} services on page {page_number}"
            )
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in service listing: {str(e)}")
            return Response(
                {'error': 'An error occurred while retrieving services.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # Disallow other HTTP methods
    def post(self, request, *args, **kwargs):
        """POST method not allowed for listing endpoint."""
        return Response(
            {'error': 'Method not allowed. Use POST on /api/services/ for service creation.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def put(self, request, *args, **kwargs):
        """PUT method not allowed."""
        return Response(
            {'error': 'Method not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def patch(self, request, *args, **kwargs):
        """PATCH method not allowed."""
        return Response(
            {'error': 'Method not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def delete(self, request, *args, **kwargs):
        """DELETE method not allowed."""
        return Response(
            {'error': 'Method not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


# ============================================================================
# Service Detail View
# ============================================================================

class ServiceDetailView(generics.RetrieveAPIView):
    """
    API endpoint for retrieving detailed information about a single moving service.
    
    Public endpoint - no authentication required.
    
    Features:
    - Public access (AllowAny permission)
    - Complete service information
    - Detailed provider information with rating summary
    - Recent reviews (limited to 10 most recent)
    - Service-specific rating statistics
    - Rating distribution (count of each star rating)
    - Query optimization with select_related and prefetch_related
    
    URL Pattern:
    - GET /api/services/<id>/
    
    Returns:
    - 200 OK: Complete service details with nested provider and reviews
    - 404 Not Found: Service with given ID doesn't exist
    
    Response Structure:
    {
        "id": 1,
        "service_name": "Premium Moving Service",
        "description": "Professional moving service...",
        "base_price": "150.00",
        "availability_status": true,
        "created_at": "2025-12-07T12:00:00Z",
        "updated_at": "2025-12-07T12:00:00Z",
        "provider": {
            "id": 1,
            "email": "provider@example.com",
            "phone_number": "+1234567890",
            "university_name": "Test University",
            "is_verified": true,
            "profile_image_url": "http://...",
            "provider_rating_average": "4.50"
        },
        "recent_reviews": [
            {
                "id": 1,
                "reviewer_name": "student@example.com",
                "rating": 5,
                "comment": "Excellent service!",
                "created_at": "2025-12-07T10:00:00Z"
            }
        ],
        "rating_average": "4.50",
        "total_reviews": 10,
        "rating_distribution": {
            "1": 0,
            "2": 1,
            "3": 2,
            "4": 3,
            "5": 4
        }
    }
    """
    
    permission_classes = [AllowAny]
    lookup_field = 'pk'
    
    def get_serializer_class(self):
        """Return the serializer class for service detail."""
        from core.serializers import ServiceDetailSerializer
        return ServiceDetailSerializer
    
    def get_queryset(self):
        """
        Get queryset with optimized query loading.
        
        Optimizations:
        - select_related('provider'): Fetch provider in single query
        - prefetch_related('bookings__review'): Prefetch reviews through bookings
        - This prevents N+1 query problems
        
        Returns:
            QuerySet: Optimized MovingService queryset
        """
        from core.models import MovingService, Review
        from django.db.models import Prefetch
        
        # Optimize queries to prevent N+1 problems
        queryset = MovingService.objects.select_related(
            'provider'  # Fetch provider in single query (ForeignKey)
        ).prefetch_related(
            # Prefetch reviews through bookings
            Prefetch(
                'bookings__review',
                queryset=Review.objects.select_related('reviewer').order_by('-created_at')
            )
        )
        
        return queryset
    
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve service detail with comprehensive error handling.
        
        Args:
            request: HTTP request
            *args: Positional arguments
            **kwargs: Keyword arguments (includes 'pk')
            
        Returns:
            Response: Service detail data or error
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, context={'request': request})
            
            logger.info(
                f"Service detail retrieved: Service ID {instance.id}, "
                f"Service Name: {instance.service_name}"
            )
            
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            # Log unexpected errors
            logger.error(
                f"Error retrieving service detail: {str(e)}, "
                f"Service ID: {kwargs.get('pk', 'unknown')}"
            )
            # Re-raise to let DRF handle it (will return 404 for DoesNotExist)
            raise


# ============================================================================
# Booking Creation View
# ============================================================================

class BookingCreateView(APIView):
    """
    API endpoint for creating bookings.
    
    Security features:
    - Requires JWT authentication (IsAuthenticated)
    - Requires student user type (IsStudent)
    - Prevents self-booking (user cannot book their own service)
    - Validates booking date is in future (minimum 1 hour advance)
    - Prevents double-booking with database-level locking
    - Uses transaction.atomic() and select_for_update() for race condition prevention
    
    POST /api/bookings/
    Headers: Authorization: Bearer <access_token>
    Request body: {
        "service": 1,
        "booking_date": "2025-12-10T14:00:00Z",
        "pickup_location": "123 Main St, Test City",
        "dropoff_location": "456 Oak Ave, Test City"
    }
    
    Success response (201):
    {
        "id": 1,
        "service": 1,
        "booking_date": "2025-12-10T14:00:00Z",
        "pickup_location": "123 Main St, Test City",
        "dropoff_location": "456 Oak Ave, Test City",
        "student": 1,
        "provider": {
            "id": 2,
            "email": "provider@example.com",
            "university_name": "Test University",
            "is_verified": true
        },
        "status": "pending",
        "total_price": "100.00",
        "created_at": "2025-12-07T16:00:00Z",
        "updated_at": "2025-12-07T16:00:00Z"
    }
    
    Error responses:
    - 401: Missing, invalid, or expired JWT token
    - 403: Non-student attempting to create booking
    - 400: Invalid data (validation errors, self-booking, unavailable service)
    - 409: Conflict (provider already booked at requested time)
    - 405: Method not allowed (only POST supported)
    """
    permission_classes = [AllowAny]  # Will check manually for better error messages
    
    def get_client_ip(self, request):
        """
        Get client IP address from request.
        Handles proxy headers for accurate IP detection.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def post(self, request, *args, **kwargs):
        """
        Handle booking creation request with conflict detection.
        
        Steps:
        1. Verify user is authenticated
        2. Verify user is a student
        3. Validate request data
        4. Check for booking conflicts (with database locking)
        5. Create booking
        6. Log creation action
        7. Return created booking details
        """
        from datetime import timedelta
        from django.db import transaction
        from django.utils import timezone
        from core.models import Booking
        from core.serializers import BookingCreateSerializer
        from core.permissions import IsStudent
        
        # Step 1: Check authentication
        if not request.user or not request.user.is_authenticated:
            return Response(
                {'detail': 'Authentication credentials were not provided.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Step 2: Check if user is a student
        permission = IsStudent()
        
        if not permission.has_permission(request, self):
            logger.warning(
                f"Non-student user attempted booking creation. "
                f"User: {request.user.email}, User Type: {getattr(request.user, 'user_type', 'unknown')}, "
                f"IP: {self.get_client_ip(request)}"
            )
            return Response(
                {'detail': 'Only students can create bookings.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Step 3: Validate request data
        serializer = BookingCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Step 4 & 5: Check for conflicts and create booking atomically
        # Use transaction.atomic() to ensure atomicity
        # Use select_for_update() to lock provider's bookings and prevent race conditions
        try:
            with transaction.atomic():
                # Get validated data
                service = serializer.validated_data['service']
                booking_date = serializer.validated_data['booking_date']
                provider = service.provider
                
                # Define conflict window (2 hours before and after)
                # This assumes each booking takes approximately 2 hours
                conflict_window_hours = 2
                conflict_start = booking_date - timedelta(hours=conflict_window_hours)
                conflict_end = booking_date + timedelta(hours=conflict_window_hours)
                
                # Lock provider's bookings to prevent concurrent modifications
                # select_for_update() acquires a database-level lock on these rows
                # Other transactions will wait until this transaction completes
                conflicting_bookings = Booking.objects.select_for_update().filter(
                    provider=provider,
                    booking_date__gte=conflict_start,
                    booking_date__lt=conflict_end,
                    status__in=['pending', 'confirmed']  # Only check active bookings
                )
                
                # Check if there are any conflicting bookings
                if conflicting_bookings.exists():
                    conflict_booking = conflicting_bookings.first()
                    logger.warning(
                        f"Booking conflict detected. "
                        f"Provider: {provider.email} (ID: {provider.id}), "
                        f"Requested Date: {booking_date}, "
                        f"Conflicting Booking ID: {conflict_booking.id}, "
                        f"Conflicting Date: {conflict_booking.booking_date}, "
                        f"Student: {request.user.email}, "
                        f"IP: {self.get_client_ip(request)}"
                    )
                    return Response(
                        {
                            'detail': 'This provider is already booked during the requested time slot. '
                                     'Please choose a different time or service.'
                        },
                        status=status.HTTP_409_CONFLICT
                    )
                
                # No conflicts - create the booking
                booking = serializer.save()
                
                # Step 6: Log creation action
                logger.info(
                    f"Booking created successfully. "
                    f"Booking ID: {booking.id}, "
                    f"Service: {service.service_name} (ID: {service.id}), "
                    f"Provider: {provider.email} (ID: {provider.id}), "
                    f"Student: {request.user.email} (ID: {request.user.id}), "
                    f"Booking Date: {booking_date}, "
                    f"IP: {self.get_client_ip(request)}"
                )
                
                # Step 7: Return created booking details
                # Re-serialize to include provider information
                response_serializer = BookingCreateSerializer(
                    booking,
                    context={'request': request}
                )
                
                return Response(
                    response_serializer.data,
                    status=status.HTTP_201_CREATED
                )
                
        except Exception as e:
            logger.error(
                f"Error creating booking: {str(e)}, "
                f"User: {request.user.email}, "
                f"IP: {self.get_client_ip(request)}"
            )
            return Response(
                {'detail': 'An error occurred while creating the booking.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get(self, request, *args, **kwargs):
        """GET method not allowed."""
        return Response(
            {'detail': 'Method "GET" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def put(self, request, *args, **kwargs):
        """PUT method not allowed."""
        return Response(
            {'detail': 'Method "PUT" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def patch(self, request, *args, **kwargs):
        """PATCH method not allowed."""
        return Response(
            {'detail': 'Method "PATCH" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def delete(self, request, *args, **kwargs):
        """DELETE method not allowed."""
        return Response(
            {'detail': 'Method "DELETE" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


# ============================================================================
# Booking Status Update View
# ============================================================================

class BookingStatusUpdateView(APIView):
    """
    API endpoint for updating booking status.
    
    Security features:
    - Requires JWT authentication
    - Requires object-level permissions (CanUpdateBookingStatus)
    - Enforces state machine transition rules
    - Validates business logic (completion date)
    - Logs all status changes for audit trail
    - Handles concurrent updates with database locking
    
    PUT /api/bookings/<id>/status/
    Headers: Authorization: Bearer <access_token>
    Request body: {"status": "confirmed"}
    
    Success response (200):
    {
        "id": 1,
        "student": {...},
        "provider": {...},
        "service": {...},
        "booking_date": "2025-12-15T10:00:00Z",
        "pickup_location": "123 Pickup St",
        "dropoff_location": "456 Dropoff Ave",
        "status": "confirmed",
        "total_price": "100.00",
        "created_at": "2025-12-08T10:00:00Z",
        "updated_at": "2025-12-08T14:30:00Z"
    }
    
    Error responses:
    - 401: Missing, invalid, or expired JWT token
    - 403: User doesn't have permission to update this booking
    - 404: Booking not found
    - 400: Invalid status transition or validation error
    """
    permission_classes = [AllowAny]  # Will check manually for better error messages
    
    def get_client_ip(self, request):
        """
        Get client IP address from request.
        Handles proxy headers for accurate IP detection.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def put(self, request, *args, **kwargs):
        """
        Handle booking status update request.
        
        Steps:
        1. Verify user is authenticated
        2. Retrieve booking by ID (404 if not found)
        3. Check object-level permissions (403 if denied)
        4. Validate status transition
        5. Update booking status
        6. Log status change
        7. Return updated booking details
        """
        from django.db import transaction
        from core.models import Booking
        from core.serializers import BookingStatusUpdateSerializer, BookingCreateSerializer
        from core.permissions import CanUpdateBookingStatus
        
        # Step 1: Check authentication
        if not request.user or not request.user.is_authenticated:
            return Response(
                {'detail': 'Authentication credentials were not provided.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Step 2: Retrieve booking
        booking_id = kwargs.get('pk')
        try:
            # Use select_for_update to lock the row for concurrent updates
            with transaction.atomic():
                booking = Booking.objects.select_for_update().select_related(
                    'student', 'provider', 'service'
                ).get(pk=booking_id)
                
                # Step 3: Check object-level permissions
                permission = CanUpdateBookingStatus()
                if not permission.has_object_permission(request, self, booking):
                    logger.warning(
                        f"Unauthorized booking status update attempt. "
                        f"Booking ID: {booking_id}, "
                        f"User: {request.user.email} (ID: {request.user.id}), "
                        f"IP: {self.get_client_ip(request)}"
                    )
                    return Response(
                        {'detail': permission.message},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Step 4 & 5: Validate and update status
                serializer = BookingStatusUpdateSerializer(
                    booking,
                    data=request.data,
                    partial=False
                )
                
                if not serializer.is_valid():
                    return Response(
                        serializer.errors,
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Save the updated booking
                old_status = booking.status
                updated_booking = serializer.save()
                new_status = updated_booking.status
                
                # Step 6: Log status change
                logger.info(
                    f"Booking status updated. "
                    f"Booking ID: {booking_id}, "
                    f"Old Status: {old_status}, "
                    f"New Status: {new_status}, "
                    f"User: {request.user.email} (ID: {request.user.id}), "
                    f"IP: {self.get_client_ip(request)}"
                )
                
                # Step 7: Return updated booking details
                # Use BookingCreateSerializer for complete response
                response_serializer = BookingCreateSerializer(
                    updated_booking,
                    context={'request': request}
                )
                
                return Response(
                    response_serializer.data,
                    status=status.HTTP_200_OK
                )
                
        except Booking.DoesNotExist:
            logger.warning(
                f"Booking status update attempted for non-existent booking. "
                f"Booking ID: {booking_id}, "
                f"User: {request.user.email} (ID: {request.user.id}), "
                f"IP: {self.get_client_ip(request)}"
            )
            return Response(
                {'detail': f'Booking with ID {booking_id} does not exist.'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def get(self, request, *args, **kwargs):
        """GET method not allowed."""
        return Response(
            {'detail': 'Method "GET" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def post(self, request, *args, **kwargs):
        """POST method not allowed."""
        return Response(
            {'detail': 'Method "POST" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def patch(self, request, *args, **kwargs):
        """PATCH method not allowed."""
        return Response(
            {'detail': 'Method "PATCH" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def delete(self, request, *args, **kwargs):
        """DELETE method not allowed."""
        return Response(
            {'detail': 'Method "DELETE" not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


# ============================================================================
# Booking Calendar View
# ============================================================================

class BookingCalendarView(APIView):
    """
    API endpoint for viewing booking calendar with availability.
    
    Public endpoint - no authentication required (AllowAny).
    
    Features:
    - Date range filtering (required: start_date, end_date)
    - Provider filtering (optional: provider_id)
    - Service filtering (optional: service_id)
    - Status filtering (optional: status, defaults to 'pending,confirmed')
    - Available time slot calculation
    - Query optimization with select_related
    - 90-day maximum date range limit
    
    GET /api/bookings/calendar/
    Query Parameters:
    - start_date (required): Start of date range (YYYY-MM-DD or ISO 8601)
    - end_date (required): End of date range (YYYY-MM-DD or ISO 8601)
    - provider_id (optional): Filter by specific provider
    - service_id (optional): Filter by specific service
    - status (optional): Filter by booking status (comma-separated: pending,confirmed,completed,cancelled)
    
    Returns:
    - 200 OK: Calendar data organized by date
    - 400 Bad Request: Missing or invalid parameters
    """
    
    permission_classes = [AllowAny]
    
    def get(self, request, *args, **kwargs):
        """
        Handle GET request for booking calendar.
        
        Implements date range filtering, provider/service/status filtering,
        and available slot calculation with query optimization.
        """
        from datetime import datetime, timedelta, time
        from django.utils import timezone
        from django.utils.dateparse import parse_date
        from core.models import Booking, User, MovingService
        from collections import defaultdict
        from itertools import groupby
        from operator import attrgetter
        
        try:
            # ================================================================
            # Step 1: Validate and parse date range parameters
            # ================================================================
            
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')
            
            # Check required parameters
            if not start_date_str:
                return Response(
                    {'error': 'start_date parameter is required (format: YYYY-MM-DD)'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not end_date_str:
                return Response(
                    {'error': 'end_date parameter is required (format: YYYY-MM-DD)'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Parse dates
            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)
            
            if not start_date:
                return Response(
                    {'error': f'Invalid start_date format: {start_date_str}. Use YYYY-MM-DD format.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not end_date:
                return Response(
                    {'error': f'Invalid end_date format: {end_date_str}. Use YYYY-MM-DD format.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate date range
            if end_date < start_date:
                return Response(
                    {'error': 'end_date must be greater than or equal to start_date'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Limit date range to 90 days to prevent performance issues
            date_range_days = (end_date - start_date).days + 1
            if date_range_days > 90:
                return Response(
                    {'error': 'Date range cannot exceed 90 days. Please use a smaller date range.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # ================================================================
            # Step 2: Build query with filters
            # ================================================================
            
            # Convert dates to datetime for filtering
            start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
            end_datetime = timezone.make_aware(datetime.combine(end_date, time.max))
            
            # Start with all bookings in date range
            queryset = Booking.objects.filter(
                booking_date__gte=start_datetime,
                booking_date__lte=end_datetime
            )
            
            # Apply provider filter if provided
            provider_id = request.query_params.get('provider_id')
            if provider_id:
                try:
                    provider_id = int(provider_id)
                    # Check if provider exists
                    if not User.objects.filter(id=provider_id, user_type='provider').exists():
                        return Response(
                            {'error': f'Provider with ID {provider_id} does not exist or is not a provider.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    queryset = queryset.filter(provider_id=provider_id)
                except ValueError:
                    return Response(
                        {'error': 'provider_id must be a valid integer'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Apply service filter if provided
            service_id = request.query_params.get('service_id')
            if service_id:
                try:
                    service_id = int(service_id)
                    # Check if service exists
                    if not MovingService.objects.filter(id=service_id).exists():
                        return Response(
                            {'error': f'Service with ID {service_id} does not exist.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    queryset = queryset.filter(service_id=service_id)
                except ValueError:
                    return Response(
                        {'error': 'service_id must be a valid integer'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Apply status filter (default to active bookings: pending, confirmed)
            status_filter = request.query_params.get('status', 'pending,confirmed')
            if status_filter:
                # Parse comma-separated status values
                status_list = [s.strip() for s in status_filter.split(',')]
                # Validate status values
                valid_statuses = ['pending', 'confirmed', 'completed', 'cancelled']
                invalid_statuses = [s for s in status_list if s not in valid_statuses]
                if invalid_statuses:
                    return Response(
                        {'error': f'Invalid status values: {", ".join(invalid_statuses)}. Valid options: {", ".join(valid_statuses)}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                queryset = queryset.filter(status__in=status_list)
            
            # Optimize query with select_related to prevent N+1 queries
            queryset = queryset.select_related('service', 'student', 'provider').order_by('booking_date')
            
            # ================================================================
            # Step 3: Organize bookings by date
            # ================================================================
            
            # Group bookings by date
            bookings_by_date = defaultdict(list)
            for booking in queryset:
                booking_date = booking.booking_date.date()
                bookings_by_date[booking_date].append(booking)
            
            # ================================================================
            # Step 4: Calculate available slots for each day
            # ================================================================
            
            def calculate_available_slots(date, bookings):
                """
                Calculate available time slots for a given date.
                
                Business hours: 8 AM - 6 PM
                Booking window: 2 hours
                Slots: 8-10, 10-12, 12-14, 14-16, 16-18
                
                Args:
                    date: Date to calculate slots for
                    bookings: List of bookings for that date
                    
                Returns:
                    tuple: (available_slots list, is_fully_booked boolean)
                """
                # Define business hours and slot duration
                business_start = 8  # 8 AM
                business_end = 18   # 6 PM
                slot_duration = 2   # 2 hours
                
                # Generate all possible slots
                all_slots = []
                current_hour = business_start
                while current_hour + slot_duration <= business_end:
                    slot_start = f"{current_hour:02d}:00"
                    slot_end = f"{(current_hour + slot_duration):02d}:00"
                    all_slots.append(f"{slot_start} - {slot_end}")
                    current_hour += slot_duration
                
                # Determine which slots are occupied
                occupied_slots = set()
                for booking in bookings:
                    booking_hour = booking.booking_date.hour
                    # Find which slot this booking falls into
                    for i, slot_hour in enumerate(range(business_start, business_end, slot_duration)):
                        if slot_hour <= booking_hour < slot_hour + slot_duration:
                            occupied_slots.add(all_slots[i])
                            break
                
                # Calculate available slots
                available_slots = [slot for slot in all_slots if slot not in occupied_slots]
                is_fully_booked = len(available_slots) == 0
                
                return available_slots, is_fully_booked
            
            # ================================================================
            # Step 5: Build calendar response
            # ================================================================
            
            # Generate all dates in range
            days_data = []
            current_date = start_date
            while current_date <= end_date:
                date_bookings = bookings_by_date.get(current_date, [])
                available_slots, is_fully_booked = calculate_available_slots(current_date, date_bookings)
                
                days_data.append({
                    'date': current_date,
                    'bookings': date_bookings,
                    'available_slots': available_slots,
                    'is_fully_booked': is_fully_booked
                })
                
                current_date += timedelta(days=1)
            
            # ================================================================
            # Step 6: Serialize and return response
            # ================================================================
            
            from core.serializers import CalendarResponseSerializer
            
            response_data = {
                'start_date': start_date,
                'end_date': end_date,
                'provider_id': int(provider_id) if provider_id else None,
                'service_id': int(service_id) if service_id else None,
                'status_filter': status_filter,
                'days': days_data
            }
            
            serializer = CalendarResponseSerializer(response_data)
            
            logger.info(
                f"Calendar retrieved: {start_date} to {end_date}, "
                f"Provider: {provider_id or 'all'}, "
                f"Service: {service_id or 'all'}, "
                f"Status: {status_filter}, "
                f"Total bookings: {queryset.count()}"
            )
            
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in calendar view: {str(e)}")
            return Response(
                {'error': 'An error occurred while retrieving calendar data.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, *args, **kwargs):
        """POST method not allowed."""
        return Response(
            {'error': 'Method not allowed. Use GET to retrieve calendar.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def put(self, request, *args, **kwargs):
        """PUT method not allowed."""
        return Response(
            {'error': 'Method not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def patch(self, request, *args, **kwargs):
        """PATCH method not allowed."""
        return Response(
            {'error': 'Method not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def delete(self, request, *args, **kwargs):
        """DELETE method not allowed."""
        return Response(
            {'error': 'Method not allowed.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
