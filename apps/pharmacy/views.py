# apps/pharmacy/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import login, logout
from django.utils import timezone
from django.db.models import Q, Count, Sum, F
from datetime import timedelta

from .models import (
    PharmacistProfile, Medication, MedicationCategory,
    MedicationManufacturer, StockAdjustment, StockAlert
)
from .serializers import (
    PharmacistLoginSerializer, PharmacistUserSerializer,
    MedicationListSerializer, MedicationDetailSerializer,
    MedicationCreateUpdateSerializer, MedicationCategorySerializer,
    MedicationManufacturerSerializer, StockAdjustmentSerializer,
    StockAlertSerializer
)
from .permissions import IsPharmacist


# ========== HELPER FUNCTIONS ==========

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ========== AUTH VIEWS ==========

class PharmacistLoginView(APIView):
    """Pharmacist login API"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PharmacistLoginSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = serializer.validated_data['user']
        login(request, user)
        
        try:
            from accounts.models import LoginAuditLog
            LoginAuditLog.objects.filter(
                user=user,
                is_active_session=True
            ).update(is_active_session=False, logout_time=timezone.now())
            
            LoginAuditLog.objects.create(
                user=user,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                is_active_session=True
            )
        except:
            pass
        
        pharmacist_profile = user.pharmacist_profile
        
        return Response({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'name': user.full_name,
                'email': user.email,
                'role': user.role,
                'role_display': 'Pharmacist',
                'pharmacist_id': pharmacist_profile.employee_id,
                'store_location': pharmacist_profile.store_location,
                'qualification': pharmacist_profile.qualification,
                'license_number': pharmacist_profile.license_number,
                'is_department_head': pharmacist_profile.is_department_head,
                'can_manage_inventory': pharmacist_profile.can_manage_inventory,
                'is_active': pharmacist_profile.is_active,
                'date_assigned': pharmacist_profile.date_assigned,
            }
        }, status=status.HTTP_200_OK)


class PharmacistLogoutView(APIView):
    """Pharmacist logout API"""
    permission_classes = [IsAuthenticated, IsPharmacist]
    
    def post(self, request):
        try:
            from accounts.models import LoginAuditLog
            LoginAuditLog.objects.filter(
                user=request.user,
                is_active_session=True
            ).update(
                is_active_session=False,
                logout_time=timezone.now()
            )
        except:
            pass
        
        logout(request)
        
        return Response({
            'success': True,
            'message': 'Logged out successfully'
        }, status=status.HTTP_200_OK)


class PharmacistProfileView(APIView):
    """Get current pharmacist's profile"""
    permission_classes = [IsAuthenticated, IsPharmacist]
    
    def get(self, request):
        user = request.user
        pharmacist_profile = user.pharmacist_profile
        
        return Response({
            'success': True,
            'profile': {
                'id': user.id,
                'name': user.full_name,
                'email': user.email,
                'role': user.role,
                'role_display': 'Pharmacist',
                'pharmacist_id': pharmacist_profile.employee_id,
                'store_location': pharmacist_profile.store_location,
                'qualification': pharmacist_profile.qualification,
                'license_number': pharmacist_profile.license_number,
                'is_department_head': pharmacist_profile.is_department_head,
                'can_manage_inventory': pharmacist_profile.can_manage_inventory,
                'is_active': pharmacist_profile.is_active,
                'date_assigned': pharmacist_profile.date_assigned
            }
        })


# ========== INVENTORY VIEWS - MINIMAL API APPROACH ==========

