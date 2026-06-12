from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import HRManagerProfile, LeaveRequest
from accounts.models import User


class HRLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        user = authenticate(username=email, password=password)
        
        if not user:
            raise serializers.ValidationError("Invalid email or password")
        if user.role != 'HRM':
            raise serializers.ValidationError("HR access only")
        if not user.is_active:
            raise serializers.ValidationError("Account inactive")
        
        data['user'] = user
        return data


class HRProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = HRManagerProfile
        fields = ['id', 'employee_id', 'name', 'email', 'contact_number',
                  'managed_depts', 'can_approve_leaves', 'can_view_salaries',
                  'can_terminate_staff', 'is_department_head', 'is_active']


class StaffListSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='full_name', read_only=True)
    role_name = serializers.CharField(source='get_role_display', read_only=True)
    department = serializers.SerializerMethodField()
    employee_id = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'role', 'role_name', 'is_active', 
                  'date_joined', 'department', 'employee_id']
    
    def get_department(self, obj):
        assign = obj.staff_assignments.filter(is_active=True, role_in_dept='PRIMARY').first()
        return assign.department.name if assign else None
    
    def get_employee_id(self, obj):
        if obj.role == 'HRM' and hasattr(obj, 'hr_profile'):
            return obj.hr_profile.employee_id
        return None


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    leave_type_name = serializers.CharField(source='get_leave_type_display', read_only=True)
    status_name = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = LeaveRequest
        fields = ['id', 'employee', 'employee_name', 'leave_type', 'leave_type_name',
                  'start_date', 'end_date', 'reason', 'status', 'status_name',
                  'created_at']
        read_only_fields = ['id', 'created_at']