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