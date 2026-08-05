# cryo/admin.py

from django.contrib import admin
from .models import (
    CryoTank,
    CryoCanister,
    CryoCane,
    CryoGoblet,
    CryoStoredSample
)


@admin.register(CryoTank)
class CryoTankAdmin(admin.ModelAdmin):
    list_display = ['name', 'tank_type', 'capacity', 'current_usage', 'usage_percentage', 'status']
    list_filter = ['tank_type', 'status']
    search_fields = ['name', 'room', 'section']
    readonly_fields = ['current_usage', 'usage_percentage']
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'tank_type', 'capacity', 'status')
        }),
        ('Location', {
            'fields': ('room', 'section')
        }),
        ('Maintenance', {
            'fields': ('last_maintenance', 'next_maintenance')
        }),
        ('RFID', {
            'fields': ('rfid_reader_id',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )


@admin.register(CryoCanister)
class CryoCanisterAdmin(admin.ModelAdmin):
    list_display = ['tank', 'canister_number', 'capacity', 'current_usage']
    list_filter = ['tank']
    search_fields = ['canister_number']


@admin.register(CryoCane)
class CryoCaneAdmin(admin.ModelAdmin):
    list_display = ['canister', 'cane_number', 'capacity', 'current_usage']
    list_filter = ['canister__tank', 'canister']
    search_fields = ['cane_number']


@admin.register(CryoGoblet)
class CryoGobletAdmin(admin.ModelAdmin):
    list_display = ['cane', 'goblet_number', 'color', 'status']
    list_filter = ['status', 'color', 'cane__canister__tank']
    search_fields = ['goblet_number']


@admin.register(CryoStoredSample)
class CryoStoredSampleAdmin(admin.ModelAdmin):
    list_display = ['sample_id', 'patient', 'sample_type', 'status', 'storage_date']
    list_filter = ['sample_type', 'status', 'storage_date']
    search_fields = ['sample_id', 'patient__user__full_name', 'rfid_tag']
    readonly_fields = ['sample_id', 'rfid_tag', 'created_at', 'updated_at']
    fieldsets = (
        ('Patient & Sample', {
            'fields': ('patient', 'sample_type', 'sample_id')
        }),
        ('Sample Details', {
            'fields': ('vial_count', 'vial_volume', 'concentration', 'motility', 'morphology')
        }),
        ('Location', {
            'fields': ('tank', 'canister', 'cane', 'goblet')
        }),
        ('RFID', {
            'fields': ('rfid_tag', 'rfid_epc')
        }),
        ('Storage', {
            'fields': ('freezing_method', 'storage_date', 'expiry_date', 'status')
        }),
        ('Thawing', {
            'fields': ('thawed_date', 'thawed_by', 'post_thaw_survival', 'thaw_notes')
        }),
        ('Usage', {
            'fields': ('used_for', 'used_date', 'used_by')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )