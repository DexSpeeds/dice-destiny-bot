"""
Caskets - Different odds per tier
Coin: 58% chance (common)
Gem: 38% chance (medium)
Rare: 4% chance (rare but big payout)
All with 10% house edge total
"""
from provably_fair import GameSession

# Weighted drop table
CASKET_WEIGHTS = [
    ('coin', 58),
    ('gem', 38),
    ('rare', 4),
]
TOTAL_WEIGHT = sum(w for _, w in CASKET_WEIGHTS)  # 100

# Payouts balanced for ~10% total house edge
# coin: 58% * 1.55 = 0.899
# gem: 38% * 2.37 = 0.901
# rare: 4% * 10.0 = 0.400
# Total EV per play weighted: ~0.90 = 10% edge
CASKET_PAYOUTS = {
    'coin': 1.55,
    'gem': 2.37,
    'rare': 10.0,
}

CASKET_EMOJIS = {
    'coin': '🪙',
    'gem': '💎',
    'rare': '👑',
}


class Caskets:
    def __init__(self, coin_payout=1.55, gem_payout=2.37, rare_payout=10.0):
        self.payouts = {
            'coin': coin_payout,
            'gem': gem_payout,
            'rare': rare_payout,
        }

    def play(self, bet, choice):
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
        multiplier = self.payouts[result] if won else 0
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
