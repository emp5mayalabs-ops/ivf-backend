# apps/hospital_settings/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.core.exceptions import PermissionDenied
from django.http import Http404
from .models import HospitalSettings
from .serializers import HospitalSettingsSerializer
from .permissions import IsAdminUser, IsAdminOrReadOnly

class HospitalSettingsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing hospital settings.
    Full access only for admin users.
    """
    queryset = HospitalSettings.objects.all()
    serializer_class = HospitalSettingsSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ['get', 'put', 'patch', 'head', 'options']
    
    def get_queryset(self):
        # Only return the singleton settings
        return HospitalSettings.objects.filter(id=1)
    
    def get_object(self):
        """Always return the singleton settings instance"""
        return HospitalSettings.get_settings()
    
    def list(self, request, *args, **kwargs):
        """Get current hospital settings"""
        settings = self.get_object()
        serializer = self.get_serializer(settings, context={'request': request})
        return Response(serializer.data)
    
    def retrieve(self, request, *args, **kwargs):
        """Get settings by ID (only id=1 exists)"""
        if kwargs.get('pk') != '1':
            raise Http404("Settings not found")
        settings = self.get_object()
        serializer = self.get_serializer(settings, context={'request': request})
        return Response(serializer.data)
    
    def update(self, request, *args, **kwargs):
        """Full update of settings"""
        if request.user.role != 'ADM':
            raise PermissionDenied("Only administrators can update settings")
        
        settings = self.get_object()
        serializer = self.get_serializer(
            settings, 
            data=request.data, 
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
    
    def partial_update(self, request, *args, **kwargs):
        """Partial update of settings"""
        if request.user.role != 'ADM':
            raise PermissionDenied("Only administrators can update settings")
        
        settings = self.get_object()
        serializer = self.get_serializer(
            settings, 
            data=request.data, 
            context={'request': request},
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
    
    def perform_update(self, serializer):
        """Save with updated_by field"""
        if hasattr(self.request.user, 'role') and self.request.user.role == 'ADM':
            serializer.save(updated_by=self.request.user)
        else:
            serializer.save()
    
    @action(detail=False, methods=['post'], url_path='upload-logo')
    def upload_logo(self, request):
        """Upload hospital logo"""
        if request.user.role != 'ADM':
            raise PermissionDenied("Only administrators can upload logos")
        
        if 'logo' not in request.FILES:
            return Response(
                {'error': 'No logo file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        settings = self.get_object()
        settings.logo = request.FILES['logo']
        settings.updated_by = request.user
        settings.save()
        
        serializer = self.get_serializer(settings, context={'request': request})
        return Response({
            'success': True,
            'message': 'Logo uploaded successfully',
            'data': serializer.data
        })
    
    @action(detail=False, methods=['post'], url_path='upload-logo-light')
    def upload_logo_light(self, request):
        """Upload light version of logo"""
        if request.user.role != 'ADM':
            raise PermissionDenied("Only administrators can upload logos")
        
        if 'logo_light' not in request.FILES:
            return Response(
                {'error': 'No logo file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        settings = self.get_object()
        settings.logo_light = request.FILES['logo_light']
        settings.updated_by = request.user
        settings.save()
        
        serializer = self.get_serializer(settings, context={'request': request})
        return Response({
            'success': True,
            'message': 'Light logo uploaded successfully',
            'data': serializer.data
        })
    
    @action(detail=False, methods=['post'], url_path='upload-favicon')
    def upload_favicon(self, request):
        """Upload favicon"""
        if request.user.role != 'ADM':
            raise PermissionDenied("Only administrators can upload favicons")
        
        if 'favicon' not in request.FILES:
            return Response(
                {'error': 'No favicon file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        settings = self.get_object()
        settings.favicon = request.FILES['favicon']
        settings.updated_by = request.user
        settings.save()
        
        serializer = self.get_serializer(settings, context={'request': request})
        return Response({
            'success': True,
            'message': 'Favicon uploaded successfully',
            'data': serializer.data
        })
    
    @action(detail=False, methods=['delete'], url_path='remove-logo')
    def remove_logo(self, request):
        """Remove hospital logo"""
        if request.user.role != 'ADM':
            raise PermissionDenied("Only administrators can remove logos")
        
        settings = self.get_object()
        if settings.logo:
            settings.logo.delete(save=False)
            settings.logo = None
            settings.updated_by = request.user
            settings.save()
        
        serializer = self.get_serializer(settings, context={'request': request})
        return Response({
            'success': True,
            'message': 'Logo removed successfully',
            'data': serializer.data
        })
    
    @action(detail=False, methods=['delete'], url_path='remove-logo-light')
    def remove_logo_light(self, request):
        """Remove light logo"""
        if request.user.role != 'ADM':
            raise PermissionDenied("Only administrators can remove logos")
        
        settings = self.get_object()
        if settings.logo_light:
            settings.logo_light.delete(save=False)
            settings.logo_light = None
            settings.updated_by = request.user
            settings.save()
        
        serializer = self.get_serializer(settings, context={'request': request})
        return Response({
            'success': True,
            'message': 'Light logo removed successfully',
            'data': serializer.data
        })
    
    @action(detail=False, methods=['delete'], url_path='remove-favicon')
    def remove_favicon(self, request):
        """Remove favicon"""
        if request.user.role != 'ADM':
            raise PermissionDenied("Only administrators can remove favicons")
        
        settings = self.get_object()
        if settings.favicon:
            settings.favicon.delete(save=False)
            settings.favicon = None
            settings.updated_by = request.user
            settings.save()
        
        serializer = self.get_serializer(settings, context={'request': request})
        return Response({
            'success': True,
            'message': 'Favicon removed successfully',
            'data': serializer.data
        })
    
    @action(detail=False, methods=['get'], url_path='public')
    def public_settings(self, request):
        """
        Public settings endpoint (no authentication required)
        Returns only non-sensitive information
        """
        settings = self.get_object()
        data = {
            'hospital_name': settings.hospital_name,
            'hospital_short_name': settings.hospital_short_name,
            'hospital_tagline': settings.hospital_tagline,
            'logo_url': settings.get_logo_url(request),
            'logo_light_url': settings.get_logo_light_url(request),
            'favicon_url': settings.get_favicon_url(request),
            'primary_color': settings.primary_color,
            'primary_color_dark': settings.primary_color_dark,
            'secondary_color': settings.secondary_color,
            'accent_color': settings.accent_color,
            'phone': settings.phone,
            'phone_secondary': settings.phone_secondary,
            'email': settings.email,
            'address': settings.get_full_address(),
            'website': settings.website,
            'facebook_url': settings.facebook_url,
            'twitter_url': settings.twitter_url,
            'instagram_url': settings.instagram_url,
            'youtube_url': settings.youtube_url,
            'linkedin_url': settings.linkedin_url,
            'footer_text': settings.footer_text,
            'footer_links': settings.footer_links,
            'business_hours': settings.business_hours,
        }
        return Response(data)