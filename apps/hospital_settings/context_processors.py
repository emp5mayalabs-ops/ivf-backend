# apps/hospital_settings/context_processors.py

from .models import HospitalSettings

def hospital_settings(request):
    """Context processor to inject hospital settings into templates"""
    try:
        settings = HospitalSettings.get_settings()
        return {
            'hospital_settings': settings,
            'hospital_name': settings.hospital_name,
            'hospital_short_name': settings.hospital_short_name,
            'hospital_tagline': settings.hospital_tagline,
            'hospital_logo_url': settings.get_logo_url(request),
            'hospital_logo_light_url': settings.get_logo_light_url(request),
            'hospital_favicon_url': settings.get_favicon_url(request),
            'primary_color': settings.primary_color,
            'primary_color_dark': settings.primary_color_dark,
            'secondary_color': settings.secondary_color,
            'accent_color': settings.accent_color,
            'success_color': settings.success_color,
            'warning_color': settings.warning_color,
            'danger_color': settings.danger_color,
            'hospital_phone': settings.phone,
            'hospital_phone_secondary': settings.phone_secondary,
            'hospital_email': settings.email,
            'hospital_email_secondary': settings.email_secondary,
            'hospital_address': settings.get_full_address(),
            'hospital_footer_text': settings.footer_text,
            'hospital_currency': settings.currency,
            'hospital_currency_symbol': settings.currency_symbol,
        }
    except:
        return {
            'hospital_name': 'Fertility Clinic',
            'hospital_currency_symbol': '₹',
        }