# api/bch_betting.py

import uuid
import random
import requests
import json
from decimal import Decimal, getcontext
import datetime

from .models import BCHRate # This is your new model

# Set precision for Decimal calculations to avoid floating point issues with money
getcontext().prec = 8 # BCH typically has 8 decimal places

class BCHBettingSystem:
    """
    A conceptual backend system for managing BCH exact score bets.
    This simplified model demonstrates core logic for matches, scores, bets, and payouts.
    """

    def __init__(self):
        self.matches = {} # Stores Match objects: {match_id: Match_object}
        self.bets = {}    # Stores bets: {match_id: {bet_id: {'address': origin_address, 'amount_bch': amount, 'score_outcome_id': score_id}}}
        self.ticket_value_usd = Decimal('1.00') # Fixed ticket value in USD
        self.fixed_prize_pool_usd = Decimal('50.00') # Fixed prize pool for the event in USD

        # For real BCH address generation, you'd load your master key here
        # self.master_key = None
        # self.load_master_key()

        # Initialize with some simulated matches when the system starts
        self.setup_initial_matches() # <--- ADDED THIS CALL


    def _generate_bch_address(self, match_id, score_outcome_id):
        """
        Conceptual function to generate a unique BCH address deterministically
        for a given match and score outcome.
        For this simulation, it returns a unique placeholder string.
        """
        return f"bitcoincash:qq{uuid.uuid4().hex[:34]}" # Placeholder testnet-like address

    # --- NEW METHOD: setup_initial_matches ---
    def setup_initial_matches(self):
        """
        Creates a set of initial, simulated matches for demonstration purposes.
        This is called once when the BCHBettingSystem is initialized.
        """
        # Define common possible scores (reusable)
        common_possible_scores = [
            "0-0", "1-0", "0-1", "1-1", "2-0", "0-2", "2-1", "1-2", "2-2", "3-0"
        ]

        # Match 1: Today's date
        match1_date = (datetime.date.today()).isoformat() # Current date
        self.create_match(
            "Flamengo", "Corinthians", match1_date, common_possible_scores
        )

        # Match 2: Tomorrow's date
        match2_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        self.create_match(
            "Palmeiras", "São Paulo", match2_date, common_possible_scores
        )

        # Match 3: A few days from now
        match3_date = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
        self.create_match(
            "Grêmio", "Internacional", match3_date, common_possible_scores
        )
        print("\n--- Initial simulated matches created ---")


    def update_bch_usd_rate(self):
        """
        Fetches the current BCH to USD rate from CoinGecko and stores it in the database.
        """
        try:
            response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin-cash&vs_currencies=usd")
            response.raise_for_status() # Raise an exception for HTTP errors
            data = response.json()
            rate = Decimal(str(data['bitcoin-cash']['usd'])) # Convert to Decimal for precision

            # Save the new rate to the database
            BCHRate.objects.create(rate=rate)

            # print(f"BCH USD Rate updated to: ${rate}") # Print in task, not here
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error fetching BCH rate: {e}")
            return False
        except KeyError:
            print("Error parsing CoinGecko response: 'bitcoin-cash' or 'usd' not found.")
            return False
        except Exception as e:
            print(f"An unexpected error occurred during rate update: {e}")
            return False

    def get_bch_usd_rate(self):
        """
        Retrieves the latest BCH to USD rate from the database.
        If no rate is found, it attempts to fetch it immediately.
        """
        try:
            latest_rate = BCHRate.objects.latest('timestamp') # Get the most recent entry
            return latest_rate.rate
        except BCHRate.DoesNotExist:
            print("No BCH rate found in the database. Attempting initial fetch...")
            self.update_bch_usd_rate() # Try to fetch it immediately
            try:
                latest_rate = BCHRate.objects.latest('timestamp')
                print(f"Initial BCH rate fetched from API: ${latest_rate.rate}")
                return latest_rate.rate
            except BCHRate.DoesNotExist:
                print("Still no BCH rate after initial fetch. Returning default 0.0.")
                return Decimal('0.0') # Fallback if API call also fails
        except Exception as e:
            print(f"Error retrieving BCH rate from DB: {e}")
            return Decimal('0.0') # Fallback


    def create_match(self, team1: str, team2: str, match_date: str, possible_scores: list):
        """
        Creates a new match and its associated betting market (score outcomes).
        Each score outcome gets a unique BCH address for betting.
        """
        match_id = str(uuid.uuid4())
        match = Match(match_id, team1, team2, match_date)

        # print(f"\n--- Creating Betting Market for Match: {team1} vs {team2} on {match_date} ---") # Removed for cleaner startup
        match.betting_outcomes = {}
        for i, score_str in enumerate(possible_scores):
            outcome_id = str(uuid.uuid4())
            bch_address = self._generate_bch_address(match_id, outcome_id)
            match.betting_outcomes[outcome_id] = {
                'score': score_str,
                'bch_address': bch_address,
                'total_betted_bch': Decimal('0'),
                'bet_count': 0,
                'bets_received': [] # Stores details of each individual bet
            }
            # print(f"  Generated address for {score_str} (Match {match_id[:8]}): {bch_address}") # Removed for cleaner startup

        self.matches[match_id] = match
        self.bets[match_id] = {} # Initialize bets storage for this match
        # print(f"Match '{match.team1} vs {match.team2}' (ID: {match_id}) created with {len(possible_scores)} betting outcomes.") # Removed for cleaner startup
        return match_id

    def simulate_deposit(self, match_id: str, score_outcome_id: str, origin_address: str, deposited_bch_amount: Decimal):
        """
        Simulates an incoming BCH deposit to a specific score outcome address.
        In a real system, this would be triggered by blockchain monitoring.
        It validates the deposit amount against the ticket value.
        """
        if match_id not in self.matches:
            print(f"Error: Match ID {match_id} not found.")
            return False

        match = self.matches[match_id]
        if score_outcome_id not in match.betting_outcomes:
            print(f"Error: Score outcome ID {score_outcome_id} not found for match {match_id}.")
            return False

        current_bch_rate = self.get_bch_usd_rate()
        if current_bch_rate <= 0:
            print("Error: Cannot simulate deposit. BCH rate is not available or invalid.")
            return False

        required_bch_for_ticket = self.ticket_value_usd / current_bch_rate
        num_tickets = (deposited_bch_amount / required_bch_for_ticket).quantize(Decimal('1'))

        if num_tickets < 1:
            print(f"Deposit too small. Minimum bet is {required_bch_for_ticket:.8f} BCH (approx ${self.ticket_value_usd:.2f} USD).")
            return False

        bet_id = str(uuid.uuid4())
        bet_info = {
            'origin_address': origin_address,
            'amount_bch': deposited_bch_amount,
            'num_tickets': int(num_tickets),
            'timestamp': datetime.datetime.now().isoformat()
        }

        self.bets[match_id][bet_id] = {
            'origin_address': origin_address,
            'amount_bch': deposited_bch_amount,
            'score_outcome_id': score_outcome_id,
            'num_tickets': int(num_tickets)
        }

        match.betting_outcomes[score_outcome_id]['total_betted_bch'] += deposited_bch_amount
        match.betting_outcomes[score_outcome_id]['bet_count'] += int(num_tickets)
        match.betting_outcomes[score_outcome_id]['bets_received'].append(bet_info)

        print(f"  BET RECEIVED: {deposited_bch_amount:.8f} BCH ({num_tickets} ticket(s)) from {origin_address} for score '{match.betting_outcomes[score_outcome_id]['score']}' in match '{match.team1} vs {match.team2}'.")
        return True

    def determine_winner_and_payout(self, match_id: str, winning_score_str: str):
        """
        Determines the winning score and calculates payouts for the match.
        The fixed prize pool is divided among winning tickets.
        """
        if match_id not in self.matches:
            print(f"Error: Match ID {match_id} not found.")
            return False

        match = self.matches[match_id]
        print(f"\n--- Determining Winner and Payout for Match: {match.team1} vs {match.team2} ---")
        print(f"Winning Score: {winning_score_str}")

        winning_outcome_id = None
        winning_outcome_details = None
        for outcome_id, details in match.betting_outcomes.items():
            if details['score'] == winning_score_str:
                winning_outcome_id = outcome_id
                winning_outcome_details = details
                break

        if not winning_outcome_id:
            print(f"Error: Winning score '{winning_score_str}' not found in betting outcomes for this match.")
            return False

        total_winning_tickets = winning_outcome_details['bet_count']

        if total_winning_tickets == 0:
            print("No bets were placed on the winning score. Prize pool is not distributed for this match.")
            return True # Still a valid outcome

        current_bch_rate = self.get_bch_usd_rate()
        if current_bch_rate <= 0:
            print("Error: Cannot determine payout. BCH rate is not available or invalid.")
            return False

        prize_pool_bch = self.fixed_prize_pool_usd / current_bch_rate
        print(f"Total prize pool for winners: {prize_pool_bch:.8f} BCH (fixed ${self.fixed_prize_pool_usd:.2f} USD).")
        print(f"Total winning tickets: {total_winning_tickets}")

        payout_per_ticket_bch = prize_pool_bch / total_winning_tickets
        print(f"Payout per winning ticket: {payout_per_ticket_bch:.8f} BCH")

        payouts_to_addresses = {}
        for bet_info in winning_outcome_details['bets_received']:
            address = bet_info['origin_address']
            num_tickets = bet_info['num_tickets']
            payouts_to_addresses[address] = payouts_to_addresses.get(address, Decimal('0')) + (payout_per_ticket_bch * num_tickets)

        print("\n--- Payouts to Winning Addresses ---")
        for address, amount in payouts_to_addresses.items():
            print(f"  Sending {amount:.8f} BCH to {address}")
            # In a real system: Execute actual BCH transaction here

        print("\nPayout process completed for this match.")
        return True

    def get_match_details(self, match_id: str):
        """Returns details for a specific match."""
        return self.matches.get(match_id)

    # --- MODIFIED: get_all_matches to return JSON-friendly data ---
    def get_all_matches(self):
        """
        Returns all created matches as a list of dictionaries, suitable for JSON serialization.
        """
        matches_data = []
        for match_id, match_obj in self.matches.items():
            outcomes_list = []
            for outcome_id, details in match_obj.betting_outcomes.items():
                outcomes_list.append({
                    'outcome_id': outcome_id,
                    'score': details['score'],
                    'bch_address': details['bch_address'],
                    'total_betted_bch': str(details['total_betted_bch']), # Convert Decimal to string
                    'bet_count': details['bet_count'],
                    # 'bets_received': details['bets_received'] # Consider omitting sensitive bet details for public API
                })
            matches_data.append({
                'match_id': match_obj.match_id,
                'team1': match_obj.team1,
                'team2': match_obj.team2,
                'match_date': match_obj.match_date,
                'betting_outcomes': outcomes_list
            })
        return matches_data


class Match:
    """Represents a single football match."""
    def __init__(self, match_id: str, team1: str, team2: str, match_date: str):
        self.match_id = match_id
        self.team1 = team1
        self.team2 = team2
        self.match_date = match_date
        self.betting_outcomes = {} # Stores score outcomes and their associated data

    def __str__(self):
        return f"{self.team1} vs {self.team2} on {self.match_date} (ID: {self.match_id})"

# The `if __name__ == "__main__":` block is for local testing of the class
# and is not typically run when Django imports the module.
# You can keep it for quick isolated testing, but it won't affect Django's behavior.