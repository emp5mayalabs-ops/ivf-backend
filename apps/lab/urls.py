# apps/lab/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.LabLoginView.as_view(), name='lab-login'),
    path('logout/', views.LabLogoutView.as_view(), name='lab-logout'),
]