class InventoryAPIView(APIView):
    """
    One API to rule them all!
    GET    /inventory/           - List with filters
    GET    /inventory/{id}/      - Get single medication
    POST   /inventory/           - Create medication
    PUT    /inventory/{id}/      - Update medication
    DELETE /inventory/{id}/      - Delete (soft delete) medication
    """
    permission_classes = [IsAuthenticated, IsPharmacist]

    def get(self, request, id=None):
        """GET /inventory/ or /inventory/{id}/"""
        
        if id:
            try:
                medication = Medication.objects.select_related(
                    'category', 'manufacturer', 'created_by', 'updated_by'
                ).get(id=id, is_active=True)
            except Medication.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Medication not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = MedicationDetailSerializer(medication)
            return Response({
                'success': True,
                'data': serializer.data
            })
        
        # List all medications with filters
        medications = Medication.objects.select_related(
            'category', 'manufacturer'
        ).filter(is_active=True)
        
        # 1. Search
        search = request.query_params.get('search')
        if search:
            medications = medications.filter(
                Q(name__icontains=search) |
                Q(generic_name__icontains=search) |
                Q(medication_id__icontains=search) |
                Q(batch_number__icontains=search)
            )
        
        # 2. Category filter
        category = request.query_params.get('category')
        if category:
            medications = medications.filter(category_id=category)
        
        # 3. Manufacturer filter
        manufacturer = request.query_params.get('manufacturer')
        if manufacturer:
            medications = medications.filter(manufacturer_id=manufacturer)
        
        # 4. Status filter
        status_filter = request.query_params.get('status')
        if status_filter:
            if status_filter == 'IN_STOCK':
                medications = medications.filter(current_stock__gt=0)
            elif status_filter == 'LOW_STOCK':
                medications = medications.filter(
                    current_stock__lte=F('reorder_level'),
                    current_stock__gt=0
                )
            elif status_filter == 'CRITICAL':
                medications = medications.filter(
                    current_stock__lte=F('minimum_stock'),
                    current_stock__gt=0
                )
            elif status_filter == 'OUT_OF_STOCK':
                medications = medications.filter(current_stock=0)
        
        # 5. Expiring filter
        expiring_days = request.query_params.get('expiring_days')
        if expiring_days:
            try:
                days = int(expiring_days)
                cutoff = timezone.now().date() + timedelta(days=days)
                medications = medications.filter(
                    expiry_date__isnull=False,
                    expiry_date__lte=cutoff
                )
            except ValueError:
                pass
        
        # 6. Expired filter
        expired = request.query_params.get('expired')
        if expired and expired.lower() == 'true':
            medications = medications.filter(
                expiry_date__isnull=False,
                expiry_date__lt=timezone.now().date()
            )
        
        # 7. Sorting
        sort_by = request.query_params.get('sort_by', 'name')
        if sort_by == 'name':
            medications = medications.order_by('name')
        elif sort_by == '-name':
            medications = medications.order_by('-name')
        elif sort_by == 'stock':
            medications = medications.order_by('current_stock')
        elif sort_by == '-stock':
            medications = medications.order_by('-current_stock')
        elif sort_by == 'expiry':
            medications = medications.order_by('expiry_date')
        elif sort_by == '-expiry':
            medications = medications.order_by('-expiry_date')
        
        # 8. Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        total = medications.count()
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_meds = medications[start:end]
        serializer = MedicationListSerializer(paginated_meds, many=True)
        
        # Get summary
        summary = {
            'total': total,
            'in_stock': medications.filter(current_stock__gt=0).count(),
            'low_stock': medications.filter(
                current_stock__lte=F('reorder_level'),
                current_stock__gt=0
            ).count(),
            'critical': medications.filter(
                current_stock__lte=F('minimum_stock'),
                current_stock__gt=0
            ).count(),
            'out_of_stock': medications.filter(current_stock=0).count(),
            'total_value': medications.aggregate(
                total=Sum(F('current_stock') * F('selling_price'))
            )['total'] or 0
        }
        
        return Response({
            'success': True,
            'data': serializer.data,
            'summary': summary,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size if page_size > 0 else 1,
                'total': total
            }
        })

    def post(self, request):
        """POST /inventory/ - Create new medication"""
        serializer = MedicationCreateUpdateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        medication = serializer.save(created_by=request.user)
        
        # Create initial stock adjustment
        if medication.current_stock > 0:
            StockAdjustment.objects.create(
                medication=medication,
                adjustment_type='ADD',
                quantity=medication.current_stock,
                reason='INVENTORY',
                stock_before=0,
                stock_after=medication.current_stock,
                performed_by=request.user,
                notes='Initial stock setup'
            )
        
        return Response({
            'success': True,
            'message': 'Medication created successfully',
            'data': MedicationDetailSerializer(medication).data
        }, status=status.HTTP_201_CREATED)

    def put(self, request, id):
        """PUT /inventory/{id}/ - Update medication"""
        try:
            medication = Medication.objects.get(id=id, is_active=True)
        except Medication.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Medication not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = MedicationCreateUpdateSerializer(
            medication, 
            data=request.data,
            partial=True
        )
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        medication = serializer.save(updated_by=request.user)
        
        return Response({
            'success': True,
            'message': 'Medication updated successfully',
            'data': MedicationDetailSerializer(medication).data
        })

    def delete(self, request, id):
        """DELETE /inventory/{id}/ - Soft delete medication"""
        try:
            medication = Medication.objects.get(id=id, is_active=True)
        except Medication.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Medication not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        medication.is_active = False
        medication.save()
        
        return Response({
            'success': True,
            'message': 'Medication deactivated successfully'
        })


