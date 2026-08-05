from rest_framework import serializers
from django.contrib.auth import authenticate
from accounts.models import User
from .models import (
    LabTechnicianProfile, 
    AndrologyLabTechnician,
    LabTestType,
    LabField,
    LabRecord
)


# ========== EXISTING SERIALIZERS ==========

class LabLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            raise serializers.ValidationError("Email and password are required")
        
        user = authenticate(username=email, password=password)
        
        if not user:
            raise serializers.ValidationError("Invalid email or password")
        
        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated")
        
        # Check if user has lab role
        lab_roles = ['TEC', 'AND', 'EMB']
        if user.role not in lab_roles:
            raise serializers.ValidationError(
                f"Access denied. Lab personnel only. Your role: {user.get_role_display()}"
            )
        
        data['user'] = user
        return data


class LabProfileSerializer(serializers.ModelSerializer):
    """Lab Profile Serializer"""
    id = serializers.IntegerField(source='user.id', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)
    role_display = serializers.SerializerMethodField()
    
    class Meta:
        model = LabTechnicianProfile
        fields = [
            'id', 'full_name', 'email', 'role', 'role_display',
            'employee_id', 'is_active', 'date_assigned',
            'technical_certification', 'specialization', 'is_department_head'
        ]
    
    def get_role_display(self, obj):
        return obj.user.get_role_display()
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not data.get('employee_id'):
            data['employee_id'] = f"LAB-{instance.user.id:04d}"
        
        # Add role-specific fields
        user = instance.user
        if user.role == 'AND':
            andro_profile = getattr(user, 'andrology_technician_profile', None)
            if andro_profile:
                data['can_perform_dna_frag'] = andro_profile.can_perform_dna_frag
                data['can_perform_cryo'] = andro_profile.can_perform_cryo
                data['technician_license'] = andro_profile.technician_license
        
        return data


class LabProfileUpdateSerializer(serializers.ModelSerializer):
    """Lab Profile Update Serializer"""
    full_name = serializers.CharField(source='user.full_name', required=False)
    email = serializers.EmailField(source='user.email', required=False)
    
    class Meta:
        model = LabTechnicianProfile
        fields = ['full_name', 'email', 'technical_certification', 'specialization']
    
    def update(self, instance, validated_data):
        # Update user fields
        user_data = validated_data.pop('user', {})
        if user_data:
            for attr, value in user_data.items():
                setattr(instance.user, attr, value)
            instance.user.save()
        
        # Update lab profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance


# ========== NEW DYNAMIC LAB TESTS SERIALIZERS ==========

