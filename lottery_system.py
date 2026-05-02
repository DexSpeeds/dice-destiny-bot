"""
Lottery System - 24 hour draw cycle
1 ticket per person, 50M per ticket
3 prizes always drawn, random fair draw
10% house edge, 50/30/20 split
"""
import json
import os
import time
import random
from lottery_renderer import generate_lottery_numbers

LOTTERY_FILE = 'lottery_data.json'
TICKET_PRICE = 50_000_000  # 50M GP
HOUSE_EDGE = 0.10
DRAW_INTERVAL = 24 * 60 * 60  # 24 hours


class LotterySystem:
    def __init__(self):
        self.entries = []
        self.ticket_counter = 0
        self.draw_time = None
        self.total_pot = 0
        self.announced = False
        self._load()

    def _load(self):
        if os.path.exists(LOTTERY_FILE):
            try:
                with open(LOTTERY_FILE, 'r') as f:
                    data = json.load(f)
                self.entries = data.get('entries', [])
                self.ticket_counter = data.get('ticket_counter', 0)
                self.draw_time = data.get('draw_time')
                self.total_pot = data.get('total_pot', 0)
                self.announced = data.get('announced', False)
            except Exception:
                pass

        if not self.draw_time:
            self.draw_time = time.time() + DRAW_INTERVAL

    def _save(self):
        try:
            with open(LOTTERY_FILE, 'w') as f:
                json.dump({
                    'entries': self.entries,
                    'ticket_counter': self.ticket_counter,
                    'draw_time': self.draw_time,
                    'total_pot': self.total_pot,
                    'announced': self.announced,
                }, f)
        except Exception:
            pass

    def has_ticket(self, user_id):
        """Check if user already has a ticket this round"""
        return any(e['user_id'] == user_id for e in self.entries)

    def buy_ticket(self, user_id, user_name):
        """Buy a lottery ticket. 1 per person."""
        if self.has_ticket(user_id):
            return None  # Already has ticket

        self.ticket_counter += 1
        numbers = generate_lottery_numbers()

        entry = {
            'user_id': user_id,
            'user_name': user_name,
            'ticket_no': self.ticket_counter,
            'numbers': numbers,
            'timestamp': time.time()
        }
        self.entries.append(entry)
        self.total_pot += TICKET_PRICE
        self._save()
        return entry

    def get_time_left(self):
        if not self.draw_time:
            return "Unknown"
        remaining = self.draw_time - time.time()
        if remaining <= 0:
            return "Drawing soon..."
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def is_draw_time(self):
        return time.time() >= self.draw_time and len(self.entries) > 0

    def should_announce(self):
        remaining = self.draw_time - time.time()
        return 0 < remaining <= 60 and not self.announced and len(self.entries) > 0

    def mark_announced(self):
        self.announced = True
        self._save()

    def get_status(self):
        pot_after = int(self.total_pot * (1 - HOUSE_EDGE))
        return {
            'total_entries': len(self.entries),
            'total_pot': self.total_pot,
            'pot_after_edge': pot_after,
            'prize_1st': int(pot_after * 0.50),
            'prize_2nd': int(pot_after * 0.30),
            'prize_3rd': int(pot_after * 0.20),
            'time_left': self.get_time_left(),
            'ticket_price': TICKET_PRICE,
        }

    def draw(self):
        """Random fair draw - 3 prizes always fall."""
        if len(self.entries) == 0:
            self.draw_time = time.time() + DRAW_INTERVAL
            self.announced = False
            self._save()
            return None

        pot_after = int(self.total_pot * (1 - HOUSE_EDGE))
        prizes = [int(pot_after * 0.50), int(pot_after * 0.30), int(pot_after * 0.20)]

        # Shuffle all entries randomly
        pool = list(self.entries)
        random.shuffle(pool)

        winners = []
        used = set()

        for place in range(3):
            if len(pool) == 1:
                # Only 1 person - they get all remaining prizes
                winner = pool[0]
            elif len(used) < len(pool):
                # Pick random winner not yet picked
                for entry in pool:
                    if entry['user_id'] not in used:
                        winner = entry
                        break
                else:
                    # All unique picked, cycle back (1 or 2 players get multiple)
                    winner = pool[place % len(pool)]
            else:
                winner = pool[place % len(pool)]

            used.add(winner['user_id'])

            winners.append({
                'user_id': winner['user_id'],
                'user_name': winner['user_name'],
                'ticket_no': winner['ticket_no'],
                'numbers': winner['numbers'],
                'matches': 0,
                'prize': prizes[place],
                'place': place + 1,
            })

        result = {
            'winning_numbers': generate_lottery_numbers(),
            'winners': winners,
            'total_pot': self.total_pot,
            'pot_after_edge': pot_after,
            'total_entries': len(self.entries),
        }

        # Reset
        self.entries = []
        self.total_pot = 0
        self.draw_time = time.time() + DRAW_INTERVAL
        self.announced = False
        self._save()

        return result
