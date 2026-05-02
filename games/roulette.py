"""
Roulette - Fixed multiplayer version
"""
from provably_fair import GameSession
from typing import Dict, List, Tuple

class Roulette:
    """Roulette game"""
    
    # Standard roulette payouts
    # All payouts set for 10% house edge
    PAYOUTS = {
        'number': 33.33,   # Single number
        'red': 1.85,       # Red/Black
        'black': 1.85,
        'even': 1.85,      # Even/Odd
        'odd': 1.85,
        'low': 1.85,       # 1-18 / 19-36
        'high': 1.85,
        'dozen1': 2.78,    # 1-12
        'dozen2': 2.78,    # 13-24
        'dozen3': 2.78,    # 25-36
        'column1': 2.78,   # Columns
        'column2': 2.78,
        'column3': 2.78
    }
    
    # Red numbers on roulette wheel
    RED_NUMBERS = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
    
    def __init__(self):
        pass
    
    def spin(self) -> int:
        """Spin the wheel, return winning number (0-36)"""
        session = GameSession()
        number, _ = session.play(37)  # 0-36
        self._last_seeds = session.get_seeds()
        return number
    
    def get_number_color(self, number: int) -> str:
        """Get color of number"""
        if number == 0:
            return 'green'
        elif number in self.RED_NUMBERS:
            return 'red'
        else:
            return 'black'
    
    def check_bet(self, number: int, bet_type: str, bet_value: int = None) -> Tuple[bool, float]:
        """
        Check if bet wins
        
        Args:
            number: Winning number
            bet_type: Type of bet
            bet_value: Value for number/dozen/column bets
        
        Returns:
            (won, multiplier)
        """
        # Number bet
        if bet_type == 'number':
            if number == bet_value:
                return (True, self.PAYOUTS['number'])
            return (False, 0)
        
        # Color bets
        color = self.get_number_color(number)
        if bet_type in ['red', 'black']:
            if color == bet_type:
                return (True, self.PAYOUTS[bet_type])
            return (False, 0)
        
        # Even/Odd
        if bet_type == 'even':
            if number > 0 and number % 2 == 0:
                return (True, self.PAYOUTS['even'])
            return (False, 0)
        
        if bet_type == 'odd':
            if number > 0 and number % 2 == 1:
                return (True, self.PAYOUTS['odd'])
            return (False, 0)
        
        # Low/High
        if bet_type == 'low':
            if 1 <= number <= 18:
                return (True, self.PAYOUTS['low'])
            return (False, 0)
        
        if bet_type == 'high':
            if 19 <= number <= 36:
                return (True, self.PAYOUTS['high'])
            return (False, 0)
        
        # Dozens
        if bet_type == 'dozen1':
            if 1 <= number <= 12:
                return (True, self.PAYOUTS['dozen1'])
            return (False, 0)
        
        if bet_type == 'dozen2':
            if 13 <= number <= 24:
                return (True, self.PAYOUTS['dozen2'])
            return (False, 0)
        
        if bet_type == 'dozen3':
            if 25 <= number <= 36:
                return (True, self.PAYOUTS['dozen3'])
            return (False, 0)
        
        return (False, 0)
    
    def play(self, bet: int, bet_type: str, bet_value: int = None) -> dict:
        """
        Play roulette
        
        Returns dict with all game data
        """
        number = self.spin()
        won, multiplier = self.check_bet(number, bet_type, bet_value)
        
        payout = int(bet * multiplier) if won else 0
        color = self.get_number_color(number)
        
        return {
            'won': won,
            'payout': payout,
            'number': number,
            'color': color,
            'bet_type': bet_type,
            'bet_value': bet_value,
            'multiplier': multiplier,
            'seeds': self._last_seeds
        }
