"""
Staking - OSRS Duel Arena style whip fight
Both fighters start at 99 HP, alternate hits (0-25 max)
Visual GIF with HP bars and hitsplats
"""
from provably_fair import GameSession

MAX_HP = 99
MAX_HIT = 25  # Whip max hit


class Staking:
    """Duel Arena staking game"""

    def __init__(self, payout: float = 1.9):
        self.payout = payout

    def play(self, bet: int) -> dict:
        """
        Play a stake fight

        Returns dict with fight sequence and result
        """
        session = GameSession()

        player_hp = MAX_HP
        host_hp = MAX_HP
        rounds = []

        while player_hp > 0 and host_hp > 0:
            # Player hits host
            player_hit, _ = session.play(MAX_HIT + 1)  # 0-25
            host_hp = max(0, host_hp - player_hit)

            # Host hits player (if still alive)
            if host_hp > 0:
                host_hit, _ = session.play(MAX_HIT + 1)
                player_hp = max(0, player_hp - host_hit)
            else:
                host_hit = 0

            rounds.append({
                'player_hit': player_hit,
                'host_hit': host_hit,
                'player_hp': player_hp,
                'host_hp': host_hp,
            })

        won = host_hp <= 0
        payout = int(bet * self.payout) if won else 0

        return {
            'won': won,
            'payout': payout,
            'rounds': rounds,
            'total_rounds': len(rounds),
            'final_player_hp': player_hp,
            'final_host_hp': host_hp,
            'seeds': session.get_seeds(),
        }
