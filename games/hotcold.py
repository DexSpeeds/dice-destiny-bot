"""
Hot/Cold Flowers - Based on real Mithril Seed drop rates
Flower planted from weighted RNG matching OSRS drop table
"""
from provably_fair import GameSession

# Real Mithril Seed drop rates (out of 1001)
# Mixed: 150, Red: 150, Yellow: 150, Blue: 150, Orange: 150
# Purple: 148, Assorted: 100, Black: 2, White: 1
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

# Hot = Red, Orange, Yellow  (450/1001 = ~44.9%)
# Cold = Blue, Purple         (298/1001 = ~29.8%)
HOT_COLORS = ['red', 'orange', 'yellow']
COLD_COLORS = ['blue', 'purple']


class HotCold:
    """Hot/Cold Flower game with real drop rates"""

    # Payouts
    # All payouts set for 10% house edge
    PAYOUTS = {
        'hot': 2.0,         # ~44.9% chance
        'cold': 3.0,        # ~29.8% chance
        'red': 6.0,         # ~15.0% chance
        'yellow': 6.0,
        'blue': 6.0,
        'orange': 6.0,
        'mixed': 6.0,
        'purple': 6.0,      # ~14.8%
        'assorted': 9.0,    # ~10.0%
        'black': 450.0,     # ~0.2%
        'white': 900.0,     # ~0.1%
    }

    def __init__(self):
        pass

    def _pick_flower(self, session):
        """Pick a flower using weighted RNG matching Mithril Seed rates"""
        roll, _ = session.play(TOTAL_WEIGHT)
        cumulative = 0
        for color, weight in FLOWER_WEIGHTS:
            cumulative += weight
            if roll < cumulative:
                return color
        return FLOWER_WEIGHTS[-1][0]

    def play(self, bet, choice):
        """Play hot/cold flowers"""
        session = GameSession()
        result_color = self._pick_flower(session)

        won = False
        if choice == 'hot':
            won = result_color in HOT_COLORS
        elif choice == 'cold':
            won = result_color in COLD_COLORS
        else:
            won = result_color == choice

        multiplier = self.PAYOUTS.get(choice, 0) if won else 0
        payout = int(bet * multiplier) if won else 0

        return {
            'won': won,
            'payout': payout,
            'result': result_color,
            'multiplier': multiplier,
            'bet_type': choice,
            'seeds': session.get_seeds()
        }
