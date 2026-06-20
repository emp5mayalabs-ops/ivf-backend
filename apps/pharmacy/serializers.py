# apps/pharmacy/serializers.py
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Sum, Q
from .models import (
    PharmacistProfile, Medication, MedicationCategory,
    MedicationManufacturer, StockAdjustment, StockAlert
)

User = get_user_model()


# ========== AUTH SERIALIZERS ==========

class PharmacistLoginSerializer(serializers.Serializer):
    """
    Serializer for pharmacist login
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            raise serializers.ValidationError(
                {'error': 'Email and password are required'}
            )
        
        user = authenticate(email=email, password=password)
        
        if not user:
            raise serializers.ValidationError(
                {'error': 'Invalid email or password'}
            )
        
        if not user.is_active:
            raise serializers.ValidationError(
                {'error': 'Account is deactivated'}
            )
        
        if user.role != 'PHA':
            role_names = {
                'REC': 'Receptionist',
                'CCO': 'Clinical Counsellor',
                'FCO': 'Financial Counsellor',
                'END': 'Reproductive Endocrinologist',
                'GYN': 'Gynaecologist',
                'ANE': 'Anesthesiologist',
                'EMB': 'Embryologist',
                'NUR': 'Nurse',
                'TEC': 'Lab Technician',
                'AND': 'Andrology Lab Technician',
                'PAT': 'Patient',
                'HRM': 'HR Manager',
                'ADM': 'Admin',
            }
            user_role_display = role_names.get(user.role, user.role)
            raise serializers.ValidationError(
                {'error': f'Access denied. This is a pharmacist-only portal. Your role: {user_role_display}'}
            )
        
        try:
            pharmacist_profile = user.pharmacist_profile
            if not pharmacist_profile.is_active:
                raise serializers.ValidationError(
                    {'error': 'Pharmacist profile is inactive. Please contact administrator.'}
                )
        except PharmacistProfile.DoesNotExist:
            raise serializers.ValidationError(
                {'error': 'Pharmacist profile not found. Please contact administrator.'}
            )
        
        data['user'] = user
        return data


class PharmacistUserSerializer(serializers.ModelSerializer):
    """
    Serializer for pharmacist user data (returned on login)
    """
    pharmacist_id = serializers.CharField(source='pharmacist_profile.employee_id', read_only=True)
    store_location = serializers.CharField(source='pharmacist_profile.store_location', read_only=True)
    qualification = serializers.CharField(source='pharmacist_profile.qualification', read_only=True)
    license_number = serializers.CharField(source='pharmacist_profile.license_number', read_only=True)
    is_department_head = serializers.BooleanField(source='pharmacist_profile.is_department_head', read_only=True)
    can_manage_inventory = serializers.BooleanField(source='pharmacist_profile.can_manage_inventory', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id',
            'full_name',
            'email',
            'role',
            'pharmacist_id',
            'store_location',
            'qualification',
            'license_number',
            'is_department_head',
            'can_manage_inventory'
        ]


# ========== INVENTORY SERIALIZERS ==========

class MedicationCategorySerializer(serializers.ModelSerializer):
    medication_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = MedicationCategory
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class MedicationManufacturerSerializer(serializers.ModelSerializer):
    medication_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = MedicationManufacturer
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class MedicationListSerializer(serializers.ModelSerializer):
    """Serializer for list view (lightweight)"""
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    manufacturer_name = serializers.CharField(source='manufacturer.name', read_only=True, default=None)
    stock_status = serializers.CharField(source='get_stock_status', read_only=True)
    stock_status_display = serializers.CharField(source='get_stock_status_display', read_only=True)
    is_expiring_soon = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Medication
        fields = [
            'id', 'medication_id', 'name', 'generic_name',
            'category', 'category_name', 'manufacturer', 'manufacturer_name',
            'unit', 'unit_price', 'selling_price',
            'current_stock', 'reorder_level', 'minimum_stock',
            'expiry_date', 'batch_number',
            'stock_status', 'stock_status_display',
            'is_expiring_soon', 'is_expired',
            'requires_prescription', 'is_controlled', 
            'is_active', 'is_available'
        ]


class MedicationDetailSerializer(serializers.ModelSerializer):
    """Serializer for detail view (full data)"""
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    manufacturer_name = serializers.CharField(source='manufacturer.name', read_only=True, default=None)
    stock_status = serializers.CharField(source='get_stock_status', read_only=True)
    stock_status_display = serializers.CharField(source='get_stock_status_display', read_only=True)
    is_expiring_soon = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.full_name', read_only=True)
    
    class Meta:
        model = Medication
        fields = '__all__'
        read_only_fields = [
            'medication_id', 'created_at', 'updated_at', 
            'created_by', 'updated_by', 'selling_price',
            'is_available'
        ]


class MedicationCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for create/update operations"""
    
    class Meta:
        model = Medication
        fields = '__all__'
        read_only_fields = [
            'medication_id', 'selling_price', 'created_at', 
            'updated_at', 'created_by', 'updated_by', 'is_available'
        ]


class StockAdjustmentSerializer(serializers.ModelSerializer):
    medication_name = serializers.CharField(source='medication.name', read_only=True)
    medication_id = serializers.CharField(source='medication.medication_id', read_only=True)
    performed_by_name = serializers.CharField(source='performed_by.full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.full_name', read_only=True)
    adjustment_type_display = serializers.CharField(source='get_adjustment_type_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    
    class Meta:
        model = StockAdjustment
        fields = '__all__'
        read_only_fields = [
            'adjustment_id', 'stock_before', 'stock_after', 
            'performed_at', 'performed_by'
        ]


class StockAlertSerializer(serializers.ModelSerializer):
    medication_name = serializers.CharField(source='medication.name', read_only=True)
    medication_id = serializers.CharField(source='medication.medication_id', read_only=True)
    stock_status = serializers.CharField(source='medication.get_stock_status', read_only=True)
    current_stock = serializers.IntegerField(source='medication.current_stock', read_only=True)
    dismissed_by_name = serializers.CharField(source='dismissed_by.full_name', read_only=True)
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = StockAlert
        fields = '__all__'
        read_only_fields = ['alert_id', 'created_at']