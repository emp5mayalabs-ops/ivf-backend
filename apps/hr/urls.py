from django.urls import path
from .views import (
    HRLoginView, HRDashboardView, StaffManagementView,
    LeaveManagementView, HRProfileView,
    HRLeaveStatisticsView, HRLeaveTrendView, HRAddStaffView,
    HRChangePasswordView,
    # Shift Management Views
    HRShiftManagementView, HRShiftAssignmentView, HRBulkShiftAssignmentView,
    HRShiftSwapApprovalView, HRShiftAttendanceView, HRShiftDashboardView,
    HolidayManagementView, LeaveBalanceManagementView
)

urlpatterns = [
    # ========== AUTHENTICATION ==========
    path('login/', HRLoginView.as_view(), name='hr_login'),
    path('profile/', HRProfileView.as_view(), name='hr_profile'),
    path('change-password/', HRChangePasswordView.as_view(), name='hr_change_password'),
    
    # ========== DASHBOARD ==========
    path('dashboard/', HRDashboardView.as_view(), name='hr_dashboard'),
    path('dashboard/shift/', HRShiftDashboardView.as_view(), name='hr_shift_dashboard'),
    
    # ========== STAFF MANAGEMENT ==========
    path('staff/', StaffManagementView.as_view(), name='hr_staff'),
    path('staff/add/', HRAddStaffView.as_view(), name='hr_add_staff'),
    
    # ========== LEAVE MANAGEMENT ==========
    path('leaves/', LeaveManagementView.as_view(), name='hr_leaves'),
    path('leaves/<int:leave_id>/', LeaveManagementView.as_view(), name='hr_leave_action'),
    path('leave-statistics/', HRLeaveStatisticsView.as_view(), name='hr_leave_statistics'),
    path('leave-trend/', HRLeaveTrendView.as_view(), name='hr_leave_trend'),
    
    # ========== SHIFT MANAGEMENT ==========
    # Shift CRUD - IMPORTANT: Specific paths must come BEFORE parameterized paths
    path('shifts/bulk/', HRBulkShiftAssignmentView.as_view(), name='hr_shifts_bulk'),  # Bulk assign
    path('shifts/', HRShiftManagementView.as_view(), name='hr_shifts'),  # List/Create
    path('shifts/<int:shift_id>/', HRShiftManagementView.as_view(), name='hr_shift_detail'),  # Get/Update/Delete
    
    # Shift Assignments
    path('shift-assignments/bulk/', HRBulkShiftAssignmentView.as_view(), name='hr_shift_assignments_bulk'),
    path('shift-assignments/', HRShiftAssignmentView.as_view(), name='hr_shift_assignments'),
    path('shift-assignments/<int:assignment_id>/', HRShiftAssignmentView.as_view(), name='hr_shift_assignment_delete'),
    
    # Shift Swaps
    path('shift-swaps/', HRShiftSwapApprovalView.as_view(), name='hr_shift_swaps'),
    path('shift-swaps/<int:swap_id>/', HRShiftSwapApprovalView.as_view(), name='hr_shift_swap_decision'),
    
    # Shift Attendance
    path('shift-attendance/', HRShiftAttendanceView.as_view(), name='hr_shift_attendance'),
    
    # ========== HOLIDAY MANAGEMENT ==========
    path('holidays/', HolidayManagementView.as_view(), name='hr_holidays'),
    path('holidays/<int:holiday_id>/', HolidayManagementView.as_view(), name='hr_holiday_delete'),
    
    # ========== LEAVE BALANCE MANAGEMENT ==========
    path('leave-balances/', LeaveBalanceManagementView.as_view(), name='hr_leave_balances'),
]