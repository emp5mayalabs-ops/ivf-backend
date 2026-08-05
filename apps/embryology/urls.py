# embryology/urls.py

from django.urls import path
from . import views

app_name = 'embryology'

urlpatterns = [
    # Authentication
    path('login/', views.EmbryologistLoginView.as_view(), name='login'),
    path('logout/', views.EmbryologistLogoutView.as_view(), name='logout'),
    
    # Profile
    path('profile/', views.EmbryologistProfileView.as_view(), name='profile'),
    path('change-password/', views.EmbryologistChangePasswordView.as_view(), name='change-password'),
    
    # Session
    path('heartbeat/', views.EmbryologistHeartbeatView.as_view(), name='heartbeat'),
]