from django.contrib import admin
from .models import BCHRate, Match, ScoreOutcome, RealBetTransaction # Import RealBetTransaction

# Inline for ScoreOutcome to be displayed within the Match admin page
class ScoreOutcomeInline(admin.StackedInline): # Using StackedInline for a more detailed form
    model = ScoreOutcome
    extra = 1 # Number of empty forms to display
    fields = ['score', 'bch_address', 'bet_count', 'outcome_id'] # Make outcome_id read-only
    readonly_fields = ['outcome_id', 'bet_count'] # outcome_id is auto-generated, bet_count updated by tasks

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('team1', 'team2', 'match_date', 'winning_outcome_display', 'match_id')
    list_filter = ('match_date',)
    search_fields = ('team1', 'team2', 'match_id')
    # Add inlines to allow editing ScoreOutcomes directly from the Match admin page
    inlines = [ScoreOutcomeInline]

    def winning_outcome_display(self, obj):
        return obj.winning_outcome.score if obj.winning_outcome else "N/A"
    winning_outcome_display.short_description = 'Winning Score'


@admin.register(BCHRate)
class BCHRateAdmin(admin.ModelAdmin):
    list_display = ('rate', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('rate',)

@admin.register(ScoreOutcome)
class ScoreOutcomeAdmin(admin.ModelAdmin):
    list_display = ('score', 'match_display', 'bch_address', 'bet_count', 'outcome_id')
    list_filter = ('match__team1', 'match__team2') # Filter by related match teams
    search_fields = ('score', 'bch_address', 'outcome_id')
    readonly_fields = ['outcome_id', 'bet_count'] # outcome_id and bet_count are auto-managed

    def match_display(self, obj):
        return f"{obj.match.team1} vs {obj.match.team2}"
    match_display.short_description = 'Match'

@admin.register(RealBetTransaction)
class RealBetTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_hash', 'bch_address', 'amount_satoshi', 'outcome_display', 'timestamp')
    list_filter = ('timestamp', 'outcome__match__team1')
    search_fields = ('transaction_hash', 'bch_address')
    readonly_fields = ('transaction_hash', 'bch_address', 'amount_satoshi', 'outcome', 'timestamp') # All fields are read-only after creation

    def outcome_display(self, obj):
        return f"{obj.outcome.match.team1} vs {obj.outcome.match.team2}: {obj.outcome.score}" if obj.outcome else "N/A"
    outcome_display.short_description = 'Prediction Outcome'
