# apps/pharmacy/views.py - COMPLETE WITH PRESCRIPTION FULFILLMENT

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
    MedicationManufacturer, StockAdjustment, StockAlert,
    PrescriptionOrder,    PharmacyBill,          # Add this
    PharmacyBillItem,      # Add this
    PharmacyPayment,  # NEW: Import PrescriptionOrder
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


# ========== INVENTORY VIEWS ==========

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


# ========== DASHBOARD VIEWS ==========

class PharmacyDashboardAPIView(APIView):
    """
    GET /api/pharmacy/dashboard/
    Complete pharmacy dashboard with all statistics and data
    """
    permission_classes = [IsAuthenticated, IsPharmacist]
    
    def get(self, request):
        medications = Medication.objects.filter(is_active=True)
        today = timezone.now().date()
        pharmacist_profile = request.user.pharmacist_profile
        
        # ========== 1. STOCK OVERVIEW ==========
        total_medications = medications.count()
        in_stock = medications.filter(current_stock__gt=0).count()
        out_of_stock = medications.filter(current_stock=0).count()
        
        low_stock = medications.filter(
            current_stock__lte=F('reorder_level'),
            current_stock__gt=0
        ).count()
        
        critical = medications.filter(
            current_stock__lte=F('minimum_stock'),
            current_stock__gt=0
        ).count()
        
        well_stocked = medications.filter(
            current_stock__gt=F('reorder_level')
        ).count()
        
        # Stock health percentage
        stock_health = round((in_stock / total_medications * 100) if total_medications > 0 else 0, 1)
        
        # ========== 2. FINANCIAL OVERVIEW ==========
        total_inventory_value = medications.aggregate(
            total=Sum(F('current_stock') * F('selling_price'))
        )['total'] or 0
        
        total_cost_value = medications.aggregate(
            total=Sum(F('current_stock') * F('unit_price'))
        )['total'] or 0
        
        potential_profit = total_inventory_value - total_cost_value
        profit_margin = round((potential_profit / total_cost_value * 100) if total_cost_value > 0 else 0, 1)
        
        # Average price per item
        avg_selling_price = medications.aggregate(
            avg=Sum(F('selling_price')) / Count('id')
        )['avg'] or 0
        
        # ========== 3. EXPIRY OVERVIEW ==========
        expiring_7_days = medications.filter(
            expiry_date__isnull=False,
            expiry_date__lte=today + timedelta(days=7),
            expiry_date__gt=today
        ).count()
        
        expiring_30_days = medications.filter(
            expiry_date__isnull=False,
            expiry_date__lte=today + timedelta(days=30),
            expiry_date__gt=today
        ).count()
        
        expiring_90_days = medications.filter(
            expiry_date__isnull=False,
            expiry_date__lte=today + timedelta(days=90),
            expiry_date__gt=today
        ).count()
        
        expired = medications.filter(
            expiry_date__isnull=False,
            expiry_date__lt=today
        ).count()
        
        no_expiry = medications.filter(expiry_date__isnull=True).count()
        
        # Expiring medications list (top 10)
        expiring_medications = medications.filter(
            expiry_date__isnull=False,
            expiry_date__lte=today + timedelta(days=30),
            expiry_date__gt=today
        ).select_related('category', 'manufacturer').order_by('expiry_date')[:10]
        
        # Expired medications list (top 10)
        expired_medications = medications.filter(
            expiry_date__isnull=False,
            expiry_date__lt=today
        ).select_related('category', 'manufacturer').order_by('expiry_date')[:10]
        
        # ========== 4. ALERTS OVERVIEW ==========
        active_alerts = StockAlert.objects.filter(status='ACTIVE')
        alerts_summary = {
            'total': active_alerts.count(),
            'critical': active_alerts.filter(alert_type='CRITICAL').count(),
            'low_stock': active_alerts.filter(alert_type='LOW_STOCK').count(),
            'expiring': active_alerts.filter(alert_type='EXPIRING').count(),
            'expired': active_alerts.filter(alert_type='EXPIRED').count(),
        }
        
        # Recent alerts (top 5)
        recent_alerts = active_alerts.select_related(
            'medication', 'dismissed_by'
        ).order_by('-created_at')[:5]
        recent_alerts_data = StockAlertSerializer(recent_alerts, many=True).data
        
        # ========== 5. RECENT ACTIVITY ==========
        last_7_days = timezone.now() - timedelta(days=7)
        last_30_days = timezone.now() - timedelta(days=30)
        
        # Stock adjustments in last 7 days
        recent_adjustments = StockAdjustment.objects.filter(
            performed_at__gte=last_7_days
        ).select_related('medication', 'performed_by').order_by('-performed_at')[:15]
        
        # Statistics for last 7 days
        weekly_additions = StockAdjustment.objects.filter(
            adjustment_type='ADD',
            performed_at__gte=last_7_days
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        weekly_removals = StockAdjustment.objects.filter(
            adjustment_type='REMOVE',
            performed_at__gte=last_7_days
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        weekly_sales = StockAdjustment.objects.filter(
            adjustment_type='SALE',
            performed_at__gte=last_7_days
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        weekly_net_change = weekly_additions - (weekly_removals + weekly_sales)
        
        # Statistics for last 30 days
        monthly_additions = StockAdjustment.objects.filter(
            adjustment_type='ADD',
            performed_at__gte=last_30_days
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        monthly_removals = StockAdjustment.objects.filter(
            adjustment_type='REMOVE',
            performed_at__gte=last_30_days
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        monthly_sales = StockAdjustment.objects.filter(
            adjustment_type='SALE',
            performed_at__gte=last_30_days
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        # Most active medications (most adjustments)
        most_active_meds = StockAdjustment.objects.filter(
            performed_at__gte=last_30_days
        ).values('medication__name', 'medication__id').annotate(
            adjustment_count=Count('id'),
            total_quantity=Sum('quantity')
        ).order_by('-adjustment_count')[:5]
        
        # ========== 6. CATEGORY BREAKDOWN ==========
        from django.db.models import Case, When, IntegerField
        
        categories = MedicationCategory.objects.filter(
            is_active=True
        ).annotate(
            medication_count=Count('medications'),
            total_stock=Sum('medications__current_stock'),
            total_value=Sum(F('medications__current_stock') * F('medications__selling_price')),
            low_stock_count=Sum(
                Case(
                    When(
                        medications__current_stock__lte=F('medications__reorder_level'),
                        medications__current_stock__gt=0,
                        then=1
                    ),
                    default=0,
                    output_field=IntegerField()
                )
            )
        ).order_by('-medication_count')
        
        category_data = MedicationCategorySerializer(categories, many=True).data
        
        # ========== 7. MANUFACTURER BREAKDOWN ==========
        manufacturers = MedicationManufacturer.objects.filter(
            is_active=True
        ).annotate(
            medication_count=Count('medications'),
            total_stock=Sum('medications__current_stock'),
            total_value=Sum(F('medications__current_stock') * F('medications__selling_price'))
        ).order_by('-medication_count')[:10]
        
        manufacturer_data = MedicationManufacturerSerializer(manufacturers, many=True).data
        
        # ========== 8. TOP & BOTTOM ITEMS ==========
        top_stocked = medications.order_by('-current_stock')[:10]
        top_stocked_data = MedicationListSerializer(top_stocked, many=True).data
        
        lowest_stock = medications.filter(
            current_stock__gt=0
        ).order_by('current_stock')[:10]
        lowest_stock_data = MedicationListSerializer(lowest_stock, many=True).data
        
        most_valuable = medications.order_by('-selling_price')[:10]
        most_valuable_data = MedicationListSerializer(most_valuable, many=True).data
        
        # ========== 9. STOCK MOVEMENT TREND (Last 7 days) ==========
        from datetime import datetime
        
        daily_trend = []
        for i in range(7, 0, -1):
            day = today - timedelta(days=i)
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())
            
            day_additions = StockAdjustment.objects.filter(
                adjustment_type='ADD',
                performed_at__gte=day_start,
                performed_at__lte=day_end
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            day_removals = StockAdjustment.objects.filter(
                adjustment_type__in=['REMOVE', 'SALE'],
                performed_at__gte=day_start,
                performed_at__lte=day_end
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            daily_trend.append({
                'date': day.strftime('%b %d'),
                'additions': day_additions,
                'removals': day_removals,
                'net_change': day_additions - day_removals
            })
        
        # ========== 10. STOCK STATUS DISTRIBUTION ==========
        stock_status = {
            'well_stocked': well_stocked,
            'low_stock': low_stock,
            'critical': critical,
            'out_of_stock': out_of_stock
        }
        
        # ========== 11. EXPIRY STATUS DISTRIBUTION ==========
        expiry_status = {
            'expired': expired,
            'expiring_soon': expiring_30_days,
            'good': total_medications - expired - expiring_30_days - no_expiry,
            'no_expiry': no_expiry
        }
        
        # ========== 12. QUICK ACTIONS ==========
        quick_actions = {
            'can_manage_inventory': pharmacist_profile.can_manage_inventory,
            'is_department_head': pharmacist_profile.is_department_head,
            'can_add_medication': pharmacist_profile.can_manage_inventory,
            'can_adjust_stock': pharmacist_profile.can_manage_inventory,
            'can_view_reports': pharmacist_profile.is_department_head,
        }
        
        # ========== 13. PHARMACIST INFO ==========
        pharmacist_info = {
            'id': request.user.id,
            'name': request.user.full_name,
            'email': request.user.email,
            'employee_id': pharmacist_profile.employee_id,
            'store_location': pharmacist_profile.store_location,
            'qualification': pharmacist_profile.qualification,
            'license_number': pharmacist_profile.license_number,
            'is_department_head': pharmacist_profile.is_department_head,
            'can_manage_inventory': pharmacist_profile.can_manage_inventory,
            'date_assigned': pharmacist_profile.date_assigned,
        }
        
        return Response({
            'success': True,
            'timestamp': timezone.now(),
            'pharmacist': pharmacist_info,
            'dashboard': {
                # Section 1: Key Metrics
                'key_metrics': {
                    'total_medications': total_medications,
                    'in_stock': in_stock,
                    'out_of_stock': out_of_stock,
                    'low_stock': low_stock,
                    'critical': critical,
                    'well_stocked': well_stocked,
                    'stock_health_percentage': stock_health,
                },
                
                # Section 2: Financial Metrics
                'financial_metrics': {
                    'total_inventory_value': float(total_inventory_value),
                    'total_cost_value': float(total_cost_value),
                    'potential_profit': float(potential_profit),
                    'profit_margin_percentage': profit_margin,
                    'average_selling_price': float(avg_selling_price),
                },
                
                # Section 3: Expiry Metrics
                'expiry_metrics': {
                    'expiring_7_days': expiring_7_days,
                    'expiring_30_days': expiring_30_days,
                    'expiring_90_days': expiring_90_days,
                    'expired': expired,
                    'no_expiry': no_expiry,
                    'expiring_medications': MedicationListSerializer(expiring_medications, many=True).data,
                    'expired_medications': MedicationListSerializer(expired_medications, many=True).data,
                },
                
                # Section 4: Alerts
                'alerts': {
                    'summary': alerts_summary,
                    'recent_alerts': recent_alerts_data,
                },
                
                # Section 5: Recent Activity
                'recent_activity': {
                    'adjustments': StockAdjustmentSerializer(recent_adjustments, many=True).data,
                    'weekly_additions': weekly_additions,
                    'weekly_removals': weekly_removals,
                    'weekly_sales': weekly_sales,
                    'weekly_net_change': weekly_net_change,
                    'monthly_additions': monthly_additions,
                    'monthly_removals': monthly_removals,
                    'monthly_sales': monthly_sales,
                    'most_active_medications': most_active_meds,
                },
                
                # Section 6: Category Breakdown
                'category_breakdown': category_data,
                
                # Section 7: Manufacturer Breakdown
                'manufacturer_breakdown': manufacturer_data,
                
                # Section 8: Top Items
                'top_items': {
                    'most_stocked': top_stocked_data,
                    'lowest_stock': lowest_stock_data,
                    'most_valuable': most_valuable_data,
                },
                
                # Section 9: Trends
                'trends': {
                    'daily_trend': daily_trend,
                    'stock_status_distribution': stock_status,
                    'expiry_status_distribution': expiry_status,
                },
                
                # Section 10: Quick Actions
                'quick_actions': quick_actions,
            }
        })


class DashboardSummaryAPIView(APIView):
    """
    GET /api/pharmacy/dashboard/summary/
    Lightweight summary for quick dashboard view
    """
    permission_classes = [IsAuthenticated, IsPharmacist]
    
    def get(self, request):
        medications = Medication.objects.filter(is_active=True)
        today = timezone.now().date()
        
        # Stock counts
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
        
        # Financial
        total_value = medications.aggregate(
            total=Sum(F('current_stock') * F('selling_price'))
        )['total'] or 0
        
        total_cost = medications.aggregate(
            total=Sum(F('current_stock') * F('unit_price'))
        )['total'] or 0
        
        # Expiry
        expiring_soon = medications.filter(
            expiry_date__isnull=False,
            expiry_date__lte=today + timedelta(days=30),
            expiry_date__gt=today
        ).count()
        expired = medications.filter(
            expiry_date__isnull=False,
            expiry_date__lt=today
        ).count()
        
        # Alerts
        active_alerts = StockAlert.objects.filter(status='ACTIVE').count()
        
        # Recent activity count
        last_7_days = timezone.now() - timedelta(days=7)
        recent_activity = StockAdjustment.objects.filter(
            performed_at__gte=last_7_days
        ).count()
        
        return Response({
            'success': True,
            'summary': {
                'medications': {
                    'total': total,
                    'in_stock': in_stock,
                    'low_stock': low_stock,
                    'critical': critical,
                    'out_of_stock': out_of_stock,
                },
                'financial': {
                    'total_value': float(total_value),
                    'total_cost': float(total_cost),
                    'potential_profit': float(total_value - total_cost),
                },
                'expiry': {
                    'expiring_soon': expiring_soon,
                    'expired': expired,
                },
                'alerts': {
                    'active': active_alerts,
                },
                'activity': {
                    'last_7_days': recent_activity,
                }
            }
        })


# ========== NEW: PRESCRIPTION FULFILLMENT VIEWS ==========

class PrescriptionOrdersView(APIView):
    """
    GET /api/pharmacy/prescriptions/ - List all prescription orders
    GET /api/pharmacy/prescriptions/{id}/ - Get single order
    PATCH /api/pharmacy/prescriptions/{id}/ - Update order status
    """
    permission_classes = [IsAuthenticated, IsPharmacist]
    
    def get(self, request, id=None):
        """Get prescription orders"""
        
        if id:
            try:
                order = PrescriptionOrder.objects.select_related(
                    'patient', 'doctor', 'medication', 'pharmacist', 'prescription'
                ).get(id=id)
            except PrescriptionOrder.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Order not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                'success': True,
                'data': self.serialize_order(order)
            })
        
        # List all orders with filters
        orders = PrescriptionOrder.objects.select_related(
            'patient', 'doctor', 'medication', 'pharmacist', 'prescription'
        ).all()
        
        # Filters
        status_filter = request.query_params.get('status')
        if status_filter:
            orders = orders.filter(status=status_filter)
        
        patient_id = request.query_params.get('patient_id')
        if patient_id:
            orders = orders.filter(patient_id=patient_id)
        
        doctor_id = request.query_params.get('doctor_id')
        if doctor_id:
            orders = orders.filter(doctor_id=doctor_id)
        
        date_from = request.query_params.get('date_from')
        if date_from:
            orders = orders.filter(created_at__date__gte=date_from)
        
        date_to = request.query_params.get('date_to')
        if date_to:
            orders = orders.filter(created_at__date__lte=date_to)
        
        search = request.query_params.get('search')
        if search:
            orders = orders.filter(
                Q(medication_name__icontains=search) |
                Q(patient__user__full_name__icontains=search) |
                Q(doctor__full_name__icontains=search) |
                Q(order_id__icontains=search)
            )
        
        # Sorting
        sort_by = request.query_params.get('sort_by', '-created_at')
        orders = orders.order_by(sort_by)
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        total = orders.count()
        start = (page - 1) * page_size
        end = start + page_size
        paginated = orders[start:end]
        
        # Get summary
        summary = {
            'total': total,
            'pending': orders.filter(status='PENDING').count(),
            'processing': orders.filter(status='PROCESSING').count(),
            'fulfilled': orders.filter(status='FULFILLED').count(),
            'partially_fulfilled': orders.filter(status='PARTIALLY_FULFILLED').count(),
            'out_of_stock': orders.filter(status='OUT_OF_STOCK').count(),
            'cancelled': orders.filter(status='CANCELLED').count(),
        }
        
        return Response({
            'success': True,
            'data': [self.serialize_order(order) for order in paginated],
            'summary': summary,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size if page_size > 0 else 1,
                'total': total
            }
        })
    
    def patch(self, request, id):
        """Update order status or notes"""
        try:
            order = PrescriptionOrder.objects.get(id=id)
        except PrescriptionOrder.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Order not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        status_update = request.data.get('status')
        pharmacist_notes = request.data.get('pharmacist_notes')
        quantity_to_fulfill = request.data.get('fulfill_quantity')
        
        # Update status
        if status_update:
            if status_update == 'PROCESSING':
                order.mark_processing(pharmacist=request.user)
            elif status_update == 'CANCELLED':
                order.mark_cancelled(pharmacist=request.user)
            elif status_update == 'OUT_OF_STOCK':
                order.mark_out_of_stock(pharmacist=request.user)
            else:
                return Response({
                    'success': False,
                    'error': f'Invalid status: {status_update}'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update notes
        if pharmacist_notes:
            order.pharmacist_notes = pharmacist_notes
            order.save()
        
        # Fulfill order
        if quantity_to_fulfill:
            try:
                quantity = int(quantity_to_fulfill)
                order.fulfill(quantity=quantity, pharmacist=request.user)
            except ValueError as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True,
            'message': 'Order updated successfully',
            'data': self.serialize_order(order)
        })
    
    def serialize_order(self, order):
        """Serialize order data"""
        return {
            'id': order.id,
            'order_id': order.order_id,
            'prescription_id': order.prescription.id if order.prescription else None,
            'medication_name': order.medication_name,
            'requested_quantity': order.requested_quantity,
            'fulfilled_quantity': order.fulfilled_quantity,
            'remaining_quantity': order.get_remaining_quantity(),
            'status': order.status,
            'status_display': order.get_status_display(),
            'patient': {
                'id': order.patient.id,
                'name': order.patient.user.full_name,
                'mrn': order.patient.patient_id,
                'phone': order.patient.phone,
            },
            'doctor': {
                'id': order.doctor.id if order.doctor else None,
                'name': order.doctor.full_name if order.doctor else None,
            },
            'medication': {
                'id': order.medication.id if order.medication else None,
                'name': order.medication.name if order.medication else None,
                'current_stock': order.medication.current_stock if order.medication else None,
                'unit': order.medication.unit if order.medication else None,
            } if order.medication else None,
            'pharmacist': {
                'id': order.pharmacist.id if order.pharmacist else None,
                'name': order.pharmacist.full_name if order.pharmacist else None,
            } if order.pharmacist else None,
            'fulfilled_at': order.fulfilled_at,
            'notes': order.notes,
            'pharmacist_notes': order.pharmacist_notes,
            'created_at': order.created_at,
            'updated_at': order.updated_at,
        }


class ReceivePrescriptionView(APIView):
    """
    POST /api/pharmacy/prescriptions/receive/
    Receive a new prescription from doctor
    
    This is called by the doctor app when a prescription is created
    """
    permission_classes = [IsAuthenticated, IsPharmacist]
    
    def post(self, request):
        prescription_id = request.data.get('prescription_id')
        medication_name = request.data.get('medication_name')
        patient_id = request.data.get('patient_id')
        doctor_id = request.data.get('doctor_id')
        requested_quantity = request.data.get('quantity', 1)
        notes = request.data.get('notes', '')
        
        # Validate required fields
        if not prescription_id:
            return Response({
                'success': False,
                'error': 'prescription_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not medication_name:
            return Response({
                'success': False,
                'error': 'medication_name is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not patient_id:
            return Response({
                'success': False,
                'error': 'patient_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from emr.models import Prescription
            prescription = Prescription.objects.get(id=prescription_id)
        except Prescription.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Prescription not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get patient and doctor
        try:
            from patients.models import PatientProfile
            patient = PatientProfile.objects.get(id=patient_id)
        except PatientProfile.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Patient not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            from accounts.models import User
            doctor = User.objects.get(id=doctor_id) if doctor_id else None
        except User.DoesNotExist:
            doctor = None
        
        # Check if order already exists
        if PrescriptionOrder.objects.filter(prescription=prescription).exists():
            return Response({
                'success': False,
                'error': 'Prescription already received'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Find matching medication in inventory
        medication = None
        try:
            medication = Medication.objects.filter(
                Q(name__iexact=medication_name) |
                Q(generic_name__iexact=medication_name),
                is_active=True
            ).first()
        except:
            pass
        
        # Create order
        order = PrescriptionOrder.objects.create(
            prescription=prescription,
            patient=patient,
            doctor=doctor,
            medication_name=medication_name,
            requested_quantity=requested_quantity,
            fulfilled_quantity=0,
            status='PENDING',
            medication=medication,
            notes=notes,
            pharmacist=request.user
        )
        
        # Check if medication is in stock
        message = "Prescription received successfully"
        if medication:
            if medication.current_stock <= 0:
                order.status = 'OUT_OF_STOCK'
                order.save()
                message = "⚠️ Medication is out of stock"
            elif medication.current_stock < requested_quantity:
                order.status = 'PARTIALLY_FULFILLED'
                order.save()
                message = f"⚠️ Only {medication.current_stock} units available"
            else:
                message = "✅ Prescription received and ready for fulfillment"
        else:
            message = "⚠️ Medication not found in inventory. Please add to inventory first."
        
        return Response({
            'success': True,
            'message': message,
            'data': PrescriptionOrdersView().serialize_order(order)
        }, status=status.HTTP_201_CREATED)


class FulfillPrescriptionView(APIView):
    """
    POST /api/pharmacy/prescriptions/{id}/fulfill/
    Fulfill a prescription order
    """
    permission_classes = [IsAuthenticated, IsPharmacist]
    
    def post(self, request, order_id):
        try:
            order = PrescriptionOrder.objects.get(id=order_id)
        except PrescriptionOrder.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Order not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if order can be fulfilled
        if order.status == 'FULFILLED':
            return Response({
                'success': False,
                'error': 'Order already fulfilled'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if order.status == 'CANCELLED':
            return Response({
                'success': False,
                'error': 'Order has been cancelled'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if order.status == 'OUT_OF_STOCK':
            return Response({
                'success': False,
                'error': 'Order is marked as out of stock'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get quantity to fulfill
        quantity = request.data.get('quantity')
        if quantity is None:
            quantity = order.get_remaining_quantity()
        else:
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
        
        try:
            order.fulfill(quantity=quantity, pharmacist=request.user)
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True,
            'message': 'Prescription fulfilled successfully',
            'data': PrescriptionOrdersView().serialize_order(order)
        })


class PrescriptionOrderStatsView(APIView):
    """
    GET /api/pharmacy/prescriptions/stats/
    Get statistics about prescription orders
    """
    permission_classes = [IsAuthenticated, IsPharmacist]
    
    def get(self, request):
        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        start_of_month = today.replace(day=1)
        
        orders = PrescriptionOrder.objects.all()
        
        # Today's orders
        today_orders = orders.filter(created_at__date=today)
        today_fulfilled = orders.filter(fulfilled_at__date=today)
        
        # Weekly
        weekly_orders = orders.filter(created_at__date__gte=start_of_week)
        weekly_fulfilled = orders.filter(fulfilled_at__date__gte=start_of_week)
        
        # Monthly
        monthly_orders = orders.filter(created_at__date__gte=start_of_month)
        monthly_fulfilled = orders.filter(fulfilled_at__date__gte=start_of_month)
        
        # Status breakdown
        status_breakdown = {
            'pending': orders.filter(status='PENDING').count(),
            'processing': orders.filter(status='PROCESSING').count(),
            'partially_fulfilled': orders.filter(status='PARTIALLY_FULFILLED').count(),
            'fulfilled': orders.filter(status='FULFILLED').count(),
            'out_of_stock': orders.filter(status='OUT_OF_STOCK').count(),
            'cancelled': orders.filter(status='CANCELLED').count(),
        }
        
        # Most prescribed medications
        top_medications = orders.values('medication_name').annotate(
            total_ordered=Sum('requested_quantity'),
            total_fulfilled=Sum('fulfilled_quantity'),
            order_count=Count('id')
        ).order_by('-order_count')[:10]
        
        return Response({
            'success': True,
            'data': {
                'today': {
                    'new_orders': today_orders.count(),
                    'fulfilled': today_fulfilled.count(),
                    'pending': today_orders.filter(status='PENDING').count(),
                },
                'weekly': {
                    'new_orders': weekly_orders.count(),
                    'fulfilled': weekly_fulfilled.count(),
                },
                'monthly': {
                    'new_orders': monthly_orders.count(),
                    'fulfilled': monthly_fulfilled.count(),
                },
                'status_breakdown': status_breakdown,
                'top_medications': list(top_medications),
                'total_orders': orders.count(),
                'total_fulfilled': orders.filter(status='FULFILLED').count(),
            }
        })

# pharmacy/views.py - ADD AFTER YOUR EXISTING VIEWS

# ========== BILLING VIEWS ==========

class PharmacyBillListView(APIView):
    """
    GET /api/pharmacy/bills/ - List all bills
    POST /api/pharmacy/bills/ - Create new bill
    """
    permission_classes = [IsAuthenticated, IsPharmacist]
    
    def get(self, request):
        bills = PharmacyBill.objects.select_related(
            'patient__user', 'created_by'
        ).prefetch_related('items__medication', 'payments').all()
        
        # Filters
        status = request.query_params.get('status')
        if status:
            bills = bills.filter(payment_status=status)
        
        patient_id = request.query_params.get('patient')
        if patient_id:
            bills = bills.filter(patient_id=patient_id)
        
        search = request.query_params.get('search')
        if search:
            bills = bills.filter(
                Q(bill_number__icontains=search) |
                Q(patient__user__full_name__icontains=search)
            )
        
        bills = bills.order_by('-bill_date')
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        total = bills.count()
        start = (page - 1) * page_size
        end = start + page_size
        paginated = bills[start:end]
        
        data = []
        for bill in paginated:
            data.append({
                'id': bill.id,
                'bill_number': bill.bill_number,
                'bill_date': bill.bill_date,
                'patient_name': bill.patient.user.full_name,
                'patient_id': bill.patient.patient_id,
                'subtotal': float(bill.subtotal),
                'discount': float(bill.discount),
                'tax': float(bill.tax),
                'total': float(bill.total),
                'payment_status': bill.payment_status,
                'payment_status_display': bill.get_payment_status_display(),
                'amount_paid': float(bill.amount_paid),
                'balance_due': float(bill.balance_due),
                'items': [
                    {
                        'medication_name': item.medication.name,
                        'quantity': item.quantity,
                        'unit_price': float(item.unit_price),
                        'total': float(item.total)
                    }
                    for item in bill.items.all()
                ],
                'created_at': bill.created_at,
            })
        
        return Response({
            'success': True,
            'data': data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': (total + page_size - 1) // page_size if page_size > 0 else 1
            }
        })
    
    def post(self, request):
        """Create new bill"""
        patient_id = request.data.get('patient')
        items_data = request.data.get('items', [])
        discount_percentage = request.data.get('discount_percentage', 0)
        tax_percentage = request.data.get('tax_percentage', 0)
        payment_method = request.data.get('payment_method', 'CASH')
        notes = request.data.get('notes', '')
        prescription_id = request.data.get('prescription_id')
        
        if not patient_id:
            return Response({
                'success': False,
                'error': 'Patient is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not items_data:
            return Response({
                'success': False,
                'error': 'At least one item is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from patients.models import PatientProfile
            patient = PatientProfile.objects.get(id=patient_id)
        except PatientProfile.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Patient not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get prescription if provided
        prescription = None
        if prescription_id:
            try:
                prescription = PrescriptionOrder.objects.get(id=prescription_id)
            except PrescriptionOrder.DoesNotExist:
                pass
        
        # Calculate subtotal
        subtotal = 0
        bill_items = []
        for item in items_data:
            medication_id = item.get('medication_id')
            quantity = item.get('quantity', 1)
            unit_price = item.get('unit_price', 0)
            item_discount = item.get('discount', 0)
            
            try:
                medication = Medication.objects.get(id=medication_id)
            except Medication.DoesNotExist:
                return Response({
                    'success': False,
                    'error': f'Medication {medication_id} not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Check stock
            if medication.current_stock < quantity:
                return Response({
                    'success': False,
                    'error': f'Insufficient stock for {medication.name}. Available: {medication.current_stock}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            item_total = unit_price * quantity - item_discount
            subtotal += item_total
            
            bill_items.append({
                'medication': medication,
                'quantity': quantity,
                'unit_price': unit_price,
                'discount': item_discount
            })
        
        # Calculate discount and tax
        discount = (subtotal * discount_percentage) / 100
        taxable_amount = subtotal - discount
        tax = (taxable_amount * tax_percentage) / 100
        total = taxable_amount + tax
        
        # Create bill
        bill = PharmacyBill.objects.create(
            patient=patient,
            subtotal=subtotal,
            discount=discount,
            discount_percentage=discount_percentage,
            tax=tax,
            tax_percentage=tax_percentage,
            total=total,
            payment_status='PENDING',
            payment_method=payment_method,
            prescription=prescription,
            notes=notes,
            created_by=request.user
        )
        
        # Create bill items and update stock
        for item in bill_items:
            PharmacyBillItem.objects.create(
                bill=bill,
                medication=item['medication'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                discount=item['discount']
            )
            
            # Update stock
            item['medication'].current_stock -= item['quantity']
            item['medication'].save()
        
        return Response({
            'success': True,
            'message': 'Bill created successfully',
            'data': {
                'id': bill.id,
                'bill_number': bill.bill_number,
                'total': float(bill.total),
                'payment_status': bill.payment_status
            }
        }, status=status.HTTP_201_CREATED)


class PharmacyBillDetailView(APIView):
    """
    GET /api/pharmacy/bills/{id}/ - Get bill details
    DELETE /api/pharmacy/bills/{id}/ - Delete/cancel bill
    """
    permission_classes = [IsAuthenticated, IsPharmacist]
    
    def get(self, request, pk):
        try:
            bill = PharmacyBill.objects.select_related(
                'patient__user', 'created_by', 'prescription'
            ).prefetch_related('items__medication', 'payments').get(id=pk)
        except PharmacyBill.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Bill not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            'success': True,
            'data': {
                'id': bill.id,
                'bill_number': bill.bill_number,
                'bill_date': bill.bill_date,
                'patient': {
                    'id': bill.patient.id,
                    'name': bill.patient.user.full_name,
                    'mrn': bill.patient.patient_id,
                    'phone': bill.patient.phone,
                },
                'subtotal': float(bill.subtotal),
                'discount': float(bill.discount),
                'discount_percentage': float(bill.discount_percentage),
                'tax': float(bill.tax),
                'tax_percentage': float(bill.tax_percentage),
                'total': float(bill.total),
                'payment_status': bill.payment_status,
                'payment_status_display': bill.get_payment_status_display(),
                'amount_paid': float(bill.amount_paid),
                'balance_due': float(bill.balance_due),
                'items': [
                    {
                        'id': item.id,
                        'medication_name': item.medication.name,
                        'medication_id': item.medication.id,
                        'quantity': item.quantity,
                        'unit_price': float(item.unit_price),
                        'discount': float(item.discount),
                        'total': float(item.total),
                    }
                    for item in bill.items.all()
                ],
                'payments': [
                    {
                        'id': p.id,
                        'amount': float(p.amount),
                        'payment_method': p.payment_method,
                        'payment_date': p.payment_date,
                        'received_by': p.received_by.full_name if p.received_by else None,
                    }
                    for p in bill.payments.all()
                ],
                'prescription_id': bill.prescription.id if bill.prescription else None,
                'notes': bill.notes,
                'created_by': bill.created_by.full_name if bill.created_by else None,
                'created_at': bill.created_at,
            }
        })
    
    def delete(self, request, pk):
        try:
            bill = PharmacyBill.objects.get(id=pk)
        except PharmacyBill.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Bill not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if bill.payment_status == 'PAID':
            return Response({
                'success': False,
                'error': 'Cannot delete a paid bill. Please refund first.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Restore stock
        for item in bill.items.all():
            item.medication.current_stock += item.quantity
            item.medication.save()
        
        bill.payment_status = 'CANCELLED'
        bill.save()
        
        return Response({
            'success': True,
            'message': 'Bill cancelled successfully'
        })


class PharmacyPaymentView(APIView):
    """
    POST /api/pharmacy/bills/{id}/pay/ - Record payment
    """
    permission_classes = [IsAuthenticated, IsPharmacist]
    
    def post(self, request, pk):
        try:
            bill = PharmacyBill.objects.get(id=pk)
        except PharmacyBill.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Bill not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        amount = request.data.get('amount')
        payment_method = request.data.get('payment_method', 'CASH')
        transaction_id = request.data.get('transaction_id', '')
        notes = request.data.get('notes', '')
        
        if not amount:
            return Response({
                'success': False,
                'error': 'Amount is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            amount = float(amount)
        except ValueError:
            return Response({
                'success': False,
                'error': 'Invalid amount'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if amount <= 0:
            return Response({
                'success': False,
                'error': 'Amount must be greater than 0'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if amount > bill.balance_due:
            return Response({
                'success': False,
                'error': f'Amount exceeds balance due: {bill.balance_due}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create payment
        payment = PharmacyPayment.objects.create(
            bill=bill,
            amount=amount,
            payment_method=payment_method,
            transaction_id=transaction_id,
            notes=notes,
            received_by=request.user
        )
        
        # Update bill
        bill.amount_paid += amount
        bill.balance_due = bill.total - bill.amount_paid
        
        if bill.balance_due <= 0:
            bill.payment_status = 'PAID'
        elif bill.amount_paid > 0:
            bill.payment_status = 'PARTIAL'
        
        bill.save()
        
        return Response({
            'success': True,
            'message': 'Payment recorded successfully',
            'data': {
                'payment': {
                    'id': payment.id,
                    'amount': float(payment.amount),
                    'payment_method': payment.payment_method,
                    'payment_date': payment.payment_date,
                },
                'bill': {
                    'id': bill.id,
                    'bill_number': bill.bill_number,
                    'payment_status': bill.payment_status,
                    'payment_status_display': bill.get_payment_status_display(),
                    'amount_paid': float(bill.amount_paid),
                    'balance_due': float(bill.balance_due),
                }
            }
        })


class PharmacyBillingDashboardView(APIView):
    """
    GET /api/pharmacy/billing/dashboard/ - Billing dashboard stats
    """
    permission_classes = [IsAuthenticated, IsPharmacist]
    
    def get(self, request):
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        start_of_week = today - timedelta(days=today.weekday())
        
        bills = PharmacyBill.objects.all()
        
        # Today
        today_bills = bills.filter(bill_date__date=today)
        today_total = today_bills.aggregate(Sum('total'))['total__sum'] or 0
        today_count = today_bills.count()
        
        # Month
        month_bills = bills.filter(bill_date__date__gte=start_of_month)
        month_total = month_bills.aggregate(Sum('total'))['total__sum'] or 0
        month_count = month_bills.count()
        
        # Pending
        pending_bills = bills.filter(payment_status='PENDING')
        pending_total = pending_bills.aggregate(Sum('balance_due'))['balance_due__sum'] or 0
        pending_count = pending_bills.count()
        
        # Partial
        partial_bills = bills.filter(payment_status='PARTIAL')
        partial_total = partial_bills.aggregate(Sum('balance_due'))['balance_due__sum'] or 0
        partial_count = partial_bills.count()
        
        # Payment methods breakdown
        payment_breakdown = bills.values('payment_method').annotate(
            count=Count('id'),
            total=Sum('total')
        )
        
        # Recent bills
        recent_bills = bills.select_related(
            'patient__user'
        ).order_by('-bill_date')[:10]
        
        recent_data = []
        for bill in recent_bills:
            recent_data.append({
                'id': bill.id,
                'bill_number': bill.bill_number,
                'patient_name': bill.patient.user.full_name,
                'total': float(bill.total),
                'payment_status': bill.payment_status,
                'payment_status_display': bill.get_payment_status_display(),
                'bill_date': bill.bill_date,
            })
        
        return Response({
            'success': True,
            'summary': {
                'today': {
                    'total': float(today_total),
                    'count': today_count,
                },
                'month': {
                    'total': float(month_total),
                    'count': month_count,
                },
                'pending': {
                    'total': float(pending_total),
                    'count': pending_count,
                },
                'partial': {
                    'total': float(partial_total),
                    'count': partial_count,
                },
                'total_bills': bills.count(),
                'total_revenue': bills.aggregate(Sum('total'))['total__sum'] or 0,
            },
            'payment_methods': list(payment_breakdown),
            'recent_bills': recent_data
        })