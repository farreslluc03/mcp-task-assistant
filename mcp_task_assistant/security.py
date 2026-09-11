"""
A minimal in-process rate limiter.

Best Practice #2 - Rate Limiting
----------------------------------
This protects the email-sending tool from being used to send a large number
of messages in a short time - whether from a malicious/compromised client,
or an LLM stuck in an accidental retry loop. It is a sliding-window counter
held in memory for the lifetime of the server process.

This is intentionally simple (no external dependency such as Redis) because
this MCP server runs as a single local process for a single user, per the
assignment's scope. In a multi-process or networked deployment, this
in-memory state would need to move to a shared store so the limit is
enforced across all processes - this is called out as a limitation in the
project reflection.

See ``demo/exploit_rate_limit.py`` for a live demonstration.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


class RateLimitExceededError(Exception):
    """Raised when a caller exceeds the allowed call rate."""

    def __init__(self, retry_after_seconds: float):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Rate limit exceeded. Try again in "
            f"{max(retry_after_seconds, 0):.0f} seconds."
        )


@dataclass
class SlidingWindowRateLimiter:
    """Allows at most ``max_calls`` calls per ``window_seconds`` seconds."""

    max_calls: int
    window_seconds: float
    _calls: deque = field(default_factory=deque)

    def check(self) -> None:
        """Raise RateLimitExceededError if calling now would exceed the
        configured limit; otherwise record this call and return normally."""
        now = time.monotonic()

        # Drop timestamps that have aged out of the window.
        while self._calls and now - self._calls[0] > self.window_seconds:
            self._calls.popleft()

        if len(self._calls) >= self.max_calls:
            oldest = self._calls[0]
            retry_after = self.window_seconds - (now - oldest)
            raise RateLimitExceededError(retry_after)

        self._calls.append(now)
