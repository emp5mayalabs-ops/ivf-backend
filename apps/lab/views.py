# lab/views.py - Complete with Billing Integration

from datetime import timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import login, logout
from django.utils import timezone
from django.db.models import Q, Sum, Count, F
from django.db import transaction
from django.shortcuts import get_object_or_404
from decimal import Decimal

from .serializers import (
    LabLoginSerializer, 
    LabProfileSerializer, 
    LabProfileUpdateSerializer,
    LabTestTypeSerializer,
    LabTestTypeCreateUpdateSerializer,
    LabFieldSerializer,
    LabRecordSerializer,
    LabRecordCreateUpdateSerializer,
    LabOrderSerializer,
    LabResultUpdateSerializer,
    LabOrderListSerializer,
    # Billing serializers
    LabBillSerializer,
    LabBillListSerializer,
    LabBillCreateSerializer,
    LabPaymentSerializer,
)
from .models import (
    LabTechnicianProfile,
    AndrologyLabTechnician,
    LabTestType,
    LabField,
    LabRecord,
    # Billing models
    LabBill,
    LabBillItem,
    LabPayment,
)
from accounts.models import LoginAuditLog
from accounts.models import User


# ========== HELPER FUNCTIONS ==========

def get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def get_lab_profile(user):
    """Get lab profile based on user role"""
    if user.role == 'TEC':
        return getattr(user, 'technician_profile', None)
    elif user.role == 'AND':
        return getattr(user, 'andrology_technician_profile', None)
    elif user.role == 'EMB':
        return getattr(user, 'embryologist_profile', None)
    return None


def check_lab_access(user):
    """Check if user has lab access"""
    return user.role in ['TEC', 'AND', 'EMB']


# ========== AUTH VIEWS ==========

class LabLoginView(APIView):
    """
    POST /api/lab/login/
    Lab Login API
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = LabLoginSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = serializer.validated_data['user']
        login(request, user)
        
        # Log login activity
        try:
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
        
        lab_profile = get_lab_profile(user)
        
        return Response({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'name': user.full_name,
                'email': user.email,
                'role': user.role,
                'role_display': user.get_role_display(),
                'employee_id': getattr(lab_profile, 'employee_id', None),
                'is_active': getattr(lab_profile, 'is_active', True),
            }
        }, status=status.HTTP_200_OK)


class LabLogoutView(APIView):
    """
    POST /api/lab/logout/
    Lab Logout API
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        if not check_lab_access(request.user):
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
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


# ========== PROFILE VIEWS ==========

