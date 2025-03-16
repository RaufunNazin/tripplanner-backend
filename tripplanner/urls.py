from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from tripapi.views import DriverViewSet, TripPlanViewSet, plan_trip
from django.conf import settings
from django.conf.urls.static import static

router = DefaultRouter()
router.register(r'drivers', DriverViewSet)
router.register(r'tripplans', TripPlanViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/plan-trip/', plan_trip, name='plan-trip'),
    # path('api/eld-log-image/<int:log_id>/', generate_eld_log_image, name='eld-log-image'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Add static and media URLs for development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)