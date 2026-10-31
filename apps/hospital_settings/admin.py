# apps/hospital_settings/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import HospitalSettings

@admin.register(HospitalSettings)
class HospitalSettingsAdmin(admin.ModelAdmin):
    list_display = ['hospital_name', 'hospital_short_name', 'updated_at', 'updated_by']
    readonly_fields = ['created_at', 'updated_at', 'logo_preview', 'logo_light_preview', 'favicon_preview']
    
    fieldsets = (
        ('Hospital Information', {
            'fields': ('hospital_name', 'hospital_short_name', 'hospital_tagline')
        }),
        ('Contact Details', {
            'fields': ('phone', 'phone_secondary', 'email', 'email_secondary')
        }),
        ('Address', {
            'fields': ('address', 'address_line2', 'city', 'state', 'postal_code', 'country')
        }),
        ('Website & Social Media', {
            'fields': ('website', 'facebook_url', 'twitter_url', 'instagram_url', 'youtube_url', 'linkedin_url')
        }),
        ('Logo & Branding', {
            'fields': ('logo', 'logo_preview', 'logo_light', 'logo_light_preview', 'favicon', 'favicon_preview')
        }),
        ('Colors', {
            'fields': ('primary_color', 'primary_color_dark', 'secondary_color', 'accent_color', 'success_color', 'warning_color', 'danger_color')
        }),
        ('Footer Settings', {
            'fields': ('footer_text', 'footer_links')
        }),
        ('System Settings', {
            'fields': ('timezone', 'date_format', 'time_format', 'currency', 'currency_symbol')
        }),
        ('Business Hours', {
            'fields': ('business_hours',)
        }),
        ('Meta', {
            'fields': ('updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 200px;" />',
                obj.logo.url
            )
        return "-"
    logo_preview.short_description = "Logo Preview"
    
    def logo_light_preview(self, obj):
        if obj.logo_light:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 200px; background: #333;" />',
                obj.logo_light.url
            )
        return "-"
    logo_light_preview.short_description = "Light Logo Preview"
    
    def favicon_preview(self, obj):
        if obj.favicon:
            return format_html(
                '<img src="{}" style="max-height: 32px; max-width: 32px;" />',
                obj.favicon.url
            )
        return "-"
    favicon_preview.short_description = "Favicon Preview"
    
    def has_add_permission(self, request):
        # Prevent adding new instances (only one should exist)
        return False if HospitalSettings.objects.exists() else True
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion
        return False