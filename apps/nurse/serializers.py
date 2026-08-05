# apps/nurse/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from accounts.models import NurseProfile
from patients.models import PatientProfile
from .models import PatientVital, PatientVitalHistory

User = get_user_model()


# ========== AUTH SERIALIZERS ==========

class NurseLoginSerializer(serializers.Serializer):
    """Nurse Login Serializer"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        from django.contrib.auth import authenticate
        
        email = data.get('email')
        password = data.get('password')
        
        if email and password:
            user = authenticate(username=email, password=password)
            
            if not user:
                raise serializers.ValidationError('Invalid email or password')
            
            if not user.is_active:
                raise serializers.ValidationError('This account is deactivated')
            
            if user.role != 'NUR':
                raise serializers.ValidationError('Not a nurse account')
            
            try:
                nurse_profile = user.nurse_profile
                if not nurse_profile.is_active:
                    raise serializers.ValidationError('Nurse profile is inactive')
            except NurseProfile.DoesNotExist:
                raise serializers.ValidationError('Nurse profile not found')
            
            data['user'] = user
            return data
        
        raise serializers.ValidationError('Email and password are required')


class NurseProfileSerializer(serializers.ModelSerializer):
    """Nurse Profile Serializer - Minimal fields only"""
    id = serializers.IntegerField(source='user.id', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)
    role_display = serializers.SerializerMethodField()
    
    class Meta:
        model = NurseProfile
        fields = [
            'id', 'full_name', 'email', 'role', 'role_display',
            'employee_id', 'is_head_nurse', 'is_department_head', 'is_active'
        ]
    
    def get_role_display(self, obj):
        return obj.user.get_role_display()
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not data.get('employee_id'):
            data['employee_id'] = f"NURSE-{instance.user.id:04d}"
        return data


class NurseProfileUpdateSerializer(serializers.ModelSerializer):
    """Nurse Profile Update Serializer"""
    full_name = serializers.CharField(source='user.full_name', required=False)
    email = serializers.EmailField(source='user.email', required=False)
    
    class Meta:
        model = NurseProfile
        fields = ['full_name', 'email', 'is_head_nurse', 'is_department_head']
    
    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        if user_data:
            for attr, value in user_data.items():
                setattr(instance.user, attr, value)
            instance.user.save()
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance


class NurseProfileListSerializer(serializers.ModelSerializer):
    """Nurse Profile List Serializer - Minimal fields"""
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = NurseProfile
        fields = ['id', 'full_name', 'email', 'employee_id', 'is_active', 'is_head_nurse']


# ========== PATIENT VITAL SERIALIZERS ==========

class PatientVitalSerializer(serializers.ModelSerializer):
    """Patient Vital Serializer - Full details"""
    patient_name = serializers.CharField(source='patient.user.full_name', read_only=True)
    patient_id = serializers.IntegerField(source='patient.id', read_only=True)
    nurse_name = serializers.CharField(source='nurse.user.full_name', read_only=True)
    nurse_id = serializers.IntegerField(source='nurse.id', read_only=True)
    blood_pressure = serializers.SerializerMethodField()
    is_abnormal = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = PatientVital
        fields = [
            'id', 'patient', 'patient_name', 'patient_id',
            'nurse', 'nurse_name', 'nurse_id',
            'blood_pressure_systolic', 'blood_pressure_diastolic',
            'blood_pressure', 'heart_rate', 'respiratory_rate',
            'temperature', 'blood_sugar', 'weight', 'height', 'bmi',
            'oxygen_saturation', 'pain_score',
            'notes', 'medications_given', 'is_emergency',
            'is_abnormal', 'recorded_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['bmi', 'is_abnormal']
    
    def get_blood_pressure(self, obj):
        return obj.blood_pressure


class PatientVitalListSerializer(serializers.ModelSerializer):
    """Patient Vital List Serializer - Minimal fields"""
    patient_name = serializers.CharField(source='patient.user.full_name', read_only=True)
    nurse_name = serializers.CharField(source='nurse.user.full_name', read_only=True)
    blood_pressure = serializers.SerializerMethodField()
    is_abnormal = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = PatientVital
        fields = [
            'id', 'patient_name', 'nurse_name',
            'blood_pressure', 'heart_rate', 'temperature',
            'blood_sugar', 'is_emergency', 'is_abnormal', 'recorded_at'
        ]
    
    def get_blood_pressure(self, obj):
        return obj.blood_pressure


class PatientVitalCreateUpdateSerializer(serializers.ModelSerializer):
    """Patient Vital Create/Update Serializer"""
    
    # Add patient_name as write-only field (for payload)
    patient_name = serializers.CharField(
        write_only=True, 
        required=False, 
        allow_blank=True,
        help_text="Patient full name for reference"
    )
    
    class Meta:
        model = PatientVital
        fields = [
            'patient', 'patient_name', 'blood_pressure_systolic', 'blood_pressure_diastolic',
            'heart_rate', 'respiratory_rate', 'temperature', 'blood_sugar',
            'weight', 'height', 'oxygen_saturation', 'pain_score',
            'notes', 'medications_given', 'is_emergency'
        ]
    
    def validate_patient_name(self, value):
        """Validate patient name against the patient ID"""
        if value:
            # Get the patient ID from the initial data
            patient_data = self.initial_data.get('patient')
            
            # If patient_data is an object, extract its ID
            if hasattr(patient_data, 'id'):
                patient_id = patient_data.id
            else:
                patient_id = patient_data
            
            if patient_id:
                try:
                    patient = PatientProfile.objects.get(id=patient_id)
                    actual_name = patient.user.full_name
                    
                    # Check if the provided name matches (case-insensitive)
                    if value.lower().strip() != actual_name.lower().strip():
                        raise serializers.ValidationError(
                            f"Patient name '{value}' does not match patient '{actual_name}'"
                        )
                except (PatientProfile.DoesNotExist, ValueError, TypeError):
                    pass  # Will be caught by patient field validation
        
        return value
    
    def validate(self, data):
        """Additional validation"""
        # Get patient from data
        patient = data.get('patient')
        
        if patient:
            try:
                # If patient is an object, get its ID
                if hasattr(patient, 'id'):
                    patient_id = patient.id
                else:
                    patient_id = int(patient)
                
                # Verify patient exists
                patient_obj = PatientProfile.objects.get(id=patient_id)
                
                # Check if patient is active
                if not patient_obj.user.is_active:
                    raise serializers.ValidationError({"patient": "Patient account is inactive"})
                    
            except (PatientProfile.DoesNotExist, ValueError, TypeError):
                raise serializers.ValidationError({"patient": "Patient not found"})
        
        return data