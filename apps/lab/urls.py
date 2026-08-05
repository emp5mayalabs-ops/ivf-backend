from django.urls import path
from .views import (
    LabLoginView,
    LabLogoutView,
    LabProfileView,
    LabProfileDetailView,
    LabTestTypeListView,
    LabTestTypeDetailView,
    LabRecordListView,
    LabRecordDetailView,
    LabRecordsByPatientView,
    LabStatisticsView,
    LabOrderCreateView,
    LabOrderListView,
    LabOrderDetailView,
    LabOrderCancelView,
)

urlpatterns = [
    # Authentication
    path('login/', LabLoginView.as_view(), name='lab_login'),
    path('logout/', LabLogoutView.as_view(), name='lab_logout'),
    
    # Profile (current user)
    path('profile/', LabProfileView.as_view(), name='lab_profile'),
    
    # Profile by ID (admin only)
    path('profile/<int:lab_id>/', LabProfileDetailView.as_view(), name='lab_profile_detail'),
    
    # ========== NEW DYNAMIC LAB TEST APIs ==========
    
    # Test Types (Dynamic Tests)
    path('test-types/', LabTestTypeListView.as_view(), name='lab_test_types'),
    path('test-types/<int:test_type_id>/', LabTestTypeDetailView.as_view(), name='lab_test_type_detail'),
    
    # Lab Records
    path('records/', LabRecordListView.as_view(), name='lab_records'),
    path('records/<int:record_id>/', LabRecordDetailView.as_view(), name='lab_record_detail'),
    path('records/patient/<int:patient_id>/', LabRecordsByPatientView.as_view(), name='lab_records_patient'),
    
    # Statistics
    path('statistics/', LabStatisticsView.as_view(), name='lab_statistics'),

        # ========== LAB ORDER URLS (Doctor-Lab Integration) ==========
    path('orders/', LabOrderListView.as_view(), name='lab-orders-list'),
    path('orders/create/', LabOrderCreateView.as_view(), name='lab-order-create'),
    path('orders/<int:order_id>/', LabOrderDetailView.as_view(), name='lab-order-detail'),
    path('orders/<int:order_id>/cancel/', LabOrderCancelView.as_view(), name='lab-order-cancel'),
]