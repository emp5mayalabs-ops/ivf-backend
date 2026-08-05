from django.urls import path
from .views import (
    AndrologistLoginView,
    AndrologistLogoutView,
    AndrologistProfileView,
    AndrologistChangePasswordView,
    AndrologistHeartbeatView,
)

urlpatterns = [
    path('login/', AndrologistLoginView.as_view(), name='andrologist_login'),
    path('logout/', AndrologistLogoutView.as_view(), name='andrologist_logout'),
    path('profile/', AndrologistProfileView.as_view(), name='andrologist_profile'),
    path('change-password/', AndrologistChangePasswordView.as_view(), name='andrologist_change_password'),
    path('heartbeat/', AndrologistHeartbeatView.as_view(), name='andrologist_heartbeat'),
]