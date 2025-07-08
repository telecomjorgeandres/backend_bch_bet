from django.urls import path
from rest_framework.reverse import reverse
from . import views

urlpatterns = [
    path('', views.api_root, name='api-root'),
    # --- CHANGE THIS LINE TO USE A HYPHEN ---
    path('bch-rate/', views.get_bch_rate, name='bch-rate'), # Changed to hyphen
    # --- END CHANGE ---
    path('simulate_bet/', views.simulate_bet, name='simulate_bet'),
    path('matches/', views.get_matches, name='match-list'),
]