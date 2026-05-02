"""
Coinflip - Fixed version
"""
from provably_fair import GameSession

class Coinflip:
    """Coinflip game"""
    
    def __init__(self, payout: float = 1.9):
        self.payout = payout
    
    def play(self, bet: int, choice: str) -> dict:
        """
        Play coinflip
        
        Args:
            bet: Amount wagered
            choice: 'heads' or 'tails'
        
        Returns dict with all game data
        """
        session = GameSession()
        
        # Flip coin
        flip_result, _ = session.play(2)
        result = 'heads' if flip_result == 0 else 'tails'
        
        # Check win
        won = result == choice.lower()
        payout = int(bet * self.payout) if won else 0
        
        return {
            'won': won,
            'payout': payout,
            'result': result,
            'choice': choice,
            'seeds': session.get_seeds()
        }
