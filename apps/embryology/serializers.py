# embryology/serializers.py

from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from .models import EmbryologistProfile  # We'll create this

User = get_user_model()


class EmbryologistLoginSerializer(serializers.Serializer):
    """Login Serializer"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        
        if email and password:
            user = authenticate(username=email, password=password)
            
            if not user:
                raise serializers.ValidationError('Invalid email or password')
            
            if not user.is_active:
                raise serializers.ValidationError('Account is deactivated')
            
            if user.role != 'EMB':
                raise serializers.ValidationError('Access denied. Embryologist only.')
            
            data['user'] = user
            return data
        
        raise serializers.ValidationError('Email and password are required')


class EmbryologistProfileSerializer(serializers.ModelSerializer):
    """Profile Serializer"""
    
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)
    role_display = serializers.SerializerMethodField()
    
    class Meta:
        model = EmbryologistProfile
        fields = [
            'id', 'full_name', 'email', 'role', 'role_display',
            'employee_id', 'contact_number', 'specialization',
            'years_of_experience', 'is_department_head',
            'date_joined', 'is_active'
        ]
    
    def get_role_display(self, obj):
        return 'Embryologist'
    
    def update(self, instance, validated_data):
        # Update user fields
        user_data = validated_data.pop('user', {})
        if user_data:
            user = instance.user
            if 'full_name' in user_data:
                user.full_name = user_data['full_name']
                user.save()
        
        # Update profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance


class EmbryologistProfileUpdateSerializer(serializers.Serializer):
    """Profile Update Serializer"""
    full_name = serializers.CharField(required=False)
    contact_number = serializers.CharField(required=False)
    specialization = serializers.CharField(required=False)


class ChangePasswordSerializer(serializers.Serializer):
    """Change Password Serializer"""
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError('New passwords do not match')
        return data