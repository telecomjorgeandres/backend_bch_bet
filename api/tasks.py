from background_task import background
import logging
import requests
import os
from decimal import Decimal
from django.utils import timezone # Import timezone

# Import the blockchain data utility functions from Chaingraph
from api.chaingraph_utils import process_new_transactions_chaingraph # Changed import to chaingraph_utils

logger = logging.getLogger(__name__)

# Make sure this task is defined and imported correctly in api/apps.py ready() method
@background(schedule=60) # Run every 60 seconds
def update_bch_price_task():
    """
    Task to fetch the latest BCH to USD price from an external API (CoinGecko).
    This price is then stored in an environment variable for use by other parts of the application.
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

# Task for monitoring BCH addresses using Chaingraph
@background(schedule=30) # Check every 30 seconds
def monitor_bch_addresses_task():
    """
    Task to periodically check all registered BCH addresses (from ScoreOutcome model)
    for new incoming transactions using the Chaingraph API.
    It delegates the transaction processing to process_new_transactions_chaingraph.
    """
    logger.info("Starting BCH address monitoring task with Chaingraph...") # Updated log message
    # Import ScoreOutcome model here to avoid potential circular dependency with chaingraph_utils
    from api.models import ScoreOutcome, RealBetTransaction # Import RealBetTransaction here too
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()

    # Get all prediction outcomes that have a BCH address assigned
    outcomes_to_monitor = ScoreOutcome.objects.filter(bch_address__isnull=False)

    if not outcomes_to_monitor.exists():
        logger.info("No prediction outcomes with BCH addresses to monitor.")
        return

    for outcome in outcomes_to_monitor:
        try:
            # Call the utility function to process transactions for this outcome's address
            # This function now also returns the processed transactions
            processed_txs = process_new_transactions_chaingraph(outcome) # Changed function call to chaingraph utility

            if processed_txs:
                for tx_info in processed_txs:
                    # --- Send WebSocket update for transaction received ---
                    async_to_sync(channel_layer.group_send)(
                        f'match_{outcome.match.match_id}', # Group for this specific match
                        {
                            'type': 'transaction_update', # Method name in MatchUpdateConsumer
                            'message': {
                                'status': 'received',
                                'tx_hash': tx_info['transaction_hash'],
                                'bch_address': tx_info['bch_address'],
                                'amount_satoshi': str(tx_info['amount_satoshi']),
                                'num_tickets': tx_info['num_tickets'],
                                'match_id': outcome.match.match_id,
                                'outcome_id': outcome.outcome_id,
                                'score': outcome.score,
                                'timestamp': str(tx_info['timestamp']),
                                'explorer_url': f"https://explorer.bitcoin.com/bch/tx/{tx_info['transaction_hash']}" # Block explorer link
                            }
                        }
                    )
                    # Corrected log message to use tx_info['transaction_hash'] instead of tx_info['tx_hash']
                    logger.debug(f"Sent WebSocket update for TX {tx_info['transaction_hash']} to match group {outcome.match.match_id}.")

        except Exception as e:
            logger.error(f"Error monitoring address {outcome.bch_address} for outcome {outcome.outcome_id} with Chaingraph: {e}") # Updated log message

    logger.info("BCH address monitoring task completed with Chaingraph.") # Updated log message

