# apps/nurse/apps.py
from django.apps import AppConfig


class NurseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.nurse'
    verbose_name = 'Nurse Management'

    # Comment out or remove the ready method if it imports signals
    # def ready(self):
    #     import apps.nurse.signals