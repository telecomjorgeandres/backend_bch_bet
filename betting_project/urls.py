from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import MatchViewSet, ScoreOutcomeViewSet, BCHRateViewSet, RealBetTransactionViewSet, SimulatePredictionView, CSRFTokenView # Import CSRFTokenView

router = DefaultRouter()
router.register(r'matches', MatchViewSet)
router.register(r'outcomes', ScoreOutcomeViewSet)
router.register(r'bch-rate', BCHRateViewSet, basename='bch-rate') # basename is required for ViewSets without a queryset
router.register(r'transactions', RealBetTransactionViewSet, basename='transactions') # New endpoint

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/simulate-prediction/', SimulatePredictionView.as_view({'post': 'simulate_prediction'}), name='simulate-prediction'),
    path('api/csrf-token/', CSRFTokenView.as_view(), name='csrf-token'), # New CSRF token endpoint
]
