"""
Dice - Under / Mid / Over
Roll 1-100, pick your range
Under (1-42): 1.9x | Mid (43-58): 3.1x | Over (59-100): 1.9x
"""
from provably_fair import GameSession

DICE_RANGES = {
    'under': {'range': (1, 42), 'multiplier': 1.9},
    'mid':   {'range': (43, 58), 'multiplier': 3.1},
    'over':  {'range': (59, 100), 'multiplier': 1.9},
}


class Dice:
    """Dice game - Under / Mid / Over"""

    def __init__(self, house_edge=0.05):
        self.house_edge = house_edge

    def play(self, bet, target=None, bet_type='mid'):
        session = GameSession()
        roll, _ = session.play(100)
        roll += 1  # 1-100

        info = DICE_RANGES.get(bet_type, DICE_RANGES['mid'])
        low, high = info['range']
        won = low <= roll <= high
        multiplier = info['multiplier']
        payout = int(bet * multiplier) if won else 0

        return {
            'won': won,
            'payout': payout,
            'roll': roll,
            'bet_type': bet_type,
            'range': f"{low}-{high}",
            'multiplier': multiplier,
            'seeds': session.get_seeds()
        }
