# apps/nurse/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    NurseLoginView,
    NurseLogoutView,
    NurseProfileView,
    NurseProfileDetailView,
    NurseViewSet,
    PatientVitalViewSet
)

# Router for ViewSets
router = DefaultRouter()
router.register(r'list', NurseViewSet, basename='nurse')
router.register(r'vitals', PatientVitalViewSet, basename='vitals')

urlpatterns = [
    # Authentication
    path('login/', NurseLoginView.as_view(), name='nurse_login'),
    path('logout/', NurseLogoutView.as_view(), name='nurse_logout'),
    
    # Profile
    path('profile/', NurseProfileView.as_view(), name='nurse_profile'),
    path('profile/<int:nurse_id>/', NurseProfileDetailView.as_view(), name='nurse_profile_detail'),
    
    # ViewSet routes
    path('', include(router.urls)),
]