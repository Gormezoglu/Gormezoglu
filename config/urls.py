from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('contracts.urls')),
    path('parties/', include('parties.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
