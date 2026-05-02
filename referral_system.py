"""
Referral System
- Admins create codes with /makecode
- Players claim codes for 10M free GP
- Referrer earns 10% of house edge on all referred player bets
- DM notifications to referrer on earnings
"""
import json
import os

REFERRAL_FILE = 'referral_data.json'
REFERRAL_BONUS = 10_000_000  # 10M free GP for claiming a code
REFERRAL_RATE = 0.10  # 10% of house edge goes to referrer


class ReferralSystem:
    def __init__(self):
        self.codes = {}       # {code: owner_user_id}
        self.referred_by = {} # {user_id: referrer_user_id}
        self.earnings = {}    # {user_id: total_earned}
        self._load()

    def _load(self):
        if os.path.exists(REFERRAL_FILE):
            try:
                with open(REFERRAL_FILE, 'r') as f:
                    data = json.load(f)
                self.codes = data.get('codes', {})
                self.referred_by = data.get('referred_by', {})
                self.earnings = data.get('earnings', {})
            except Exception:
                pass

    def _save(self):
        try:
            with open(REFERRAL_FILE, 'w') as f:
                json.dump({
                    'codes': self.codes,
                    'referred_by': self.referred_by,
                    'earnings': self.earnings,
                }, f, indent=2)
        except Exception:
            pass

    def create_code(self, code, owner_id):
        """Create a referral code for a user"""
        code = code.lower().strip()
        if code in self.codes:
            return False, "Code already exists!"
        self.codes[code] = owner_id
        self._save()
        return True, f"Code '{code}' created!"

    def delete_code(self, code):
        """Delete a referral code"""
        code = code.lower().strip()
        if code not in self.codes:
            return False, "Code not found!"
        del self.codes[code]
        self._save()
        return True, f"Code '{code}' deleted!"

    def claim_code(self, code, user_id):
        """Claim a referral code"""
        code = code.lower().strip()
        user_key = str(user_id)

        if user_key in self.referred_by:
            return False, "You already used a referral code!", None

        if code not in self.codes:
            return False, "Invalid code!", None

        referrer_id = self.codes[code]
        if referrer_id == user_id:
            return False, "You can't use your own code!", None

        self.referred_by[user_key] = referrer_id
        self._save()
        return True, f"Code claimed! You received **{REFERRAL_BONUS:,} GP**!", referrer_id

    def get_referrer(self, user_id):
        """Get who referred this user"""
        return self.referred_by.get(str(user_id))

    def add_earning(self, referrer_id, amount):
        """Add referral earnings"""
        key = str(referrer_id)
        if key not in self.earnings:
            self.earnings[key] = 0
        self.earnings[key] += amount
        self._save()

    def get_earnings(self, user_id):
        """Get total referral earnings"""
        return self.earnings.get(str(user_id), 0)

    def calculate_referral_bonus(self, user_id, bet_amount, house_edge_rate=0.05):
        """
        Calculate referral bonus from a bet.
        Returns (referrer_id, bonus_amount) or (None, 0)
        """
        referrer_id = self.get_referrer(user_id)
        if not referrer_id:
            return None, 0

        # House edge from this bet
        house_edge = int(bet_amount * house_edge_rate)
        # Referrer gets 10% of house edge
        bonus = int(house_edge * REFERRAL_RATE)

        if bonus > 0:
            self.add_earning(referrer_id, bonus)

        return referrer_id, bonus

    def get_code_info(self, code):
        """Get info about a code"""
        code = code.lower().strip()
        if code not in self.codes:
            return None
        owner_id = self.codes[code]
        # Count how many people used this code
        used_count = sum(1 for uid, rid in self.referred_by.items() if rid == owner_id)
        return {
            'code': code,
            'owner_id': owner_id,
            'used_count': used_count,
            'total_earned': self.earnings.get(str(owner_id), 0)
        }

    def get_all_codes(self):
        """Get all codes with info"""
        result = []
        for code, owner_id in self.codes.items():
            used = sum(1 for uid, rid in self.referred_by.items() if rid == owner_id)
            earned = self.earnings.get(str(owner_id), 0)
            result.append({
                'code': code,
                'owner_id': owner_id,
                'used_count': used,
                'total_earned': earned
            })
        return result
