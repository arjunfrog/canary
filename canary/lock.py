"""Rules for unlocking the app: a few tries, then a wait. No Qt in here, so it is easy to test."""
import time


class LockGuard:
    def __init__(self, max_tries: int = 5, delay: float = 60.0, clock=time.monotonic):
        self.max_tries, self.delay, self._clock = max_tries, delay, clock
        self._failures = 0
        self._blocked_until = 0.0

    def blocked_for(self) -> float:
        """Seconds until another try is allowed. 0 means go ahead."""
        return max(0.0, self._blocked_until - self._clock())

    def failed(self) -> None:
        self._failures += 1
        if self._failures >= self.max_tries:
            self._failures = 0
            self._blocked_until = self._clock() + self.delay

    def succeeded(self) -> None:
        self._failures = 0
        self._blocked_until = 0.0
