"""
Blackjack with Split support
"""
from typing import Tuple, List
from provably_fair import GameSession


class Blackjack:
    """Blackjack game with split"""

    CARD_VALUES = {
        "A": 11, "2": 2, "3": 3, "4": 4, "5": 5,
        "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
        "J": 10, "Q": 10, "K": 10
    }

    CARD_SUITS = ["♠", "♥", "♦", "♣"]
    CARD_RANKS = list(CARD_VALUES.keys())

    def __init__(self, win_payout=1.9, blackjack_payout=2.5):
        self.win_payout = win_payout
        self.blackjack_payout = blackjack_payout
        self.player_hand = []
        self.dealer_hand = []
        self.split_hand = None  # Second hand if split
        self.active_hand = 'main'  # 'main' or 'split'
        self.is_split = False
        self.session = None

    def draw_card(self, session):
        rank_idx, _ = session.play(len(self.CARD_RANKS))
        suit_idx, _ = session.play(len(self.CARD_SUITS))
        return self.CARD_RANKS[rank_idx], self.CARD_SUITS[suit_idx]

    def calculate_hand_value(self, cards):
        value = 0
        aces = 0
        for rank, suit in cards:
            value += self.CARD_VALUES[rank]
            if rank == "A":
                aces += 1
        while value > 21 and aces > 0:
            value -= 10
            aces -= 1
        return value

    def can_split(self):
        """Check if current hand can be split"""
        if self.is_split or len(self.player_hand) != 2:
            return False
        rank1 = self.player_hand[0][0]
        rank2 = self.player_hand[1][0]
        # Split on same value (K-K, 10-J, etc all count as 10)
        return self.CARD_VALUES[rank1] == self.CARD_VALUES[rank2]

    def play(self, bet):
        """Start new blackjack game"""
        self.session = GameSession()
        self.player_hand = [self.draw_card(self.session), self.draw_card(self.session)]
        self.dealer_hand = [self.draw_card(self.session), self.draw_card(self.session)]
        self.split_hand = None
        self.is_split = False
        self.active_hand = 'main'

        player_value = self.calculate_hand_value(self.player_hand)
        player_bj = player_value == 21

        state = 'player_blackjack' if player_bj else 'playing'
        dealer_shows_ace = self.dealer_hand[0][0] == 'A'

        return {
            'player_hand': list(self.player_hand),
            'dealer_hand': list(self.dealer_hand),
            'player_value': player_value,
            'dealer_value': self.calculate_hand_value(self.dealer_hand),
            'state': state,
            'bet': bet,
            'dealer_shows_ace': dealer_shows_ace,
            'can_split': self.can_split()
        }

    def split(self):
        """Split the hand into two"""
        if not self.can_split():
            return None

        self.is_split = True
        self.split_hand = [self.player_hand.pop()]  # Move second card to split hand

        # Deal one new card to each hand
        self.player_hand.append(self.draw_card(self.session))
        self.split_hand.append(self.draw_card(self.session))

        self.active_hand = 'main'

        return {
            'player_hand': list(self.player_hand),
            'split_hand': list(self.split_hand),
            'player_value': self.calculate_hand_value(self.player_hand),
            'split_value': self.calculate_hand_value(self.split_hand),
            'state': 'playing',
            'active_hand': 'main'
        }

    def get_active_hand(self):
        """Get the currently active hand"""
        if self.active_hand == 'main':
            return self.player_hand
        return self.split_hand

    def hit(self):
        """Hit on active hand"""
        hand = self.get_active_hand()
        hand.append(self.draw_card(self.session))
        value = self.calculate_hand_value(hand)

        state = 'playing'
        if value > 21:
            if self.is_split and self.active_hand == 'main':
                # Bust on hand 1, move to hand 2
                state = 'hand1_bust'
                self.active_hand = 'split'
            else:
                state = 'player_bust'

        return {
            'player_hand': list(self.player_hand),
            'split_hand': list(self.split_hand) if self.split_hand else None,
            'player_value': self.calculate_hand_value(self.player_hand),
            'split_value': self.calculate_hand_value(self.split_hand) if self.split_hand else 0,
            'state': state,
            'active_hand': self.active_hand
        }

    def stand(self):
        """Stand on active hand"""
        if self.is_split and self.active_hand == 'main':
            # Stand on hand 1, move to hand 2
            self.active_hand = 'split'
            return {
                'player_hand': list(self.player_hand),
                'split_hand': list(self.split_hand),
                'player_value': self.calculate_hand_value(self.player_hand),
                'split_value': self.calculate_hand_value(self.split_hand),
                'state': 'playing',
                'active_hand': 'split'
            }

        # Final stand - dealer plays
        while self.calculate_hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.draw_card(self.session))

        player_value = self.calculate_hand_value(self.player_hand)
        dealer_value = self.calculate_hand_value(self.dealer_hand)

        if len(self.dealer_hand) == 2 and dealer_value == 21:
            if player_value == 21 and len(self.player_hand) == 2:
                state = 'push'
            else:
                state = 'dealer_blackjack'
        elif dealer_value > 21:
            state = 'dealer_bust'
        elif player_value > dealer_value:
            state = 'player_wins'
        elif dealer_value > player_value:
            state = 'dealer_wins'
        else:
            state = 'push'

        result = {
            'player_hand': list(self.player_hand),
            'dealer_hand': list(self.dealer_hand),
            'player_value': player_value,
            'dealer_value': dealer_value,
            'state': state
        }

        # If split, also evaluate second hand
        if self.is_split:
            split_value = self.calculate_hand_value(self.split_hand)
            if split_value > 21:
                split_state = 'player_bust'
            elif dealer_value > 21:
                split_state = 'dealer_bust'
            elif split_value > dealer_value:
                split_state = 'player_wins'
            elif dealer_value > split_value:
                split_state = 'dealer_wins'
            else:
                split_state = 'push'

            result['split_hand'] = list(self.split_hand)
            result['split_value'] = split_value
            result['split_state'] = split_state

        return result

    def get_payout(self, state, bet):
        if state == 'player_blackjack':
            return (True, int(bet * self.blackjack_payout))
        elif state in ['dealer_bust', 'player_wins']:
            return (True, int(bet * self.win_payout))
        elif state == 'push':
            return (False, 0)
        else:
            return (False, 0)
