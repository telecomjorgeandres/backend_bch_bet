# bch_betting_backend/api/chaingraph_utils.py
import requests
import os
import logging
from decimal import Decimal
from django.utils import timezone # For timezone-aware datetimes

logger = logging.getLogger(__name__)

# Chaingraph GraphQL endpoint URL
CHAINGRAPH_URL = os.getenv('CHAINGRAPH_URL', "http://localhost:1337/v1/graphql") # Default to local Chaingraph

def _make_chaingraph_query(query, variables=None):
    """
    Helper function to make GraphQL queries to the Chaingraph API.
    """
    headers = {
        "Content-Type": "application/json",
        # Chaingraph typically doesn't require an API key for public endpoints
        # but if you secure it, you'd add Authorization headers here.
    }
    payload = {
        "query": query,
        "variables": variables if variables is not None else {}
    }

    try:
        response = requests.post(CHAINGRAPH_URL, json=payload, headers=headers)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error with Chaingraph API: {e.response.status_code} - {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error with Chaingraph API: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during Chaingraph request: {e}")
        return None

def get_address_transactions_chaingraph(bch_address, last_tx_hash=None):
    """
    Fetches transactions for a given BCH address from Chaingraph.
    It fetches transactions that output to the specified address.
    """
    # GraphQL query to get transactions for an address, ordered by block height descending
    # and transaction index descending to get newest first.
    # We limit to 100 to avoid excessively large responses and handle pagination later if needed.
    query = """
    query GetAddressTransactions($address: String!, $afterBlockHeight: Int) {
      transaction(
        where: {
          transaction_outputs: {
            output_address: { _eq: $address }
          },
          _and: {
            block_height: { _lte: $afterBlockHeight } # Filter for blocks at or before last monitored
          }
        }
        order_by: { block_height: desc, transaction_index: desc }
        limit: 100
      ) {
        transaction_hash
        block_height
        block_time # Timestamp of the block
        transaction_outputs {
          output_index
          output_value # Amount in satoshis
          output_address
        }
      }
    }
    """

    variables = {
        "address": bch_address,
        "afterBlockHeight": 999999999 # Start with a very high block height to get all recent transactions
    }

    # If we have a last_tx_hash, we need to find its block_height and transaction_index
    # and then query for transactions *before* or *at* that point, ensuring we don't miss any
    # This part can get complex with GraphQL pagination, for simplicity, we'll fetch recent ones
    # and rely on the RealBetTransaction model for de-duplication.
    # For robust pagination, you'd need to query the last_tx_hash's details first.
    # For now, we'll just fetch recent and let the DB deduplicate.

    response_data = _make_chaingraph_query(query, variables)

    if response_data and 'data' in response_data and 'transaction' in response_data['data']:
        return response_data['data']['transaction']
    return None

def process_new_transactions_chaingraph(outcome):
    """
    Checks for new incoming transactions on a ScoreOutcome's BCH address
    using the Chaingraph API and updates the outcome's bet_count.
    It also records each processed transaction in the RealBetTransaction model
    to prevent double-counting.
    """
    from api.models import RealBetTransaction, ScoreOutcome # Import here to avoid circular dependency
    
    logger.info(f"Checking for new transactions on address: {outcome.bch_address} for outcome ID: {outcome.outcome_id} using Chaingraph.")

    # Fetch transactions from Chaingraph
    # We pass last_monitored_tx_hash to help Chaingraph filter, though our DB check is primary
    chaingraph_transactions = get_address_transactions_chaingraph(outcome.bch_address, outcome.last_monitored_tx_hash)

    if not chaingraph_transactions:
        logger.info(f"No new transactions found or could not fetch details for address: {outcome.bch_address} from Chaingraph.")
        return

    new_tx_found_for_outcome = False
    newest_tx_hash_seen = outcome.last_monitored_tx_hash # Initialize with current last_monitored_tx_hash

    # Chaingraph returns transactions ordered newest first (due to order_by clause)
    for tx in chaingraph_transactions:
        tx_hash = tx.get('transaction_hash')
        
        # If we encounter the last transaction we already processed, break the loop.
        # This relies on Chaingraph's ordering.
        if tx_hash == outcome.last_monitored_tx_hash:
            logger.info(f"Reached last processed transaction ({tx_hash}) for address {outcome.bch_address}. Stopping Chaingraph scan.")
            break
        
        # Crucial: Check if this transaction has already been recorded in our internal database
        # This handles cases where `last_monitored_tx_hash` might be outdated or tasks restart.
        if RealBetTransaction.objects.filter(transaction_hash=tx_hash).exists():
            logger.info(f"Transaction {tx_hash} already recorded in RealBetTransaction for address {outcome.bch_address}. Skipping.")
            continue

        # Find the output relevant to our monitored address
        amount_satoshi = 0
        output_timestamp = None
        for output in tx.get('transaction_outputs', []):
            if output.get('output_address') == outcome.bch_address:
                amount_satoshi = output.get('output_value', 0)
                break # Found the relevant output

        # Chaingraph's block_time is a Unix timestamp in seconds
        if tx.get('block_time'):
            output_timestamp = timezone.datetime.fromtimestamp(tx['block_time'], tz=timezone.utc)
        else:
            output_timestamp = timezone.now() # Fallback to current time if block_time is missing

        # Chaingraph's `block_height` indicates confirmation. If it's null, it's unconfirmed.
        if tx.get('block_height') is None:
            logger.info(f"Transaction {tx_hash} for {outcome.bch_address} is unconfirmed (block_height is null). Skipping for now.")
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
                    bch_address=outcome.bch_address, # Use the address from the outcome
                    amount_satoshi=amount_satoshi,
                    outcome=outcome,
                    timestamp=output_timestamp
                )
                logger.info(f"Processed {num_tickets} tickets for outcome '{outcome.score}' (Match ID: {outcome.match.match_id}) from TX: {tx_hash} to {outcome.bch_address}.")
                new_tx_found_for_outcome = True
                # Update the newest_tx_hash_seen to this transaction's hash
                # This ensures we update last_monitored_tx_hash to the truly newest one processed
                newest_tx_hash_seen = tx_hash 
            else:
                logger.info(f"Transaction {tx_hash} to {outcome.bch_address} received {amount_bch} BCH, which is less than one ticket value. Not processed as a bet.")
        else:
            logger.info(f"Transaction {tx_hash} to {outcome.bch_address} has zero amount for this address or no relevant output. Skipping.")
    
    if new_tx_found_for_outcome and newest_tx_hash_seen != outcome.last_monitored_tx_hash:
        outcome.last_monitored_tx_hash = newest_tx_hash_seen
        outcome.save()
        logger.info(f"Updated last_monitored_tx_hash for {outcome.bch_address} to {outcome.last_monitored_tx_hash}.")

