from background_task import background
import logging
import requests
import os
from decimal import Decimal
from django.utils import timezone # Import timezone

# Import the utility function for blockchain data interaction (placeholder)
from api.blockchain_data_utils import process_new_transactions_for_outcome

logger = logging.getLogger(__name__)

# Make sure this task is defined and imported correctly in api/apps.py ready() method
@background(schedule=60) # Run every 60 seconds
def update_bch_price_task():
    """
    Task to fetch the latest BCH to USD price from an external API (CoinGecko).
    This price is then stored in the BCHRate model in the database.
    """
    from api.models import BCHRate # Import model inside task to avoid circular imports

    logger.info("Attempting to update BCH price...")
    try:
        # Using CoinGecko API for simplicity and no API key needed for basic rate
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin-cash&vs_currencies=usd")
        response.raise_for_status() # Raise an exception for HTTP errors
        data = response.json()
        bch_usd_rate = data.get('bitcoin-cash', {}).get('usd')

        if bch_usd_rate:
            # Save the rate to the BCHRate model in the database
            BCHRate.objects.create(rate=Decimal(str(bch_usd_rate)))
            logger.info(f"BCH to USD rate updated to: {bch_usd_rate} and saved to database.")
            # Also update environment variable for immediate use by other tasks if needed before DB read
            os.environ['LAST_FETCHED_BCH_USD_RATE'] = str(bch_usd_rate)
        else:
            logger.warning("Could not retrieve BCH to USD rate from CoinGecko API.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching BCH price: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in update_bch_price_task: {e}")

# New task for monitoring BCH addresses using the chosen blockchain data service
@background(schedule=30) # Check every 30 seconds
def monitor_bch_addresses_task():
    """
    Task to periodically check all registered BCH addresses (from ScoreOutcome model)
    for new incoming transactions using the chosen blockchain data service (placeholder).
    It delegates the transaction processing to process_new_transactions_for_outcome.
    """
    logger.info("Starting BCH address monitoring task with blockchain data service placeholder...")
    # Import ScoreOutcome model here to avoid potential circular dependency with blockchain_data_utils
    from api.models import ScoreOutcome 

    # Get all prediction outcomes that have a BCH address assigned
    outcomes_to_monitor = ScoreOutcome.objects.filter(bch_address__isnull=False)

    if not outcomes_to_monitor.exists():
        logger.info("No prediction outcomes with BCH addresses to monitor.")
        return

    for outcome in outcomes_to_monitor:
        try:
            # Call the utility function to process transactions for this outcome's address
            process_new_transactions_for_outcome(outcome)
        except Exception as e:
            logger.error(f"Error monitoring address {outcome.bch_address} for outcome {outcome.outcome_id} with blockchain data service: {e}")

    logger.info("BCH address monitoring task completed with blockchain data service placeholder.")

