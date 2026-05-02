"""
Wallet System - From original bot
"""
import json
import os
from typing import Optional

class WalletSystem:
    """Manage player balances"""
    
    def __init__(self, wallet_file: str = "wallets.json"):
        self.wallet_file = wallet_file
        self.wallets = self.load_wallets()
    
    def load_wallets(self) -> dict:
        """Load wallets from file"""
        if os.path.exists(self.wallet_file):
            try:
                with open(self.wallet_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_wallets(self):
        """Save wallets to file"""
        with open(self.wallet_file, 'w') as f:
            json.dump(self.wallets, f, indent=2)
    
    def get_balance(self, user_id: int) -> int:
        """Get user balance"""
        return self.wallets.get(str(user_id), 0)
    
    def set_balance(self, user_id: int, amount: int):
        """Set user balance"""
        self.wallets[str(user_id)] = max(0, amount)
        self.save_wallets()
    
    def add_balance(self, user_id: int, amount: int):
        """Add to user balance"""
        current = self.get_balance(user_id)
        self.set_balance(user_id, current + amount)
    
    def remove_balance(self, user_id: int, amount: int) -> bool:
        """
        Remove from user balance
        Returns True if successful, False if insufficient funds
        """
        current = self.get_balance(user_id)
        if current < amount:
            return False
        self.set_balance(user_id, current - amount)
        return True
    
    def has_balance(self, user_id: int, amount: int) -> bool:
        """Check if user has sufficient balance"""
        return self.get_balance(user_id) >= amount
