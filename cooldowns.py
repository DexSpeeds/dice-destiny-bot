"""
Cooldown System - Prevent spam
"""
import time
from typing import Dict, Tuple

class CooldownManager:
    """Manage game cooldowns"""
    
    def __init__(self, cooldown_seconds: int = 3):
        self.cooldown_seconds = cooldown_seconds
        self.last_played: Dict[Tuple[int, str], float] = {}  # (user_id, game_name): timestamp
    
    def check_cooldown(self, user_id: int, game_name: str) -> Tuple[bool, float]:
        """
        Check if user is on cooldown for this game
        
        Returns:
            (can_play: bool, remaining_time: float)
        """
        key = (user_id, game_name)
        
        if key not in self.last_played:
            return (True, 0.0)
        
        elapsed = time.time() - self.last_played[key]
        remaining = self.cooldown_seconds - elapsed
        
        if remaining <= 0:
            return (True, 0.0)
        
        return (False, remaining)
    
    def set_cooldown(self, user_id: int, game_name: str):
        """Set cooldown for user on this game"""
        key = (user_id, game_name)
        self.last_played[key] = time.time()
    
    def reset_cooldown(self, user_id: int, game_name: str):
        """Reset cooldown (for admin override)"""
        key = (user_id, game_name)
        if key in self.last_played:
            del self.last_played[key]
