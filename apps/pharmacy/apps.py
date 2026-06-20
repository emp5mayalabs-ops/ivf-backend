# apps/pharmacy/apps.py
from django.apps import AppConfig

class PharmacyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pharmacy'
    
    def ready(self):
        # Import signals if any
        pass