"""
Mines Game - 5x5 grid, pick safe tiles, avoid bombs
Multiplier increases with each safe tile revealed
"""
from provably_fair import ProvablyFair

# Grid is 5x5 = 25 tiles, but we use rows 0-3 for tiles (20 tiles)
# and row 4 for the cashout button
GRID_TILES = 25

# Multiplier tables: mines -> [mult for 1 tile, 2 tiles, ...]
MULTIPLIER_TABLES = {
    1: [1.04, 1.09, 1.14, 1.20, 1.26, 1.33, 1.41, 1.50, 1.60, 1.71,
        1.84, 2.00, 2.18, 2.40, 2.67, 3.00, 3.43, 4.00, 4.80],
    3: [1.18, 1.41, 1.69, 2.05, 2.52, 3.14, 3.98, 5.14, 6.80,
        9.26, 13.08, 19.31, 30.14, 50.93, 96.08, 210.80, 632.40],
    5: [1.33, 1.79, 2.45, 3.43, 4.95, 7.36, 11.38, 18.40, 31.37,
        57.26, 114.52, 257.67, 686.00, 2401.00, 14406.00],
    7: [1.52, 2.34, 3.69, 6.01, 10.16, 17.96, 33.49, 66.57, 142.64,
        334.76, 878.35, 2635.00, 9869.00, 52899.00],
    10: [2.00, 4.00, 8.40, 18.67, 44.80, 118.10, 349.00, 1186.00,
         4745.00, 23724.00],
    15: [4.00, 17.78, 88.89, 533.33, 4267.00, 55467.00],
    19: [20.00, 380.00, 25333.00],
}


class Mines:
    """Mines game - progressive cashout"""

    def __init__(self):
        self.grid = []
        self.revealed = []
        self.mine_count = 0
        self.bet = 0
        self.pf = None
        self.active = False
        self.tiles_revealed = 0

    def start(self, bet, mine_count=5):
        """Start a new mines game"""
        self.bet = bet
        self.mine_count = min(max(mine_count, 1), GRID_TILES - 1)
        self.pf = ProvablyFair()
        self.active = True
        self.tiles_revealed = 0

        # Generate tiles (0=safe, 1=mine)
        self.grid = [0] * GRID_TILES
        mines_placed = 0
        while mines_placed < self.mine_count:
            pos = self.pf.roll(GRID_TILES)
            if self.grid[pos] == 0:
                self.grid[pos] = 1
                mines_placed += 1

        self.revealed = [False] * GRID_TILES

        return {
            'mine_count': self.mine_count,
            'grid_size': GRID_TILES,
            'current_multiplier': 1.0,
            'seeds': self.pf.get_seeds()
        }

    def reveal_tile(self, position):
        """Reveal a tile"""
        if not self.active or position < 0 or position >= GRID_TILES:
            return None
        if self.revealed[position]:
            return None

        self.revealed[position] = True

        if self.grid[position] == 1:
            self.active = False
            # Reveal all mines
            for i in range(GRID_TILES):
                if self.grid[i] == 1:
                    self.revealed[i] = True
            return {
                'hit_mine': True,
                'position': position,
                'payout': 0,
                'multiplier': 0,
                'tiles_revealed': self.tiles_revealed,
                'seeds': self.pf.get_seeds()
            }

        self.tiles_revealed += 1
        mult = self._get_multiplier()

        return {
            'hit_mine': False,
            'position': position,
            'current_multiplier': mult,
            'potential_payout': int(self.bet * mult),
            'tiles_revealed': self.tiles_revealed,
            'seeds': self.pf.get_seeds()
        }

    def cashout(self):
        """Cash out at current multiplier"""
        if not self.active or self.tiles_revealed == 0:
            return None

        self.active = False
        mult = self._get_multiplier()
        payout = int(self.bet * mult)

        # Reveal all mines for the final display
        for i in range(GRID_TILES):
            if self.grid[i] == 1:
                self.revealed[i] = True

        return {
            'payout': payout,
            'multiplier': mult,
            'tiles_revealed': self.tiles_revealed,
            'seeds': self.pf.get_seeds()
        }

    def _get_multiplier(self):
        """Get current multiplier"""
        table = MULTIPLIER_TABLES.get(self.mine_count)
        if not table:
            # Fallback calculation
            safe_tiles = GRID_TILES - self.mine_count
            mult = 1.0
            for i in range(self.tiles_revealed):
                mult *= safe_tiles / (GRID_TILES - i)
                safe_tiles -= 1
            return round(0.97 / mult, 2) if mult > 0 else 1.0

        idx = self.tiles_revealed - 1
        if idx < 0:
            return 1.0
        if idx >= len(table):
            return table[-1]
        return table[idx]
