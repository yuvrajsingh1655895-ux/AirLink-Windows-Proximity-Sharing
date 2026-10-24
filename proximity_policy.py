"""Conservative proximity gate. RSSI is a noisy proxy, not a metre-accurate sensor."""
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional

class State(str, Enum):
    ALLOWED = "allowed"
    TOO_FAR = "too_far"
    UNPAIRED = "unpaired"
    DISCONNECTED = "disconnected"
    STALE = "stale"
    UNSTABLE = "unstable"
    NO_SIGNAL = "no_signal"

@dataclass(frozen=True)
class Decision:
    state: State
    allowed: bool
    estimated_metres: Optional[float]
    reason: str

class ProximityPolicy:
    def __init__(self, target_metres=5.0, minimum_rssi_dbm=-65, required_samples=3, max_spread_db=8):
        self.target_metres = target_metres
        self.minimum_rssi_dbm = minimum_rssi_dbm  # illustrative; calibrate per hardware/environment
        self.required_samples = required_samples
        self.max_spread_db = max_spread_db

    def evaluate(self, rssi_dbm, connected, paired, samples: Iterable[int]=(), fresh=True):
        if not paired:
            return Decision(State.UNPAIRED, False, None, "Device is not paired.")
        if not connected:
            return Decision(State.DISCONNECTED, False, None, "Wireless link is disconnected.")
        if not fresh:
            return Decision(State.STALE, False, None, "Signal measurement is stale.")
        if rssi_dbm is None:
            return Decision(State.NO_SIGNAL, False, None, "No signal measurement available.")
        values = list(samples)
        if len(values) < self.required_samples:
            return Decision(State.UNSTABLE, False, None, f"Need {self.required_samples} recent samples.")
        if max(values) - min(values) > self.max_spread_db:
            return Decision(State.UNSTABLE, False, None, "Signal fluctuates too much; sample again.")
        # Illustrative propagation estimate only; not a guaranteed physical distance.
        n, reference_at_1m = 2.2, -40
        metres = max(0.1, min(100.0, 10 ** ((reference_at_1m-rssi_dbm)/(10*n))))
        if rssi_dbm < self.minimum_rssi_dbm:
            return Decision(State.TOO_FAR, False, metres, f"Signal weaker than policy threshold ({self.minimum_rssi_dbm} dBm).")
        return Decision(State.ALLOWED, True, metres, "Signal passed threshold; this does not prove a 5 m boundary.")
