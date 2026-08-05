# cryo/urls.py

from django.urls import path
from . import views

app_name = 'cryo'

urlpatterns = [
    # ============================================================
    # DASHBOARD
    # ============================================================
    path('dashboard/', views.CryoDashboardView.as_view(), name='dashboard'),
    path('available-positions/', views.CryoAvailablePositionsView.as_view(), name='available-positions'),
    
    # ============================================================
    # TANKS
    # ============================================================
    path('tanks/', views.CryoTankListView.as_view(), name='tank-list'),
    path('tanks/<int:pk>/', views.CryoTankDetailView.as_view(), name='tank-detail'),
    
    # ============================================================
    # CANISTERS
    # ============================================================
    path('canisters/', views.CryoCanisterListView.as_view(), name='canister-list'),
    path('canisters/<int:pk>/', views.CryoCanisterDetailView.as_view(), name='canister-detail'),
    
    # ============================================================
    # CANES
    # ============================================================
    path('canes/', views.CryoCaneListView.as_view(), name='cane-list'),
    path('canes/<int:pk>/', views.CryoCaneDetailView.as_view(), name='cane-detail'),
    
    # ============================================================
    # GOBLETS
    # ============================================================
    path('goblets/', views.CryoGobletListView.as_view(), name='goblet-list'),
    path('goblets/<int:pk>/', views.CryoGobletDetailView.as_view(), name='goblet-detail'),
    
    # ============================================================
    # STORED SAMPLES
    # ============================================================
    path('samples/', views.CryoStoredSampleListView.as_view(), name='sample-list'),
    path('samples/create/', views.CryoStoredSampleCreateView.as_view(), name='sample-create'),
    path('samples/<int:pk>/', views.CryoStoredSampleDetailView.as_view(), name='sample-detail'),
    path('samples/<int:pk>/update/', views.CryoStoredSampleUpdateView.as_view(), name='sample-update'),
    path('samples/<int:pk>/delete/', views.CryoStoredSampleDeleteView.as_view(), name='sample-delete'),
    path('samples/<int:pk>/thaw/', views.CryoThawSampleView.as_view(), name='sample-thaw'),
]