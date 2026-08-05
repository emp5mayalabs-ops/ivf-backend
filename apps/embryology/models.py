# embryology/models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class EmbryologistProfile(models.Model):
    """
    Embryologist Profile Model
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='embryology_profile'  # ← CHANGED THIS
    )
    
    # Basic Info
    employee_id = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        help_text="Employee ID"
    )
    contact_number = models.CharField(
        max_length=15,
        blank=True,
        help_text="Contact number"
    )
    
    # Professional Info
    specialization = models.CharField(
        max_length=100,
        blank=True,
        help_text="Specialization area"
    )
    years_of_experience = models.IntegerField(
        default=0,
        help_text="Years of experience"
    )
    
    # Permissions
    is_department_head = models.BooleanField(
        default=False,
        help_text="Is department head?"
    )
    can_perform_icsi = models.BooleanField(
        default=True,
        help_text="Can perform ICSI?"
    )
    can_perform_biopsy = models.BooleanField(
        default=True,
        help_text="Can perform biopsy?"
    )
    can_perform_embryo_biopsy = models.BooleanField(
        default=True,
        help_text="Can perform embryo biopsy?"
    )
    can_handle_cryo = models.BooleanField(
        default=True,
        help_text="Can handle cryopreservation?"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'embryology_profiles'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Embryologist: {self.user.full_name}"