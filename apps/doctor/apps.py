# apps/doctor/apps.py
from django.apps import AppConfig

class DoctorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.doctor'
    label = 'doctor'
    verbose_name = 'Doctor Portal'