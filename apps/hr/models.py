from django.db import models
from django.conf import settings
from django.utils.text import slugify


class HRManagerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hr_profile'
    )
    employee_id = models.CharField(max_length=20, unique=True, blank=True)
    slug = models.SlugField(unique=True, blank=True)

    managed_depts = models.CharField(max_length=200, blank=True, null=True)
    contact_number = models.CharField(max_length=15, unique=True, blank=True, null=True)

    can_approve_leaves = models.BooleanField(default=True)
    can_view_salaries = models.BooleanField(default=True)
    can_terminate_staff = models.BooleanField(default=False)
    can_edit_attendance = models.BooleanField(default=False)
    can_generate_payslips = models.BooleanField(default=True)
    can_update_documents = models.BooleanField(default=True)
    is_department_head = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    date_assigned = models.DateField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.employee_id:
            last = HRManagerProfile.objects.order_by('-id').first()
            if last and last.employee_id:
                last_num = int(last.employee_id.replace('HR', ''))
                self.employee_id = f"HR{last_num + 1:03d}"
            else:
                self.employee_id = "HR001"
        if not self.slug:
            self.slug = slugify(f"{self.user.full_name}-{self.employee_id}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"HR: {self.user.full_name}"


class LeaveRequest(models.Model):
    LEAVE_TYPES = [
        ('ANNUAL', 'Annual Leave'),
        ('SICK', 'Sick Leave'),
        ('CASUAL', 'Casual Leave'),
        ('EMERGENCY', 'Emergency'),
        ('MATERNITY', 'Maternity Leave'),
        ('PATERNITY', 'Paternity Leave'),
        ('UNPAID', 'Unpaid Leave'),
    ]
    
    STATUS = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='leave_requests'
    )
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS, default='PENDING')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_leaves'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    attachment = models.FileField(upload_to='leaves/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.full_name} - {self.get_leave_type_display()}"


# ========== SHIFT MANAGEMENT MODELS ==========

class Shift(models.Model):
    """Shift definitions - created by HR"""
    SHIFT_TYPES = [
        ('MORNING', 'Morning (8 AM - 2 PM)'),
        ('EVENING', 'Evening (2 PM - 8 PM)'),
        ('NIGHT', 'Night (8 PM - 8 AM)'),
        ('ONCALL', 'On-Call (24 hours)'),
        ('CUSTOM', 'Custom'),
    ]
    
    name = models.CharField(max_length=50)
    shift_type = models.CharField(max_length=20, choices=SHIFT_TYPES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_hours = models.DecimalField(max_digits=4, decimal_places=1, help_text="Duration in hours")
    is_active = models.BooleanField(default=True)
    requires_on_site = models.BooleanField(default=True)
    description = models.TextField(blank=True, help_text="Additional notes about this shift")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['start_time']
        verbose_name = 'Shift'
        verbose_name_plural = 'Shifts'
    
    def __str__(self):
        return f"{self.name} ({self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')})"


class DoctorShiftAssignment(models.Model):
    """Which doctor is assigned to which shift on which date"""
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('PENDING_SWAP', 'Pending Swap'),
        ('SWAPPED', 'Swapped'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    ]
    
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='shift_assignments',
        limit_choices_to={'role__in': ['END', 'GYN', 'ANE']}
    )
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='assignments')
    shift_date = models.DateField()
    
    # Assignment details
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='assigned_shifts'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    
    # Swap functionality
    swap_requested_with = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='swap_requests_received'
    )
    swap_status = models.CharField(max_length=20, blank=True, null=True)  # PENDING, APPROVED, REJECTED
    swap_requested_at = models.DateTimeField(blank=True, null=True)
    
    # Attendance tracking
    check_in_time = models.DateTimeField(blank=True, null=True)
    check_out_time = models.DateTimeField(blank=True, null=True)
    is_present = models.BooleanField(default=False)
    attendance_notes = models.TextField(blank=True)
    
    # Other fields
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['doctor', 'shift_date', 'shift']
        ordering = ['shift_date', 'shift__start_time']
        indexes = [
            models.Index(fields=['shift_date', 'status']),
            models.Index(fields=['doctor', 'shift_date']),
        ]
        verbose_name = 'Doctor Shift Assignment'
        verbose_name_plural = 'Doctor Shift Assignments'
    
    def __str__(self):
        return f"{self.doctor.full_name} - {self.shift.name} on {self.shift_date}"


