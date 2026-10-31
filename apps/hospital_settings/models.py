# apps/hospital_settings/models.py

from django.db import models
from django.core.validators import FileExtensionValidator
from django.conf import settings

class HospitalSettings(models.Model):
    """
    Singleton model for hospital configuration.
    Only one instance should exist (id=1).
    """
    
    # Basic Information
    hospital_name = models.CharField(
        max_length=255,
        default="Fertility Clinic",
        help_text="Full name of the hospital"
    )
    hospital_short_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Short name or abbreviation"
    )
    hospital_tagline = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Tagline or slogan"
    )
    
    # Contact Information
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Main phone number"
    )
    phone_secondary = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Secondary phone number"
    )
    email = models.EmailField(
        blank=True,
        null=True,
        help_text="Main email address"
    )
    email_secondary = models.EmailField(
        blank=True,
        null=True,
        help_text="Secondary email address"
    )
    address = models.TextField(
        blank=True,
        null=True,
        help_text="Physical address"
    )
    address_line2 = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Address line 2"
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    state = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    postal_code = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )
    country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        default="India"
    )
    website = models.URLField(
        blank=True,
        null=True,
        help_text="Website URL"
    )
    
    # Social Media
    facebook_url = models.URLField(blank=True, null=True)
    twitter_url = models.URLField(blank=True, null=True)
    instagram_url = models.URLField(blank=True, null=True)
    youtube_url = models.URLField(blank=True, null=True)
    linkedin_url = models.URLField(blank=True, null=True)
    
    # Logo and Branding
    logo = models.ImageField(
        upload_to='hospital/logos/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'svg', 'webp'])],
        help_text="Upload hospital logo (JPG, PNG, SVG, WEBP)"
    )
    logo_light = models.ImageField(
        upload_to='hospital/logos/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'svg', 'webp'])],
        help_text="Light version of logo for dark backgrounds"
    )
    favicon = models.ImageField(
        upload_to='hospital/favicons/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(['ico', 'png'])],
        help_text="Upload favicon (ICO, PNG)"
    )
    
    # Theme Colors
    primary_color = models.CharField(
        max_length=7,
        default='#0d6efd',
        help_text="Primary color (hex code)"
    )
    primary_color_dark = models.CharField(
        max_length=7,
        default='#0a58ca',
        help_text="Dark primary color (hex code)"
    )
    secondary_color = models.CharField(
        max_length=7,
        default='#6c757d',
        help_text="Secondary color (hex code)"
    )
    accent_color = models.CharField(
        max_length=7,
        default='#0dcaf0',
        help_text="Accent color (hex code)"
    )
    success_color = models.CharField(
        max_length=7,
        default='#198754',
        help_text="Success color (hex code)"
    )
    warning_color = models.CharField(
        max_length=7,
        default='#ffc107',
        help_text="Warning color (hex code)"
    )
    danger_color = models.CharField(
        max_length=7,
        default='#dc3545',
        help_text="Danger color (hex code)"
    )
    
    # Footer Information
    footer_text = models.TextField(
        blank=True,
        null=True,
        help_text="Footer text or copyright information"
    )
    footer_links = models.JSONField(
        default=list,
        blank=True,
        help_text="Footer links (JSON format)"
    )
    
    # System Settings
    timezone = models.CharField(
        max_length=50,
        default='Asia/Kolkata',
        help_text="Default timezone"
    )
    date_format = models.CharField(
        max_length=20,
        default='Y-m-d',
        help_text="Date format (e.g., Y-m-d, d/m/Y)"
    )
    time_format = models.CharField(
        max_length=20,
        default='H:i',
        help_text="Time format (e.g., H:i, h:i A)"
    )
    currency = models.CharField(
        max_length=10,
        default='INR',
        help_text="Currency code"
    )
    currency_symbol = models.CharField(
        max_length=10,
        default='₹',
        help_text="Currency symbol"
    )
    
    # Business Hours
    business_hours = models.JSONField(
        default=dict,
        blank=True,
        help_text="Business hours configuration"
    )
    
    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hospital_settings_updates'
    )
    
    class Meta:
        verbose_name = "Hospital Settings"
        verbose_name_plural = "Hospital Settings"
        db_table = 'hospital_settings'
    
    def __str__(self):
        return self.hospital_name
    
    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance"""
        settings, created = cls.objects.get_or_create(id=1)
        return settings
    
    def get_logo_url(self, request=None):
        """Get the full URL of the logo"""
        if self.logo and hasattr(self.logo, 'url'):
            if request:
                return request.build_absolute_uri(self.logo.url)
            return self.logo.url
        return None
    
    def get_logo_light_url(self, request=None):
        """Get the full URL of the light logo"""
        if self.logo_light and hasattr(self.logo_light, 'url'):
            if request:
                return request.build_absolute_uri(self.logo_light.url)
            return self.logo_light.url
        return None
    
    def get_favicon_url(self, request=None):
        """Get the full URL of the favicon"""
        if self.favicon and hasattr(self.favicon, 'url'):
            if request:
                return request.build_absolute_uri(self.favicon.url)
            return self.favicon.url
        return None
    
    def get_full_address(self):
        """Get complete formatted address"""
        parts = []
        if self.address:
            parts.append(self.address)
        if self.address_line2:
            parts.append(self.address_line2)
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(self.state)
        if self.postal_code:
            parts.append(self.postal_code)
        if self.country:
            parts.append(self.country)
        return ', '.join(parts)