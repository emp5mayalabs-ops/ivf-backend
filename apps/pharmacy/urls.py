# apps/pharmacy/urls.py
from django.urls import path
from .views import (
    PharmacistLoginView,
    PharmacistLogoutView,
    PharmacistProfileView,
    InventoryAPIView,
    StockAdjustmentAPIView,
    InventoryAlertsAPIView,
    DismissAlertAPIView,
    InventorySummaryAPIView,
    MedicationCategoriesAPIView,
    MedicationManufacturersAPIView,
)

app_name = 'pharmacy'

urlpatterns = [
    # ========== AUTH ==========
    path('login/', PharmacistLoginView.as_view(), name='login'),
    path('logout/', PharmacistLogoutView.as_view(), name='logout'),
    path('profile/', PharmacistProfileView.as_view(), name='profile'),
    
    # ========== INVENTORY - MINIMAL API ==========
    path('inventory/', InventoryAPIView.as_view(), name='inventory-list'),
    path('inventory/<int:id>/', InventoryAPIView.as_view(), name='inventory-detail'),
    
    # ========== STOCK ADJUSTMENTS ==========
    path('inventory/<int:medication_id>/adjust/', StockAdjustmentAPIView.as_view(), name='stock-adjust'),
    path('inventory/adjustments/', StockAdjustmentAPIView.as_view(), name='stock-adjustments'),
    path('inventory/<int:medication_id>/adjustments/', StockAdjustmentAPIView.as_view(), name='medication-adjustments'),
    
    # ========== ALERTS ==========
    path('inventory/alerts/', InventoryAlertsAPIView.as_view(), name='alerts'),
    path('inventory/alerts/<int:alert_id>/dismiss/', DismissAlertAPIView.as_view(), name='dismiss-alert'),
    
    # ========== SUMMARY ==========
    path('inventory/summary/', InventorySummaryAPIView.as_view(), name='inventory-summary'),
    
    # ========== CATEGORIES & MANUFACTURERS ==========
    path('inventory/categories/', MedicationCategoriesAPIView.as_view(), name='categories'),
    path('inventory/manufacturers/', MedicationManufacturersAPIView.as_view(), name='manufacturers'),
]