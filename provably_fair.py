"""
Provably Fair System - HMAC-SHA256 based
Server seed + Client seed + Nonce = Verifiable result
"""
import hashlib
import hmac
import secrets


class ProvablyFair:
    """Per-game provably fair session"""

    def __init__(self):
        self.server_seed = secrets.token_hex(32)
        self.server_seed_hash = hashlib.sha256(self.server_seed.encode()).hexdigest()
        self.client_seed = secrets.token_hex(16)
        self.nonce = 0

    def roll(self, max_value=100):
        """Generate a provably fair number 0 to max_value-1"""
        self.nonce += 1
        message = f"{self.server_seed}:{self.client_seed}:{self.nonce}"
        h = hmac.new(self.server_seed.encode(), message.encode(), hashlib.sha256).hexdigest()
        return int(h[:8], 16) % max_value

    def get_seeds(self):
        """Return seed data for embed display"""
        return {
            'server_seed_hash': self.server_seed_hash,
            'client_seed': self.client_seed,
            'nonce': self.nonce,
            'server_seed': self.server_seed
        }


# Legacy compatibility
class GameSession:
    """Wrapper for backwards compat with existing games"""

    def __init__(self):
        self._pf = ProvablyFair()

    def play(self, max_value):
        result = self._pf.roll(max_value)
        return result, self._pf.server_seed_hash[:16]

    def get_seeds(self):
        return self._pf.get_seeds()
