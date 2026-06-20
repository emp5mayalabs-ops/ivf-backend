# apps/attendance/apps.py

from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'attendance'  # ✅ Changed from 'apps.attendance'
    label = 'attendance'
    verbose_name = 'Attendance Management'
    
    def ready(self):
        """Import signals when app is ready"""
        try:
            import attendance.signals  # ✅ Changed from apps.attendance.signals
        except ImportError:
            pass