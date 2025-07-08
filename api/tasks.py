from background_task import background
from api.views import betting_system # Import the global instance of your BCHBettingSystem

@background(schedule=60) # Schedule this task to run every 60 seconds
def update_bch_price_task():
    """
    Background task to periodically update the BCH to USD exchange rate.
    This calls the update_bch_usd_rate method on the global betting_system instance.
    """
    print("Running background task: update_bch_price_task...")
    success = betting_system.update_bch_usd_rate()
    if success:
        print(f"BCH price updated successfully by background task to ${betting_system.get_bch_usd_rate()}")
    else:
        print("Failed to update BCH price via background task.")