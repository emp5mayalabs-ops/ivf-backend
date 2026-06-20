# apps/attendance/admin.py

from django.contrib import admin
from .models import StaffAttendance, AttendanceSettings, AttendanceCorrectionRequest


@admin.register(AttendanceSettings)
class AttendanceSettingsAdmin(admin.ModelAdmin):
    list_display = ['id', 'department', 'work_start_time', 'work_end_time', 'is_active']
    list_filter = ['is_active', 'department']
    search_fields = ['department__name']
    fieldsets = (
        ('Department', {'fields': ('department', 'is_active')}),
        ('Timings', {'fields': ('work_start_time', 'work_end_time')}),
        ('Rules', {'fields': ('late_threshold_minutes', 'self_correction_hours', 'allowed_late_per_month')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    readonly_fields = ['created_at', 'updated_at']


@admin.register(StaffAttendance)
class StaffAttendanceAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'date', 'check_in', 'check_out', 'status', 'total_hours']
    list_filter = ['status', 'date', 'user__role']
    search_fields = ['user__full_name', 'user__email', 'remarks']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at', 'total_hours', 'late_minutes']
    fieldsets = (
        ('Staff', {'fields': ('user', 'date')}),
        ('Timings', {'fields': ('check_in', 'check_out', 'total_hours', 'late_minutes', 'overtime_minutes')}),
        ('Status', {'fields': ('status', 'remarks')}),
        ('Meta', {'fields': ('marked_by', 'shift_assignment', 'created_at', 'updated_at')}),
    )


@admin.register(AttendanceCorrectionRequest)
class AttendanceCorrectionRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'date', 'status', 'created_at']
    list_filter = ['status', 'date']
    search_fields = ['user__full_name', 'reason']
    readonly_fields = ['created_at', 'updated_at', 'approved_at']