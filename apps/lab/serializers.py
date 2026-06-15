# apps/lab/serializers.py
from rest_framework import serializers
from django.contrib.auth import authenticate
from accounts.models import User


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
        lab_roles = ['TEC', 'AND', 'EMB']  # Technician, Andrologist, Embryologist
        if user.role not in lab_roles:
            raise serializers.ValidationError(
                f"Access denied. Lab personnel only. Your role: {user.get_role_display()}"
            )
        
        data['user'] = user
        return data