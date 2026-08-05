# cryo/models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import random

User = get_user_model()


# ============================================================
# 1. CRYO TANK
# ============================================================

class CryoTank(models.Model):
    """Liquid Nitrogen Storage Tank"""
    
    TANK_TYPES = [
        ('LN2', 'Liquid Nitrogen'),
        ('FREEZER', 'Freezer'),
        ('CRYO', 'Cryo Tank'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('MAINTENANCE', 'Under Maintenance'),
        ('FULL', 'Full'),
        ('EMPTY', 'Empty'),
        ('OFFLINE', 'Offline'),
    ]
    
    name = models.CharField(max_length=50, unique=True, help_text="Tank name (e.g., Tank A)")
    tank_type = models.CharField(max_length=20, choices=TANK_TYPES, default='LN2')
    capacity = models.IntegerField(help_text="Total vial capacity")
    current_usage = models.IntegerField(default=0, help_text="Current vials stored")
    
    # Physical Location
    room = models.CharField(max_length=100, blank=True, help_text="Room location")
    section = models.CharField(max_length=100, blank=True, help_text="Section in room")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    
    # RFID Reader (Future)
    rfid_reader_id = models.CharField(max_length=50, blank=True, help_text="RFID Reader ID")
    
    # Maintenance
    last_maintenance = models.DateField(null=True, blank=True)
    next_maintenance = models.DateField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cryo_tanks_created'
    )
    
    class Meta:
        db_table = 'cryo_tanks'
        ordering = ['name']
        verbose_name = 'Cryo Tank'
        verbose_name_plural = 'Cryo Tanks'
    
    def __str__(self):
        return f"{self.name} ({self.current_usage}/{self.capacity})"
    
    @property
    def available_space(self):
        return self.capacity - self.current_usage
    
    @property
    def usage_percentage(self):
        if self.capacity > 0:
            return round((self.current_usage / self.capacity) * 100, 1)
        return 0
    
    @property
    def is_full(self):
        return self.current_usage >= self.capacity


# ============================================================
# 2. CRYO CANISTER (RACK)
# ============================================================

