# lab/models.py - Complete with Billing

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import json

User = settings.AUTH_USER_MODEL


# ============================================================
# 1. EXISTING LAB TECHNICIAN PROFILES
# ============================================================

class LabTechnicianProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='technician_profile'
    )
    employee_id = models.CharField(max_length=20, unique=True, blank=True, help_text='LT001')
    technical_certification = models.CharField(max_length=250, blank=True)
    specialization = models.CharField(max_length=50, blank=True)
    is_department_head = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_assigned = models.DateField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.employee_id:
            last_profile = LabTechnicianProfile.objects.order_by('-id').first()
            if not last_profile:
                self.employee_id = "LT001"
            else:
                last_id = int(last_profile.employee_id.replace("LT", ""))
                new_id = last_id + 1
                self.employee_id = f"LT{new_id:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Lab-Technician: {self.user.full_name}"


class AndrologyLabTechnician(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="andrology_technician_profile"
    )
    employee_id = models.CharField(max_length=20, unique=True, blank=True, help_text='AT001')
    technician_license = models.CharField(max_length=100, unique=True, blank=True)
    specialization = models.CharField(max_length=50, blank=True)
    can_perform_dna_frag = models.BooleanField(default=False,
                                               help_text="Authorized for Sperm DNA Fragmentation Indexing")
    can_perform_cryo = models.BooleanField(default=True,
                                           help_text="Authorized to freeze and map semen samples")
    is_department_head = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_assigned = models.DateField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.employee_id:
            last_profile = AndrologyLabTechnician.objects.order_by('-id').first()
            if not last_profile:
                self.employee_id = "AT001"
            else:
                last_id = int(last_profile.employee_id.replace("AT", ""))
                new_id = last_id + 1
                self.employee_id = f"AT{new_id:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Andrology Lab-Technician: {self.user.full_name}"


# ============================================================
# 2. DYNAMIC LAB TEST TYPES
# ============================================================

class LabTestType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)
    icon = models.CharField(max_length=50, blank=True, null=True,
                            help_text="FontAwesome icon class (e.g., fa-droplet)")
    color = models.CharField(max_length=20, default='#4F46E5', help_text="Color for UI")
    description = models.TextField(blank=True, null=True)
    
    # ========== NEW: PRICE FIELD FOR BILLING ==========
    price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Standard price for this test"
    )
    
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_test_types'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lab_test_types'
        ordering = ['display_order', 'name']
        verbose_name = 'Lab Test Type'
        verbose_name_plural = 'Lab Test Types'

    def __str__(self):
        return self.name

    def get_field_count(self):
        return self.fields.filter(is_active=True).count()

    def get_record_count(self):
        return self.records.filter(is_active=True).count()


# ============================================================
# 3. DYNAMIC FIELDS FOR TEST TYPES
# ============================================================

