from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils import timezone
from .models import HRManagerProfile, LeaveRequest, Shift, DoctorShiftAssignment, ShiftSwapRequest, ShiftAttendance, LeaveBalance, Holiday
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
        # HR Manager
        if obj.role == 'HRM' and hasattr(obj, 'hr_profile'):
            return obj.hr_profile.employee_id
        
        # Receptionist
        elif obj.role == 'REC' and hasattr(obj, 'receptionist_profile'):
            return obj.receptionist_profile.employee_id
        
        # Endocrinologist
        elif obj.role == 'END' and hasattr(obj, 'endocrinologist_profile'):
            return obj.endocrinologist_profile.employee_id
        
        # Gynaecologist
        elif obj.role == 'GYN' and hasattr(obj, 'gynaec_profile'):
            return obj.gynaec_profile.employee_id
        
        # Andrologist (Anesthesiologist)
        elif obj.role == 'ANE' and hasattr(obj, 'anesth_profile'):
            return obj.anesth_profile.employee_id
        
        # Nurse
        elif obj.role == 'NUR' and hasattr(obj, 'nurse_profile'):
            return obj.nurse_profile.employee_id
        
        # Lab Technician
        elif obj.role == 'TEC' and hasattr(obj, 'technician_profile'):
            return obj.technician_profile.employee_id
        
        # Admin
        elif obj.role == 'ADM' and hasattr(obj, 'admin_profile'):
            return obj.admin_profile.employee_id
        
        # Pharmacist
        elif obj.role == 'PHA' and hasattr(obj, 'pharmacist_profile'):
            return obj.pharmacist_profile.employee_id
        
        # Clinical Counsellor
        elif obj.role == 'CCO' and hasattr(obj, 'clinical_counsellor_profile'):
            return obj.clinical_counsellor_profile.employee_id
        
        # Financial Counsellor
        elif obj.role == 'FCO' and hasattr(obj, 'financial_counsellor_profile'):
            return obj.financial_counsellor_profile.employee_id
        
        # Embryologist
        elif obj.role == 'EMB' and hasattr(obj, 'embryologist_profile'):
            return obj.embryologist_profile.employee_id
        
        return None


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    leave_type_name = serializers.CharField(source='get_leave_type_display', read_only=True)
    status_name = serializers.CharField(source='get_status_display', read_only=True)
    days = serializers.SerializerMethodField()
    
    class Meta:
        model = LeaveRequest
        fields = ['id', 'employee', 'employee_name', 'leave_type', 'leave_type_name',
                  'start_date', 'end_date', 'days', 'reason', 'status', 'status_name',
                  'created_at', 'approved_by', 'approved_at', 'rejection_reason']
        read_only_fields = ['id', 'created_at', 'approved_by', 'approved_at']
    
    def get_days(self, obj):
        if obj.start_date and obj.end_date:
            delta = obj.end_date - obj.start_date
            return delta.days + 1
        return 0


# ========== SHIFT MANAGEMENT SERIALIZERS ==========

class ShiftSerializer(serializers.ModelSerializer):
    shift_type_display = serializers.CharField(source='get_shift_type_display', read_only=True)
    
    class Meta:
        model = Shift
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    def validate(self, data):
        """Validate shift timings - allows overnight shifts"""
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        shift_type = data.get('shift_type')
        
        if start_time and end_time:
            # Convert to minutes
            start_min = start_time.hour * 60 + start_time.minute
            end_min = end_time.hour * 60 + end_time.minute
            
            # Calculate duration
            if shift_type == 'NIGHT':
                # Night shift: end time is next day
                if end_min <= start_min:
                    duration = ((end_min + 24 * 60) - start_min) / 60
                else:
                    duration = (end_min - start_min) / 60
            else:
                # Regular shifts: end time must be after start time
                if end_min <= start_min:
                    raise serializers.ValidationError(
                        "End time must be after start time for non-night shifts"
                    )
                duration = (end_min - start_min) / 60
            
            # Set duration (convert to proper type)
            from decimal import Decimal
            data['duration_hours'] = Decimal(str(round(duration, 1)))
        
        return data


class DoctorShiftAssignmentSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source='doctor.full_name', read_only=True)
    doctor_role = serializers.CharField(source='doctor.get_role_display', read_only=True)
    doctor_email = serializers.EmailField(source='doctor.email', read_only=True)
    shift_name = serializers.CharField(source='shift.name', read_only=True)
    shift_type = serializers.CharField(source='shift.shift_type', read_only=True)
    shift_type_display = serializers.CharField(source='shift.get_shift_type_display', read_only=True)
    shift_start = serializers.TimeField(source='shift.start_time', read_only=True)
    shift_end = serializers.TimeField(source='shift.end_time', read_only=True)
    shift_duration = serializers.DecimalField(source='shift.duration_hours', read_only=True, max_digits=4, decimal_places=1)
    assigned_by_name = serializers.CharField(source='assigned_by.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = DoctorShiftAssignment
        fields = [
            'id', 'doctor', 'doctor_name', 'doctor_role', 'doctor_email',
            'shift', 'shift_name', 'shift_type', 'shift_type_display', 
            'shift_start', 'shift_end', 'shift_duration',
            'shift_date', 'status', 'status_display', 'notes',
            'check_in_time', 'check_out_time', 'is_present', 'attendance_notes',
            'assigned_by', 'assigned_by_name', 'assigned_at', 'updated_at'
        ]
        read_only_fields = ['assigned_at', 'updated_at', 'assigned_by']
    
    def validate(self, data):
        """Validate shift assignment"""
        doctor = data.get('doctor')
        shift = data.get('shift')
        shift_date = data.get('shift_date')
        
        # Check if shift_date is not in past
        if shift_date and shift_date < timezone.now().date():
            raise serializers.ValidationError("Cannot assign shift to past date")
        
        # Check for duplicate assignment
        if doctor and shift and shift_date:
            existing = DoctorShiftAssignment.objects.filter(
                doctor=doctor,
                shift_date=shift_date,
                status__in=['SCHEDULED', 'PENDING_SWAP']
            ).exclude(id=self.instance.id if self.instance else None)
            
            if existing.exists():
                raise serializers.ValidationError(f"Doctor {doctor.full_name} already has a shift on {shift_date}")
        
        return data


class BulkShiftAssignmentSerializer(serializers.Serializer):
    """Serializer for bulk shift assignments"""
    assignments = DoctorShiftAssignmentSerializer(many=True)
    
    def create(self, validated_data):
        assignments_data = validated_data.get('assignments', [])
        created_assignments = []
        
        for data in assignments_data:
            assignment = DoctorShiftAssignment.objects.create(**data)
            created_assignments.append(assignment)
        
        return created_assignments


class ShiftSwapRequestSerializer(serializers.ModelSerializer):
    requesting_doctor_name = serializers.CharField(source='requesting_doctor.full_name', read_only=True)
    target_doctor_name = serializers.CharField(source='target_doctor.full_name', read_only=True)
    requesting_doctor_role = serializers.CharField(source='requesting_doctor.get_role_display', read_only=True)
    target_doctor_role = serializers.CharField(source='target_doctor.get_role_display', read_only=True)
    requesting_shift_date = serializers.DateField(source='requesting_assignment.shift_date', read_only=True)
    target_shift_date = serializers.DateField(source='target_assignment.shift_date', read_only=True)
    requesting_shift_name = serializers.CharField(source='requesting_assignment.shift.name', read_only=True)
    target_shift_name = serializers.CharField(source='target_assignment.shift.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.full_name', read_only=True)
    
    class Meta:
        model = ShiftSwapRequest
        fields = [
            'id', 'requesting_doctor', 'requesting_doctor_name', 'requesting_doctor_role',
            'target_doctor', 'target_doctor_name', 'target_doctor_role',
            'requesting_assignment', 'requesting_shift_date', 'requesting_shift_name',
            'target_assignment', 'target_shift_date', 'target_shift_name',
            'reason', 'status', 'status_display',
            'approved_by', 'approved_by_name', 'approved_at', 'rejection_reason',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'approved_by', 'approved_at']


class ShiftAttendanceSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source='assignment.doctor.full_name', read_only=True)
    doctor_role = serializers.CharField(source='assignment.doctor.get_role_display', read_only=True)
    shift_name = serializers.CharField(source='assignment.shift.name', read_only=True)
    shift_date = serializers.DateField(source='assignment.shift_date', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    marked_by_name = serializers.CharField(source='marked_by.full_name', read_only=True)
    
    class Meta:
        model = ShiftAttendance
        fields = [
            'id', 'assignment', 'doctor_name', 'doctor_role', 'shift_name', 'shift_date',
            'date', 'check_in', 'check_out', 'status', 'status_display',
            'late_minutes', 'overtime_minutes', 'marked_by', 'marked_by_name',
            'remarks', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate(self, data):
        """Validate attendance data"""
        check_in = data.get('check_in')
        check_out = data.get('check_out')
        assignment = data.get('assignment')
        
        if check_in and check_out and check_in > check_out:
            raise serializers.ValidationError("Check-in time must be before check-out time")
        
        # Calculate late minutes if check_in is provided
        if check_in and assignment:
            shift_start = assignment.shift.start_time
            check_in_time = check_in.time()
            
            if check_in_time > shift_start:
                # Calculate minutes late
                late_minutes = (check_in_time.hour - shift_start.hour) * 60
                late_minutes += (check_in_time.minute - shift_start.minute)
                data['late_minutes'] = max(0, late_minutes)
        
        return data


class LeaveBalanceSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    annual_remaining = serializers.DecimalField(max_digits=5, decimal_places=1, read_only=True)
    sick_remaining = serializers.DecimalField(max_digits=5, decimal_places=1, read_only=True)
    casual_remaining = serializers.DecimalField(max_digits=5, decimal_places=1, read_only=True)
    total_remaining = serializers.DecimalField(max_digits=5, decimal_places=1, read_only=True)
    
    class Meta:
        model = LeaveBalance
        fields = [
            'id', 'user', 'user_name', 'year',
            'annual_allocated', 'annual_used', 'annual_remaining',
            'sick_allocated', 'sick_used', 'sick_remaining',
            'casual_allocated', 'casual_used', 'casual_remaining',
            'total_remaining'
        ]
    
    def validate(self, data):
        """Validate leave allocations"""
        year = data.get('year')
        user = data.get('user')
        
        if year and user:
            # Check if balance already exists for this user and year
            existing = LeaveBalance.objects.filter(user=user, year=year)
            if self.instance:
                existing = existing.exclude(id=self.instance.id)
            
            if existing.exists():
                raise serializers.ValidationError(f"Leave balance for {user.full_name} in {year} already exists")
        
        return data


class HolidaySerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source='date.strftime', read_only=True)
    is_weekend = serializers.SerializerMethodField()
    
    class Meta:
        model = Holiday
        fields = ['id', 'name', 'date', 'day_name', 'is_optional', 'description', 'is_weekend', 'created_at']
        read_only_fields = ['created_at']
    
    def get_is_weekend(self, obj):
        # Returns True if holiday falls on weekend
        return obj.date.weekday() >= 5  # 5 = Saturday, 6 = Sunday


class ShiftCoverageReportSerializer(serializers.Serializer):
    """Serializer for shift coverage reports"""
    date = serializers.DateField()
    total_shifts = serializers.IntegerField()
    filled_shifts = serializers.IntegerField()
    vacant_shifts = serializers.IntegerField()
    coverage_percentage = serializers.DecimalField(max_digits=5, decimal_places=1)
    shifts_detail = serializers.DictField()


class DoctorShiftCalendarSerializer(serializers.Serializer):
    """Serializer for doctor's shift calendar view"""
    date = serializers.DateField()
    day_name = serializers.CharField()
    shifts = DoctorShiftAssignmentSerializer(many=True)
    total_hours = serializers.DecimalField(max_digits=5, decimal_places=1)
    has_assignment = serializers.BooleanField()


class ShiftDashboardStatsSerializer(serializers.Serializer):
    """Serializer for shift dashboard statistics"""
    today_summary = serializers.DictField()
    weekly_summary = serializers.DictField()
    monthly_summary = serializers.DictField()
    shift_distribution = serializers.DictField()
    attendance_rate = serializers.DecimalField(max_digits=5, decimal_places=1)
    pending_swaps = serializers.IntegerField()