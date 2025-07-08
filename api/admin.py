from django.contrib import admin
from .models import Match, ScoreOutcome

class ScoreOutcomeInline(admin.TabularInline):
    model = ScoreOutcome
    extra = 3 # Show 3 empty forms for adding outcomes immediately
    fields = ('score', 'bch_address', 'bet_count')
    readonly_fields = ('bet_count',) # Bet count should be updated by the system, not manually

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('team1', 'team2', 'match_date', 'display_outcome_count')
    list_filter = ('match_date',)
    search_fields = ('team1', 'team2')
    inlines = [ScoreOutcomeInline]

    def display_outcome_count(self, obj):
        return obj.outcomes.count()
    display_outcome_count.short_description = "Outcomes"