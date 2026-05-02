"""
Wager Tracker - Track deposits and wager requirements
"""
import json
import os

class WagerTracker:
    """Track deposits and wager progress"""
    
    def __init__(self, tracker_file: str = "wager_tracker.json"):
        self.tracker_file = tracker_file
        self.data = self.load_data()
    
    def load_data(self) -> dict:
        """Load wager data from file"""
        if os.path.exists(self.tracker_file):
            try:
                with open(self.tracker_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_data(self):
        """Save wager data to file"""
        try:
            with open(self.tracker_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error saving wager data: {e}")
    
    def get_user_data(self, user_id: int) -> dict:
        """Get user wager data"""
        user_key = str(user_id)
        if user_key not in self.data:
            self.data[user_key] = {
                'total_deposited': 0,
                'total_wagered': 0,
                'wager_requirement': 0,  # Amount needed to wager
                'can_withdraw': True
            }
        return self.data[user_key]
    
    def record_deposit(self, user_id: int, amount: int):
        """Record a deposit (adds to wager requirement)"""
        user_data = self.get_user_data(user_id)
        user_data['total_deposited'] += amount
        user_data['wager_requirement'] += amount  # 100% wager requirement
        user_data['can_withdraw'] = False  # Must wager first
        self.save_data()
    
    def record_wager(self, user_id: int, amount: int):
        """Record a wager (bet placed)"""
        user_data = self.get_user_data(user_id)
        user_data['total_wagered'] += amount
        
        # Check if wager requirement met
        if user_data['total_wagered'] >= user_data['wager_requirement']:
            user_data['can_withdraw'] = True
        
        self.save_data()
    
    def get_wager_progress(self, user_id: int) -> dict:
        """
        Get wager progress
        
        Returns:
            {
                'required': int,
                'completed': int,
                'remaining': int,
                'percentage': float,
                'can_withdraw': bool
            }
        """
        user_data = self.get_user_data(user_id)
        
        required = user_data['wager_requirement']
        completed = min(user_data['total_wagered'], required)
        remaining = max(0, required - completed)
        percentage = (completed / required * 100) if required > 0 else 100.0
        
        return {
            'required': required,
            'completed': completed,
            'remaining': remaining,
            'percentage': percentage,
            'can_withdraw': user_data['can_withdraw']
        }
    
    def reset_wager_requirement(self, user_id: int):
        """Reset wager requirement after withdrawal"""
        user_data = self.get_user_data(user_id)
        user_data['wager_requirement'] = 0
        user_data['total_wagered'] = 0
        user_data['can_withdraw'] = True
        self.save_data()