class StockAdjustmentAPIView(APIView):
    """
    POST /inventory/{id}/adjust/
    One API for all stock adjustments
    """
    permission_classes = [IsAuthenticated, IsPharmacist]

    def post(self, request, medication_id):
        try:
            medication = Medication.objects.get(id=medication_id, is_active=True)
        except Medication.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Medication not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        adjustment_type = request.data.get('adjustment_type')
        quantity = request.data.get('quantity')
        reason = request.data.get('reason', 'OTHER')
        notes = request.data.get('notes', '')
        reference = request.data.get('reference', '')
        
        if not adjustment_type or quantity is None:
            return Response({
                'success': False,
                'error': 'adjustment_type and quantity are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            quantity = int(quantity)
        except ValueError:
            return Response({
                'success': False,
                'error': 'Quantity must be a number'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if quantity <= 0:
            return Response({
                'success': False,
                'error': 'Quantity must be greater than 0'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        adjustment = StockAdjustment(
            medication=medication,
            adjustment_type=adjustment_type,
            quantity=quantity,
            reason=reason,
            notes=notes,
            reference=reference,
            performed_by=request.user
        )
        adjustment.save()
        
        return Response({
            'success': True,
            'message': 'Stock adjusted successfully',
            'data': {
                'medication': MedicationListSerializer(medication).data,
                'adjustment': StockAdjustmentSerializer(adjustment).data,
                'stock_before': adjustment.stock_before,
                'stock_after': adjustment.stock_after
            }
        })

    def get(self, request, medication_id=None):
        """GET /inventory/adjustments/ or /inventory/{id}/adjustments/"""
        adjustments = StockAdjustment.objects.select_related(
            'medication', 'performed_by', 'approved_by'
        )
        
        if medication_id:
            adjustments = adjustments.filter(medication_id=medication_id)
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        total = adjustments.count()
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated = adjustments[start:end]
        serializer = StockAdjustmentSerializer(paginated, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': (total + page_size - 1) // page_size if page_size > 0 else 1
            }
        })


class InventoryAlertsAPIView(APIView):
    """
    GET /inventory/alerts/
    Returns all alerts: low stock, critical, expiring, expired
    """
    permission_classes = [IsAuthenticated, IsPharmacist]

    def get(self, request):
        alert_type = request.query_params.get('type')
        status_filter = request.query_params.get('status', 'ACTIVE')
        
        alerts = StockAlert.objects.select_related('medication', 'dismissed_by')
        
        if alert_type:
            alerts = alerts.filter(alert_type=alert_type)
        
        if status_filter:
            alerts = alerts.filter(status=status_filter)
        
        # Check for medications that need alerts
        medications = Medication.objects.filter(is_active=True)
        
        # Check critical stock
        critical_meds = medications.filter(
            current_stock__lte=F('minimum_stock'),
            current_stock__gt=0
        )
        for med in critical_meds:
            StockAlert.objects.get_or_create(
                medication=med,
                alert_type='CRITICAL',
                status='ACTIVE',
                defaults={
                    'message': f'Stock is at critical level: {med.current_stock} units'
                }
            )
        
        # Check low stock
        low_meds = medications.filter(
            current_stock__lte=F('reorder_level'),
            current_stock__gt=F('minimum_stock')
        )
        for med in low_meds:
            StockAlert.objects.get_or_create(
                medication=med,
                alert_type='LOW_STOCK',
                status='ACTIVE',
                defaults={
                    'message': f'Stock is below reorder level: {med.current_stock} units'
                }
            )
        
        # Update alerts
        alerts = StockAlert.objects.select_related('medication', 'dismissed_by')
        
        if alert_type:
            alerts = alerts.filter(alert_type=alert_type)
        
        if status_filter:
            alerts = alerts.filter(status=status_filter)
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        total = alerts.count()
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated = alerts[start:end]
        serializer = StockAlertSerializer(paginated, many=True)
        
        return Response({
            'success': True,
            'count': total,
            'summary': {
                'critical': StockAlert.objects.filter(alert_type='CRITICAL', status='ACTIVE').count(),
                'low_stock': StockAlert.objects.filter(alert_type='LOW_STOCK', status='ACTIVE').count(),
                'expiring': StockAlert.objects.filter(alert_type='EXPIRING', status='ACTIVE').count(),
                'expired': StockAlert.objects.filter(alert_type='EXPIRED', status='ACTIVE').count(),
                'total_active': StockAlert.objects.filter(status='ACTIVE').count(),
            },
            'data': serializer.data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': (total + page_size - 1) // page_size if page_size > 0 else 1
            }
        })


class DismissAlertAPIView(APIView):
    """
    PATCH /inventory/alerts/{id}/dismiss/
    Dismiss an alert
    """
    permission_classes = [IsAuthenticated, IsPharmacist]

    def patch(self, request, alert_id):
        try:
            alert = StockAlert.objects.get(id=alert_id, status='ACTIVE')
        except StockAlert.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Active alert not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        alert.status = 'DISMISSED'
        alert.dismissed_at = timezone.now()
        alert.dismissed_by = request.user
        alert.save()
        
        return Response({
            'success': True,
            'message': 'Alert dismissed successfully',
            'data': StockAlertSerializer(alert).data
        })


class InventorySummaryAPIView(APIView):
    """
    GET /inventory/summary/
    Dashboard summary statistics
    """
    permission_classes = [IsAuthenticated, IsPharmacist]

    def get(self, request):
        medications = Medication.objects.filter(is_active=True)
        
        # Counts
        total = medications.count()
        in_stock = medications.filter(current_stock__gt=0).count()
        low_stock = medications.filter(
            current_stock__lte=F('reorder_level'),
            current_stock__gt=0
        ).count()
        critical = medications.filter(
            current_stock__lte=F('minimum_stock'),
            current_stock__gt=0
        ).count()
        out_of_stock = medications.filter(current_stock=0).count()
        
        # Expiry
        today = timezone.now().date()
        expiring_soon = medications.filter(
            expiry_date__isnull=False,
            expiry_date__lte=today + timedelta(days=30),
            expiry_date__gt=today
        ).count()
        expired = medications.filter(
            expiry_date__isnull=False,
            expiry_date__lt=today
        ).count()
        
        # Total value
        total_value = medications.aggregate(
            total=Sum(F('current_stock') * F('selling_price'))
        )['total'] or 0
        
        # Active alerts
        active_alerts = StockAlert.objects.filter(status='ACTIVE').count()
        
        # Recent activity
        recent_adjustments = StockAdjustment.objects.select_related(
            'medication', 'performed_by'
        ).order_by('-performed_at')[:10]
        
        return Response({
            'success': True,
            'summary': {
                'total_medications': total,
                'in_stock': in_stock,
                'low_stock': low_stock,
                'critical': critical,
                'out_of_stock': out_of_stock,
                'expiring_soon': expiring_soon,
                'expired': expired,
                'total_value': total_value,
                'active_alerts': active_alerts,
            },
            'recent_activity': StockAdjustmentSerializer(recent_adjustments, many=True).data,
            'quick_actions': {
                'can_manage_inventory': request.user.pharmacist_profile.can_manage_inventory,
                'is_department_head': request.user.pharmacist_profile.is_department_head,
            }
        })


class MedicationCategoriesAPIView(APIView):
    """
    GET /inventory/categories/
    List all categories with medication counts
    """
    permission_classes = [IsAuthenticated, IsPharmacist]

    def get(self, request):
        categories = MedicationCategory.objects.filter(is_active=True)
        
        # Annotate with medication count
        categories = categories.annotate(
            medication_count=Count('medications')
        )
        
        serializer = MedicationCategorySerializer(categories, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data
        })


class MedicationManufacturersAPIView(APIView):
    """
    GET /inventory/manufacturers/
    List all manufacturers with medication counts
    """
    permission_classes = [IsAuthenticated, IsPharmacist]

    def get(self, request):
        manufacturers = MedicationManufacturer.objects.filter(is_active=True)
        
        # Annotate with medication count
        manufacturers = manufacturers.annotate(
            medication_count=Count('medications')
        )
        
        serializer = MedicationManufacturerSerializer(manufacturers, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data
        })