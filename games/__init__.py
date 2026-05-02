"""Games package"""
from .coinflip import Coinflip
from .blackjack import Blackjack
from .flowerpoker import FlowerPoker
from .dice import Dice
from .hotcold import HotCold
from .caskets import Caskets
from .roulette import Roulette
from .mines import Mines
from .ninetynine import NinetyNine
from .diceduel import DiceDuel

__all__ = [
    'Coinflip', 'Blackjack', 'FlowerPoker', 'Dice',
    'HotCold', 'Caskets', 'Roulette',
    'Mines', 'NinetyNine', 'DiceDuel'
]
