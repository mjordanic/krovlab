"""In-memory per-IP limits for POST /agent. Last line of defence, not auth."""

from __future__ import annotations

import time


class RateLimiter:
    """Sliding windows. Per Cloud Run instance; the provider spend cap is the fuse."""

    def __init__(self, *, per_minute: int = 8, per_hour: int = 30) -> None:
        self.per_minute = per_minute
        self.per_hour = per_hour
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str, *, now: float | None = None) -> bool:
        stamp = time.monotonic() if now is None else now
        hits = [t for t in self._hits.get(key, []) if stamp - t < 3600.0]
        minute = sum(1 for t in hits if stamp - t < 60.0)
        if minute >= self.per_minute or len(hits) >= self.per_hour:
            self._hits[key] = hits
            return False
        hits.append(stamp)
        self._hits[key] = hits
        return True
