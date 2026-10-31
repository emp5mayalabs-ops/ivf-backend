# apps/hospital_settings/serializers.py

from rest_framework import serializers
from .models import HospitalSettings

class HospitalSettingsSerializer(serializers.ModelSerializer):
    """Serializer for hospital settings"""
    
    logo_url = serializers.SerializerMethodField()
    logo_light_url = serializers.SerializerMethodField()
    favicon_url = serializers.SerializerMethodField()
    full_address = serializers.SerializerMethodField()
    
    class Meta:
        model = HospitalSettings
        fields = [
            'id', 'hospital_name', 'hospital_short_name', 'hospital_tagline',
            'phone', 'phone_secondary', 'email', 'email_secondary',
            'address', 'address_line2', 'city', 'state', 'postal_code', 
            'country', 'website', 'full_address',
            'facebook_url', 'twitter_url', 'instagram_url', 
            'youtube_url', 'linkedin_url',
            'logo', 'logo_url', 'logo_light', 'logo_light_url',
            'favicon', 'favicon_url',
            'primary_color', 'primary_color_dark', 'secondary_color',
            'accent_color', 'success_color', 'warning_color', 'danger_color',
            'footer_text', 'footer_links',
            'timezone', 'date_format', 'time_format',
            'currency', 'currency_symbol',
            'business_hours',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_logo_url(self, obj):
        request = self.context.get('request')
        return obj.get_logo_url(request)
    
    def get_logo_light_url(self, obj):
        request = self.context.get('request')
        return obj.get_logo_light_url(request)
    
    def get_favicon_url(self, obj):
        request = self.context.get('request')
        return obj.get_favicon_url(request)
    
    def get_full_address(self, obj):
        return obj.get_full_address()
    
    def update(self, instance, validated_data):
        # Track who updated
        request = self.context.get('request')
        if request and request.user:
            validated_data['updated_by'] = request.user
        return super().update(instance, validated_data)