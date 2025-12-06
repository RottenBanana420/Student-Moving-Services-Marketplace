"""
Custom JWT serializers for email-based authentication.
"""

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom serializer to use email instead of username for authentication.
    """
    username_field = 'email'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove username field and ensure email field exists
        if 'username' in self.fields:
            del self.fields['username']
        if 'email' not in self.fields:
            self.fields['email'] = serializers.EmailField()

