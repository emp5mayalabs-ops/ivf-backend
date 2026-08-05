from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import login, logout
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import get_object_or_404

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
)
from .models import (
    LabTechnicianProfile,
    AndrologyLabTechnician,
    LabTestType,
    LabField,
    LabRecord
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
        # Check lab role
        if not check_lab_access(request.user):
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Update login audit log
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
        """Get current lab profile"""
        user = request.user
        
        # Check lab role
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
        """Update current lab profile"""
        user = request.user
        
        # Check lab role
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
        
        # Handle password change
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
        
        # Update profile
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
        """Delete/Deactivate current lab profile"""
        user = request.user
        
        # Check lab role
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
        
        # Soft delete - deactivate user and profile
        user.is_active = False
        user.save()
        lab_profile.is_active = False
        lab_profile.save()
        
        # Logout the user
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
        """Get lab profile by ID (for admin/head)"""
        # Only admins or head can view other profiles
        if request.user.role not in ['ADM']:
            # Allow viewing own profile through the main endpoint
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
        """Delete lab profile by ID (Admin only)"""
        # Only admins can delete other profiles
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
        
        # Soft delete
        user.is_active = False
        user.save()
        lab_profile.is_active = False
        lab_profile.save()
        
        return Response({
            'success': True,
            'message': f'User {user.full_name} deactivated successfully'
        }, status=status.HTTP_200_OK)


# ========== NEW DYNAMIC LAB TESTS VIEWS ==========

# lab/views.py - UPDATED LabTestTypeListView

class LabTestTypeListView(APIView):
    """
    GET /api/lab/test-types/ - List all test types (full details)
    GET /api/lab/test-types/?simple=true - List test types (lightweight, for dropdowns)
    GET /api/lab/test-types/?search=lipid - Search test types
    POST /api/lab/test-types/ - Create new test type
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all active test types"""
        test_types = LabTestType.objects.filter(is_active=True)
        
        # Filter by search
        search = request.query_params.get('search')
        if search:
            test_types = test_types.filter(
                Q(name__icontains=search) | 
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        # ========== 🆕 CHECK FOR SIMPLE RESPONSE ==========
        simple = request.query_params.get('simple', '').lower() == 'true'
        
        if simple:
            # Lightweight response for dropdowns (receptionist, doctor, etc.)
            data = [{
                'id': test.id,
                'name': test.name,
                'code': test.code,
                'icon': test.icon,
                'color': test.color,
                'description': test.description,
            } for test in test_types]
            return Response({
                'success': True,
                'count': test_types.count(),
                'test_types': data
            }, status=status.HTTP_200_OK)
        
        # Full response with fields (for admin/lab management)
        serializer = LabTestTypeSerializer(test_types, many=True)
        return Response({
            'success': True,
            'count': test_types.count(),
            'test_types': serializer.data
        }, status=status.HTTP_200_OK)
    
    def post(self, request):
        """Create new test type"""
        # Check if user has permission (Admin or Lab Head)
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
        """Get test type details with fields"""
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
        """Update test type"""
        # Check permission
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
        """Delete test type (soft delete)"""
        # Check permission
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


class LabRecordListView(APIView):
    """
    GET /api/lab/records/ - List all lab records
    POST /api/lab/records/ - Create new lab record
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get lab records with filters"""
        # Check lab access
        if not check_lab_access(request.user) and request.user.role != 'ADM':
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        records = LabRecord.objects.filter(is_active=True)
        
        # Filter by test type
        test_type = request.query_params.get('test_type')
        if test_type:
            records = records.filter(test_type_id=test_type)
        
        # Filter by patient
        patient = request.query_params.get('patient')
        if patient:
            records = records.filter(patient_id=patient)
        
        # Filter by date range
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            records = records.filter(test_date__gte=date_from)
        if date_to:
            records = records.filter(test_date__lte=date_to)
        
        # Filter by status
        status_filter = request.query_params.get('status')
        if status_filter:
            records = records.filter(status=status_filter)
        
        # Search
        search = request.query_params.get('search')
        if search:
            records = records.filter(
                Q(patient__full_name__icontains=search) |
                Q(test_type__name__icontains=search) |
                Q(notes__icontains=search)
            )
        
        # Ordering
        ordering = request.query_params.get('ordering', '-test_date')
        records = records.order_by(ordering)
        
        # Pagination
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
        """Create new lab record"""
        # Check lab access
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
        """Get record details"""
        # Check lab access
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
        """Update record"""
        # Check lab access
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
        """Delete record (soft delete)"""
        # Check lab access
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
        """Get all records for a specific patient"""
        # Check lab access
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
        """Get lab statistics"""
        # Check lab access
        if not check_lab_access(request.user) and request.user.role != 'ADM':
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        total_records = LabRecord.objects.filter(is_active=True).count()
        total_test_types = LabTestType.objects.filter(is_active=True).count()
        
        # Records by status
        records_by_status = {}
        for status_choice in LabRecord.STATUS_CHOICES:
            status_code = status_choice[0]
            count = LabRecord.objects.filter(status=status_code, is_active=True).count()
            if count > 0:
                records_by_status[status_code] = count
        
        # Records by test type
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
        
        # Recent records
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
        # Allow doctors AND receptionists
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
        
        # ========== 🆕 FIND PATIENT: PatientProfile ID first, then User ID ==========
        patient = None
        patient_name = None
        
        # 1️⃣ FIRST: try as PatientProfile ID
        try:
            from patients.models import PatientProfile
            patient_profile = PatientProfile.objects.get(id=patient_id)
            patient = patient_profile.user
            patient_name = patient_profile.user.full_name
            print(f"✅ Found patient via PatientProfile ID: {patient_id} → {patient_name}")
        except PatientProfile.DoesNotExist:
            # 2️⃣ SECOND: try as User ID
            try:
                patient = User.objects.get(id=patient_id)
                patient_name = patient.full_name
                print(f"✅ Found patient via User ID: {patient_id} → {patient_name}")
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': f'Patient not found with ID: {patient_id}'
                }, status=status.HTTP_404_NOT_FOUND)
        
        # Get test type
        try:
            test_type = LabTestType.objects.get(id=test_type_id, is_active=True)
        except LabTestType.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Test type not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Create lab record with ORDERED status (token auto‑generated)
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
        
        # Return response WITH token_number and correct patient name
        return Response({
            'success': True,
            'message': 'Lab test ordered successfully',
            'order': {
                'id': lab_record.id,
                'token_number': lab_record.token_number,
                'test_name': test_type.name,
                'test_code': test_type.code,
                'patient_name': patient.full_name,  # ✅ Correct patient name
                'patient_id': patient.id,           # ✅ User ID
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
        # Allowed roles: lab techs, admin, doctors, receptionists
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
        
        # If doctor, only show orders for their patients
        if request.user.role in ['END', 'GYN', 'ANE']:
            from patients.models import PatientProfile
            doctor_patients = PatientProfile.objects.filter(
                op_tickets__assigned_doctor=request.user
            ).values_list('user_id', flat=True)
            orders = orders.filter(patient_id__in=doctor_patients)
        
        # Receptionists see all orders (no restriction)
        
        # Apply filters
        if patient_id:
            orders = orders.filter(patient_id=patient_id)
        if status_filter:
            orders = orders.filter(status=status_filter)
        if test_type_id:
            orders = orders.filter(test_type_id=test_type_id)
        if priority_filter:
            orders = orders.filter(priority=priority_filter)
        
        orders = orders.order_by('-created_at')
        
        # Serialize (LabOrderListSerializer includes token_number)
        serializer = LabOrderListSerializer(orders, many=True)
        
        # Get counts for statistics
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
        """Get order details"""
        try:
            order = LabRecord.objects.get(id=order_id, is_active=True)
        except LabRecord.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Order not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check access
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
        
        # Get all fields for this test type
        fields = order.test_type.fields.filter(is_active=True).order_by('display_order')
        
        # Build field values with metadata
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
                'token_number': order.token_number,  # 🆕 token included
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
        """Update with results - Lab only"""
        # Only lab technicians can update results
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
        
        # Check if order can be updated
        if order.status in ['COMPLETED', 'CANCELLED']:
            return Response({
                'success': False,
                'error': f'Cannot update order in {order.status} status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update with results
        field_values = request.data.get('field_values', {})
        notes = request.data.get('notes')
        status_update = request.data.get('status', 'COMPLETED')
        
        # Merge field values
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
        
        # If completed, update test_date
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
        """Cancel a lab order"""
        try:
            order = LabRecord.objects.get(id=order_id, is_active=True)
        except LabRecord.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Order not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # ========== CHECK PERMISSIONS ==========
        user_role = request.user.role
        
        # Case 1: Doctors can cancel their own orders
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
        
        # 🆕 Case 2: Receptionists can cancel any order
        elif user_role == 'REC':
            # Receptionists have full permission to cancel any order
            pass
        
        # Case 3: Lab staff and admins can cancel any order
        elif user_role in ['TEC', 'AND', 'EMB', 'ADM']:
            # Lab staff and admins can cancel any order
            pass
        
        # Case 4: All other roles are denied
        else:
            return Response({
                'success': False,
                'error': 'Access denied. You do not have permission to cancel orders.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # ========== CHECK ORDER STATUS ==========
        if order.status in ['COMPLETED', 'CANCELLED']:
            return Response({
                'success': False,
                'error': f'Cannot cancel order in "{order.get_status_display()}" status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ========== CANCEL THE ORDER ==========
        order.status = 'CANCELLED'
        order.updated_by = request.user
        order.save()
        
        return Response({
            'success': True,
            'message': 'Order cancelled successfully',
            'order': {
                'id': order.id,
                'token_number': order.token_number,  # 🆕 Include token for reference
                'status': order.status,
                'status_display': order.get_status_display(),
                'cancelled_by': request.user.full_name,
                'cancelled_at': order.updated_at
            }
        })