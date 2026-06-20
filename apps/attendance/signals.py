# apps/attendance/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import AttendanceSettings

User = get_user_model()


@receiver(post_save, sender=User)
def create_attendance_settings(sender, instance, created, **kwargs):
    """Auto-create attendance settings for new staff"""
    if created and instance.role not in ['PAT', 'DON']:
        # Create default attendance settings if needed
        pass