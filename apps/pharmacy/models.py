# apps/pharmacy/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

User = settings.AUTH_USER_MODEL

# ========== EXISTING PHARMACIST PROFILE ==========
class PharmacistProfile(models.Model):
    user = models.OneToOneField(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='pharmacist_profile'
    )
    employee_id = models.CharField(max_length=20, unique=True, blank=True, help_text='PH001')
    license_number = models.CharField(max_length=50, blank=True)
    qualification = models.CharField(max_length=100, blank=True)
    store_location = models.CharField(max_length=55, blank=True, help_text='First Floor')
    
    can_manage_inventory = models.BooleanField(default=False)
    is_department_head = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    date_assigned = models.DateField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.employee_id:
            last_profile = PharmacistProfile.objects.order_by('-id').first()
            if not last_profile:
                self.employee_id = "PH001"
            else:
                last_id = int(last_profile.employee_id.replace("PH", ""))
                new_id = last_id + 1
                self.employee_id = f"PH{new_id:03d}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Pharmacist {self.user.full_name}"
    
    def get_role_display(self):
        return "Pharmacist"


# ========== NEW INVENTORY MODELS ==========

class MedicationCategory(models.Model):
    """Categories for medications"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    requires_prescription = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Medication Categories"
        ordering = ['name']


class MedicationManufacturer(models.Model):
    """Manufacturers of medications"""
    name = models.CharField(max_length=200, unique=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Medication(models.Model):
    """Main medication/inventory item"""
    UNIT_CHOICES = [
        ('IU', 'IU'),
        ('MG', 'mg'),
        ('MCG', 'mcg'),
        ('ML', 'ml'),
        ('G', 'g'),
        ('TABLET', 'Tablet'),
        ('CAPSULE', 'Capsule'),
        ('VIAL', 'Vial'),
        ('AMPOULE', 'Ampoule'),
        ('BOX', 'Box'),
        ('UNIT', 'Unit'),
    ]

    medication_id = models.CharField(max_length=20, unique=True, editable=False)
    
    # Basic Information
    name = models.CharField(max_length=200)
    generic_name = models.CharField(max_length=200, blank=True)
    category = models.ForeignKey(
        MedicationCategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='medications'
    )
    manufacturer = models.ForeignKey(
        MedicationManufacturer, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='medications'
    )
    
    # Pricing & Unit
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='UNIT')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Stock Management
    current_stock = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=10)
    minimum_stock = models.IntegerField(default=5)
    maximum_stock = models.IntegerField(default=50)
    
    # Expiry Tracking
    expiry_date = models.DateField(null=True, blank=True)
    batch_number = models.CharField(max_length=50, blank=True)
    
    # Storage
    storage_location = models.CharField(max_length=100, blank=True)
    temperature_requirement = models.CharField(max_length=50, blank=True)
    special_handling = models.TextField(blank=True)
    
    # Restrictions
    requires_prescription = models.BooleanField(default=True)
    is_controlled = models.BooleanField(default=False)
    requires_refrigeration = models.BooleanField(default=False)
    requires_doctor_approval = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    
    # Additional Info
    side_effects = models.TextField(blank=True)
    interactions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    # Metadata
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='medications_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='medications_updated'
    )
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.medication_id:
            # Generate medication ID: MED-2026001
            year = timezone.now().strftime('%Y')
            last = Medication.objects.filter(
                medication_id__startswith=f'MED-{year}'
            ).count()
            self.medication_id = f'MED-{year}{str(last + 1).zfill(4)}'
        
        # Calculate selling price
        if self.unit_price and self.tax_rate:
            self.selling_price = self.unit_price * (1 + self.tax_rate / 100)
        
        # Update availability
        self.is_available = self.current_stock > 0
        
        super().save(*args, **kwargs)

    def get_stock_status(self):
        """Get stock status"""
        if self.current_stock <= 0:
            return 'OUT_OF_STOCK'
        elif self.current_stock <= self.minimum_stock:
            return 'CRITICAL'
        elif self.current_stock <= self.reorder_level:
            return 'LOW_STOCK'
        else:
            return 'IN_STOCK'

    def get_stock_status_display(self):
        """Get stock status display"""
        statuses = {
            'IN_STOCK': '✅ In Stock',
            'LOW_STOCK': '⚠️ Low Stock',
            'CRITICAL': '🔴 Critical',
            'OUT_OF_STOCK': '❌ Out of Stock'
        }
        return statuses.get(self.get_stock_status(), 'Unknown')

    def is_expiring_soon(self, days=30):
        """Check if medication is expiring soon"""
        if not self.expiry_date:
            return False
        return self.expiry_date <= timezone.now().date() + timedelta(days=days)

    def is_expired(self):
        """Check if medication is expired"""
        if not self.expiry_date:
            return False
        return self.expiry_date < timezone.now().date()

    def __str__(self):
        return f"{self.name} ({self.medication_id})"

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['category']),
            models.Index(fields=['current_stock']),
            models.Index(fields=['expiry_date']),
        ]


class StockAdjustment(models.Model):
    """Track all stock movements"""
    ADJUSTMENT_TYPES = [
        ('ADD', 'Add Stock'),
        ('REMOVE', 'Remove Stock'),
        ('SET', 'Set Quantity'),
        ('DAMAGED', 'Damaged'),
        ('EXPIRED', 'Expired'),
        ('RETURNED', 'Returned'),
        ('DISPENSED', 'Dispensed'),
    ]

    REASON_CHOICES = [
        ('PURCHASE', 'Purchase Order'),
        ('DISPENSING', 'Dispensing to Patient'),
        ('RETURN', 'Return from Patient'),
        ('DAMAGE', 'Damaged Goods'),
        ('EXPIRY', 'Expired Stock'),
        ('INVENTORY', 'Inventory Count'),
        ('OTHER', 'Other'),
    ]

    adjustment_id = models.CharField(max_length=20, unique=True, editable=False)
    
    medication = models.ForeignKey(
        Medication, 
        on_delete=models.CASCADE, 
        related_name='stock_adjustments'
    )
    adjustment_type = models.CharField(max_length=20, choices=ADJUSTMENT_TYPES)
    quantity = models.IntegerField()
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    reference = models.CharField(max_length=100, blank=True)  # RX ID, PO ID, etc.
    
    # Stock before/after
    stock_before = models.IntegerField()
    stock_after = models.IntegerField()
    
    # Additional info
    notes = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='stock_adjustments'
    )
    performed_at = models.DateTimeField(auto_now_add=True)
    
    # Approval (if needed)
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='stock_adjustments_approved'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.adjustment_id:
            year = timezone.now().strftime('%Y')
            last = StockAdjustment.objects.filter(
                adjustment_id__startswith=f'ADJ-{year}'
            ).count()
            self.adjustment_id = f'ADJ-{year}{str(last + 1).zfill(6)}'
        
        # Update medication stock
        medication = self.medication
        self.stock_before = medication.current_stock
        
        if self.adjustment_type in ['ADD', 'RETURNED']:
            self.stock_after = self.stock_before + self.quantity
        elif self.adjustment_type in ['REMOVE', 'DAMAGED', 'EXPIRED', 'DISPENSED']:
            self.stock_after = max(0, self.stock_before - self.quantity)
        elif self.adjustment_type == 'SET':
            self.stock_after = self.quantity
        
        # Update medication stock
        medication.current_stock = self.stock_after
        medication.save()
        
        # Check and create alerts if needed
        self.check_stock_alerts(medication)
        
        super().save(*args, **kwargs)

    def check_stock_alerts(self, medication):
        """Check if stock alert needs to be created"""
        if medication.current_stock <= medication.minimum_stock:
            StockAlert.objects.get_or_create(
                medication=medication,
                alert_type='CRITICAL',
                defaults={
                    'message': f'Stock is at critical level: {medication.current_stock} units',
                    'status': 'ACTIVE'
                }
            )
        elif medication.current_stock <= medication.reorder_level:
            StockAlert.objects.get_or_create(
                medication=medication,
                alert_type='LOW_STOCK',
                defaults={
                    'message': f'Stock is below reorder level: {medication.current_stock} units',
                    'status': 'ACTIVE'
                }
            )
        else:
            # Resolve alerts if stock is sufficient
            StockAlert.objects.filter(
                medication=medication,
                status='ACTIVE'
            ).exclude(alert_type='EXPIRING').update(
                status='RESOLVED',
                resolved_at=timezone.now()
            )
        
        # Check for expiring alerts
        if medication.expiry_date:
            if medication.is_expired():
                StockAlert.objects.get_or_create(
                    medication=medication,
                    alert_type='EXPIRED',
                    defaults={
                        'message': f'Medication has expired on {medication.expiry_date}',
                        'status': 'ACTIVE'
                    }
                )
            elif medication.is_expiring_soon():
                StockAlert.objects.get_or_create(
                    medication=medication,
                    alert_type='EXPIRING',
                    defaults={
                        'message': f'Medication expires soon on {medication.expiry_date}',
                        'status': 'ACTIVE'
                    }
                )

    def __str__(self):
        return f"{self.adjustment_id} - {self.medication.name} ({self.quantity})"

    class Meta:
        ordering = ['-performed_at']
        indexes = [
            models.Index(fields=['medication']),
            models.Index(fields=['performed_at']),
        ]


class StockAlert(models.Model):
    """Stock alerts for medications"""
    ALERT_TYPES = [
        ('LOW_STOCK', 'Low Stock'),
        ('CRITICAL', 'Critical Stock'),
        ('EXPIRING', 'Expiring Soon'),
        ('EXPIRED', 'Expired'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('RESOLVED', 'Resolved'),
        ('DISMISSED', 'Dismissed'),
    ]

    alert_id = models.CharField(max_length=20, unique=True, editable=False)
    
    medication = models.ForeignKey(
        Medication, 
        on_delete=models.CASCADE, 
        related_name='alerts'
    )
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    dismissed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='dismissed_alerts'
    )

    def save(self, *args, **kwargs):
        if not self.alert_id:
            year = timezone.now().strftime('%Y')
            last = StockAlert.objects.filter(
                alert_id__startswith=f'ALT-{year}'
            ).count()
            self.alert_id = f'ALT-{year}{str(last + 1).zfill(6)}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.alert_id} - {self.medication.name} ({self.alert_type})"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['medication']),
            models.Index(fields=['alert_type']),
            models.Index(fields=['status']),
        ]