class ShiftSwapRequest(models.Model):
    """Doctor-initiated shift swap requests"""
    SWAP_STATUS = [
        ('PENDING', 'Pending HR Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    requesting_doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='sent_swap_requests'
    )
    target_doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='received_swap_requests'
    )
    requesting_assignment = models.ForeignKey(
        DoctorShiftAssignment, 
        on_delete=models.CASCADE, 
        related_name='swap_request_from'
    )
    target_assignment = models.ForeignKey(
        DoctorShiftAssignment, 
        on_delete=models.CASCADE, 
        related_name='swap_request_to'
    )
    
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=SWAP_STATUS, default='PENDING')
    
    # Approval tracking
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='approved_swaps'
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Shift Swap Request'
        verbose_name_plural = 'Shift Swap Requests'
    
    def __str__(self):
        return f"Swap: {self.requesting_doctor.full_name} ↔ {self.target_doctor.full_name}"


class ShiftAttendance(models.Model):
    """Daily shift attendance tracking"""
    ATTENDANCE_STATUS = [
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('LATE', 'Late'),
        ('HALF_DAY', 'Half Day'),
        ('ON_LEAVE', 'On Leave'),
    ]
    
    assignment = models.ForeignKey(
        DoctorShiftAssignment, 
        on_delete=models.CASCADE, 
        related_name='attendances'
    )
    date = models.DateField()
    check_in = models.DateTimeField(blank=True, null=True)
    check_out = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS, default='ABSENT')
    late_minutes = models.IntegerField(default=0, help_text="Minutes late for the shift")
    overtime_minutes = models.IntegerField(default=0, help_text="Minutes worked beyond shift end")
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['assignment', 'date']
        ordering = ['-date']
        verbose_name = 'Shift Attendance'
        verbose_name_plural = 'Shift Attendances'
    
    def __str__(self):
        return f"{self.assignment.doctor.full_name} - {self.date} - {self.status}"


class LeaveBalance(models.Model):
    """Track leave balance for each employee"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='leave_balance'
    )
    year = models.IntegerField(help_text="Year for which balance applies")
    
    # Leave allocations
    annual_allocated = models.DecimalField(max_digits=5, decimal_places=1, default=20)
    annual_used = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    
    sick_allocated = models.DecimalField(max_digits=5, decimal_places=1, default=12)
    sick_used = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    
    casual_allocated = models.DecimalField(max_digits=5, decimal_places=1, default=10)
    casual_used = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    
    # Calculated fields
    @property
    def annual_remaining(self):
        return self.annual_allocated - self.annual_used
    
    @property
    def sick_remaining(self):
        return self.sick_allocated - self.sick_used
    
    @property
    def casual_remaining(self):
        return self.casual_allocated - self.casual_used
    
    @property
    def total_remaining(self):
        return self.annual_remaining + self.sick_remaining + self.casual_remaining
    
    class Meta:
        unique_together = ['user', 'year']
        verbose_name = 'Leave Balance'
        verbose_name_plural = 'Leave Balances'
    
    def __str__(self):
        return f"{self.user.full_name} - {self.year} Leave Balance"


class Holiday(models.Model):
    """Company holidays"""
    name = models.CharField(max_length=100)
    date = models.DateField(unique=True)
    is_optional = models.BooleanField(default=False, help_text="Optional holiday (not mandatory)")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['date']
    
    def __str__(self):
        return f"{self.name} - {self.date}"