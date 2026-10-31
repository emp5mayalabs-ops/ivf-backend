from django.core.management.base import BaseCommand
from hospital_settings.models import HospitalSettings

class Command(BaseCommand):
    help = 'Initialize hospital settings with default values'

    def handle(self, *args, **options):
        settings, created = HospitalSettings.objects.get_or_create(
            id=1,
            defaults={
                'hospital_name': 'Fertility Clinic',
                'hospital_tagline': 'Excellence in Reproductive Health',
                'primary_color': '#0d6efd',
                'primary_color_dark': '#0a58ca',
                'secondary_color': '#6c757d',
                'accent_color': '#0dcaf0',
                'success_color': '#198754',
                'warning_color': '#ffc107',
                'danger_color': '#dc3545',
                'currency': 'INR',
                'currency_symbol': '₹',
                'timezone': 'Asia/Kolkata',
                'date_format': 'Y-m-d',
                'time_format': 'H:i',
                'country': 'India',
            }
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS('Hospital settings initialized successfully!')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Hospital settings already exist.')
            )