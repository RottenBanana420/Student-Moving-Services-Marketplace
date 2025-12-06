"""
Custom views for Student Moving Services Marketplace.
"""

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import IntegrityError
from .serializers import EmailTokenObtainPairSerializer, UserRegistrationSerializer


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
