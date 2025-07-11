from django.contrib import admin
from django.urls import path, include # Ensure 'include' is imported

urlpatterns = [
    path('admin/', admin.site.urls),
    # This line tells Django to look for URLs starting with 'api/'
    # inside the 'api.urls' module (i.e., bch_betting_backend/api/urls.py)
    path('api/', include('api.urls')),
]