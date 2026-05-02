"""
Caskets - Pick a tier, if it drops you win!
Coin: 58% chance, 1.55x | Gem: 38% chance, 2.37x | Rare: 4% chance, 22.5x
Each tier has exactly 10% house edge
"""
from provably_fair import GameSession

CASKET_WEIGHTS = [
    ('coin', 58),
    ('gem', 38),
    ('rare', 4),
]
TOTAL_WEIGHT = 100

# Each tier: payout = 0.90 / probability (10% house edge per tier)
CASKET_PAYOUTS = {
    'coin': 1.55,    # 0.90 / 0.58
    'gem': 2.37,     # 0.90 / 0.38
    'rare': 22.5,    # 0.90 / 0.04
}

CASKET_EMOJIS = {
    'coin': '🪙',
    'gem': '💎',
    'rare': '👑',
}


class Caskets:
    def __init__(self, coin_payout=1.55, gem_payout=2.37, rare_payout=22.5):
        self.payouts = {
            'coin': coin_payout,
            'gem': gem_payout,
            'rare': rare_payout,
        }

    def play(self, bet, choice):
        """Pick a tier - if it drops you win the payout"""
        session = GameSession()

        # Weighted random pick
        roll, _ = session.play(TOTAL_WEIGHT)
        cumulative = 0
        result = 'coin'
        for tier, weight in CASKET_WEIGHTS:
            cumulative += weight
            if roll < cumulative:
                result = tier
                break

        won = result == choice
        multiplier = self.payouts[choice] if won else 0
        payout = int(bet * multiplier) if won else 0

        return {
            'won': won,
            'payout': payout,
            'result': result,
            'emoji_result': CASKET_EMOJIS[result],
            'payout_multiplier': multiplier,
            'choice': choice,
            'seeds': session.get_seeds()
        }