class LabProfileView(APIView):
    """
    GET /api/lab/profile/    - Get current lab profile
    PUT /api/lab/profile/    - Update current lab profile
    DELETE /api/lab/profile/ - Delete/Deactivate current lab profile
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        if not check_lab_access(user):
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        lab_profile = get_lab_profile(user)
        if not lab_profile:
            return Response({
                'success': False,
                'error': 'Profile not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = LabProfileSerializer(lab_profile)
        return Response({
            'success': True,
            'profile': serializer.data
        }, status=status.HTTP_200_OK)
    
    def put(self, request):
        user = request.user
        
        if not check_lab_access(user):
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        lab_profile = get_lab_profile(user)
        if not lab_profile:
            return Response({
                'success': False,
                'error': 'Profile not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if 'new_password' in request.data:
            old_password = request.data.get('old_password')
            new_password = request.data.get('new_password')
            
            if not old_password:
                return Response({
                    'success': False,
                    'error': 'Current password is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not user.check_password(old_password):
                return Response({
                    'success': False,
                    'error': 'Current password is incorrect'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if len(new_password) < 6:
                return Response({
                    'success': False,
                    'error': 'Password must be at least 6 characters'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user.set_password(new_password)
            user.save()
            
            return Response({
                'success': True,
                'message': 'Password updated successfully'
            }, status=status.HTTP_200_OK)
        
        serializer = LabProfileUpdateSerializer(
            lab_profile,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            lab_profile = serializer.save()
            return Response({
                'success': True,
                'message': 'Profile updated successfully',
                'profile': LabProfileSerializer(lab_profile).data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request):
        user = request.user
        
        if not check_lab_access(user):
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        lab_profile = get_lab_profile(user)
        if not lab_profile:
            return Response({
                'success': False,
                'error': 'Profile not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        user.is_active = False
        user.save()
        lab_profile.is_active = False
        lab_profile.save()
        
        logout(request)
        
        return Response({
            'success': True,
            'message': 'Profile deactivated successfully'
        }, status=status.HTTP_200_OK)


class LabProfileDetailView(APIView):
    """
    GET /api/lab/profile/{id}/ - Get lab profile by ID
    DELETE /api/lab/profile/{id}/ - Delete lab profile by ID (Admin only)
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, lab_id):
        if request.user.role not in ['ADM']:
            if request.user.id != lab_id:
                return Response({
                    'success': False,
                    'error': 'Access denied'
                }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            user = User.objects.get(id=lab_id)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        lab_profile = get_lab_profile(user)
        if not lab_profile:
            return Response({
                'success': False,
                'error': 'Profile not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = LabProfileSerializer(lab_profile)
        return Response({
            'success': True,
            'profile': serializer.data
        }, status=status.HTTP_200_OK)
    
    def delete(self, request, lab_id):
        if request.user.role != 'ADM':
            return Response({
                'success': False,
                'error': 'Access denied. Admin only'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            user = User.objects.get(id=lab_id)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        lab_profile = get_lab_profile(user)
        if not lab_profile:
            return Response({
                'success': False,
                'error': 'Profile not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        user.is_active = False
        user.save()
        lab_profile.is_active = False
        lab_profile.save()
        
        return Response({
            'success': True,
            'message': f'User {user.full_name} deactivated successfully'
        }, status=status.HTTP_200_OK)


# ========== LAB TEST TYPES VIEWS ==========

class LabTestTypeListView(APIView):
    """
    GET /api/lab/test-types/ - List all test types (full details)
    GET /api/lab/test-types/?simple=true - List test types (lightweight, for dropdowns)
    GET /api/lab/test-types/?search=lipid - Search test types
    POST /api/lab/test-types/ - Create new test type
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        test_types = LabTestType.objects.filter(is_active=True)
        
        search = request.query_params.get('search')
        if search:
            test_types = test_types.filter(
                Q(name__icontains=search) | 
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        simple = request.query_params.get('simple', '').lower() == 'true'
        
        if simple:
            data = [{
                'id': test.id,
                'name': test.name,
                'code': test.code,
                'icon': test.icon,
                'color': test.color,
                'description': test.description,
                'price': float(test.price) if test.price else 0,
            } for test in test_types]
            return Response({
                'success': True,
                'count': test_types.count(),
                'test_types': data
            }, status=status.HTTP_200_OK)
        
        serializer = LabTestTypeSerializer(test_types, many=True)
        return Response({
            'success': True,
            'count': test_types.count(),
            'test_types': serializer.data
        }, status=status.HTTP_200_OK)
    
    def post(self, request):
        if request.user.role not in ['ADM'] and not request.user.is_superuser:
            return Response({
                'success': False,
                'error': 'Only admin can create test types'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = LabTestTypeCreateUpdateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            test_type = serializer.save(created_by=request.user)
            return Response({
                'success': True,
                'message': 'Test type created successfully',
                'test_type': LabTestTypeSerializer(test_type).data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class LabTestTypeDetailView(APIView):
    """
    GET /api/lab/test-types/{id}/ - Get test type details
    PUT /api/lab/test-types/{id}/ - Update test type
    DELETE /api/lab/test-types/{id}/ - Delete test type
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, test_type_id):
        try:
            test_type = LabTestType.objects.get(id=test_type_id, is_active=True)
        except LabTestType.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Test type not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = LabTestTypeSerializer(test_type)
        return Response({
            'success': True,
            'test_type': serializer.data
        }, status=status.HTTP_200_OK)
    
    def put(self, request, test_type_id):
        if request.user.role not in ['ADM'] and not request.user.is_superuser:
            return Response({
                'success': False,
                'error': 'Only admin can update test types'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            test_type = LabTestType.objects.get(id=test_type_id)
        except LabTestType.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Test type not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = LabTestTypeCreateUpdateSerializer(
            test_type,
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            test_type = serializer.save()
            return Response({
                'success': True,
                'message': 'Test type updated successfully',
                'test_type': LabTestTypeSerializer(test_type).data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, test_type_id):
        if request.user.role not in ['ADM'] and not request.user.is_superuser:
            return Response({
                'success': False,
                'error': 'Only admin can delete test types'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            test_type = LabTestType.objects.get(id=test_type_id)
        except LabTestType.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Test type not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        test_type.is_active = False
        test_type.save()
        
        return Response({
            'success': True,
            'message': f'Test type "{test_type.name}" deleted successfully'
        }, status=status.HTTP_200_OK)


# ========== LAB RECORD VIEWS ==========

class LabRecordListView(APIView):
    """
    GET /api/lab/records/ - List all lab records
    POST /api/lab/records/ - Create new lab record
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not check_lab_access(request.user) and request.user.role != 'ADM':
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        records = LabRecord.objects.filter(is_active=True)
        
        test_type = request.query_params.get('test_type')
        if test_type:
            records = records.filter(test_type_id=test_type)
        
        patient = request.query_params.get('patient')
        if patient:
            records = records.filter(patient_id=patient)
        
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            records = records.filter(test_date__gte=date_from)
        if date_to:
            records = records.filter(test_date__lte=date_to)
        
        status_filter = request.query_params.get('status')
        if status_filter:
            records = records.filter(status=status_filter)
        
        search = request.query_params.get('search')
        if search:
            records = records.filter(
                Q(patient__full_name__icontains=search) |
                Q(test_type__name__icontains=search) |
                Q(notes__icontains=search)
            )
        
        ordering = request.query_params.get('ordering', '-test_date')
        records = records.order_by(ordering)
        
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        start = (page - 1) * page_size
        end = start + page_size
        
        total = records.count()
        records_page = records[start:end]
        
        serializer = LabRecordSerializer(records_page, many=True)
        
        return Response({
            'success': True,
            'count': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size,
            'records': serializer.data
        }, status=status.HTTP_200_OK)
    
    def post(self, request):
        if not check_lab_access(request.user):
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = LabRecordCreateUpdateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            record = serializer.save(created_by=request.user)
            return Response({
                'success': True,
                'message': 'Lab record created successfully',
                'record': LabRecordSerializer(record).data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class LabRecordDetailView(APIView):
    """
    GET /api/lab/records/{id}/ - Get record details
    PUT /api/lab/records/{id}/ - Update record
    DELETE /api/lab/records/{id}/ - Delete record
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, record_id):
        if not check_lab_access(request.user) and request.user.role != 'ADM':
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            record = LabRecord.objects.get(id=record_id, is_active=True)
        except LabRecord.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Record not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = LabRecordSerializer(record)
        return Response({
            'success': True,
            'record': serializer.data
        }, status=status.HTTP_200_OK)
    
    def put(self, request, record_id):
        if not check_lab_access(request.user):
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            record = LabRecord.objects.get(id=record_id, is_active=True)
        except LabRecord.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Record not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = LabRecordCreateUpdateSerializer(
            record,
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            record = serializer.save(updated_by=request.user)
            return Response({
                'success': True,
                'message': 'Record updated successfully',
                'record': LabRecordSerializer(record).data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, record_id):
        if not check_lab_access(request.user):
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            record = LabRecord.objects.get(id=record_id)
        except LabRecord.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Record not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        record.is_active = False
        record.save()
        
        return Response({
            'success': True,
            'message': 'Record deleted successfully'
        }, status=status.HTTP_200_OK)


class LabRecordsByPatientView(APIView):
    """
    GET /api/lab/records/patient/{patient_id}/ - Get records for a patient
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, patient_id):
        if not check_lab_access(request.user) and request.user.role != 'ADM':
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            patient = User.objects.get(id=patient_id)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Patient not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        records = LabRecord.objects.filter(patient=patient, is_active=True).order_by('-test_date')
        
        serializer = LabRecordSerializer(records, many=True)
        return Response({
            'success': True,
            'patient': {
                'id': patient.id,
                'name': patient.full_name,
                'email': patient.email
            },
            'count': records.count(),
            'records': serializer.data
        }, status=status.HTTP_200_OK)


class LabStatisticsView(APIView):
    """
    GET /api/lab/statistics/ - Get lab statistics
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not check_lab_access(request.user) and request.user.role != 'ADM':
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        total_records = LabRecord.objects.filter(is_active=True).count()
        total_test_types = LabTestType.objects.filter(is_active=True).count()
        
        records_by_status = {}
        for status_choice in LabRecord.STATUS_CHOICES:
            status_code = status_choice[0]
            count = LabRecord.objects.filter(status=status_code, is_active=True).count()
            if count > 0:
                records_by_status[status_code] = count
        
        records_by_test_type = []
        test_types = LabTestType.objects.filter(is_active=True)
        for test_type in test_types:
            count = LabRecord.objects.filter(test_type=test_type, is_active=True).count()
            if count > 0:
                records_by_test_type.append({
                    'id': test_type.id,
                    'name': test_type.name,
                    'count': count
                })
        
        recent_records = LabRecord.objects.filter(is_active=True).order_by('-test_date')[:10]
        recent_data = LabRecordSerializer(recent_records, many=True).data
        
        return Response({
            'success': True,
            'statistics': {
                'total_records': total_records,
                'total_test_types': total_test_types,
                'records_by_status': records_by_status,
                'records_by_test_type': records_by_test_type,
                'recent_records': recent_data
            }
        }, status=status.HTTP_200_OK)


# ========== LAB ORDER VIEWS FOR DOCTOR-LAB INTEGRATION ==========

class LabOrderCreateView(APIView):
    """
    POST /api/lab/orders/create/
    Create a lab test order from doctor or receptionist
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        if request.user.role not in ['END', 'GYN', 'ANE', 'REC']:
            return Response({
                'success': False,
                'error': 'Only doctors and receptionists can order lab tests'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = LabOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        patient_id = serializer.validated_data['patient_id']
        test_type_id = serializer.validated_data['test_type_id']
        notes = serializer.validated_data.get('notes', '')
        priority = serializer.validated_data.get('priority', 'ROUTINE')
        
        patient = None
        patient_name = None
        
        try:
            from patients.models import PatientProfile
            patient_profile = PatientProfile.objects.get(id=patient_id)
            patient = patient_profile.user
            patient_name = patient_profile.user.full_name
        except PatientProfile.DoesNotExist:
            try:
                patient = User.objects.get(id=patient_id)
                patient_name = patient.full_name
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': f'Patient not found with ID: {patient_id}'
                }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            test_type = LabTestType.objects.get(id=test_type_id, is_active=True)
        except LabTestType.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Test type not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        lab_record = LabRecord.objects.create(
            patient=patient,
            test_type=test_type,
            test_date=timezone.now(),
            status='ORDERED',
            priority=priority,
            field_values={},
            notes=f"Ordered by {request.user.full_name} ({request.user.role}). {notes}",
            created_by=request.user
        )
        
        return Response({
            'success': True,
            'message': 'Lab test ordered successfully',
            'order': {
                'id': lab_record.id,
                'token_number': lab_record.token_number,
                'test_name': test_type.name,
                'test_code': test_type.code,
                'patient_name': patient.full_name,
                'patient_id': patient.id,
                'status': lab_record.status,
                'status_display': lab_record.get_status_display(),
                'priority': priority,
                'priority_display': lab_record.get_priority_display(),
                'ordered_by': request.user.full_name,
                'ordered_at': lab_record.created_at
            }
        }, status=status.HTTP_201_CREATED)


class LabOrderListView(APIView):
    """
    GET /api/lab/orders/
    GET /api/lab/orders/?patient_id=1
    GET /api/lab/orders/?status=ORDERED
    GET /api/lab/orders/?test_type_id=5
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if request.user.role not in ['TEC', 'AND', 'EMB', 'ADM', 'END', 'GYN', 'ANE', 'REC']:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        patient_id = request.query_params.get('patient_id')
        status_filter = request.query_params.get('status')
        test_type_id = request.query_params.get('test_type_id')
        priority_filter = request.query_params.get('priority')
        
        orders = LabRecord.objects.filter(is_active=True)
        
        if request.user.role in ['END', 'GYN', 'ANE']:
            from patients.models import PatientProfile
            doctor_patients = PatientProfile.objects.filter(
                op_tickets__assigned_doctor=request.user
            ).values_list('user_id', flat=True)
            orders = orders.filter(patient_id__in=doctor_patients)
        
        if patient_id:
            orders = orders.filter(patient_id=patient_id)
        if status_filter:
            orders = orders.filter(status=status_filter)
        if test_type_id:
            orders = orders.filter(test_type_id=test_type_id)
        if priority_filter:
            orders = orders.filter(priority=priority_filter)
        
        orders = orders.order_by('-created_at')
        
        serializer = LabOrderListSerializer(orders, many=True)
        
        pending_count = orders.filter(status='ORDERED').count()
        in_progress_count = orders.filter(status='IN_PROGRESS').count()
        completed_count = orders.filter(status='COMPLETED').count()
        cancelled_count = orders.filter(status='CANCELLED').count()
        
        return Response({
            'success': True,
            'statistics': {
                'total': orders.count(),
                'ordered': pending_count,
                'in_progress': in_progress_count,
                'completed': completed_count,
                'cancelled': cancelled_count,
            },
            'orders': serializer.data
        })


class LabOrderDetailView(APIView):
    """
    GET /api/lab/orders/{id}/
    PUT /api/lab/orders/{id}/ - Update with results (Lab only)
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, order_id):
        try:
            order = LabRecord.objects.get(id=order_id, is_active=True)
        except LabRecord.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Order not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if request.user.role in ['END', 'GYN', 'ANE']:
            from patients.models import PatientProfile
            if not PatientProfile.objects.filter(
                user=order.patient,
                op_tickets__assigned_doctor=request.user
            ).exists():
                return Response({
                    'success': False,
                    'error': 'Access denied'
                }, status=status.HTTP_403_FORBIDDEN)
        elif request.user.role not in ['TEC', 'AND', 'EMB', 'ADM', 'REC']:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        fields = order.test_type.fields.filter(is_active=True).order_by('display_order')
        
        field_data = []
        for field in fields:
            field_data.append({
                'id': field.id,
                'label': field.label,
                'field_key': field.field_key,
                'field_type': field.field_type,
                'value': order.field_values.get(field.field_key),
                'is_required': field.is_required,
                'options': field.get_options_list() if field.field_type in ['select', 'radio', 'multiselect'] else None,
                'placeholder': field.placeholder,
                'help_text': field.help_text,
            })
        
        return Response({
            'success': True,
            'order': {
                'id': order.id,
                'token_number': order.token_number,
                'patient': {
                    'id': order.patient.id,
                    'name': order.patient.full_name,
                    'email': order.patient.email,
                },
                'test_type': {
                    'id': order.test_type.id,
                    'name': order.test_type.name,
                    'code': order.test_type.code,
                    'description': order.test_type.description,
                    'price': float(order.test_type.price) if order.test_type.price else 0,
                    'fields': field_data,
                },
                'test_date': order.test_date,
                'status': order.status,
                'status_display': order.get_status_display(),
                'priority': order.priority,
                'priority_display': order.get_priority_display(),
                'field_values': order.field_values,
                'notes': order.notes,
                'ordered_by': order.created_by.full_name if order.created_by else None,
                'created_at': order.created_at,
                'updated_at': order.updated_at
            }
        })
    
    def put(self, request, order_id):
        if request.user.role not in ['TEC', 'AND', 'EMB', 'ADM']:
            return Response({
                'success': False,
                'error': 'Only lab technicians can update results'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            order = LabRecord.objects.get(id=order_id, is_active=True)
        except LabRecord.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Order not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if order.status in ['COMPLETED', 'CANCELLED']:
            return Response({
                'success': False,
                'error': f'Cannot update order in {order.status} status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        field_values = request.data.get('field_values', {})
        notes = request.data.get('notes')
        status_update = request.data.get('status', 'COMPLETED')
        
        if field_values:
            if order.field_values:
                order.field_values.update(field_values)
            else:
                order.field_values = field_values
        
        if notes:
            if order.notes:
                order.notes = f"{order.notes}\n\nLab Results Notes: {notes}"
            else:
                order.notes = f"Lab Results Notes: {notes}"
        
        order.status = status_update
        order.updated_by = request.user
        
        if status_update == 'COMPLETED':
            order.test_date = timezone.now()
        
        order.save()
        
        return Response({
            'success': True,
            'message': 'Lab results updated successfully',
            'order': {
                'id': order.id,
                'status': order.status,
                'status_display': order.get_status_display(),
                'field_values': order.field_values,
                'notes': order.notes,
                'updated_by': request.user.full_name,
                'updated_at': order.updated_at
            }
        }, status=status.HTTP_200_OK)


class LabOrderCancelView(APIView):
    """
    POST /api/lab/orders/{id}/cancel/
    Cancel a lab order
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, order_id):
        try:
            order = LabRecord.objects.get(id=order_id, is_active=True)
        except LabRecord.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Order not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        user_role = request.user.role
        
        if user_role in ['END', 'GYN', 'ANE']:
            if order.created_by != request.user:
                from patients.models import PatientProfile
                if not PatientProfile.objects.filter(
                    user=order.patient,
                    op_tickets__assigned_doctor=request.user
                ).exists():
                    return Response({
                        'success': False,
                        'error': 'Access denied. You can only cancel orders for your patients.'
                    }, status=status.HTTP_403_FORBIDDEN)
        elif user_role == 'REC':
            pass
        elif user_role in ['TEC', 'AND', 'EMB', 'ADM']:
            pass
        else:
            return Response({
                'success': False,
                'error': 'Access denied. You do not have permission to cancel orders.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if order.status in ['COMPLETED', 'CANCELLED']:
            return Response({
                'success': False,
                'error': f'Cannot cancel order in "{order.get_status_display()}" status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        order.status = 'CANCELLED'
        order.updated_by = request.user
        order.save()
        
        return Response({
            'success': True,
            'message': 'Order cancelled successfully',
            'order': {
                'id': order.id,
                'token_number': order.token_number,
                'status': order.status,
                'status_display': order.get_status_display(),
                'cancelled_by': request.user.full_name,
                'cancelled_at': order.updated_at
            }
        })


# ============================================================
# 🆕 LAB BILLING VIEWS
# ============================================================

class LabBillListView(APIView):
    """
    GET /api/lab/bills/ - List all lab bills
    POST /api/lab/bills/ - Create new lab bill & push to Finance
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List all lab bills with filters"""
        if not check_lab_access(request.user) and request.user.role not in ['ADM', 'REC']:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        bills = LabBill.objects.select_related(
            'patient__user', 'created_by'
        ).prefetch_related('items__test_type', 'payments').all()
        
        # Filters
        status_filter = request.query_params.get('status')
        if status_filter:
            bills = bills.filter(payment_status=status_filter)
        
        patient_id = request.query_params.get('patient')
        if patient_id:
            bills = bills.filter(patient_id=patient_id)
        
        search = request.query_params.get('search')
        if search:
            bills = bills.filter(
                Q(bill_number__icontains=search) |
                Q(patient__user__full_name__icontains=search)
            )
        
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            bills = bills.filter(bill_date__date__gte=date_from)
        if date_to:
            bills = bills.filter(bill_date__date__lte=date_to)
        
        bills = bills.order_by('-bill_date')
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        total = bills.count()
        start = (page - 1) * page_size
        end = start + page_size
        paginated = bills[start:end]
        
        serializer = LabBillListSerializer(paginated, many=True)
        
        # Summary
        summary = {
            'total_bills': total,
            'pending': bills.filter(payment_status='PENDING').count(),
            'partial': bills.filter(payment_status='PARTIAL').count(),
            'paid': bills.filter(payment_status='PAID').count(),
            'cancelled': bills.filter(payment_status='CANCELLED').count(),
            'total_revenue': bills.aggregate(Sum('total'))['total__sum'] or 0,
            'total_balance': bills.aggregate(Sum('balance_due'))['balance_due__sum'] or 0,
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
        """Create new lab bill and push to Finance"""
        if not check_lab_access(request.user) and request.user.role not in ['ADM', 'REC']:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = LabBillCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        patient_id = data['patient_id']
        test_ids = data['test_ids']
        quantities = data.get('quantities', [1] * len(test_ids))
        discount_percentage = data.get('discount_percentage', 0)
        tax_percentage = data.get('tax_percentage', 0)
        payment_method = data.get('payment_method', 'CASH')
        notes = data.get('notes', '')
        lab_record_ids = data.get('lab_record_ids', [])
        
        # Get patient
        try:
            from patients.models import PatientProfile
            patient = PatientProfile.objects.get(id=patient_id)
        except PatientProfile.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Patient not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get tests and calculate subtotal
        tests = []
        subtotal = 0
        
        for i, test_id in enumerate(test_ids):
            try:
                test = LabTestType.objects.get(id=test_id, is_active=True)
            except LabTestType.DoesNotExist:
                return Response({
                    'success': False,
                    'error': f'Test type {test_id} not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            qty = quantities[i] if i < len(quantities) else 1
            price = test.price or Decimal('0.00')
            
            tests.append({
                'test': test,
                'quantity': qty,
                'unit_price': price,
            })
            subtotal += price * qty
        
        # Get lab records to link
        lab_records = []
        if lab_record_ids:
            lab_records = LabRecord.objects.filter(id__in=lab_record_ids, is_active=True)
        
        # ============================================================
        # 🔥 START ATOMIC TRANSACTION
        # ============================================================
        with transaction.atomic():
            
            # Calculate discount and tax
            discount = (subtotal * discount_percentage) / 100
            taxable_amount = subtotal - discount
            tax = (taxable_amount * tax_percentage) / 100
            total = taxable_amount + tax
            
            # Create bill
            bill = LabBill.objects.create(
                patient=patient,
                subtotal=subtotal,
                discount=discount,
                discount_percentage=discount_percentage,
                tax=tax,
                tax_percentage=tax_percentage,
                total=total,
                payment_status='PENDING',
                payment_method=payment_method,
                notes=notes,
                created_by=request.user
            )
            
            # Create bill items
            for item in tests:
                LabBillItem.objects.create(
                    bill=bill,
                    test_type=item['test'],
                    test_name=item['test'].name,
                    quantity=item['quantity'],
                    unit_price=item['unit_price'],
                    discount=0
                )
            
            # Link lab records
            if lab_records:
                bill.lab_records.set(lab_records)
            
            # ============================================================
            # 🚀 INTEGRATION WITH FINANCE APP
            # ============================================================
            try:
                from finance.services import JournalService
                
                finance_payment_type = 'CASH' if payment_method in ['CASH', 'ONLINE'] else 'CREDIT'
                
                entry = JournalService.process_bill(
                    source_type='LAB',
                    source_id=bill.bill_number,
                    total_amount=bill.total,
                    revenue_account_code='4200',  # Lab Revenue
                    payment_type=finance_payment_type
                )
                
                bill.journal_entry_id = entry.id
                bill.save(update_fields=['journal_entry_id'])
                
            except Exception as e:
                return Response({
                    'success': False,
                    'error': f'Finance integration failed: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response({
                'success': True,
                'message': 'Lab bill created successfully and pushed to Finance',
                'data': LabBillSerializer(bill).data
            }, status=status.HTTP_201_CREATED)


class LabBillDetailView(APIView):
    """
    GET /api/lab/bills/{id}/ - Get bill details
    DELETE /api/lab/bills/{id}/ - Delete/cancel bill
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Get bill details"""
        if not check_lab_access(request.user) and request.user.role not in ['ADM', 'REC']:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            bill = LabBill.objects.select_related(
                'patient__user', 'created_by'
            ).prefetch_related('items__test_type', 'payments', 'lab_records').get(id=pk)
        except LabBill.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Bill not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = LabBillSerializer(bill)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    def delete(self, request, pk):
        """Cancel bill"""
        if not check_lab_access(request.user) and request.user.role not in ['ADM', 'REC']:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            bill = LabBill.objects.get(id=pk)
        except LabBill.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Bill not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if bill.payment_status == 'PAID':
            return Response({
                'success': False,
                'error': 'Cannot delete a paid bill. Please refund first.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        bill.payment_status = 'CANCELLED'
        bill.save()
        
        return Response({
            'success': True,
            'message': 'Bill cancelled successfully'
        })


class LabPaymentView(APIView):
    """
    POST /api/lab/bills/{id}/pay/ - Record payment
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        """Record payment for a lab bill"""
        if not check_lab_access(request.user) and request.user.role not in ['ADM', 'REC']:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            bill = LabBill.objects.get(id=pk)
        except LabBill.DoesNotExist:
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
        payment = LabPayment.objects.create(
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
                'payment': LabPaymentSerializer(payment).data,
                'bill': {
                    'id': bill.id,
                    'bill_number': bill.bill_number,
                    'payment_status': bill.payment_status,
                    'amount_paid': float(bill.amount_paid),
                    'balance_due': float(bill.balance_due),
                }
            }
        })


class LabBillingDashboardView(APIView):
    """
    GET /api/lab/billing/dashboard/ - Billing dashboard stats
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get billing dashboard statistics"""
        if not check_lab_access(request.user) and request.user.role not in ['ADM', 'REC']:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        start_of_week = today - timedelta(days=today.weekday())
        
        bills = LabBill.objects.all()
        
        # Today
        today_bills = bills.filter(bill_date__date=today)
        today_total = today_bills.aggregate(Sum('total'))['total__sum'] or 0
        today_count = today_bills.count()
        
        # Week
        week_bills = bills.filter(bill_date__date__gte=start_of_week)
        week_total = week_bills.aggregate(Sum('total'))['total__sum'] or 0
        week_count = week_bills.count()
        
        # Month
        month_bills = bills.filter(bill_date__date__gte=start_of_month)
        month_total = month_bills.aggregate(Sum('total'))['total__sum'] or 0
        month_count = month_bills.count()
        
        # Pending
        pending_bills = bills.filter(payment_status='PENDING')
        pending_total = pending_bills.aggregate(Sum('balance_due'))['balance_due__sum'] or 0
        pending_count = pending_bills.count()
        
        # Payment methods breakdown
        payment_breakdown = bills.values('payment_method').annotate(
            count=Count('id'),
            total=Sum('total')
        )
        
        # Test type revenue breakdown
        test_revenue = LabBillItem.objects.filter(
            bill__payment_status__in=['PAID', 'PARTIAL']
        ).values('test_type__name').annotate(
            total_revenue=Sum('total'),
            count=Count('id')
        ).order_by('-total_revenue')[:10]
        
        # Recent bills
        recent_bills = bills.select_related(
            'patient__user'
        ).prefetch_related('items').order_by('-bill_date')[:10]
        
        recent_data = []
        for bill in recent_bills:
            recent_data.append({
                'id': bill.id,
                'bill_number': bill.bill_number,
                'patient_name': bill.patient.user.full_name,
                'total': float(bill.total),
                'payment_status': bill.payment_status,
                'bill_date': bill.bill_date,
                'test_count': bill.items.count(),
            })
        
        return Response({
            'success': True,
            'summary': {
                'today': {
                    'total': float(today_total),
                    'count': today_count,
                },
                'week': {
                    'total': float(week_total),
                    'count': week_count,
                },
                'month': {
                    'total': float(month_total),
                    'count': month_count,
                },
                'pending': {
                    'total': float(pending_total),
                    'count': pending_count,
                },
                'total_bills': bills.count(),
                'total_revenue': bills.aggregate(Sum('total'))['total__sum'] or 0,
                'total_balance': bills.aggregate(Sum('balance_due'))['balance_due__sum'] or 0,
            },
            'payment_methods': list(payment_breakdown),
            'test_revenue_breakdown': list(test_revenue),
            'recent_bills': recent_data
        })


class LabBillByRecordView(APIView):
    """
    GET /api/lab/bills/by-record/{record_id}/ - Get bill for a lab record
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, record_id):
        """Get bill associated with a lab record"""
        if not check_lab_access(request.user) and request.user.role not in ['ADM', 'REC']:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            record = LabRecord.objects.get(id=record_id, is_active=True)
        except LabRecord.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Lab record not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        bills = record.bills.all()
        
        if not bills.exists():
            return Response({
                'success': True,
                'has_bill': False,
                'message': 'No bill associated with this record'
            })
        
        serializer = LabBillListSerializer(bills, many=True)
        
        return Response({
            'success': True,
            'has_bill': True,
            'bills': serializer.data
        })


class LabBillByPatientView(APIView):
    """
    GET /api/lab/bills/patient/{patient_id}/ - Get all bills for a patient
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, patient_id):
        """Get all bills for a specific patient"""
        if not check_lab_access(request.user) and request.user.role not in ['ADM', 'REC']:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from patients.models import PatientProfile
            patient = PatientProfile.objects.get(id=patient_id)
        except PatientProfile.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Patient not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        bills = LabBill.objects.filter(patient=patient).order_by('-bill_date')
        
        serializer = LabBillListSerializer(bills, many=True)
        
        return Response({
            'success': True,
            'patient': {
                'id': patient.id,
                'name': patient.user.full_name,
                'mrn': patient.patient_id,
            },
            'total_bills': bills.count(),
            'total_amount': bills.aggregate(Sum('total'))['total__sum'] or 0,
            'balance_due': bills.aggregate(Sum('balance_due'))['balance_due__sum'] or 0,
            'bills': serializer.data
        })