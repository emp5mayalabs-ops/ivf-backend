# apps/attendance/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # ===== STAFF APIs (All Staff) =====
    path('my/', views.MyAttendanceView.as_view(), name='my-attendance'),
    path('mark/', views.MarkMyAttendanceView.as_view(), name='mark-attendance'),
    path('history/', views.MyAttendanceHistoryView.as_view(), name='my-history'),
    path('stats/', views.MyAttendanceStatsView.as_view(), name='my-stats'),
    
    # ===== HR ADMIN APIs =====
    path('admin/dashboard/', views.AdminAttendanceDashboardView.as_view(), name='admin-dashboard'),
    path('admin/all/', views.AdminAllAttendanceView.as_view(), name='admin-all'),
    path('admin/mark/', views.AdminMarkAttendanceView.as_view(), name='admin-mark'),
    path('admin/<int:pk>/', views.AdminAttendanceDetailView.as_view(), name='admin-detail'),
    path('admin/bulk/', views.AdminBulkAttendanceView.as_view(), name='admin-bulk'),
    path('admin/staff/<int:user_id>/', views.AdminStaffAttendanceView.as_view(), name='admin-staff'),
]