"""Estimate the vehicle boot clock against local monotonic time."""

from collections import deque
from dataclasses import dataclass
from statistics import median

TIMESYNC_MAX_RTT_NS = 40_000_000
TIMESYNC_STALE_S = 1.0
TIMESYNC_MIN_SAMPLES = 5


@dataclass(frozen=True)
class TimeSyncStatus:
    """Host monotonic nanoseconds minus vehicle boot nanoseconds."""

    offset_ns: int
    rtt_ns: int
    accepted_samples: int
    updated_at: float

    def fresh(self, now: float) -> bool:
        return (self.accepted_samples >= TIMESYNC_MIN_SAMPLES
                and 0 <= now - self.updated_at <= TIMESYNC_STALE_S)


class TimeSyncEstimator:
    def __init__(self):
        self._pending_ns: int | None = None
        self._last_vehicle_ns: int | None = None
        self._offsets: deque[int] = deque(maxlen=TIMESYNC_MIN_SAMPLES)
        self._accepted = 0

    def request(self, now_ns: int) -> int:
        """Return the nonce to send as ts1 with tc1=0."""
        self._pending_ns = now_ns
        return now_ns

    def reply(self, tc1: int, ts1: int, now_ns: int) -> TimeSyncStatus | None:
        if (self._pending_ns is None or ts1 != self._pending_ns or tc1 <= 0
                or not 0 <= now_ns - ts1 <= TIMESYNC_MAX_RTT_NS):
            return None
        self._pending_ns = None
        if self._last_vehicle_ns is not None and tc1 <= self._last_vehicle_ns:
            self._offsets.clear()
            self._accepted = 0
        self._last_vehicle_ns = tc1
        self._offsets.append((ts1 + now_ns) // 2 - tc1)
        self._accepted += 1
        return TimeSyncStatus(round(median(self._offsets)), now_ns - ts1,
                              self._accepted, now_ns / 1e9)
