"""
Flower Poker - Uses real Mithril Seed drop rates
5 flowers planted, poker hand evaluation
Supports player/host/draw bets
"""
from provably_fair import GameSession
from typing import List, Tuple

# Real Mithril Seed drop rates (out of 1001)
FLOWER_WEIGHTS = [
    ('red', 150),
    ('yellow', 150),
    ('blue', 150),
    ('orange', 150),
    ('mixed', 150),
    ('purple', 148),
    ('assorted', 100),
    ('black', 2),
    ('white', 1),
]
TOTAL_WEIGHT = sum(w for _, w in FLOWER_WEIGHTS)  # 1001

# Hand names for display
HAND_NAMES = {
    'bust': 'Bust',
    'pair': 'One Pair',
    'two_pair': 'Two Pairs',
    'three': 'Three of a Kind',
    'full_house': 'Full House',
    'four': 'Four of a Kind',
    'five': 'Five of a Kind',
}

HAND_RANKINGS = {
    'bust': 0,
    'pair': 1,
    'two_pair': 2,
    'three': 3,
    'full_house': 4,
    'five': 5,
}


class FlowerPoker:
    """Flower Poker game with real drop rates"""

    def __init__(self, player_payout=2.0, host_payout=2.0, draw_payout=9.0):
        self.player_payout = player_payout
        self.host_payout = host_payout
        self.draw_payout = draw_payout

    def _pick_flower(self, session):
        """Pick a flower using weighted RNG"""
        roll, _ = session.play(TOTAL_WEIGHT)
        cumulative = 0
        for color, weight in FLOWER_WEIGHTS:
            cumulative += weight
            if roll < cumulative:
                return color
        return FLOWER_WEIGHTS[-1][0]

    def draw_hand(self, session) -> List[str]:
        """Draw 5 flowers"""
        return [self._pick_flower(session) for _ in range(5)]

    def evaluate_hand(self, hand: List[str]) -> Tuple[str, int]:
        """Evaluate poker hand"""
        counts = {}
        for flower in hand:
            counts[flower] = counts.get(flower, 0) + 1

        sorted_counts = sorted(counts.values(), reverse=True)

        if sorted_counts == [5]:
            return ('five', 6)
        elif sorted_counts[0] == 4:
            return ('four', 5)
        elif sorted_counts == [3, 2]:
            return ('full_house', 4)
        elif sorted_counts[0] == 3:
            return ('three', 3)
        elif sorted_counts[:2] == [2, 2]:
            return ('two_pair', 2)
        elif sorted_counts[0] == 2:
            return ('pair', 1)
        else:
            return ('bust', 0)

    def play(self, bet, bet_type):
        """
        Play flower poker

        Args:
            bet: wager amount
            bet_type: 'player', 'host', or 'draw'
        """
        session = GameSession()

        player_flowers = self.draw_hand(session)
        host_flowers = self.draw_hand(session)

        # Black or White flower in EITHER hand = instant replant
        has_bw = any(f in ('black', 'white') for f in player_flowers + host_flowers)
        if has_bw:
            winner = 'draw'
            player_hand = 'Replant (Black/White)'
            host_hand = 'Replant (Black/White)'
            player_rank = -1
            host_rank = -1
        else:
            player_hand, player_rank = self.evaluate_hand(player_flowers)
            host_hand, host_rank = self.evaluate_hand(host_flowers)

            if player_rank > host_rank:
                winner = 'player'
            elif host_rank > player_rank:
                winner = 'host'
            else:
                winner = 'draw'

        # Determine win based on bet type
        if bet_type == 'draw':
            won = winner == 'draw'
            multiplier = self.draw_payout if won else 0
        elif bet_type == 'player':
            if winner == 'draw':
                # Draw = replant (refund) when betting player/host
                won = False
                multiplier = 0
            else:
                won = winner == 'player'
                multiplier = self.player_payout if won else 0
        else:  # host
            if winner == 'draw':
                won = False
                multiplier = 0
            else:
                won = winner == 'host'
                multiplier = self.host_payout if won else 0

        payout = int(bet * multiplier) if won else 0

        return {
            'won': won,
            'payout': payout,
            'player_flowers': player_flowers,
            'host_flowers': host_flowers,
            'player_hand': HAND_NAMES.get(player_hand, player_hand),
            'host_hand': HAND_NAMES.get(host_hand, host_hand),
            'winner': winner,
            'bet_type': bet_type,
            'is_draw': winner == 'draw',
            'seeds': session.get_seeds()
        }
