import requests
import os
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)

# Base URL for the chosen blockchain data service (e.g., Blockchair, Bitquery, etc.)
BLOCKCHAIN_DATA_SERVICE_BASE_URL = os.getenv('BLOCKCHAIN_DATA_SERVICE_BASE_URL', "http://localhost:8000/api/mock-blockchain-service") # Default to a mock/placeholder URL
# API Key for the chosen blockchain data service
BLOCKCHAIN_DATA_SERVICE_API_KEY = os.getenv('BLOCKCHAIN_DATA_SERVICE_API_KEY')

def _make_blockchain_service_request(endpoint, method='GET', params=None, data=None):
    """
    Helper function to make requests to the chosen blockchain data service.
    This is a placeholder. You will replace the internal logic with actual
    API calls to your chosen service (e.g., Blockchair, Bitquery, etc.).
    """
    headers = {
        "Content-Type": "application/json",
    }
    if BLOCKCHAIN_DATA_SERVICE_API_KEY:
        # Add authentication header based on your chosen service's requirements
        # Example for Bearer token:
        headers["Authorization"] = f"Bearer {BLOCKCHAIN_DATA_SERVICE_API_KEY}"
        # Example for API key in a custom header:
        # headers["X-API-Key"] = BLOCKCHAIN_DATA_SERVICE_API_KEY
    else:
        logger.warning("BLOCKCHAIN_DATA_SERVICE_API_KEY is not set. Requests might fail if the service requires authentication.")
    
    url = f"{BLOCKCHAIN_DATA_SERVICE_BASE_URL}/{endpoint}"

    try:
        # --- PLACEHOLDER LOGIC ---
        # In a real implementation, you would replace this with actual API calls
        # to your chosen blockchain data service.
        # For now, this will simulate a successful response for testing the task flow.
        if "address/details" in endpoint:
            # Simulate a response structure similar to mainnet.cash for compatibility
            # In a real scenario, you'd adapt this to your chosen service's response.
            mock_transactions = []
            # Simulate a new transaction if we're testing the flow
            if "mock_new_tx" in endpoint: # A simple way to trigger a mock new transaction
                mock_transactions.append({
                    "txid": f"mock_tx_{timezone.now().timestamp()}",
                    "height": 1000000, # Confirmed
                    "time": int(timezone.now().timestamp()),
                    "outputs": {
                        endpoint.split('/')[-1]: 100000 # 100,000 satoshis (0.001 BCH)
                    }
                })
            
            return {
                "address": endpoint.split('/')[-1],
                "transactions": mock_transactions # Ordered newest first
            }
        
        # Default mock response for other endpoints if needed
        return {"message": "Mock response from placeholder blockchain service."}

        # --- END PLACEHOLDER LOGIC ---

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error with blockchain data service for {endpoint}: {e.response.status_code} - {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error with blockchain data service for {endpoint}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during blockchain data service request to {endpoint}: {e}")
        return None

def get_address_transactions(bch_address, last_tx_hash=None):
    """
    Fetches transactions for a given BCH address from the chosen blockchain data service.
    This is a placeholder function.
    """
    # This endpoint and its response will depend entirely on the chosen service.
    # For now, it uses a mock endpoint for demonstration.
    endpoint = f"address/details/{bch_address}"
    return _make_blockchain_service_request(endpoint)

def process_new_transactions_for_outcome(outcome):
    """
    Checks for new incoming transactions on a ScoreOutcome's BCH address
    using the chosen blockchain data service and updates the outcome's bet_count.
    It also records each processed transaction in the RealBetTransaction model
    to prevent double-counting.
    """
    from api.models import RealBetTransaction, ScoreOutcome # Import here to avoid circular dependency
    
    logger.info(f"Checking for new transactions on address: {outcome.bch_address} for outcome ID: {outcome.outcome_id} using blockchain data service placeholder.")

    # Fetch transactions from the blockchain data service
    # The structure of `transactions_data` will depend on the chosen service.
    transactions_data = get_address_transactions(outcome.bch_address, outcome.last_monitored_tx_hash)

    if not transactions_data:
        logger.error(f"Could not fetch transactions for address: {outcome.bch_address} from blockchain data service.")
        return

    transactions = transactions_data.get('transactions', [])
    
    # Filter for incoming transactions where our address is a recipient
    # This logic might need adjustment based on the chosen service's response format.
    incoming_transactions = [
        tx for tx in transactions
        if outcome.bch_address in tx.get('outputs', {})
    ]

    new_tx_found_for_outcome = False
    newest_tx_hash_seen = outcome.last_monitored_tx_hash # Initialize with current last_monitored_tx_hash

    # Iterate through transactions from newest to oldest (assuming service provides this order)
    for tx in incoming_transactions:
        tx_hash = tx.get('txid')
        
        # If we encounter the last transaction we already processed, break the loop.
        if tx_hash == outcome.last_monitored_tx_hash:
            logger.info(f"Reached last processed transaction ({tx_hash}) for address {outcome.bch_address}. Stopping blockchain service scan.")
            break
        
        # Crucial: Check if this transaction has already been recorded in our internal database
        if RealBetTransaction.objects.filter(transaction_hash=tx_hash).exists():
            logger.info(f"Transaction {tx_hash} already recorded in RealBetTransaction for address {outcome.bch_address}. Skipping.")
            continue

        # Get the amount sent to our specific address in satoshis
        amount_satoshi = tx.get('outputs', {}).get(outcome.bch_address, 0)
        
        # Ensure the transaction is confirmed (logic depends on service's response)
        # Assuming 'height' or 'confirmations' field exists and indicates confirmation.
        if tx.get('height', 0) == 0: # Example: height 0 means unconfirmed
            logger.info(f"Transaction {tx_hash} for {outcome.bch_address} is unconfirmed. Skipping for now.")
            continue

        if amount_satoshi > 0:
            amount_bch = Decimal(amount_satoshi) / Decimal(100_000_000)
            
            current_bch_usd_rate_str = os.getenv('LAST_FETCHED_BCH_USD_RATE', '0.00')
            current_bch_usd_rate = Decimal(current_bch_usd_rate_str)

            ticket_value_usd = Decimal('1.00') # Fixed ticket value for prediction contest
            
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
                    # Adjust timestamp extraction based on your chosen service's response
                    timestamp=timezone.datetime.fromtimestamp(tx.get('time'), tz=timezone.utc) if tx.get('time') else timezone.now()
                )
                logger.info(f"Processed {num_tickets} tickets for outcome '{outcome.score}' (Match ID: {outcome.match.match_id}) from TX: {tx_hash} to {outcome.bch_address}.")
                new_tx_found_for_outcome = True
                # Update the newest_tx_hash_seen to this transaction's hash
                newest_tx_hash_seen = tx_hash 
            else:
                logger.info(f"Transaction {tx_hash} to {outcome.bch_address} received {amount_bch} BCH, which is less than one ticket value. Not processed as a prediction entry.")
        else:
            logger.info(f"Transaction {tx_hash} to {outcome.bch_address} has zero amount for this address or no relevant output. Skipping.")
    
    if new_tx_found_for_outcome and newest_tx_hash_seen != outcome.last_monitored_tx_hash:
        outcome.last_monitored_tx_hash = newest_tx_hash_seen
        outcome.save()
        logger.info(f"Updated last_monitored_tx_hash for {outcome.bch_address} to {outcome.last_monitored_tx_hash}.")

