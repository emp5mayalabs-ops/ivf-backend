# apps/nurse/admin.py
from django.contrib import admin
from accounts.models import NurseProfile
from .models import PatientVital, PatientVitalHistory


@admin.register(NurseProfile)
class NurseProfileAdmin(admin.ModelAdmin):
    """Nurse Profile Admin - Using accounts NurseProfile model"""
    
    # Only use fields that exist in accounts NurseProfile
    list_display = ['get_full_name', 'employee_id', 'is_active', 'is_head_nurse', 'is_department_head']
    list_filter = ['is_active', 'is_head_nurse', 'is_department_head']
    search_fields = ['user__full_name', 'user__email', 'employee_id']
    readonly_fields = ['employee_id']
    
    def get_full_name(self, obj):
        return obj.user.full_name
    get_full_name.short_description = 'Full Name'
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'employee_id')
        }),
        ('Permissions', {
            'fields': ('is_head_nurse', 'is_department_head', 'is_active')
        }),
    )


@admin.register(PatientVital)
class PatientVitalAdmin(admin.ModelAdmin):
    """Patient Vital Admin"""
    list_display = ['get_patient_name', 'get_nurse_name', 'blood_pressure', 'heart_rate', 'temperature', 'is_emergency', 'recorded_at']
    list_filter = ['is_emergency', 'recorded_at']
    search_fields = ['patient__user__full_name', 'nurse__user__full_name']
    readonly_fields = ['bmi', 'created_at', 'updated_at']
    
    def get_patient_name(self, obj):
        return obj.patient.user.full_name
    get_patient_name.short_description = 'Patient'
    
    def get_nurse_name(self, obj):
        return obj.nurse.user.full_name
    get_nurse_name.short_description = 'Nurse'
    
    def blood_pressure(self, obj):
        return obj.blood_pressure
    blood_pressure.short_description = 'BP'
    
    fieldsets = (
        ('Patient Information', {
            'fields': ('patient', 'nurse')
        }),
        ('Vital Signs', {
            'fields': (
                'blood_pressure_systolic', 'blood_pressure_diastolic',
                'heart_rate', 'respiratory_rate', 'temperature',
                'blood_sugar', 'weight', 'height', 'bmi',
                'oxygen_saturation', 'pain_score'
            )
        }),
        ('Additional Information', {
            'fields': ('notes', 'medications_given', 'is_emergency')
        }),
        ('Timestamps', {
            'fields': ('recorded_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PatientVitalHistory)
class PatientVitalHistoryAdmin(admin.ModelAdmin):
    """Patient Vital History Admin"""
    list_display = ['get_patient_name', 'get_changed_by', 'changed_at']
    list_filter = ['changed_at']
    search_fields = ['vital__patient__user__full_name']
    readonly_fields = ['vital', 'changed_by', 'changes', 'changed_at']
    
    def get_patient_name(self, obj):
        return obj.vital.patient.user.full_name
    get_patient_name.short_description = 'Patient'
    
    def get_changed_by(self, obj):
        return obj.changed_by.user.full_name
    get_changed_by.short_description = 'Changed By'