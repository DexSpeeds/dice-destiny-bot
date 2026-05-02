"""
Caskets - Fixed version  
"""
from provably_fair import GameSession

class Caskets:
    """Caskets game"""
    
    def __init__(self, coin_payout: float = 1.9, gem_payout: float = 2.5, rare_payout: float = 5.0):
        self.coin_payout = coin_payout
        self.gem_payout = gem_payout
        self.rare_payout = rare_payout
    
    def play(self, bet: int, choice: str) -> dict:
        """Play caskets"""
        session = GameSession()
        
        # Results: 0=coin, 1=gem, 2=rare
        result_idx, _ = session.play(3)
        results = ['coin', 'gem', 'rare']
        result = results[result_idx]
        
        emojis = {
            'coin': '🪙',
            'gem': '💎',
            'rare': '👑'
        }
        
        payouts = {
            'coin': self.coin_payout,
            'gem': self.gem_payout,
            'rare': self.rare_payout
        }
        
        won = result == choice
        multiplier = payouts[result] if won else 0
        payout = int(bet * multiplier) if won else 0
        
        return {
            'won': won,
            'payout': payout,
            'result': result,
            'emoji_result': emojis[result],
            'payout_multiplier': multiplier,
            'choice': choice,
            'seeds': session.get_seeds()
        }
