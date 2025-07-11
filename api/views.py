from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action # For custom actions on ViewSets
from .models import Match, ScoreOutcome, BCHRate, RealBetTransaction
from .serializers import MatchSerializer, ScoreOutcomeSerializer, BCHRateSerializer, RealBetTransactionSerializer
import os
from decimal import Decimal
import uuid
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class MatchViewSet(viewsets.ModelViewSet):
    """
    A ViewSet for viewing and editing Match instances.
    """
    queryset = Match.objects.all().prefetch_related('outcomes')
    serializer_class = MatchSerializer
    # You might want to add permission classes later, e.g., permissions.IsAdminUser for write operations

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({"matches": serializer.data}) # Return as {"matches": [...]}

class ScoreOutcomeViewSet(viewsets.ModelViewSet):
    """
    A ViewSet for viewing and editing ScoreOutcome instances.
    """
    queryset = ScoreOutcome.objects.all()
    serializer_class = ScoreOutcomeSerializer
    # You might want to add permission classes later

class BCHRateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    A ReadOnly ViewSet for viewing the current BCH to USD exchange rate.
    """
    queryset = BCHRate.objects.all().order_by('-timestamp')
    serializer_class = BCHRateSerializer

    def list(self, request, *args, **kwargs):
        latest_rate = self.get_queryset().first()
        if latest_rate:
            serializer = self.get_serializer(latest_rate)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response({"error": "BCH rate not available. Please wait for the background task to fetch it."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

class RealBetTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    A ReadOnly ViewSet for viewing RealBetTransaction instances.
    """
    queryset = RealBetTransaction.objects.all().order_by('-timestamp')
    serializer_class = RealBetTransactionSerializer
    # You might want to add permission classes later to restrict access

class SimulatePredictionView(viewsets.ViewSet):
    """
    A ViewSet for simulating prediction entries.
    This is a custom ViewSet because it doesn't directly map to a model's CRUD operations.
    """
    @action(detail=False, methods=['post'])
    def simulate_prediction(self, request):
        match_id = request.data.get('match_id')
        score_outcome_id = request.data.get('score_outcome_id')

        if not match_id or not score_outcome_id:
            return Response({"error": "Both match_id and score_outcome_id are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            match = Match.objects.get(match_id=match_id)
            score_outcome = ScoreOutcome.objects.get(outcome_id=score_outcome_id, match=match)
        except Match.DoesNotExist:
            return Response({"error": "Match not found."}, status=status.HTTP_404_NOT_FOUND)
        except ScoreOutcome.DoesNotExist:
            return Response({"error": "Score outcome not found for the given match."}, status=status.HTTP_404_NOT_FOUND)

        # Simulate the transaction details
        simulated_tx_hash = str(uuid.uuid4()).replace('-', '') # Generate a unique hash
        
        # Get the current BCH/USD rate from environment variable (set by background task)
        current_bch_usd_rate_str = os.getenv('LAST_FETCHED_BCH_USD_RATE', '0.00')
        current_bch_usd_rate = Decimal(current_bch_usd_rate_str)
        
        ticket_value_usd = Decimal('1.00') # Fixed value for one prediction entry

        simulated_amount_satoshi = 0
        num_tickets = 0

        if current_bch_usd_rate > 0:
            # Calculate the BCH amount equivalent to 1 USD
            required_bch_per_ticket = ticket_value_usd / current_bch_usd_rate
            # Simulate sending exactly one ticket's worth of BCH in satoshis
            simulated_amount_satoshi = int(required_bch_per_ticket * Decimal(100_000_000))
            num_tickets = 1 # We are simulating one ticket per call for simplicity
        else:
            logger.warning("BCH/USD rate is zero or not available. Cannot simulate amount.")
            return Response({"error": "BCH rate not available for simulation."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Increment the bet_count for the chosen outcome
        score_outcome.bet_count += num_tickets
        score_outcome.save()

        # Create a RealBetTransaction record for the simulated transaction
        RealBetTransaction.objects.create(
            transaction_hash=simulated_tx_hash,
            bch_address=score_outcome.bch_address, # Use the outcome's address
            amount_satoshi=simulated_amount_satoshi,
            outcome=score_outcome,
            timestamp=timezone.now()
        )
        logger.info(f"Simulated {num_tickets} prediction entry for outcome '{score_outcome.score}' (Match ID: {match_id}). TX: {simulated_tx_hash}")

        return Response({
            "message": "Prediction simulated successfully!",
            "match_id": match_id,
            "score_outcome_id": score_outcome_id,
            "simulated_tx_hash": simulated_tx_hash,
            "num_tickets": num_tickets,
            "simulated_amount_satoshi": simulated_amount_satoshi
        }, status=status.HTTP_200_OK)

