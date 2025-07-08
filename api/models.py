# betting_app/models.py

from django.db import models
import uuid # Required for generating unique IDs for matches and outcomes

# Model to store the current BCH to USD exchange rate
class BCHRate(models.Model):
    rate = models.DecimalField(max_digits=10, decimal_places=4)
    timestamp = models.DateTimeField(auto_now=True) # Automatically updates on save

    def __str__(self):
        return f"BCH/USD: {self.rate} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

    class Meta:
        verbose_name = "BCH Rate"
        verbose_name_plural = "BCH Rates"
        # Optional: Ensure only one active rate by ordering by timestamp
        # This is useful if you retrieve the "latest" rate.
        get_latest_by = 'timestamp'


# Model to represent a single sports match
class Match(models.Model):
    # Use CharField with UUID default for a clean, external-facing ID
    match_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4, editable=False)
    team1 = models.CharField(max_length=100)
    team2 = models.CharField(max_length=100)
    match_date = models.DateTimeField() # Stores both date and time

    def __str__(self):
        # Human-readable representation for the admin and debugging
        return f"{self.team1} vs {self.team2} on {self.match_date.strftime('%Y-%m-%d %H:%M')}"


# Model to represent a specific betting outcome (e.g., a score) for a match
class ScoreOutcome(models.Model):
    # Unique ID for each specific betting outcome
    outcome_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4, editable=False)
    
    # Foreign key link to the Match model:
    # - `related_name='outcomes'` allows you to access `match.outcomes.all()`
    # - `on_delete=models.CASCADE` means if a Match is deleted, its Outcomes are also deleted
    match = models.ForeignKey(Match, related_name='outcomes', on_delete=models.CASCADE)
    
    score = models.CharField(max_length=20) # e.g., "1-0", "Any Other Score" - increased max_length to 20 for flexibility
    bch_address = models.CharField(max_length=255, blank=True, null=True) # Bitcoin Cash receiving address for this outcome
    bet_count = models.IntegerField(default=0) # Counter for how many bets have been placed on this outcome

    def __str__(self):
        # Human-readable representation
        return f"{self.match.team1} vs {self.match.team2}: {self.score}"

    class Meta:
        # Ensures that for a given match, each score outcome is unique.
        # e.g., you can't have two "1-0" outcomes for the same match.
        unique_together = ('match', 'score')