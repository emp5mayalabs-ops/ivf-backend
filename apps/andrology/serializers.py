from rest_framework import serializers
from django.contrib.auth import authenticate
from accounts.models import User
from lab.models import AndrologyLabTechnician


# ---------- Login Serializer ----------
class AndrologistLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        if email and password:
            user = authenticate(username=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            if user.role != 'AND':
                raise serializers.ValidationError('Not an Andrologist account')
            if not user.is_active:
                raise serializers.ValidationError('Account is disabled')
            data['user'] = user
        else:
            raise serializers.ValidationError('Must include "email" and "password"')
        return data


# ---------- Profile Serializer (for reading) ----------
class AndrologistProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = AndrologyLabTechnician
        fields = '__all__'


# ---------- Profile Update Serializer ----------
class AndrologistProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AndrologyLabTechnician
        fields = [
            'contact_number',
            'specialization',
            'years_of_experience',
        ]


# ---------- Change Password Serializer ----------
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)