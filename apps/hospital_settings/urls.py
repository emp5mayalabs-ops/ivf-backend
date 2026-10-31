# apps/hospital_settings/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HospitalSettingsViewSet

router = DefaultRouter()
router.register(r'settings', HospitalSettingsViewSet, basename='hospital-settings')

urlpatterns = [
    path('', include(router.urls)),
]