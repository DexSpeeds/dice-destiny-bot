"""
99x Game - Pick a number 1-100, roll 1-100
Match = 99x payout
"""
from provably_fair import GameSession


class NinetyNine:
    """99x - pick your number, match the roll for 99x"""

    MULTIPLIER = 99.0

    def __init__(self):
        pass

    def play(self, bet, choice, number=None):
        """
        Play 99x

        Args:
            bet: wager amount
            choice: ignored (always 'exact'), kept for interface compat
            number: player's chosen number (1-100)
        """
        session = GameSession()
        roll, _ = session.play(100)
        roll += 1  # 1-100

        won = number is not None and roll == number
        payout = int(bet * self.MULTIPLIER) if won else 0

        return {
            'won': won,
            'payout': payout,
            'roll': roll,
            'choice': 'exact',
            'number': number,
            'multiplier': self.MULTIPLIER if won else 0,
            'seeds': session.get_seeds()
        }