class LabField(models.Model):
    FIELD_TYPES = [
        ('text', 'Text'),
        ('number', 'Number'),
        ('decimal', 'Decimal'),
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('date', 'Date'),
        ('datetime', 'DateTime'),
        ('time', 'Time'),
        ('select', 'Dropdown'),
        ('multiselect', 'Multi-select'),
        ('checkbox', 'Checkbox'),
        ('radio', 'Radio Buttons'),
        ('textarea', 'Text Area'),
        ('file', 'File Upload'),
    ]

    test_type = models.ForeignKey(LabTestType, on_delete=models.CASCADE, related_name='fields')
    label = models.CharField(max_length=200)
    field_key = models.CharField(max_length=100, help_text="Unique identifier for the field")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, default='text')
    placeholder = models.CharField(max_length=200, blank=True, null=True)
    help_text = models.CharField(max_length=500, blank=True, null=True)
    default_value = models.TextField(blank=True, null=True)
    is_required = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)

    # For select, multiselect, radio fields
    options = models.JSONField(blank=True, null=True, help_text='["Option 1", "Option 2"]')

    # Validation rules
    min_value = models.DecimalField(max_digits=20, decimal_places=6, blank=True, null=True)
    max_value = models.DecimalField(max_digits=20, decimal_places=6, blank=True, null=True)
    min_length = models.IntegerField(blank=True, null=True)
    max_length = models.IntegerField(blank=True, null=True)

    # UI settings
    column_width = models.IntegerField(default=12, help_text="Bootstrap column width (1-12)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lab_fields'
        ordering = ['display_order', 'label']
        unique_together = ['test_type', 'field_key']

    def __str__(self):
        return f"{self.test_type.name} - {self.label}"

    def get_options_list(self):
        """Return options as list"""
        if self.options:
            if isinstance(self.options, list):
                return self.options
            elif isinstance(self.options, str):
                try:
                    return json.loads(self.options)
                except:
                    return [opt.strip() for opt in self.options.split(',')]
        return []

    def get_validation_rules(self):
        """Get validation rules for frontend"""
        rules = {}
        if self.is_required:
            rules['required'] = True
        if self.min_value is not None:
            rules['min'] = float(self.min_value)
        if self.max_value is not None:
            rules['max'] = float(self.max_value)
        if self.min_length is not None:
            rules['minLength'] = self.min_length
        if self.max_length is not None:
            rules['maxLength'] = self.max_length
        return rules


# ============================================================
# 4. LAB RECORDS (with TOKEN NUMBER)
# ============================================================

class LabRecord(models.Model):
    # ========== STATUS & PRIORITY CHOICES ==========
    STATUS_CHOICES = [
        ('ORDERED', 'Ordered'),
        ('IN_PROGRESS', 'In Progress'),
        ('DRAFT', 'Draft'),
        ('PENDING', 'Pending Review'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled')
    ]

    PRIORITY_CHOICES = [
        ('ROUTINE', 'Routine'),
        ('URGENT', 'Urgent'),
        ('STAT', 'STAT'),
    ]

    # ========== CORE FIELDS ==========
    test_type = models.ForeignKey(LabTestType, on_delete=models.CASCADE, related_name='records')
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lab_records')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_lab_records'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_lab_records'
    )

    field_values = models.JSONField(default=dict, help_text="JSON object of field_key: value pairs")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='ROUTINE')
    test_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ORDERED')
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ========== TOKEN NUMBER ==========
    token_number = models.IntegerField(
        default=0,
        help_text="Token number for lab queue (daily counter)"
    )

    class Meta:
        db_table = 'lab_records'
        ordering = ['-test_date']
        indexes = [
            models.Index(fields=['test_type', 'patient']),
            models.Index(fields=['test_date']),
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['token_number']),
        ]

    def __str__(self):
        return f"{self.test_type.name} - {self.patient.full_name} - {self.test_date.strftime('%Y-%m-%d')}"

    # ========== TOKEN GENERATION ==========
    def generate_token(self):
        """Generate the next token number for today (global daily queue)."""
        today = timezone.now().date()
        last = LabRecord.objects.filter(test_date__date=today).order_by('-token_number').first()
        return (last.token_number + 1) if last else 1

    def save(self, *args, **kwargs):
        # Auto‑assign token only if not set yet
        if not self.token_number:
            self.token_number = self.generate_token()
        super().save(*args, **kwargs)

    # ========== HELPER METHODS ==========
    def get_field_value(self, field_key):
        return self.field_values.get(field_key)

    def get_display_fields(self):
        """Get fields with their values for display"""
        display_data = []
        for field in self.test_type.fields.filter(is_active=True).order_by('display_order'):
            value = self.field_values.get(field.field_key)
            display_data.append({
                'field': field,
                'value': value,
                'formatted_value': self._format_value(field, value)
            })
        return display_data

    def _format_value(self, field, value):
        if value is None:
            return '-'

        if field.field_type in ['select', 'radio']:
            options = field.get_options_list()
            if options and isinstance(options, list):
                for option in options:
                    if isinstance(option, dict) and option.get('value') == value:
                        return option.get('label', value)
            return value

        if field.field_type == 'date' and value:
            try:
                from datetime import datetime
                if isinstance(value, str):
                    return datetime.fromisoformat(value).strftime('%Y-%m-%d')
            except:
                pass

        return value

    def get_priority_display(self):
        """Get human-readable priority display"""
        return dict(self.PRIORITY_CHOICES).get(self.priority, self.priority)

    def get_status_display(self):
        """Get human-readable status display"""
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    def is_pending(self):
        """Check if order is pending (not completed or cancelled)"""
        return self.status in ['ORDERED', 'IN_PROGRESS', 'DRAFT', 'PENDING']

    def is_completed(self):
        return self.status == 'COMPLETED'

    def can_be_updated_by_lab(self):
        return self.status in ['ORDERED', 'IN_PROGRESS', 'DRAFT', 'PENDING']

    def can_be_cancelled(self):
        return self.status in ['ORDERED', 'IN_PROGRESS', 'DRAFT', 'PENDING']


# ============================================================
# 5. LAB BILLING MODELS
# ============================================================

