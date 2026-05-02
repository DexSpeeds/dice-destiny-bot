"""
Statistics Tracker - Track all game stats
"""
import json
import os
from typing import Dict, List, Tuple
from datetime import datetime

class StatsTracker:
    """Track player statistics"""
    
    def __init__(self, stats_file: str = "player_stats.json"):
        self.stats_file = stats_file
        self.stats = self.load_stats()
    
    def load_stats(self) -> Dict:
        """Load stats from file"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_stats(self):
        """Save stats to file"""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            print(f"Error saving stats: {e}")
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Get stats for a user"""
        user_key = str(user_id)
        if user_key not in self.stats:
            self.stats[user_key] = {
                'total_wagered': 0,
                'total_won': 0,
                'total_lost': 0,
                'games_played': 0,
                'games_won': 0,
                'games_lost': 0,
                'biggest_win': 0,
                'biggest_loss': 0,
                'by_game': {}
            }
        return self.stats[user_key]
    
    def record_game(
        self,
        user_id: int,
        game_name: str,
        bet: int,
        won: bool,
        payout: int = 0
    ):
        """Record a game result"""
        user_stats = self.get_user_stats(user_id)
        user_key = str(user_id)
        
        # Update totals
        user_stats['total_wagered'] += bet
        user_stats['games_played'] += 1
        
        if won:
            user_stats['games_won'] += 1
            user_stats['total_won'] += payout
            if payout > user_stats['biggest_win']:
                user_stats['biggest_win'] = payout
        else:
            user_stats['games_lost'] += 1
            user_stats['total_lost'] += bet
            if bet > user_stats['biggest_loss']:
                user_stats['biggest_loss'] = bet
        
        # Update per-game stats
        if game_name not in user_stats['by_game']:
            user_stats['by_game'][game_name] = {
                'played': 0,
                'won': 0,
                'lost': 0,
                'wagered': 0,
                'profit': 0
            }
        
        game_stats = user_stats['by_game'][game_name]
        game_stats['played'] += 1
        game_stats['wagered'] += bet
        
        if won:
            game_stats['won'] += 1
            game_stats['profit'] += (payout - bet)
        else:
            game_stats['lost'] += 1
            game_stats['profit'] -= bet
        
        self.save_stats()
    
    def get_leaderboard(self, limit: int = 10) -> List[Tuple[int, Dict]]:
        """
        Get top players by total won
        
        Returns:
            List of (user_id, stats) tuples
        """
        leaderboard = []
        for user_id, stats in self.stats.items():
            leaderboard.append((int(user_id), stats))
        
        # Sort by total won (descending)
        leaderboard.sort(key=lambda x: x[1]['total_won'], reverse=True)
        
        return leaderboard[:limit]
    
    def get_win_rate(self, user_id: int) -> float:
        """Get user's win rate"""
        stats = self.get_user_stats(user_id)
        if stats['games_played'] == 0:
            return 0.0
        return (stats['games_won'] / stats['games_played']) * 100
    
    def get_profit(self, user_id: int) -> int:
        """Get user's total profit/loss"""
        stats = self.get_user_stats(user_id)
        return stats['total_won'] - stats['total_lost']
