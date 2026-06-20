# apps/attendance/models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

User = get_user_model()


class AttendanceSettings(models.Model):
    """
    Attendance settings - Global and Department specific
    """
    department = models.ForeignKey(
        'departments.Department',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='attendance_settings'
    )
    work_start_time = models.TimeField(default='09:00:00')
    work_end_time = models.TimeField(default='17:00:00')
    late_threshold_minutes = models.IntegerField(default=15)
    self_correction_hours = models.IntegerField(default=2)
    allowed_late_per_month = models.IntegerField(default=5)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Attendance Settings'
        unique_together = ['department']
    
    def __str__(self):
        dept_name = self.department.name if self.department else 'Global'
        return f"Settings - {dept_name}"
    
    @classmethod
    def get_settings(cls, user=None):
        """Get settings for a user"""
        if user:
            # ✅ Import WITHOUT 'apps.' prefix
            from departments.models import StaffDepartmentAssignment
            dept_assign = StaffDepartmentAssignment.objects.filter(
                user=user,
                is_active=True,
                role_in_dept='PRIMARY'
            ).first()
            
            if dept_assign:
                settings = cls.objects.filter(
                    department=dept_assign.department,
                    is_active=True
                ).first()
                if settings:
                    return settings
        
        return cls.objects.filter(department__isnull=True, is_active=True).first()


class StaffAttendance(models.Model):
    """
    Main attendance model - Used by ALL staff members
    """
    STATUS_CHOICES = [
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('LATE', 'Late'),
        ('ON_LEAVE', 'On Leave'),
        ('HALF_DAY', 'Half Day'),
        ('WORK_FROM_HOME', 'Work from Home'),
        ('HOLIDAY', 'Holiday'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='attendances'
    )
    date = models.DateField()
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PRESENT'
    )
    late_minutes = models.IntegerField(default=0)
    overtime_minutes = models.IntegerField(default=0)
    total_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    remarks = models.TextField(blank=True)
    
    marked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='marked_attendances'
    )
    
    shift_assignment = models.ForeignKey(
        'hr.DoctorShiftAssignment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_attendances'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'date']
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['status', 'date']),
        ]
    
    def __str__(self):
        return f"{self.user.full_name} - {self.date} - {self.get_status_display()}"
    
    def _to_time(self, value):
        """Convert string to time object if needed"""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return datetime.strptime(value, '%H:%M').time()
            except ValueError:
                return None
        return value
    
    def calculate_hours(self):
        """Calculate total working hours"""
        if not self.check_in or not self.check_out:
            return Decimal('0.00')
        
        check_in_time = self._to_time(self.check_in)
        check_out_time = self._to_time(self.check_out)
        
        if not check_in_time or not check_out_time:
            return Decimal('0.00')
        
        check_in_dt = datetime.combine(self.date, check_in_time)
        check_out_dt = datetime.combine(self.date, check_out_time)
        
        if check_out_dt < check_in_dt:
            check_out_dt += timedelta(days=1)
        
        delta = check_out_dt - check_in_dt
        return Decimal(str(round(delta.seconds / 3600, 2)))
    
    def calculate_late_minutes(self):
        """Calculate late minutes"""
        if not self.check_in:
            return 0
        
        check_in_time = self._to_time(self.check_in)
        if not check_in_time:
            return 0
        
        settings = AttendanceSettings.get_settings(self.user)
        if not settings:
            return 0
        
        work_start = settings.work_start_time
        
        if check_in_time > work_start:
            late_delta = datetime.combine(self.date, check_in_time) - datetime.combine(self.date, work_start)
            return late_delta.seconds // 60
        
        return 0
    
    def save(self, *args, **kwargs):
        """Auto-calculate before saving"""
        if self.check_in and isinstance(self.check_in, str):
            self.check_in = self._to_time(self.check_in)
        if self.check_out and isinstance(self.check_out, str):
            self.check_out = self._to_time(self.check_out)
        
        if self.check_in and self.check_out:
            self.total_hours = self.calculate_hours()
        
        if self.check_in and self.status in ['PRESENT', 'LATE']:
            self.late_minutes = self.calculate_late_minutes()
        
        super().save(*args, **kwargs)


class AttendanceCorrectionRequest(models.Model):
    """
    Staff can request attendance correction
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='attendance_corrections'
    )
    date = models.DateField()
    current_check_in = models.TimeField(null=True, blank=True)
    current_check_out = models.TimeField(null=True, blank=True)
    current_status = models.CharField(max_length=20, blank=True)
    requested_check_in = models.TimeField()
    requested_check_out = models.TimeField()
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    rejection_reason = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_corrections'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.date} - {self.status}"