class LabBill(models.Model):
    """
    Billing model for lab tests
    Integrates with finance system via JournalService
    """
    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PARTIAL', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('CARD', 'Card'),
        ('ONLINE', 'Online'),
        ('INSURANCE', 'Insurance'),
        ('CREDIT', 'Credit'),
    ]
    
    # ========== BILL IDENTIFICATION ==========
    bill_number = models.CharField(
        max_length=50, 
        unique=True, 
        editable=False,
        help_text="Format: LAB-YYYYMMDD-XXXX"
    )
    bill_date = models.DateTimeField(default=timezone.now)
    
    # ========== PATIENT ==========
    patient = models.ForeignKey(
        'patients.PatientProfile', 
        on_delete=models.PROTECT, 
        related_name='lab_bills'
    )
    
    # ========== FINANCIAL FIELDS ==========
    subtotal = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    discount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    tax = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    tax_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    total = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    
    # ========== PAYMENT TRACKING ==========
    payment_status = models.CharField(
        max_length=20, 
        choices=PAYMENT_STATUS_CHOICES, 
        default='PENDING'
    )
    payment_method = models.CharField(
        max_length=20, 
        choices=PAYMENT_METHOD_CHOICES, 
        default='CASH'
    )
    amount_paid = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    balance_due = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    
    # ========== LINKS ==========
    # Link to lab records (many-to-many)
    lab_records = models.ManyToManyField(
        'LabRecord', 
        related_name='bills', 
        blank=True,
        help_text="Lab test records included in this bill"
    )
    
    # Link to finance journal entry
    journal_entry_id = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Reference to finance journal entry ID"
    )
    
    # ========== METADATA ==========
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='created_lab_bills'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'lab_bills'
        ordering = ['-bill_date']
        indexes = [
            models.Index(fields=['bill_number']),
            models.Index(fields=['patient', 'payment_status']),
            models.Index(fields=['bill_date']),
            models.Index(fields=['journal_entry_id']),
        ]
        verbose_name = 'Lab Bill'
        verbose_name_plural = 'Lab Bills'
    
    def save(self, *args, **kwargs):
        # Generate bill number if not set
        if not self.bill_number:
            today = timezone.now().strftime('%Y%m%d')
            last_bill = LabBill.objects.filter(
                bill_number__startswith=f'LAB-{today}'
            ).order_by('-bill_number').first()
            
            if last_bill:
                last_num = int(last_bill.bill_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.bill_number = f'LAB-{today}-{new_num:04d}'
        
        # Calculate balance due
        self.balance_due = self.total - self.amount_paid
        
        # Update payment status based on balance
        if self.payment_status != 'CANCELLED':
            if self.balance_due <= 0:
                self.payment_status = 'PAID'
            elif self.amount_paid > 0:
                self.payment_status = 'PARTIAL'
            else:
                self.payment_status = 'PENDING'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.bill_number} - {self.patient.user.full_name} - {self.total}"
    
    def get_payment_status_display(self):
        return dict(self.PAYMENT_STATUS_CHOICES).get(self.payment_status, self.payment_status)
    
    def get_payment_method_display(self):
        return dict(self.PAYMENT_METHOD_CHOICES).get(self.payment_method, self.payment_method)
    
    def is_paid(self):
        return self.payment_status == 'PAID'
    
    def is_cancelled(self):
        return self.payment_status == 'CANCELLED'


class LabBillItem(models.Model):
    """
    Individual items on a lab bill
    Each item represents one test type
    """
    bill = models.ForeignKey(
        LabBill, 
        on_delete=models.CASCADE, 
        related_name='items'
    )
    test_type = models.ForeignKey(
        'LabTestType', 
        on_delete=models.PROTECT, 
        related_name='bill_items'
    )
    test_name = models.CharField(
        max_length=200,
        help_text="Denormalized test name for history"
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    total = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="(unit_price * quantity) - discount"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'lab_bill_items'
        ordering = ['id']
        verbose_name = 'Lab Bill Item'
        verbose_name_plural = 'Lab Bill Items'
    
    def save(self, *args, **kwargs):
        # Calculate total
        self.total = (self.unit_price * self.quantity) - self.discount
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.test_name} - {self.quantity} x {self.unit_price}"
    
    def get_subtotal(self):
        return self.unit_price * self.quantity


class LabPayment(models.Model):
    """
    Payment records for lab bills
    """
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('CARD', 'Card'),
        ('ONLINE', 'Online'),
        ('INSURANCE', 'Insurance'),
        ('CREDIT', 'Credit'),
    ]
    
    bill = models.ForeignKey(
        LabBill, 
        on_delete=models.CASCADE, 
        related_name='payments'
    )
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    payment_method = models.CharField(
        max_length=20, 
        choices=PAYMENT_METHOD_CHOICES, 
        default='CASH'
    )
    transaction_id = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Transaction ID from payment gateway"
    )
    payment_date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='lab_payments_received'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'lab_payments'
        ordering = ['-payment_date']
        verbose_name = 'Lab Payment'
        verbose_name_plural = 'Lab Payments'
    
    def __str__(self):
        return f"{self.bill.bill_number} - {self.amount} ({self.payment_method})"
    
    def get_payment_method_display(self):
        return dict(self.PAYMENT_METHOD_CHOICES).get(self.payment_method, self.payment_method)


# ============================================================
# 6. SIGNALS FOR AUTO-BILLING LAB RECORDS (Optional)
# ============================================================

# You can add signals here to automatically create bills
# when lab records are completed, or you can do it manually
# via the API

# Example signal (uncomment if needed):
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# 
# @receiver(post_save, sender=LabRecord)
# def create_bill_on_completion(sender, instance, created, **kwargs):
#     """
#     Automatically create a bill when a lab record is completed
#     """
#     if not created and instance.status == 'COMPLETED':
#         # Check if bill already exists
#         if not instance.bills.exists():
#             from .services import LabBillingService
#             LabBillingService.create_bill_from_record(instance)