# apps/nurse/models.py
from django.db import models
from django.conf import settings
from accounts.models import NurseProfile
from patients.models import PatientProfile


class PatientVital(models.Model):
    """
    Patient Vital Signs Model - For nurses to record patient vitals
    """
    # Relationships
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='vitals'
    )
    nurse = models.ForeignKey(
        NurseProfile,
        on_delete=models.CASCADE,
        related_name='recorded_vitals'
    )
    
    # Vital Signs
    blood_pressure_systolic = models.IntegerField(null=True, blank=True, help_text="Systolic BP in mmHg")
    blood_pressure_diastolic = models.IntegerField(null=True, blank=True, help_text="Diastolic BP in mmHg")
    heart_rate = models.IntegerField(null=True, blank=True, help_text="Heart rate in bpm")
    respiratory_rate = models.IntegerField(null=True, blank=True, help_text="Respiratory rate in breaths/min")
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="Temperature in °F")
    blood_sugar = models.IntegerField(null=True, blank=True, help_text="Blood sugar in mg/dL")
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Weight in kg")
    height = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Height in cm")
    bmi = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="BMI")
    oxygen_saturation = models.IntegerField(null=True, blank=True, help_text="SpO2 in %")
    pain_score = models.IntegerField(null=True, blank=True, choices=[(i, str(i)) for i in range(0, 11)], help_text="Pain score 0-10")
    
    # Additional Info
    notes = models.TextField(blank=True)
    medications_given = models.TextField(blank=True, help_text="Medications administered")
    is_emergency = models.BooleanField(default=False)
    
    # Metadata
    recorded_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'patient_vitals'
        verbose_name = 'Patient Vital'
        verbose_name_plural = 'Patient Vitals'
        ordering = ['-recorded_at']
    
    def __str__(self):
        return f"{self.patient.user.full_name} - {self.recorded_at.strftime('%Y-%m-%d %H:%M')}"
    
    def calculate_bmi(self):
        """Calculate BMI if weight and height are available"""
        if self.weight and self.height and self.height > 0:
            height_m = self.height / 100  # Convert cm to m
            return round(self.weight / (height_m ** 2), 2)
        return None
    
    def save(self, *args, **kwargs):
        """Auto-calculate BMI before saving"""
        if self.weight and self.height:
            self.bmi = self.calculate_bmi()
        super().save(*args, **kwargs)
    
    @property
    def blood_pressure(self):
        """Get formatted blood pressure"""
        if self.blood_pressure_systolic and self.blood_pressure_diastolic:
            return f"{self.blood_pressure_systolic}/{self.blood_pressure_diastolic}"
        return None
    
    @property
    def is_abnormal(self):
        """Check if any vital is abnormal"""
        # BP: Normal < 120/80
        if self.blood_pressure_systolic and self.blood_pressure_systolic > 140:
            return True
        if self.blood_pressure_diastolic and self.blood_pressure_diastolic > 90:
            return True
        # Heart Rate: Normal 60-100
        if self.heart_rate and (self.heart_rate < 60 or self.heart_rate > 100):
            return True
        # Temperature: Normal 97.7-99.5
        if self.temperature and (self.temperature < 97.7 or self.temperature > 99.5):
            return True
        # Blood Sugar: Normal 70-140
        if self.blood_sugar and (self.blood_sugar < 70 or self.blood_sugar > 140):
            return True
        # Oxygen: Normal > 95
        if self.oxygen_saturation and self.oxygen_saturation < 95:
            return True
        return False


class PatientVitalHistory(models.Model):
    """
    Track changes to patient vitals for audit
    """
    vital = models.ForeignKey(PatientVital, on_delete=models.CASCADE, related_name='history')
    changed_by = models.ForeignKey(NurseProfile, on_delete=models.CASCADE)
    changes = models.JSONField(default=dict)
    changed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'patient_vital_history'
        verbose_name = 'Vital History'
        verbose_name_plural = 'Vital Histories'
        ordering = ['-changed_at']
    
    def __str__(self):
        return f"{self.vital.patient.user.full_name} - {self.changed_at}"