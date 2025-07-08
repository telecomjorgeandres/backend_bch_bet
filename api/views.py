from django.http import JsonResponse # Keep for now if other parts of your app use it, though DRF's Response is preferred for API views
from rest_framework.decorators import api_view
from rest_framework.response import Response # Import Response from DRF for API views
from rest_framework.reverse import reverse
from rest_framework import status
import json
import uuid
import random
from decimal import Decimal
from datetime import date, datetime, timezone # Import date, datetime, and timezone for filtering

# Ensure these imports are correct
from .bch_betting import BCHBettingSystem
from .models import BCHRate, Match # <-- IMPORTANT: Import the Match model
from .serializers import MatchSerializer # <-- IMPORTANT: Import your MatchSerializer

# Initialize the betting system globally
betting_system = BCHBettingSystem()

# --- API Root View ---
@api_view(['GET'])
def api_root(request, format=None):
    """
    The root of the API, providing links to available endpoints.
    """
    return Response({ # Changed to Response
        'bch_rate': reverse('api:bch_rate', request=request, format=format),
        'simulate_bet': reverse('api:simulate_bet', request=request, format=format),
        'matches': reverse('api:match-list', request=request, format=format),
    })


# --- MODIFIED View for Matches (fetches from database) ---
@api_view(['GET'])
def get_matches(request):
    """
    API endpoint to get a list of all current matches with their details from the database.
    Filters for matches on July 12, 2025.
    """
    # Define the target date.
    # Note: If your match_date in the database is timezone-aware and stores UTC,
    # and your server's timezone (TIME_ZONE in settings.py) is different,
    # direct comparison with `date(2025, 7, 12)` might behave differently
    # depending on the database backend. `__date` lookup is generally robust.
    target_date = date(2025, 7, 12)

    # Fetch matches from the database that are on the target date
    # .prefetch_related('outcomes') is good practice to avoid N+1 queries when
    # serializing related ScoreOutcome objects.
    matches = Match.objects.filter(match_date__date=target_date).prefetch_related('outcomes').order_by('match_date')

    # Serialize the queryset using your MatchSerializer
    # `many=True` is crucial when serializing a list (queryset) of objects
    serializer = MatchSerializer(matches, many=True)
    
    # Return the serialized data using DRF's Response
    return Response({'matches': serializer.data})


# --- Existing get_bch_rate function (updated to use Response) ---
@api_view(['GET'])
def get_bch_rate(request):
    """
    API endpoint to get the current BCH to USD exchange rate.
    This will read the latest rate from the database.
    """
    # Assuming betting_system.get_bch_usd_rate() is configured to read from BCHRate model
    rate = betting_system.get_bch_usd_rate()
    if rate is not None:
        return Response({'bch_usd_rate': str(rate)}) # Changed to Response
    else:
        return Response({'error': 'BCH rate not available'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) # Changed to Response

# --- Existing simulate_bet function (updated to use Response) ---
@api_view(['POST'])
def simulate_bet(request):
    """
    Simulates a deposit and returns the required BCH amount for a given USD value.
    This will use the CURRENT rate from the database.
    """
    try:
        match_id = request.data.get('match_id')
        score_outcome_id = request.data.get('score_outcome_id')

        if not all([match_id, score_outcome_id]):
            return Response({"error": "Missing match_id or score_outcome_id"}, status=status.HTTP_400_BAD_REQUEST) # Changed to Response

        # The update_bch_usd_rate and simulate_deposit calls within betting_system
        # need to be updated to interact with the database models directly
        # if they aren't already.
        
        # For BCH rate, ensure betting_system.get_bch_usd_rate() reads from BCHRate model.
        # For simulate_deposit, ensure it updates the bet_count in the ScoreOutcome model.
        
        betting_system.update_bch_usd_rate() # Trigger an update before calculation
        current_bch_rate = betting_system.get_bch_usd_rate()

        if current_bch_rate is None or current_bch_rate <= 0:
            return Response({'error': 'BCH exchange rate not available or invalid'}, status=status.HTTP_503_SERVICE_UNAVAILABLE) # Changed to Response

        random_num_tickets = Decimal(str(random.randint(1, 5)))
        # Assuming betting_system.ticket_value_usd is defined correctly (e.g., as a Decimal)
        required_bch_for_ticket = betting_system.ticket_value_usd / current_bch_rate
        simulated_bch_amount = (required_bch_for_ticket * random_num_tickets).quantize(Decimal('0.00000001'))

        success = betting_system.simulate_deposit(
            match_id, score_outcome_id, "bchtest:simulateduser" + str(uuid.uuid4().hex[:10]), simulated_bch_amount
        )

        if success:
            return Response({ # Changed to Response
                "message": f"Simulated bet successful for {simulated_bch_amount:.8f} BCH ({random_num_tickets} ticket(s))",
                "simulated_bch_amount": str(simulated_bch_amount),
                "num_tickets_placed": str(random_num_tickets),
                "match_id": match_id,
                "score_outcome_id": score_outcome_id
            }, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Failed to simulate bet (check server logs for details)."}, status=status.HTTP_400_BAD_REQUEST) # Changed to Response
    except Exception as e:
        print(f"Error in simulate_bet view: {e}")
        return Response({'error': f'An unexpected error occurred: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) # Changed to Response