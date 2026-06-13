from django.db import models
from django.conf import settings
from django.utils import timezone
import qrcode
from io import BytesIO
import base64
import json


class OPTicket(models.Model):
    VISIT_REASONS = [
        ('CONSULTATION', 'Consultation'),
        ('FOLLOW_UP', 'Follow-up'),
        ('LAB_COLLECTION', 'Lab Sample Collection'),
        ('SCAN', 'Scan/Ultrasound'),
        ('PROCEDURE', 'Procedure'),
        ('MEDICATION', 'Medication'),
        ('OTHER', 'Other'),
    ]

    STATUS_CHOICES = [
        ('WAITING', 'Waiting'),
        ('IN_CONSULT', 'In Consult'),
        ('DONE', 'Done'),
        ('CANCELLED', 'Cancelled'),
    ]

    # Auto Incremented token per day
    token_number = models.PositiveIntegerField()
    date = models.DateField(default=timezone.localdate)
    patient = models.ForeignKey('patients.PatientProfile', on_delete=models.CASCADE, related_name='op_tickets')
    assigned_doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        blank=True, 
        null=True, 
        related_name='op_tickets_as_doctor',
        limit_choices_to={'role__in': ['END', 'GYN', 'ANE']}
    )
    department = models.ForeignKey(
        'departments.Department', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='op_tickets'
    )
    visit_reason = models.CharField(max_length=50, choices=VISIT_REASONS, default='CONSULTATION')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='WAITING')
    notes = models.TextField(blank=True)
    payment_done = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='op_tickets_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # QR Code field - store as TextField to hold base64 string
    qr_code = models.TextField(blank=True, null=True)
    qr_code_generated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['date', 'token_number']
        unique_together = ('date', 'token_number')

    def __str__(self):
        return f"Token {self.token_number} - {self.patient.patient_id} - {self.date}"
    
    @property
    def token(self):
        return self.token_number
    
    @classmethod
    def next_token_for_today(cls):
        today = timezone.now().date()
        last = cls.objects.filter(date=today).order_by('-token_number').first()
        return (last.token_number + 1) if last else 1
    
    def generate_qr_code(self, request=None):
        """
        Generate QR code for the ticket and store as base64.
        Pass request to generate absolute URLs.
        Returns: base64 string of QR code image
        """
        # Don't generate QR for cancelled tickets
        if self.status == 'CANCELLED':
            return None
        
        # Create data to encode in QR
        frontend_url = 'http://localhost:3000'  # Default frontend URL
        
        # Try to get the frontend URL from request if provided
        if request:
            frontend_url = request.build_absolute_uri('/').rstrip('/')
        
        qr_data = {
            'ticket_id': self.id,
            'token_number': self.token_number,
            'patient_name': self.patient.user.full_name if self.patient else '',
            'patient_id': self.patient.patient_id if self.patient else '',
            'doctor_name': self.assigned_doctor.full_name if self.assigned_doctor else '',
            'date': str(self.date),
            'status': self.status,
            'verify_url': f"{frontend_url}/verify-ticket/{self.id}"
        }
        
        # Convert to JSON string
        qr_string = json.dumps(qr_data)
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_string)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # Store in database
        self.qr_code = f"data:image/png;base64,{img_base64}"
        self.qr_code_generated_at = timezone.now()
        
        return self.qr_code
    
    def get_qr_code(self, request=None):
        """
        Get existing QR code or generate a new one.
        Returns: base64 string of QR code image
        """
        # If QR code exists and is not expired (optional: add expiry logic)
        if self.qr_code and self.qr_code_generated_at:
            # Optional: Regenerate if older than 24 hours
            # if timezone.now() - self.qr_code_generated_at > timedelta(hours=24):
            #     return self.generate_qr_code(request)
            return self.qr_code
        
        # Generate new QR code
        return self.generate_qr_code(request)
    
    def save(self, *args, **kwargs):
        """
        Override save method to generate QR code for new tickets.
        """
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Generate QR code for new tickets (only if not cancelled)
        if is_new and self.status != 'CANCELLED':
            self.generate_qr_code()
            # Save again without triggering recursion
            super().save(update_fields=['qr_code', 'qr_code_generated_at'])


