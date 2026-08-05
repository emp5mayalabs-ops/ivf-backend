# apps/pharmacy/urls.py - COMPLETE WITH PRESCRIPTION FULFILLMENT URLs

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
    PharmacyDashboardAPIView,
    DashboardSummaryAPIView,
    # NEW: Import prescription views
    PrescriptionOrdersView,
    ReceivePrescriptionView,
    FulfillPrescriptionView,
    PrescriptionOrderStatsView,
    PharmacyBillListView,
    PharmacyBillDetailView,
    PharmacyPaymentView,
    PharmacyBillingDashboardView,
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

    # ========== DASHBOARD ==========
    path('dashboard/', PharmacyDashboardAPIView.as_view(), name='pharmacy_dashboard'),
    path('dashboard/summary/', DashboardSummaryAPIView.as_view(), name='dashboard_summary'),
    
    # ========== PRESCRIPTION FULFILLMENT (NEW) ==========
    path('prescriptions/', PrescriptionOrdersView.as_view(), name='prescription-orders'),
    path('prescriptions/<int:id>/', PrescriptionOrdersView.as_view(), name='prescription-order-detail'),
    path('prescriptions/receive/', ReceivePrescriptionView.as_view(), name='receive-prescription'),
    path('prescriptions/<int:order_id>/fulfill/', FulfillPrescriptionView.as_view(), name='fulfill-prescription'),
    path('prescriptions/stats/', PrescriptionOrderStatsView.as_view(), name='prescription-stats'),

    # ========== BILLING ==========
    path('bills/', PharmacyBillListView.as_view(), name='bill-list'),
    path('bills/<int:pk>/', PharmacyBillDetailView.as_view(), name='bill-detail'),
    path('bills/<int:pk>/pay/', PharmacyPaymentView.as_view(), name='bill-pay'),
    path('billing/dashboard/', PharmacyBillingDashboardView.as_view(), name='billing-dashboard'),
]