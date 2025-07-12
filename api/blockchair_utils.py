import requests
import os
import logging
from decimal import Decimal
from django.utils import timezone

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
    
    # Blockchair API key is typically passed as a query parameter
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
    Fetches transactions for a given BCH address from Blockchair.
    Returns a list of transaction dictionaries.
    """
    endpoint = f"dashboards/address/{bch_address}"
    # Blockchair's address dashboard includes a 'transactions' array
    # We might need to adjust parameters if we need more than default transactions (e.g., limit, offset)
    params = {
        'limit': 100, # Fetch up to 100 recent transactions
        'offset': 0
    }
    response_data = _make_blockchair_request(endpoint, params=params)

    if response_data and 'data' in response_data and bch_address in response_data['data']:
        address_data = response_data['data'][bch_address]
        # Blockchair's address dashboard has 'transactions' and 'utxo'
        # We need to look at 'transactions' which lists transaction hashes.
        # Then, we might need to fetch individual transaction details if the dashboard doesn't provide enough.
        # For simplicity, let's assume the dashboard gives us enough info for incoming.
        
        # Blockchair's address dashboard provides 'transactions' as a list of transaction hashes.
        # To get details (like outputs and inputs), we usually need to query individual transactions.
        # For now, let's simplify and assume we can get enough from the dashboard or will fetch tx details
        # in the processing step if needed.
        
        # A more robust approach would be to fetch individual transaction details for each hash
        # or use a different Blockchair endpoint that provides more comprehensive transaction data directly.
        # For now, let's use the 'transactions' list from the dashboard.
        
        # Let's refine this: Blockchair's 'dashboards/address/{address}' returns
        # a 'transactions' object where keys are tx_hashes and values are summary.
        # We need to iterate through these and then potentially fetch full tx details.
        
        # Alternative: Use /dashboards/transactions endpoint with an address filter if available
        # or iterate and fetch each transaction.
        
        # For simplicity in this initial integration, let's use the transaction hashes
        # and then fetch full details for each if necessary.
        
        # Blockchair's address dashboard provides a list of `transaction` objects under `data[address]['transactions']`
        # which include `balance_change`, `time`, `block_id`, `hash`.
        # To get outputs and inputs, we need `/dashboards/transaction/{hash}`.
        
        # Let's modify `process_new_transactions_blockchair` to fetch individual transaction details.
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
    It also records each processed transaction in the RealBetTransaction model
    to prevent double-counting.
    """
    from api.models import RealBetTransaction, ScoreOutcome # Import here to avoid circular dependency
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    
    logger.info(f"Checking for new transactions on address: {outcome.bch_address} for outcome ID: {outcome.outcome_id} using Blockchair.")

    # Get recent transaction hashes for the address
    address_transactions_summary = get_address_transactions_blockchair(outcome.bch_address)

    if not address_transactions_summary:
        logger.info(f"No new transactions found or could not fetch summary for address: {outcome.bch_address} from Blockchair.")
        return

    new_tx_found_for_outcome = False
    newest_tx_hash_seen = outcome.last_monitored_tx_hash # Initialize with current last_monitored_tx_hash

    # Blockchair's address transactions are often ordered newest first.
    # We iterate through them, fetching full details as needed.
    for tx_summary in address_transactions_summary:
        tx_hash = tx_summary.get('hash')
        
        if tx_hash == outcome.last_monitored_tx_hash:
            logger.info(f"Reached last processed transaction ({tx_hash}) for address {outcome.bch_address}. Stopping Blockchair scan.")
            break
        
        if RealBetTransaction.objects.filter(transaction_hash=tx_hash).exists():
            logger.info(f"Transaction {tx_hash} already recorded in RealBetTransaction for address {outcome.bch_address}. Skipping.")
            continue

        # Fetch full transaction details to get outputs (and inputs for RBF/fee checks later)
        full_tx_details = get_transaction_details_blockchair(tx_hash)

        if not full_tx_details:
            logger.warning(f"Could not fetch full details for transaction {tx_hash}. Skipping.")
            continue

        # Extract relevant data from full_tx_details
        # Blockchair's transaction details are under 'transaction' and 'inputs'/'outputs' arrays
        transaction_data = full_tx_details.get('transaction', {})
        outputs = full_tx_details.get('outputs', [])
        inputs = full_tx_details.get('inputs', []) # For future RBF/fee checks

        amount_satoshi = 0
        output_timestamp = None
        
        # Find the amount sent to our specific outcome address
        for output in outputs:
            if output.get('recipient') == outcome.bch_address: # Blockchair uses 'recipient' for output address
                amount_satoshi = output.get('value', 0) # 'value' is in satoshis
                break

        # Blockchair's transaction 'time' is a string, convert to datetime object
        if transaction_data.get('time'):
            # Blockchair time format: "2024-07-12 18:00:00"
            output_timestamp = timezone.datetime.strptime(transaction_data['time'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        else:
            output_timestamp = timezone.now() # Fallback to current time

        # Blockchair's `block_id` being null or 0 indicates unconfirmed
        if transaction_data.get('block_id') is None or transaction_data.get('block_id') == 0:
            logger.info(f"Transaction {tx_hash} for {outcome.bch_address} is unconfirmed (block_id is null/0). Skipping for now.")
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

                # Send WebSocket update for transaction received
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
                            'outcome_id': outcome.outcome_id,
                            'score': outcome.score,
                            'timestamp': str(output_timestamp),
                            'explorer_url': f"https://blockchair.com/bitcoin-cash/transaction/{tx_hash}" # Blockchair explorer link
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

