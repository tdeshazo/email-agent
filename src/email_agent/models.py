from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

DEFAULT_TIME_DELTA = timedelta(hours=1)
DEFAULT_MAX_RESULTS = 50


@dataclass(frozen=True)
class RunConfig:
    time_delta: timedelta
