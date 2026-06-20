# apps/pharmacy/admin.py
from django.contrib import admin
from .models import (
    PharmacistProfile, Medication, MedicationCategory,
    MedicationManufacturer, StockAdjustment, StockAlert
)

@admin.register(PharmacistProfile)
class PharmacistProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'employee_id', 'store_location', 'is_active', 'is_department_head']
    search_fields = ['user__email', 'user__full_name', 'employee_id', 'license_number']
    list_filter = ['is_active', 'is_department_head', 'can_manage_inventory', 'store_location']
    readonly_fields = ['employee_id', 'date_assigned']


@admin.register(MedicationCategory)
class MedicationCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'requires_prescription', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    list_filter = ['requires_prescription', 'is_active']


@admin.register(MedicationManufacturer)
class MedicationManufacturerAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_email', 'contact_phone', 'is_active']
    search_fields = ['name', 'contact_email']


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ['medication_id', 'name', 'category', 'current_stock', 'get_stock_status', 'is_active']
    search_fields = ['name', 'generic_name', 'medication_id', 'batch_number']
    list_filter = ['category', 'is_active', 'requires_prescription', 'is_controlled']
    readonly_fields = ['medication_id', 'selling_price', 'created_at', 'updated_at']


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ['adjustment_id', 'medication', 'adjustment_type', 'quantity', 'stock_before', 'stock_after', 'performed_at']
    list_filter = ['adjustment_type', 'reason']
    search_fields = ['adjustment_id', 'medication__name', 'reference']
    readonly_fields = ['adjustment_id', 'stock_before', 'stock_after', 'performed_at']


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ['alert_id', 'medication', 'alert_type', 'status', 'created_at']
    list_filter = ['alert_type', 'status']
    search_fields = ['alert_id', 'medication__name', 'message']
    readonly_fields = ['alert_id', 'created_at']