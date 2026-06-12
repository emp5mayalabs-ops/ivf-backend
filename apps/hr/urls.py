from django.urls import path
from .views import (
    HRLoginView, HRDashboardView, StaffManagementView,
    LeaveManagementView, HRProfileView,
    HRLeaveStatisticsView, HRLeaveTrendView,HRAddStaffView,
    HRChangePasswordView
)

urlpatterns = [
    path('login/', HRLoginView.as_view(), name='hr_login'),
    path('dashboard/', HRDashboardView.as_view(), name='hr_dashboard'),
    path('staff/', StaffManagementView.as_view(), name='hr_staff'),
    path('leaves/', LeaveManagementView.as_view(), name='hr_leaves'),
    path('leaves/<int:leave_id>/', LeaveManagementView.as_view(), name='hr_leave_action'),
    path('profile/', HRProfileView.as_view(), name='hr_profile'),
    path('change-password/', HRChangePasswordView.as_view(), name='hr_change_password'),

    # New statistics URLs
    path('leave-statistics/', HRLeaveStatisticsView.as_view(), name='hr_leave_statistics'),
    path('leave-trend/', HRLeaveTrendView.as_view(), name='hr_leave_trend'),

    path('staff/add/', HRAddStaffView.as_view(), name='hr_add_staff'),
]