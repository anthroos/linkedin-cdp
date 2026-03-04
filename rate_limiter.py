#!/usr/bin/env python3
"""
Rate limiter for LinkedIn automation.
Prevents account restrictions by enforcing daily limits and delays.
"""
import fcntl
import json
import os
import random
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class RateLimiter:
    """
    Rate limiter with configurable daily limits and delays.
    Persists state to disk to survive restarts.
    """

    # Default daily limits (conservative to avoid blocks)
    DEFAULT_LIMITS = {
        'messages': 50,
        'profile_views': 100,
        'connection_requests': 25,
        'searches': 30,
        'connection_accepts': 50,
    }

    # Minimum delays between actions (seconds)
    DEFAULT_DELAYS = {
        'messages': (30, 60),           # 30-60 seconds between messages
        'profile_views': (10, 30),      # 10-30 seconds between profile views
        'connection_requests': (60, 120), # 1-2 minutes between requests
        'searches': (15, 45),           # 15-45 seconds between searches
        'connection_accepts': (5, 15),   # 5-15 seconds between accepts
    }

    def __init__(
        self,
        state_file: str = None,
        limits: Dict[str, int] = None,
        delays: Dict[str, tuple] = None
    ):
        """
        Initialize rate limiter.

        Args:
            state_file: Path to persist state (default: ~/.linkedin_cdp_state.json)
            limits: Custom daily limits (overrides defaults)
            delays: Custom delays in seconds as (min, max) tuples
        """
        self.state_file = state_file or os.path.expanduser('~/.linkedin_cdp_state.json')
        self.limits = {**self.DEFAULT_LIMITS, **(limits or {})}
        self.delays = {**self.DEFAULT_DELAYS, **(delays or {})}
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load state from disk or create new. Uses file locking to prevent races."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    fcntl.flock(f, fcntl.LOCK_SH)
                    try:
                        state = json.load(f)
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)
                    # Check if state is from today
                    if state.get('date') == datetime.now().strftime('%Y-%m-%d'):
                        return state
        except (json.JSONDecodeError, IOError):
            pass

        # Return fresh state for today
        return self._fresh_state()

    def _fresh_state(self) -> Dict[str, Any]:
        """Create fresh state for a new day."""
        return {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'counts': {
                'messages': 0,
                'profile_views': 0,
                'connection_requests': 0,
                'searches': 0,
                'connection_accepts': 0,
            },
            'last_action': {
                'messages': 0,
                'profile_views': 0,
                'connection_requests': 0,
                'searches': 0,
                'connection_accepts': 0,
            }
        }

    def _save_state(self):
        """Persist state to disk. Uses file locking to prevent races."""
        try:
            with open(self.state_file, 'w') as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    json.dump(self.state, f, indent=2, default=str)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
            os.chmod(self.state_file, 0o600)
        except IOError as e:
            print(f"Warning: Could not save rate limiter state: {e}")

    def _check_date(self):
        """Reset counts if it's a new day."""
        today = datetime.now().strftime('%Y-%m-%d')
        if self.state.get('date') != today:
            self.state = self._fresh_state()
            self._save_state()

    def _can_do(self, action: str) -> bool:
        """Check if action is allowed (under limit)."""
        self._check_date()
        return self.state['counts'].get(action, 0) < self.limits.get(action, 0)

    def _get_delay(self, action: str) -> float:
        """Get required delay before next action of this type."""
        last = self.state['last_action'].get(action, 0)
        if last == 0:
            return 0

        min_delay, max_delay = self.delays.get(action, (0, 0))
        elapsed = time.time() - last

        if elapsed >= max_delay:
            return 0
        elif elapsed >= min_delay:
            # Random delay within remaining window
            return random.uniform(0, max_delay - elapsed)
        else:
            # Must wait at least min_delay
            return min_delay - elapsed

    def _record(self, action: str):
        """Record that an action was performed."""
        self._check_date()
        self.state['counts'][action] = self.state['counts'].get(action, 0) + 1
        self.state['last_action'][action] = time.time()
        self._save_state()

    # Public API - Check methods

    def can_send_message(self) -> bool:
        """Check if can send a message."""
        return self._can_do('messages')

    def can_view_profile(self) -> bool:
        """Check if can view a profile."""
        return self._can_do('profile_views')

    def can_send_connection(self) -> bool:
        """Check if can send a connection request."""
        return self._can_do('connection_requests')

    def can_search(self) -> bool:
        """Check if can perform a search."""
        return self._can_do('searches')

    def can_accept_connection(self) -> bool:
        """Check if can accept a connection."""
        return self._can_do('connection_accepts')

    # Public API - Delay methods

    def get_message_delay(self) -> float:
        """Get delay before next message (seconds)."""
        return self._get_delay('messages')

    def get_profile_delay(self) -> float:
        """Get delay before next profile view (seconds)."""
        return self._get_delay('profile_views')

    def get_connection_delay(self) -> float:
        """Get delay before next connection request (seconds)."""
        return self._get_delay('connection_requests')

    def get_search_delay(self) -> float:
        """Get delay before next search (seconds)."""
        return self._get_delay('searches')

    # Public API - Record methods

    def record_message(self):
        """Record a sent message."""
        self._record('messages')

    def record_profile_view(self):
        """Record a profile view."""
        self._record('profile_views')

    def record_connection_request(self):
        """Record a connection request."""
        self._record('connection_requests')

    def record_search(self):
        """Record a search."""
        self._record('searches')

    def record_connection_accept(self):
        """Record accepting a connection."""
        self._record('connection_accepts')

    # Public API - Info methods

    def get_stats(self) -> Dict[str, Any]:
        """Get current usage statistics."""
        self._check_date()
        stats = {
            'date': self.state['date'],
            'usage': {}
        }
        for action, limit in self.limits.items():
            count = self.state['counts'].get(action, 0)
            stats['usage'][action] = {
                'used': count,
                'limit': limit,
                'remaining': max(0, limit - count),
                'percentage': round(count / limit * 100, 1) if limit > 0 else 0
            }
        return stats

    def get_remaining(self, action: str) -> int:
        """Get remaining count for an action."""
        self._check_date()
        return max(0, self.limits.get(action, 0) - self.state['counts'].get(action, 0))

    def time_until_reset(self) -> str:
        """Get human-readable time until daily reset."""
        now = datetime.now()
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        diff = tomorrow - now
        hours, remainder = divmod(int(diff.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{hours}h {minutes}m"

    def wait_if_needed(self, action: str) -> float:
        """Wait for required delay if needed. Returns actual wait time."""
        delay = self._get_delay(action)
        if delay > 0:
            print(f"  Rate limit: waiting {delay:.1f}s before {action}...")
            time.sleep(delay)
        return delay

    def print_stats(self):
        """Print formatted usage statistics."""
        stats = self.get_stats()
        print(f"\n📊 LinkedIn Rate Limiter - {stats['date']}")
        print("=" * 45)
        for action, data in stats['usage'].items():
            bar_len = 20
            filled = int(data['percentage'] / 100 * bar_len)
            bar = '█' * filled + '░' * (bar_len - filled)
            status = '⚠️' if data['percentage'] >= 80 else '✓'
            print(f"{status} {action:20} [{bar}] {data['used']}/{data['limit']}")
        print(f"\nResets in: {self.time_until_reset()}")


# Convenience function for quick checks
def check_limits():
    """Print current rate limit status."""
    limiter = RateLimiter()
    limiter.print_stats()


if __name__ == '__main__':
    check_limits()
