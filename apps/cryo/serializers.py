# cryo/serializers.py

from rest_framework import serializers
from django.utils import timezone
from .models import (
    CryoTank,
    CryoCanister,
    CryoCane,
    CryoGoblet,
    CryoStoredSample
)


# ============================================================
# TANK SERIALIZERS
# ============================================================

class CryoTankSerializer(serializers.ModelSerializer):
    """Complete Tank Serializer"""
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tank_type_display = serializers.CharField(source='get_tank_type_display', read_only=True)
    available_space = serializers.IntegerField(read_only=True)
    usage_percentage = serializers.FloatField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = CryoTank
        fields = [
            'id', 'name', 'tank_type', 'tank_type_display',
            'capacity', 'current_usage', 'available_space',
            'usage_percentage', 'is_full',
            'room', 'section',
            'status', 'status_display',
            'rfid_reader_id',
            'last_maintenance', 'next_maintenance',
            'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CryoTankListSerializer(serializers.ModelSerializer):
    """Lightweight Tank List Serializer"""
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    usage_percentage = serializers.FloatField(read_only=True)
    
    class Meta:
        model = CryoTank
        fields = [
            'id', 'name', 'capacity', 'current_usage',
            'usage_percentage', 'status', 'status_display'
        ]


# ============================================================
# CANISTER SERIALIZERS
# ============================================================

class CryoCanisterSerializer(serializers.ModelSerializer):
    """Canister Serializer"""
    
    tank_name = serializers.CharField(source='tank.name', read_only=True)
    available_space = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = CryoCanister
        fields = [
            'id', 'tank', 'tank_name',
            'canister_number', 'capacity', 'current_usage',
            'available_space', 'is_full',
            'canister_rfid',
            'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================
# CANE SERIALIZERS
# ============================================================

class CryoCaneSerializer(serializers.ModelSerializer):
    """Cane Serializer"""
    
    canister_info = serializers.CharField(source='canister.__str__', read_only=True)
    available_space = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = CryoCane
        fields = [
            'id', 'canister', 'canister_info',
            'cane_number', 'capacity', 'current_usage',
            'available_space', 'is_full',
            'cane_rfid',
            'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================
# GOBLET SERIALIZERS
# ============================================================

class CryoGobletSerializer(serializers.ModelSerializer):
    """Goblet Serializer"""
    
    cane_info = serializers.CharField(source='cane.__str__', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    color_display = serializers.CharField(source='get_color_display', read_only=True)
    
    class Meta:
        model = CryoGoblet
        fields = [
            'id', 'cane', 'cane_info',
            'goblet_number', 'color', 'color_display',
            'status', 'status_display',
            'goblet_rfid'
        ]
        read_only_fields = ['id']


# ============================================================
# STORED SAMPLE SERIALIZERS
# ============================================================

class CryoStoredSampleSerializer(serializers.ModelSerializer):
    """Complete Stored Sample Serializer"""
    
    # Patient Info
    patient_name = serializers.CharField(source='patient.user.full_name', read_only=True)
    patient_id = serializers.CharField(source='patient.patient_id', read_only=True)
    
    # Location Info
    tank_name = serializers.CharField(source='tank.name', read_only=True)
    canister_number = serializers.CharField(source='canister.canister_number', read_only=True)
    cane_number = serializers.CharField(source='cane.cane_number', read_only=True)
    goblet_number = serializers.CharField(source='goblet.goblet_number', read_only=True)
    full_location = serializers.CharField(read_only=True)
    
    # Display Fields
    sample_type_display = serializers.CharField(source='get_sample_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    freezing_method_display = serializers.CharField(source='get_freezing_method_display', read_only=True)
    stored_by_name = serializers.CharField(source='stored_by.full_name', read_only=True)
    thawed_by_name = serializers.CharField(source='thawed_by.full_name', read_only=True)
    
    class Meta:
        model = CryoStoredSample
        fields = [
            'id',
            'sample_id',
            'sample_type',
            'sample_type_display',
            'patient',
            'patient_name',
            'patient_id',
            
            # Location
            'tank',
            'tank_name',
            'canister',
            'canister_number',
            'cane',
            'cane_number',
            'goblet',
            'goblet_number',
            'full_location',
            
            # Sample Details
            'vial_count',
            'vial_volume',
            'concentration',
            'motility',
            'morphology',
            
            # RFID
            'rfid_tag',
            'rfid_epc',
            
            # Storage
            'freezing_method',
            'freezing_method_display',
            'storage_date',
            'expiry_date',
            'status',
            'status_display',
            
            # Thawing
            'thawed_date',
            'thawed_by',
            'thawed_by_name',
            'post_thaw_survival',
            'thaw_notes',
            
            # Usage
            'used_for',
            'used_date',
            'used_by',
            
            # Notes
            'notes',
            'stored_by',
            'stored_by_name',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id', 'sample_id', 'rfid_tag', 'full_location',
            'created_at', 'updated_at'
        ]
    
    def create(self, validated_data):
        if self.context.get('request'):
            validated_data['stored_by'] = self.context['request'].user
        return super().create(validated_data)


class CryoStoredSampleListSerializer(serializers.ModelSerializer):
    """Lightweight Sample List Serializer"""
    
    patient_name = serializers.CharField(source='patient.user.full_name', read_only=True)
    sample_type_display = serializers.CharField(source='get_sample_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    full_location = serializers.CharField(read_only=True)
    days_in_storage = serializers.SerializerMethodField()
    
    class Meta:
        model = CryoStoredSample
        fields = [
            'id',
            'sample_id',
            'sample_type',
            'sample_type_display',
            'patient_name',
            'full_location',
            'storage_date',
            'expiry_date',
            'status',
            'status_display',
            'days_in_storage',
        ]
    
    def get_days_in_storage(self, obj):
        if obj.storage_date:
            delta = timezone.now() - obj.storage_date
            return delta.days
        return 0