class CryoCanister(models.Model):
    """Storage Canister inside Tank"""
    
    tank = models.ForeignKey(
        CryoTank,
        on_delete=models.CASCADE,
        related_name='canisters'
    )
    canister_number = models.CharField(max_length=20, help_text="Canister number (e.g., Canister B)")
    capacity = models.IntegerField(default=10, help_text="Number of canes")
    current_usage = models.IntegerField(default=0)
    
    # RFID (Future)
    canister_rfid = models.CharField(max_length=50, blank=True, null=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cryo_canisters'
        unique_together = ['tank', 'canister_number']
        ordering = ['tank', 'canister_number']
        verbose_name = 'Cryo Canister'
        verbose_name_plural = 'Cryo Canisters'
    
    def __str__(self):
        return f"{self.tank.name} - {self.canister_number}"
    
    @property
    def available_space(self):
        return self.capacity - self.current_usage
    
    @property
    def is_full(self):
        return self.current_usage >= self.capacity


# ============================================================
# 3. CRYO CANE (BOX)
# ============================================================

class CryoCane(models.Model):
    """Storage Cane inside Canister"""
    
    canister = models.ForeignKey(
        CryoCanister,
        on_delete=models.CASCADE,
        related_name='canes'
    )
    cane_number = models.CharField(max_length=20, help_text="Cane number (e.g., Cane 3)")
    capacity = models.IntegerField(default=9, help_text="Number of goblets")
    current_usage = models.IntegerField(default=0)
    
    # RFID (Future)
    cane_rfid = models.CharField(max_length=50, blank=True, null=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cryo_canes'
        unique_together = ['canister', 'cane_number']
        ordering = ['canister', 'cane_number']
        verbose_name = 'Cryo Cane'
        verbose_name_plural = 'Cryo Canes'
    
    def __str__(self):
        return f"{self.canister} - Cane {self.cane_number}"
    
    @property
    def available_space(self):
        return self.capacity - self.current_usage
    
    @property
    def is_full(self):
        return self.current_usage >= self.capacity


# ============================================================
# 4. CRYO GOBLET (POSITION)
# ============================================================

class CryoGoblet(models.Model):
    """Storage Goblet inside Cane"""
    
    GOBLET_STATUS = [
        ('EMPTY', 'Empty'),
        ('OCCUPIED', 'Occupied'),
        ('RESERVED', 'Reserved'),
        ('DAMAGED', 'Damaged'),
    ]
    
    COLOR_CHOICES = [
        ('WHITE', 'White'),
        ('RED', 'Red'),
        ('BLUE', 'Blue'),
        ('GREEN', 'Green'),
        ('YELLOW', 'Yellow'),
        ('PURPLE', 'Purple'),
        ('ORANGE', 'Orange'),
        ('PINK', 'Pink'),
    ]
    
    cane = models.ForeignKey(
        CryoCane,
        on_delete=models.CASCADE,
        related_name='goblets'
    )
    goblet_number = models.CharField(max_length=10, help_text="Goblet number (e.g., Goblet 2)")
    color = models.CharField(max_length=20, choices=COLOR_CHOICES, default='WHITE')
    status = models.CharField(max_length=20, choices=GOBLET_STATUS, default='EMPTY')
    
    # RFID (Future)
    goblet_rfid = models.CharField(max_length=50, blank=True, null=True)
    
    class Meta:
        db_table = 'cryo_goblets'
        unique_together = ['cane', 'goblet_number']
        ordering = ['cane', 'goblet_number']
        verbose_name = 'Cryo Goblet'
        verbose_name_plural = 'Cryo Goblets'
    
    def __str__(self):
        return f"{self.cane} - Goblet {self.goblet_number} ({self.get_status_display()})"


# ============================================================
# 5. CRYO STORED SAMPLE
# ============================================================

class CryoStoredSample(models.Model):
    """Main Storage Record"""
    
    SAMPLE_TYPES = [
        ('SPERM', 'Sperm Sample'),
        ('EGG', 'Egg/Oocyte'),
        ('EMBRYO', 'Embryo'),
        ('TISSUE', 'Tissue Sample'),
        ('TESTICULAR', 'Testicular Tissue'),
        ('OVARIAN', 'Ovarian Tissue'),
        ('OTHER', 'Other'),
    ]
    
    STORAGE_STATUS = [
        ('STORED', 'Stored'),
        ('RESERVED', 'Reserved'),
        ('THAWED', 'Thawed'),
        ('USED', 'Used'),
        ('DISCARDED', 'Discarded'),
        ('EXPIRED', 'Expired'),
        ('TRANSFERRED', 'Transferred'),
    ]
    
    FREEZING_METHOD = [
        ('VITRIFICATION', 'Vitrification'),
        ('SLOW_FREEZE', 'Slow Freeze'),
        ('ULTRA_RAPID', 'Ultra Rapid'),
    ]
    
    # Patient
    patient = models.ForeignKey(
        'patients.PatientProfile',
        on_delete=models.CASCADE,
        related_name='cryo_samples'
    )
    
    # Sample Info
    sample_type = models.CharField(max_length=20, choices=SAMPLE_TYPES)
    sample_id = models.CharField(max_length=50, unique=True, blank=True)
    
    # Sample Details
    vial_count = models.IntegerField(default=1)
    vial_volume = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Volume in mL"
    )
    concentration = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Concentration (million/mL)"
    )
    motility = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Motility percentage (%)"
    )
    morphology = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Normal morphology (%)"
    )
    
    # Location
    tank = models.ForeignKey(
        CryoTank,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='samples'
    )
    canister = models.ForeignKey(
        CryoCanister,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='samples'
    )
    cane = models.ForeignKey(
        CryoCane,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='samples'
    )
    goblet = models.ForeignKey(
        CryoGoblet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='samples'
    )
    
    # RFID (Future)
    rfid_tag = models.CharField(max_length=50, unique=True, blank=True, null=True)
    rfid_epc = models.CharField(max_length=50, blank=True, null=True)
    
    # Storage Details
    freezing_method = models.CharField(max_length=20, choices=FREEZING_METHOD, default='VITRIFICATION')
    storage_date = models.DateTimeField(default=timezone.now)
    expiry_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STORAGE_STATUS, default='STORED')
    
    # Thawing
    thawed_date = models.DateTimeField(null=True, blank=True)
    thawed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cryo_thawed'
    )
    post_thaw_survival = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    thaw_notes = models.TextField(blank=True)
    
    # Usage
    used_for = models.CharField(max_length=100, blank=True)
    used_date = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cryo_used'
    )
    
    # Notes & Audit
    notes = models.TextField(blank=True)
    stored_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cryo_stored'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cryo_stored_samples'
        ordering = ['-storage_date']
        verbose_name = 'Stored Sample'
        verbose_name_plural = 'Stored Samples'
        indexes = [
            models.Index(fields=['sample_id']),
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['rfid_tag']),
            models.Index(fields=['sample_type']),
        ]
    
    def __str__(self):
        return f"{self.sample_id} - {self.patient.user.full_name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate sample ID
        if not self.sample_id:
            today = timezone.now().strftime('%Y%m%d')
            rand_num = random.randint(100, 999)
            self.sample_id = f"{self.sample_type}-{today}-{rand_num}"
        
        # Auto-generate RFID tag
        if not self.rfid_tag:
            today = timezone.now().strftime('%Y%m%d')
            rand_num = random.randint(1000, 9999)
            self.rfid_tag = f"EPC-{today}-{rand_num}"
        
        # Set expiry date (10 years from storage)
        if not self.expiry_date and self.storage_date:
            from datetime import timedelta
            self.expiry_date = self.storage_date.date() + timedelta(days=3650)
        
        # Update location status when storing
        if self.goblet and self.status == 'STORED':
            self.goblet.status = 'OCCUPIED'
            self.goblet.save()
            
            if self.cane:
                self.cane.current_usage += 1
                self.cane.save()
                
                if self.canister:
                    self.canister.current_usage += 1
                    self.canister.save()
                    
                    if self.tank:
                        self.tank.current_usage += 1
                        self.tank.save()
        
        super().save(*args, **kwargs)
    
    @property
    def full_location(self):
        """Get full location path"""
        parts = []
        if self.tank:
            parts.append(self.tank.name)
        if self.canister:
            parts.append(self.canister.canister_number)
        if self.cane:
            parts.append(f"Cane {self.cane.cane_number}")
        if self.goblet:
            parts.append(f"Goblet {self.goblet.goblet_number}")
        return " → ".join(parts) if parts else "Location not set"