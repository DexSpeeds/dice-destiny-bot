"""
Lottery System - 24 hour draw cycle
Buy tickets, get DM'd your ticket image, 3 winners per draw
10% house edge, 50/30/20 split for top 3
"""
import json
import os
import time
from datetime import datetime
from lottery_renderer import generate_lottery_numbers

LOTTERY_FILE = 'lottery_data.json'
TICKET_PRICE = 10_000_000  # 10M GP
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
        data = {
            'entries': self.entries,
            'ticket_counter': self.ticket_counter,
            'draw_time': self.draw_time,
            'total_pot': self.total_pot,
            'announced': self.announced,
        }
        try:
            with open(LOTTERY_FILE, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass

    def buy_ticket(self, user_id, user_name):
        """Buy a lottery ticket. Returns ticket data."""
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
        """Get formatted time remaining"""
        if not self.draw_time:
            return "Unknown"
        remaining = self.draw_time - time.time()
        if remaining <= 0:
            return "Drawing soon..."

        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        seconds = int(remaining % 60)

        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    def is_draw_time(self):
        return time.time() >= self.draw_time and len(self.entries) > 0

    def should_announce(self):
        """1 minute warning"""
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
        """Perform the draw. Returns result dict or None."""
        if len(self.entries) == 0:
            # No entries - reset timer
            self.draw_time = time.time() + DRAW_INTERVAL
            self.announced = False
            self._save()
            return None

        winning_numbers = generate_lottery_numbers()

        # Score entries
        scored = []
        for entry in self.entries:
            matches = sum(1 for n in entry['numbers'] if n in winning_numbers)
            scored.append({**entry, 'matches': matches})

        scored.sort(key=lambda x: (-x['matches'], x['ticket_no']))

        pot_after = int(self.total_pot * (1 - HOUSE_EDGE))
        prizes = [int(pot_after * 0.50), int(pot_after * 0.30), int(pot_after * 0.20)]

        winners = []
        for i in range(min(3, len(scored))):
            winners.append({
                'user_id': scored[i]['user_id'],
                'user_name': scored[i]['user_name'],
                'ticket_no': scored[i]['ticket_no'],
                'numbers': scored[i]['numbers'],
                'matches': scored[i]['matches'],
                'prize': prizes[i] if i < len(prizes) else 0,
                'place': i + 1,
            })

        result = {
            'winning_numbers': winning_numbers,
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
