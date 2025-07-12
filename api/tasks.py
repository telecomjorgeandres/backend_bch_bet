# bch_betting_backend/api/tasks.py
from background_task import background
import logging
import requests
import os
from decimal import Decimal
from django.utils import timezone # Import timezone

# Import the utility function for Blockchair interaction
from api.blockchair_utils import process_new_transactions_blockchair # Changed import to blockchair_utils

logger = logging.getLogger(__name__)

# Make sure this task is defined and imported correctly in api/apps.py ready() method
@background(schedule=60) # Run every 60 seconds
def update_bch_price_task():
    """
    Task to fetch the latest BCH to USD price from an external API (CoinGecko).
    This price is then stored in an environment variable for use by other parts of the application.
    It also sends real-time updates via WebSocket.
    """
    from api.models import BCHRate # Import model inside task to avoid circular imports
    from channels.layers import get_channel_layer # For sending WebSocket messages
    from asgiref.sync import async_to_sync # Helper for calling async from sync code

    channel_layer = get_channel_layer() # Get the global channel layer instance

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

            # Send real-time BCH rate update via WebSocket
            async_to_sync(channel_layer.group_send)(
                'bch_rate_updates', # Group name defined in BCHRateConsumer
                {
                    'type': 'bch_rate_update', # Method name in BCHRateConsumer
                    'message': {
                        'rate': str(bch_usd_rate), # Send as string for JSON
                        'timestamp': str(timezone.now())
                    }
                }
            )
            logger.debug("Sent BCH rate update via WebSocket.")
        else:
            logger.warning("Could not retrieve BCH to USD rate from CoinGecko API.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching BCH price: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in update_bch_price_task: {e}")

# Task for monitoring BCH addresses using Blockchair
@background(schedule=30) # Check every 30 seconds
def monitor_bch_addresses_task():
    """
    Task to periodically check all registered BCH addresses (from ScoreOutcome model)
    for new incoming transactions using the Blockchair API.
    It delegates the transaction processing to process_new_transactions_blockchair.
    """
    logger.info("Starting BCH address monitoring task with Blockchair...") # Updated log message
    # Import ScoreOutcome model here to avoid potential circular dependency
    from api.models import ScoreOutcome 

    # Get all prediction outcomes that have a BCH address assigned
    outcomes_to_monitor = ScoreOutcome.objects.filter(bch_address__isnull=False)

    if not outcomes_to_monitor.exists():
        logger.info("No prediction outcomes with BCH addresses to monitor.")
        return

    for outcome in outcomes_to_monitor:
        try:
            # Call the utility function to process transactions for this outcome's address
            # The process_new_transactions_blockchair function now handles WebSocket updates internally
            process_new_transactions_blockchair(outcome) # Changed function call to blockchair utility

        except Exception as e:
            logger.error(f"Error monitoring address {outcome.bch_address} for outcome {outcome.outcome_id} with Blockchair: {e}", exc_info=True) # Updated log message

    logger.info("BCH address monitoring task completed with Blockchair.") # Updated log message
