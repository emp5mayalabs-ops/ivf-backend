# lab/urls.py - Complete with Billing URLs

from django.urls import path
from .views import (
    # Auth views
    LabLoginView,
    LabLogoutView,
    
    # Profile views
    LabProfileView,
    LabProfileDetailView,
    
    # Test Type views
    LabTestTypeListView,
    LabTestTypeDetailView,
    
    # Record views
    LabRecordListView,
    LabRecordDetailView,
    LabRecordsByPatientView,
    
    # Statistics views
    LabStatisticsView,
    
    # Order views (Doctor-Lab Integration)
    LabOrderCreateView,
    LabOrderListView,
    LabOrderDetailView,
    LabOrderCancelView,
    
    # 🆕 Billing views
    LabBillListView,
    LabBillDetailView,
    LabPaymentView,
    LabBillingDashboardView,
    LabBillByRecordView,
    LabBillByPatientView,
)

urlpatterns = [
    # ========== AUTHENTICATION ==========
    path('login/', LabLoginView.as_view(), name='lab_login'),
    path('logout/', LabLogoutView.as_view(), name='lab_logout'),
    
    # ========== PROFILE ==========
    path('profile/', LabProfileView.as_view(), name='lab_profile'),
    path('profile/<int:lab_id>/', LabProfileDetailView.as_view(), name='lab_profile_detail'),
    
    # ========== TEST TYPES ==========
    path('test-types/', LabTestTypeListView.as_view(), name='lab_test_types'),
    path('test-types/<int:test_type_id>/', LabTestTypeDetailView.as_view(), name='lab_test_type_detail'),
    
    # ========== LAB RECORDS ==========
    path('records/', LabRecordListView.as_view(), name='lab_records'),
    path('records/<int:record_id>/', LabRecordDetailView.as_view(), name='lab_record_detail'),
    path('records/patient/<int:patient_id>/', LabRecordsByPatientView.as_view(), name='lab_records_patient'),
    
    # ========== STATISTICS ==========
    path('statistics/', LabStatisticsView.as_view(), name='lab_statistics'),
    
    # ========== LAB ORDERS (Doctor-Lab Integration) ==========
    path('orders/', LabOrderListView.as_view(), name='lab-orders-list'),
    path('orders/create/', LabOrderCreateView.as_view(), name='lab-order-create'),
    path('orders/<int:order_id>/', LabOrderDetailView.as_view(), name='lab-order-detail'),
    path('orders/<int:order_id>/cancel/', LabOrderCancelView.as_view(), name='lab-order-cancel'),
    
    # ========== 🆕 LAB BILLING ==========
    # Bills
    path('bills/', LabBillListView.as_view(), name='lab-bill-list'),
    path('bills/<int:pk>/', LabBillDetailView.as_view(), name='lab-bill-detail'),
    path('bills/<int:pk>/pay/', LabPaymentView.as_view(), name='lab-bill-pay'),
    
    # Billing Dashboard
    path('billing/dashboard/', LabBillingDashboardView.as_view(), name='lab-billing-dashboard'),
    
    # Bills by Record
    path('bills/by-record/<int:record_id>/', LabBillByRecordView.as_view(), name='lab-bill-by-record'),
    
    # Bills by Patient
    path('bills/patient/<int:patient_id>/', LabBillByPatientView.as_view(), name='lab-bill-by-patient'),
]