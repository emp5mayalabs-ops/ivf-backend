# apps/attendance/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import StaffAttendance, AttendanceSettings, AttendanceCorrectionRequest

User = get_user_model()


class AttendanceSettingsSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = AttendanceSettings
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class StaffAttendanceSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_role = serializers.CharField(source='user.role', read_only=True)
    user_role_display = serializers.CharField(source='user.get_role_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    marked_by_name = serializers.CharField(source='marked_by.full_name', read_only=True)
    day_name = serializers.SerializerMethodField()
    working_hours = serializers.SerializerMethodField()
    
    class Meta:
        model = StaffAttendance
        fields = [
            'id', 'user', 'user_name', 'user_email', 'user_role', 'user_role_display',
            'date', 'day_name', 'check_in', 'check_out', 'status', 'status_display',
            'late_minutes', 'overtime_minutes', 'total_hours', 'working_hours',
            'remarks', 'marked_by', 'marked_by_name',
            'shift_assignment', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'total_hours', 'late_minutes']
    
    def get_day_name(self, obj):
        return obj.date.strftime('%A')
    
    def get_working_hours(self, obj):
        return str(obj.total_hours) if obj.total_hours else '0.00'


class AttendanceCorrectionRequestSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.full_name', read_only=True)
    
    class Meta:
        model = AttendanceCorrectionRequest
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'approved_at', 'approved_by']


class AttendanceStatsSerializer(serializers.Serializer):
    total_days = serializers.IntegerField()
    present = serializers.IntegerField()
    absent = serializers.IntegerField()
    late = serializers.IntegerField()
    on_leave = serializers.IntegerField()
    half_day = serializers.IntegerField()
    work_from_home = serializers.IntegerField()
    attendance_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    total_hours = serializers.DecimalField(max_digits=10, decimal_places=2)


class MonthlyAttendanceSummarySerializer(serializers.Serializer):
    month = serializers.CharField()
    year = serializers.IntegerField()
    total_days = serializers.IntegerField()
    present = serializers.IntegerField()
    absent = serializers.IntegerField()
    late = serializers.IntegerField()
    attendance_rate = serializers.DecimalField(max_digits=5, decimal_places=2)