from django.db import models
import uuid # Required for generating unique IDs for matches and outcomes
from django.utils import timezone # Required for timestamp in RealBetTransaction

# Model to store the current BCH to USD exchange rate
class BCHRate(models.Model):
    rate = models.DecimalField(max_digits=10, decimal_places=4)
    timestamp = models.DateTimeField(auto_now=True) # Automatically updates on save

    def __str__(self):
        return f"BCH/USD: {self.rate} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

    class Meta:
        verbose_name = "BCH Rate"
        verbose_name_plural = "BCH Rates"
        get_latest_by = 'timestamp'


# Model to represent a single sports match
class Match(models.Model):
    # Use CharField with UUID default for a clean, external-facing ID
    match_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4, editable=False)
    team1 = models.CharField(max_length=100)
    team2 = models.CharField(max_length=100)
    match_date = models.DateTimeField() # Stores both date and time
    # New field: Link to the winning outcome once the match is resolved (for simulated payouts)
    winning_outcome = models.ForeignKey('ScoreOutcome', on_delete=models.SET_NULL, null=True, blank=True, related_name='won_matches')

    def __str__(self):
        # Human-readable representation for the admin and debugging
        return f"{self.team1} vs {self.team2} on {self.match_date.strftime('%Y-%m-%d %H:%M')}"


# Model to represent a specific prediction outcome (e.g., a score) for a match
class ScoreOutcome(models.Model):
    # Unique ID for each specific prediction outcome
    outcome_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4, editable=False)
    
    # Foreign key link to the Match model:
    # - `related_name='outcomes'` allows you to access `match.outcomes.all()`
    # - `on_delete=models.CASCADE` means if a Match is deleted, its Outcomes are also deleted
    match = models.ForeignKey(Match, related_name='outcomes', on_delete=models.CASCADE)
    
    score = models.CharField(max_length=20) # e.g., "1-0", "Any Other Score" - increased max_length to 20 for flexibility
    # Bitcoin Cash receiving address for this outcome. Made unique for monitoring.
    bch_address = models.CharField(max_length=255, unique=True, blank=True, null=True)
    bet_count = models.IntegerField(default=0) # Counter for how many prediction entries have been made on this outcome
    # New field: To track the hash of the last processed transaction for monitoring
    last_monitored_tx_hash = models.CharField(max_length=64, null=True, blank=True)

    def __str__(self):
        # Human-readable representation
        return f"{self.match.team1} vs {self.match.team2}: {self.score}"

    class Meta:
        # Ensures that for a given match, each score outcome is unique.
        # e.g., you can't have two "1-0" outcomes for the same match.
        unique_together = ('match', 'score')


class RealBetTransaction(models.Model):
    """
    Model to record actual BCH transactions detected by the monitoring system.
    This prevents double-counting and provides an audit trail.
    """
    transaction_hash = models.CharField(max_length=64, unique=True)
    bch_address = models.CharField(max_length=50) # The address that received the payment
    amount_satoshi = models.BigIntegerField()
    # Link to the specific ScoreOutcome this transaction contributed to
    outcome = models.ForeignKey(ScoreOutcome, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    # You might add a 'user' field here if you implement authentication

    def __str__(self):
        return f"TX: {self.transaction_hash[:8]}... to {self.bch_address[:10]}... Amount: {self.amount_satoshi} satoshis"

