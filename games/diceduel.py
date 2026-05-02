"""
Dice Duel - Player vs House, highest roll wins
Simple and fast - both roll 1-100
"""
from provably_fair import GameSession


class DiceDuel:
    """Dice Duel - player vs house, highest roll wins"""

    def __init__(self, payout=1.9):
        self.payout = payout

    def play(self, bet):
        """
        Play dice duel

        Args:
            bet: wager amount

        Returns dict with game data
        """
        session = GameSession()

        # Both roll 1-100
        player_roll, _ = session.play(100)
        player_roll += 1
        house_roll, _ = session.play(100)
        house_roll += 1

        # Reroll ties
        rounds = 1
        while player_roll == house_roll:
            player_roll, _ = session.play(100)
            player_roll += 1
            house_roll, _ = session.play(100)
            house_roll += 1
            rounds += 1

        won = player_roll > house_roll
        payout = int(bet * self.payout) if won else 0

        return {
            'won': won,
            'payout': payout,
            'player_roll': player_roll,
            'house_roll': house_roll,
            'rounds': rounds,
            'seeds': session.get_seeds()
        }
