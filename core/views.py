"""
Custom views for Student Moving Services Marketplace.
"""

import logging
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from .serializers import EmailTokenObtainPairSerializer, UserRegistrationSerializer, LoginSerializer

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
