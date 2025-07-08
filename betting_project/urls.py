from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Ensure 'api' app URLs are correctly included with a namespace
    path('api/', include(('api.urls', 'api'), namespace='api')),
    path('', RedirectView.as_view(url='/api/', permanent=False)),
]