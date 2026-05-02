"""
Game History + ID Tracker
Tracks last 10 results per game and assigns sequential game IDs
"""
import json
import os
from collections import deque

HISTORY_FILE = 'game_history.json'


class GameHistory:
    """Track game results history and IDs"""

    def __init__(self):
        self.history = {}  # game_name -> deque of last 10 results
        self.game_counter = 0
        self._load()

    def _load(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    data = json.load(f)
                self.game_counter = data.get('counter', 0)
                for game, results in data.get('history', {}).items():
                    self.history[game] = deque(results, maxlen=10)
            except Exception:
                pass

    def _save(self):
        data = {
            'counter': self.game_counter,
            'history': {k: list(v) for k, v in self.history.items()}
        }
        try:
            with open(HISTORY_FILE, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass

    def next_id(self):
        """Get next game ID"""
        self.game_counter += 1
        self._save()
        return self.game_counter

    def add_result(self, game_name, result_text):
        """Add a result to game history"""
        if game_name not in self.history:
            self.history[game_name] = deque(maxlen=10)
        self.history[game_name].appendleft(result_text)
        self._save()

    def get_history(self, game_name, count=10):
        """Get last N results for a game"""
        if game_name not in self.history:
            return []
        return list(self.history[game_name])[:count]

    def format_history(self, game_name, count=10):
        """Format history as string for embed"""
        results = self.get_history(game_name, count)
        if not results:
            return "No games yet"
        lines = []
        for i, r in enumerate(results):
            prefix = "**>** " if i == 0 else "  "
            lines.append(f"{prefix}{r}")
        return "\n".join(lines)
