"""
URL configuration for student_moving_marketplace project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
    TokenBlacklistView,
)
from core.views import (
    EmailTokenObtainPairView,
    UserRegistrationView,
    LoginView,
    CustomTokenRefreshView,
    UserProfileView,
    ProviderVerificationView,
    ServiceCreateView,
    ServiceListView,
    ServiceDetailView,
    BookingCreateView
)


urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Authentication endpoints
    path('api/auth/register/', UserRegistrationView.as_view(), name='user_register'),
    path('api/auth/login/', LoginView.as_view(), name='user_login'),
    path('api/auth/logout/', TokenBlacklistView.as_view(), name='user_logout'),
    path('api/auth/profile/', UserProfileView.as_view(), name='user_profile'),
    path('api/auth/verify-provider/', ProviderVerificationView.as_view(), name='verify_provider'),
    
    # Service endpoints
    path('api/services/list/', ServiceListView.as_view(), name='service_list'),
    path('api/services/<int:pk>/', ServiceDetailView.as_view(), name='service_detail'),
    path('api/services/', ServiceCreateView.as_view(), name='service_create'),
    
    # Booking endpoints
    path('api/bookings/', BookingCreateView.as_view(), name='booking_create'),


    
    # JWT Authentication endpoints
    path('api/token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),  # Custom view with rate limiting
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('api/token/blacklist/', TokenBlacklistView.as_view(), name='token_blacklist'),
]