class Appointment(models.Model):
    """
    Separate Appointment table for better management
    This handles scheduled appointments distinctly from OP tickets
    """
    
    APPOINTMENT_STATUS = [
        ('SCHEDULED', 'Scheduled'),
        ('CONFIRMED', 'Confirmed'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('NO_SHOW', 'No Show'),
        ('RESCHEDULED', 'Rescheduled'),
    ]
    
    APPOINTMENT_TYPE = [
        ('REGULAR', 'Regular'),
        ('FOLLOW_UP', 'Follow-up'),
        ('EMERGENCY', 'Emergency'),
        ('WALK_IN', 'Walk-in'),
        ('TELEHEALTH', 'Telehealth'),
    ]
    
    # Basic Information
    appointment_id = models.CharField(max_length=20, unique=True, editable=False)
    token_number = models.PositiveIntegerField(null=True, blank=True)  # Daily token
    
    # Relationships
    patient = models.ForeignKey('patients.PatientProfile', on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='appointments', 
        limit_choices_to={'role__in': ['END', 'GYN', 'ANE']}
    )
    department = models.ForeignKey(
        'departments.Department', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='appointments'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_appointments'
    )
    
    # Date & Time
    appointment_date = models.DateField(db_index=True)
    appointment_time = models.TimeField(null=True, blank=True)
    time_slot = models.CharField(max_length=20, blank=True, null=True)  # "09:00 AM", "10:30 AM"
    duration_minutes = models.PositiveIntegerField(default=30)  # Appointment duration
    
    # Appointment Details
    appointment_type = models.CharField(max_length=20, choices=APPOINTMENT_TYPE, default='REGULAR')
    status = models.CharField(max_length=20, choices=APPOINTMENT_STATUS, default='SCHEDULED')
    visit_reason = models.CharField(max_length=50, choices=OPTicket.VISIT_REASONS, default='CONSULTATION')
    symptoms = models.TextField(blank=True, help_text="Patient's symptoms or complaints")
    notes = models.TextField(blank=True)
    
    # Tracking
    payment_status = models.BooleanField(default=False)
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Cancellation/Reschedule Tracking
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=200, blank=True)
    rescheduled_from = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='rescheduled_to'
    )
    rescheduled_count = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # QR Code
    qr_code = models.TextField(blank=True, null=True)
    qr_code_generated_at = models.DateTimeField(null=True, blank=True)
    
    # Reminders
    reminder_sent = models.BooleanField(default=False)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_type = models.CharField(max_length=20, blank=True)  # SMS, EMAIL, BOTH
    
    class Meta:
        ordering = ['appointment_date', 'appointment_time', 'token_number']
        indexes = [
            models.Index(fields=['appointment_date', 'doctor']),
            models.Index(fields=['patient', 'appointment_date']),
            models.Index(fields=['status', 'appointment_date']),
        ]
        verbose_name = 'Appointment'
        verbose_name_plural = 'Appointments'
    
    def __str__(self):
        patient_name = self.patient.user.full_name if self.patient else 'Unknown Patient'
        return f"{self.appointment_id} - {patient_name} - {self.appointment_date}"
    
    def save(self, *args, **kwargs):
        if not self.appointment_id:
            # Generate appointment ID: APT-20240001 format
            year = timezone.now().year
            last_appointment = Appointment.objects.filter(
                appointment_id__startswith=f'APT-{year}'
            ).order_by('-appointment_id').first()
            
            if last_appointment:
                # Extract the numeric part after the year
                last_num = int(last_appointment.appointment_id.split('-')[1][4:])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.appointment_id = f"APT-{year}{new_num:04d}"
        
        # Generate token for the day if not set
        if not self.token_number and self.appointment_date == timezone.now().date():
            last_token = Appointment.objects.filter(
                appointment_date=self.appointment_date
            ).order_by('-token_number').first()
            self.token_number = (last_token.token_number + 1) if last_token else 1
        
        super().save(*args, **kwargs)
    
    def generate_qr_code(self, request=None):
        """Generate QR code for appointment"""
        frontend_url = request.build_absolute_uri('/').rstrip('/') if request else 'http://localhost:3000'
        
        qr_data = {
            'type': 'appointment',
            'appointment_id': self.appointment_id,
            'patient_name': self.patient.user.full_name if self.patient else '',
            'patient_mrn': self.patient.patient_id if self.patient else '',
            'doctor_name': self.doctor.full_name if self.doctor else '',
            'date': str(self.appointment_date),
            'time': str(self.appointment_time) if self.appointment_time else '',
            'status': self.status,
            'verify_url': f"{frontend_url}/verify-appointment/{self.id}"
        }
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        self.qr_code = f"data:image/png;base64,{img_base64}"
        self.qr_code_generated_at = timezone.now()
        return self.qr_code
    
    def get_qr_code(self, request=None):
        """Get existing QR code or generate a new one"""
        if self.qr_code and self.qr_code_generated_at:
            return self.qr_code
        return self.generate_qr_code(request)
    
    @classmethod
    def get_available_time_slots(cls, doctor_id, date):
        """Get available time slots for a doctor on a specific date"""
        # Define default time slots
        all_slots = [
            '09:00 AM', '09:30 AM', '10:00 AM', '10:30 AM',
            '11:00 AM', '11:30 AM', '12:00 PM', '12:30 PM',
            '02:00 PM', '02:30 PM', '03:00 PM', '03:30 PM',
            '04:00 PM', '04:30 PM'
        ]
        
        # Get booked slots
        booked_slots = cls.objects.filter(
            doctor_id=doctor_id,
            appointment_date=date,
            status__in=['SCHEDULED', 'CONFIRMED', 'IN_PROGRESS']
        ).values_list('time_slot', flat=True)
        
        return [slot for slot in all_slots if slot not in booked_slots]
    
    @classmethod
    def get_appointments_for_date(cls, date, doctor_id=None):
        """Get appointments for a specific date, optionally filtered by doctor"""
        queryset = cls.objects.filter(appointment_date=date).select_related(
            'patient__user', 'doctor', 'department'
        )
        if doctor_id:
            queryset = queryset.filter(doctor_id=doctor_id)
        return queryset.order_by('appointment_time', 'token_number')
    
    def cancel(self, reason=None, cancelled_by=None):
        """Cancel appointment with reason"""
        self.status = 'CANCELLED'
        self.cancelled_at = timezone.now()
        if reason:
            self.cancellation_reason = reason
        self.save()
        return True
    
    def reschedule(self, new_date, new_time=None, reason=None):
        """Reschedule appointment to new date/time"""
        # Create reschedule record
        old_date = self.appointment_date
        old_time = self.appointment_time
        
        self.appointment_date = new_date
        if new_time:
            self.appointment_time = new_time
        self.rescheduled_count += 1
        self.status = 'RESCHEDULED'
        
        # Add note about reschedule
        reschedule_note = f"Rescheduled from {old_date} {old_time or ''} to {new_date} {new_time or ''}"
        if reason:
            reschedule_note += f". Reason: {reason}"
        
        if self.notes:
            self.notes = f"{self.notes}\n[{reschedule_note}]"
        else:
            self.notes = f"[{reschedule_note}]"
        
        self.save()
        return True
    
    def confirm(self):
        """Confirm the appointment"""
        if self.status == 'SCHEDULED':
            self.status = 'CONFIRMED'
            self.save()
            return True
        return False
    
    def start_consultation(self):
        """Mark appointment as in progress"""
        if self.status in ['SCHEDULED', 'CONFIRMED']:
            self.status = 'IN_PROGRESS'
            self.save()
            return True
        return False
    
    def complete(self):
        """Mark appointment as completed"""
        if self.status == 'IN_PROGRESS':
            self.status = 'COMPLETED'
            self.save()
            return True
        return False
    
    def mark_no_show(self):
        """Mark appointment as no-show"""
        if self.status in ['SCHEDULED', 'CONFIRMED']:
            self.status = 'NO_SHOW'
            self.save()
            return True
        return False