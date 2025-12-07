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


