from rest_framework import serializers
from .models import Match, ScoreOutcome, BCHRate, RealBetTransaction

class ScoreOutcomeSerializer(serializers.ModelSerializer):
    # This will ensure the UUID is returned as a string rather than a UUID object
    outcome_id = serializers.CharField(read_only=True)
    class Meta:
        model = ScoreOutcome
        fields = ['outcome_id', 'score', 'bch_address', 'bet_count']

class MatchSerializer(serializers.ModelSerializer):
    # This will ensure the UUID is returned as a string rather than a UUID object
    match_id = serializers.CharField(read_only=True)
    # Use a SerializerMethodField to get outcomes as a dictionary
    betting_outcomes = serializers.SerializerMethodField()

    class Meta:
        model = Match
        # Add team1_logo_url and team2_logo_url to the fields
        fields = ['match_id', 'team1', 'team2', 'match_date', 'betting_outcomes', 'winning_outcome', 'team1_logo_url', 'team2_logo_url']

    def get_betting_outcomes(self, obj):
        # Returns a dictionary where keys are outcome_id and values are serialized outcomes
        outcomes = obj.outcomes.all()
        return {outcome.outcome_id: ScoreOutcomeSerializer(outcome).data for outcome in outcomes}

class BCHRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BCHRate
        fields = ['rate', 'timestamp']

class RealBetTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RealBetTransaction
        fields = '__all__' # Include all fields for this serializer
