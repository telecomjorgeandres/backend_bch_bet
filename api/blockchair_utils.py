import requests
import os
import logging
from decimal import Decimal
from django.utils import timezone
from datetime import datetime, timezone as dt_timezone # ✅ Import timezone from datetime

logger = logging.getLogger(__name__)

# Base URL for the chosen blockchain data service (Blockchair BCH API)
BLOCKCHAIN_DATA_SERVICE_BASE_URL = os.getenv('BLOCKCHAIN_DATA_SERVICE_BASE_URL', "https://api.blockchair.com/bitcoin-cash")
# API Key for the chosen blockchain data service
BLOCKCHAIN_DATA_SERVICE_API_KEY = os.getenv('BLOCKCHAIN_DATA_SERVICE_API_KEY')

def _make_blockchair_request(endpoint, method='GET', params=None, data=None):
    """
    Helper function to make requests to the Blockchair API.
    """
    headers = {
        "Content-Type": "application/json",
    }
    
    if params is None:
        params = {}
    
    if BLOCKCHAIN_DATA_SERVICE_API_KEY:
        params['key'] = BLOCKCHAIN_DATA_SERVICE_API_KEY
    else:
        logger.error("BLOCKCHAIN_DATA_SERVICE_API_KEY is not set. Blockchair requests will likely fail.")
        return None
    
    url = f"{BLOCKCHAIN_DATA_SERVICE_BASE_URL}/{endpoint}"

    try:
        if method == 'POST':
            response = requests.post(url, json=data, headers=headers, params=params)
        else: # Default to GET
            response = requests.get(url, params=params, headers=headers)

        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error with Blockchair API for {endpoint}: {e.response.status_code} - {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error with Blockchair API for {endpoint}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during Blockchair request to {endpoint}: {e}")
        return None

def get_address_transactions_blockchair(bch_address):
    """
    Fetches transaction hashes for a given BCH address from Blockchair.
    Returns a list of transaction hash strings.
    """
    endpoint = f"dashboards/address/{bch_address}"
    params = {
        'limit': 100,
        'offset': 0
    }
    response_data = _make_blockchair_request(endpoint, params=params)

    if response_data and 'data' in response_data and bch_address in response_data['data']:
        address_data = response_data['data'][bch_address]
        # The 'transactions' key contains a list of transaction hash STRINGS
        return address_data.get('transactions', [])
    return None

def get_transaction_details_blockchair(tx_hash):
    """
    Fetches full details for a given transaction hash from Blockchair.
    """
    endpoint = f"dashboards/transaction/{tx_hash}"
    response_data = _make_blockchair_request(endpoint)
    if response_data and 'data' in response_data and tx_hash in response_data['data']:
        return response_data['data'][tx_hash]
    return None


def process_new_transactions_blockchair(outcome):
    """
    Checks for new incoming transactions on a ScoreOutcome's BCH address
    using the Blockchair API and updates the outcome's bet_count.
    """
    from api.models import RealBetTransaction, ScoreOutcome # Import here to avoid circular dependency
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    
    logger.info(f"Checking for new transactions on address: {outcome.bch_address} for outcome ID: {outcome.outcome_id} using Blockchair.")

    # Get recent transaction hashes for the address
    transaction_hashes = get_address_transactions_blockchair(outcome.bch_address)

    if not transaction_hashes:
        logger.info(f"No new transactions found or could not fetch summary for address: {outcome.bch_address} from Blockchair.")
        return

    new_tx_found_for_outcome = False
    newest_tx_hash_seen = outcome.last_monitored_tx_hash

    for tx_hash in transaction_hashes:
        
        if tx_hash == outcome.last_monitored_tx_hash:
            logger.info(f"Reached last processed transaction ({tx_hash}) for address {outcome.bch_address}. Stopping Blockchair scan.")
            break
        
        if RealBetTransaction.objects.filter(transaction_hash=tx_hash).exists():
            logger.info(f"Transaction {tx_hash} already recorded in RealBetTransaction for address {outcome.bch_address}. Skipping.")
            continue

        full_tx_details = get_transaction_details_blockchair(tx_hash)

        if not full_tx_details:
            logger.warning(f"Could not fetch full details for transaction {tx_hash}. Skipping.")
            continue

        transaction_data = full_tx_details.get('transaction', {})
        outputs = full_tx_details.get('outputs', [])
        inputs = full_tx_details.get('inputs', [])

        amount_satoshi = 0
        output_timestamp = None
        
        for output in outputs:
            if output.get('recipient') == outcome.bch_address:
                amount_satoshi = output.get('value', 0)
                break

        if transaction_data.get('time'):
            # ✅ FIX: Use dt_timezone.utc from the datetime library
            output_timestamp = datetime.strptime(transaction_data['time'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=dt_timezone.utc)
        else:
            output_timestamp = timezone.now()

        if transaction_data.get('block_id') is None or transaction_data.get('block_id') == 0:
            logger.info(f"Transaction {tx_hash} for {outcome.bch_address} is unconfirmed. Skipping for now.")
            continue

        if amount_satoshi > 0:
            amount_bch = Decimal(amount_satoshi) / Decimal(100_000_000)
            
            current_bch_usd_rate_str = os.getenv('LAST_FETCHED_BCH_USD_RATE', '0.00')
            current_bch_usd_rate = Decimal(current_bch_usd_rate_str)

            ticket_value_usd = Decimal('1.00')
            
            num_tickets = 0
            if current_bch_usd_rate > 0:
                required_bch_per_ticket = ticket_value_usd / current_bch_usd_rate
                if required_bch_per_ticket > 0:
                    num_tickets = int(amount_bch / required_bch_per_ticket)
                else:
                    logger.warning(f"Required BCH per ticket is zero for {outcome.bch_address}. Check BCH/USD rate.")
            else:
                logger.warning(f"BCH/USD rate is zero or not available ({current_bch_usd_rate_str}). Cannot calculate tickets for {outcome.bch_address}.")

            if num_tickets > 0:
                outcome.bet_count += num_tickets
                outcome.save()
                
                RealBetTransaction.objects.create(
                    transaction_hash=tx_hash,
                    bch_address=outcome.bch_address,
                    amount_satoshi=amount_satoshi,
                    outcome=outcome,
                    timestamp=output_timestamp
                )
                logger.info(f"Processed {num_tickets} tickets for outcome '{outcome.score}' (Match ID: {outcome.match.match_id}) from TX: {tx_hash} to {outcome.bch_address}.")
                new_tx_found_for_outcome = True
                newest_tx_hash_seen = tx_hash 

                async_to_sync(channel_layer.group_send)(
                    f'match_{outcome.match.match_id}',
                    {
                        'type': 'transaction_update',
                        'message': {
                            'status': 'received',
                            'tx_hash': tx_hash,
                            'bch_address': outcome.bch_address,
                            'amount_satoshi': str(amount_satoshi),
                            'num_tickets': num_tickets,
                            'match_id': outcome.match.match_id,
                            'outcome_id': str(outcome.outcome_id),
                            'score': outcome.score,
                            'timestamp': str(output_timestamp),
                            'explorer_url': f"https://blockchair.com/bitcoin-cash/transaction/{tx_hash}"
                        }
                    }
                )
                logger.debug(f"Sent WebSocket update for TX {tx_hash} to match group {outcome.match.match_id}.")
            else:
                logger.info(f"Transaction {tx_hash} to {outcome.bch_address} received {amount_bch} BCH, which is less than one ticket value. Not processed as a bet.")
        else:
            logger.info(f"Transaction {tx_hash} to {outcome.bch_address} has zero amount for this address or no relevant output. Skipping.")
    
    if new_tx_found_for_outcome and newest_tx_hash_seen != outcome.last_monitored_tx_hash:
        outcome.last_monitored_tx_hash = newest_tx_hash_seen
        outcome.save()
        logger.info(f"Updated last_monitored_tx_hash for {outcome.bch_address} to {outcome.last_monitored_tx_hash}.")
