# bch_betting_backend/api/views.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView # Import APIView
from django.middleware.csrf import get_token # Import get_token
from .models import Match, ScoreOutcome, BCHRate, RealBetTransaction
from .serializers import MatchSerializer, ScoreOutcomeSerializer, BCHRateSerializer, RealBetTransactionSerializer
import uuid
import os
import logging
from decimal import Decimal
from django.utils import timezone
import requests

logger = logging.getLogger(__name__)

class MatchViewSet(viewsets.ReadOnlyModelViewSet):
    """
    A simple ViewSet for viewing matches and their outcomes.
    """
    queryset = Match.objects.all().order_by('match_date')
    serializer_class = MatchSerializer

    def get_queryset(self):
        # Prefetch related outcomes to avoid N+1 queries
        return super().get_queryset().prefetch_related('outcomes')

class ScoreOutcomeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    A simple ViewSet for viewing score outcomes.
    """
    queryset = ScoreOutcome.objects.all()
    serializer_class = ScoreOutcomeSerializer

class BCHRateViewSet(viewsets.ViewSet):
    """
    A ViewSet for retrieving the latest BCH to USD exchange rate.
    """
    def list(self, request):
        try:
            # Get the latest BCHRate from the database
            latest_rate = BCHRate.objects.latest('timestamp')
            serializer = BCHRateSerializer(latest_rate)
            return Response(serializer.data)
        except BCHRate.DoesNotExist:
            logger.warning("No BCH rate found in the database. Attempting initial fetch...")
            # If no rate is in DB, try to fetch it immediately (blocking)
            # This is a fallback for the very first startup before the task runs
            try:
                response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin-cash&vs_currencies=usd")
                response.raise_for_status()
                data = response.json()
                bch_usd_rate = data.get('bitcoin-cash', {}).get('usd')
                if bch_usd_rate:
                    # Save it to DB for future requests
                    new_rate_obj = BCHRate.objects.create(rate=Decimal(str(bch_usd_rate)))
                    logger.info(f"Initial BCH rate fetched from API: ${bch_usd_rate}")
                    serializer = BCHRateSerializer(new_rate_obj)
                    return Response(serializer.data)
                else:
                    logger.error("Could not retrieve BCH to USD rate from CoinGecko API during initial fetch.")
                    return Response({"error": "BCH rate not available"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching initial BCH price from CoinGecko: {e}")
                return Response({"error": "Failed to fetch BCH rate from external API"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

class RealBetTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    A ViewSet for viewing recorded real bet transactions.
    """
    queryset = RealBetTransaction.objects.all().order_by('-timestamp')
    serializer_class = RealBetTransactionSerializer

class SimulatePredictionView(viewsets.ViewSet):
    """
    API endpoint to simulate a prediction transaction for testing purposes.
    """
    @action(detail=False, methods=['post'])
    def simulate_prediction(self, request):
        match_id = request.data.get('match_id')
        score_outcome_id = request.data.get('score_outcome_id')

        if not match_id or not score_outcome_id:
            return Response({"error": "Match ID and Score Outcome ID are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Find the specific ScoreOutcome
            outcome = ScoreOutcome.objects.get(match__match_id=match_id, outcome_id=score_outcome_id)
        except ScoreOutcome.DoesNotExist:
            return Response({"error": "Match or Score Outcome not found."}, status=status.HTTP_404_NOT_FOUND)

        # --- Simulate a transaction and update the outcome directly ---
        # This simulation logic directly updates the database for demonstration.
        # In a real setup, the `monitor_bch_addresses_task` would detect and process real transactions.

        mock_tx_hash = f"simulated_tx_{uuid.uuid4().hex}"
        mock_bch_address = outcome.bch_address # The address the "payment" is for
        # Increased simulated amount to ensure it's enough for at least one ticket
        mock_amount_satoshi = 500000 # Simulate 0.005 BCH (e.g., if 1 BCH = $200, this is $1)

        current_bch_usd_rate_str = os.getenv('LAST_FETCHED_BCH_USD_RATE', '0.00')
        current_bch_usd_rate = Decimal(current_bch_usd_rate_str)
        ticket_value_usd = Decimal('1.00')
        
        num_tickets = 0
        if current_bch_usd_rate > 0:
            required_bch_per_ticket = ticket_value_usd / current_bch_usd_rate
            if required_bch_per_ticket > 0:
                num_tickets = int(Decimal(mock_amount_satoshi) / Decimal(100_000_000) / required_bch_per_ticket)
            else:
                logger.warning(f"Required BCH per ticket is zero for {outcome.bch_address}. Check BCH/USD rate.")
        else:
            logger.warning(f"BCH/USD rate is zero or not available ({current_bch_usd_rate_str}). Cannot calculate tickets for {outcome.bch_address}.")

        if num_tickets > 0:
            outcome.bet_count += num_tickets
            outcome.save()

            RealBetTransaction.objects.create(
                transaction_hash=mock_tx_hash,
                bch_address=mock_bch_address,
                amount_satoshi=mock_amount_satoshi,
                outcome=outcome,
                timestamp=timezone.now()
            )
            logger.info(f"Simulated {num_tickets} tickets for outcome '{outcome.score}' (Match ID: {outcome.match.match_id}) from TX: {mock_tx_hash}.")
            return Response({"message": "Simulated prediction successfully!", "num_tickets": num_tickets}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Simulated amount too low for one ticket based on current rate."}, status=status.HTTP_400_BAD_REQUEST)

class CSRFTokenView(APIView):
    """
    API endpoint to retrieve the CSRF token for frontend AJAX requests.
    """
    def get(self, request):
        token = get_token(request)
        return Response({'csrfToken': token})