class LabFieldSerializer(serializers.ModelSerializer):
    """Serializer for dynamic fields"""
    options_list = serializers.SerializerMethodField()
    validation_rules = serializers.SerializerMethodField()
    
    class Meta:
        model = LabField
        fields = [
            'id', 'label', 'field_key', 'field_type',
            'placeholder', 'help_text', 'default_value', 'is_required',
            'display_order', 'options', 'options_list', 'validation_rules',
            'min_value', 'max_value', 'min_length', 'max_length',
            'column_width', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_options_list(self, obj):
        return obj.get_options_list()
    
    def get_validation_rules(self, obj):
        return obj.get_validation_rules()


class LabTestTypeSerializer(serializers.ModelSerializer):
    """Serializer for test types"""
    fields = LabFieldSerializer(many=True, read_only=True)
    field_count = serializers.SerializerMethodField()
    record_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = LabTestType
        fields = [
            'id', 'name', 'code', 'icon', 'color', 'description',
            'is_active', 'display_order', 'fields', 'field_count',
            'record_count', 'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_field_count(self, obj):
        return obj.get_field_count()
    
    def get_record_count(self, obj):
        return obj.get_record_count()
    
    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else None


class LabTestTypeCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating test types with fields"""
    fields = LabFieldSerializer(many=True, required=False)
    
    class Meta:
        model = LabTestType
        fields = [
            'id', 'name', 'code', 'icon', 'color', 'description',
            'is_active', 'display_order', 'fields'
        ]
    
    def create(self, validated_data):
        fields_data = validated_data.pop('fields', [])
        test_type = LabTestType.objects.create(**validated_data)
        
        for field_data in fields_data:
            LabField.objects.create(test_type=test_type, **field_data)
        
        return test_type
    
    def update(self, instance, validated_data):
        fields_data = validated_data.pop('fields', [])
        
        # Update test type fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update fields - simple approach: delete and recreate
        if fields_data:
            instance.fields.all().delete()
            for field_data in fields_data:
                LabField.objects.create(test_type=instance, **field_data)
        
        return instance


class LabRecordSerializer(serializers.ModelSerializer):
    """Serializer for lab records (detail view)"""
    test_type_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    display_fields = serializers.SerializerMethodField()
    token_number = serializers.IntegerField(read_only=True)  # 🆕 Added token number

    class Meta:
        model = LabRecord
        fields = [
            'id', 'token_number', 'test_type', 'test_type_name', 'patient', 'patient_name',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name',
            'field_values', 'display_fields', 'test_date', 'status',
            'priority', 'notes', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'token_number', 'created_at', 'updated_at']
    
    def get_test_type_name(self, obj):
        return obj.test_type.name
    
    def get_patient_name(self, obj):
        return obj.patient.full_name
    
    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else None
    
    def get_updated_by_name(self, obj):
        return obj.updated_by.full_name if obj.updated_by else None
    
    def get_display_fields(self, obj):
        """Return field data with values"""
        display_data = []
        for field in obj.test_type.fields.filter(is_active=True).order_by('display_order'):
            value = obj.field_values.get(field.field_key)
            display_data.append({
                'field_id': field.id,
                'label': field.label,
                'field_key': field.field_key,
                'field_type': field.field_type,
                'value': value,
                'formatted_value': obj._format_value(field, value)
            })
        return display_data


class LabRecordCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating records"""
    field_values = serializers.JSONField(required=True)
    
    class Meta:
        model = LabRecord
        fields = [
            'id', 'test_type', 'patient', 'field_values',
            'test_date', 'status', 'priority', 'notes'
        ]
    
    def validate_field_values(self, value):
        """Validate field values against test type fields"""
        test_type = self.initial_data.get('test_type')
        if not test_type:
            raise serializers.ValidationError("test_type is required")
        
        try:
            test_type_obj = LabTestType.objects.get(id=test_type)
        except LabTestType.DoesNotExist:
            raise serializers.ValidationError("Invalid test type")
        
        # Get all active fields for this test type
        fields = test_type_obj.fields.filter(is_active=True)
        
        # Validate each field
        for field in fields:
            field_value = value.get(field.field_key)
            
            # Check required fields
            if field.is_required and (field_value is None or field_value == ''):
                raise serializers.ValidationError({
                    field.field_key: f"{field.label} is required"
                })
            
            # Validate based on field type
            if field_value is not None and field_value != '':
                if field.field_type in ['number', 'decimal']:
                    try:
                        num_value = float(field_value)
                        if field.min_value is not None and num_value < float(field.min_value):
                            raise serializers.ValidationError({
                                field.field_key: f"{field.label} must be at least {field.min_value}"
                            })
                        if field.max_value is not None and num_value > float(field.max_value):
                            raise serializers.ValidationError({
                                field.field_key: f"{field.label} must be at most {field.max_value}"
                            })
                    except ValueError:
                        raise serializers.ValidationError({
                            field.field_key: f"{field.label} must be a valid number"
                        })
                
                if field.field_type in ['select', 'radio']:
                    options = field.get_options_list()
                    if options and field_value not in options:
                        raise serializers.ValidationError({
                            field.field_key: f"Invalid option for {field.label}"
                        })
        
        return value
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        validated_data['updated_by'] = self.context['request'].user
        return super().update(instance, validated_data)


# ========== LAB ORDER SERIALIZERS (for Doctor-Lab Integration) ==========

class LabOrderSerializer(serializers.Serializer):
    """Serializer for ordering lab tests from doctor or receptionist"""
    patient_id = serializers.IntegerField()
    test_type_id = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(
        choices=['ROUTINE', 'URGENT', 'STAT'],
        default='ROUTINE'
    )


class LabResultUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating lab results (Lab Technician)"""
    class Meta:
        model = LabRecord
        fields = ['field_values', 'notes', 'status']
    
    def update(self, instance, validated_data):
        # Merge field values
        if 'field_values' in validated_data:
            if instance.field_values:
                instance.field_values.update(validated_data['field_values'])
            else:
                instance.field_values = validated_data['field_values']
        
        if 'notes' in validated_data:
            instance.notes = validated_data['notes']
        
        if 'status' in validated_data:
            instance.status = validated_data['status']
        
        instance.updated_by = self.context['request'].user
        instance.save()
        return instance


class LabOrderListSerializer(serializers.ModelSerializer):
    """Serializer for listing lab orders (with token)"""
    patient_name = serializers.SerializerMethodField()
    test_type_name = serializers.SerializerMethodField()
    test_type_code = serializers.SerializerMethodField()
    ordered_by_name = serializers.SerializerMethodField()
    priority_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    token_number = serializers.IntegerField(read_only=True)  # 🆕 Token number

    class Meta:
        model = LabRecord
        fields = [
            'id', 'token_number', 'patient', 'patient_name', 'test_type', 'test_type_name',
            'test_type_code', 'test_date', 'status', 'status_display',
            'priority', 'priority_display', 'field_values', 'notes',
            'ordered_by_name', 'created_at', 'updated_at'
        ]
    
    def get_patient_name(self, obj):
        return obj.patient.full_name if obj.patient else None
    
    def get_test_type_name(self, obj):
        return obj.test_type.name if obj.test_type else None
    
    def get_test_type_code(self, obj):
        return obj.test_type.code if obj.test_type else None
    
    def get_ordered_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else None
    
    def get_priority_display(self, obj):
        return obj.get_priority_display() if hasattr(obj, 'get_priority_display') else obj.priority
    
    def get_status_display(self, obj):
        return obj.get_status_display() if hasattr(obj, 'get_status_display') else obj.status