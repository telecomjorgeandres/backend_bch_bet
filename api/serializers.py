from rest_framework import serializers
from .models import Match, ScoreOutcome

class ScoreOutcomeSerializer(serializers.ModelSerializer):
    # This will use the outcome_id as the key in the JSON, matching your frontend
    # It ensures betting_outcomes is an object, not an array.
    class Meta:
        model = ScoreOutcome
        fields = ['outcome_id', 'score', 'bch_address', 'bet_count']

    def to_representation(self, instance):
        # Customize representation to include outcome_id in the serialized data
        data = super().to_representation(instance)
        # We don't need to do anything special here as outcome_id is already a field
        return data

class MatchSerializer(serializers.ModelSerializer):
    # Use a custom serializer method field to structure outcomes as an object
    betting_outcomes = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = ['match_id', 'team1', 'team2', 'match_date', 'betting_outcomes']

    def get_betting_outcomes(self, obj):
        # Fetch all outcomes related to this match and return them as a dictionary
        # where the key is the outcome_id
        outcomes = obj.outcomes.all()
        return {outcome.outcome_id: ScoreOutcomeSerializer(outcome).data for outcome in outcomes}