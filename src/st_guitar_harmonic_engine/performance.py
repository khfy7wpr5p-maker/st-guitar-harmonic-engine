"""Stage 7-G diagnostic performance profiling.

Timing and memory measurements are observability only. They never feed resolver,
confidence, ambiguity, abstention, ranking, or AI authority decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
import statistics
import time
import tracemalloc

from .public_api import PublicRequestMode, validate_public_request
from .public_runtime import execute_public_request


PERFORMANCE_CONTRACT_VERSION = "1.0"
MAX_PERFORMANCE_REPEATS = 100
PERFORMANCE_AUTHORITY = "diagnostic_only"


@dataclass(frozen=True, slots=True)
class PerformanceProfile:
    contract_version: str
    authority: str
    mode: PublicRequestMode
    repeats: int
    median_latency_seconds: float
    max_latency_seconds: float
    retained_bytes_delta: int
    peak_traced_bytes: int
    outputs_stable: bool

    def __post_init__(self) -> None:
        if self.contract_version != PERFORMANCE_CONTRACT_VERSION:
            raise ValueError("unsupported performance contract version")
        if self.authority != PERFORMANCE_AUTHORITY:
            raise ValueError("performance profile must remain diagnostic only")
        if not isinstance(self.mode, PublicRequestMode):
            raise TypeError("mode must be a PublicRequestMode")
        if isinstance(self.repeats, bool) or not isinstance(self.repeats, int):
            raise TypeError("repeats must be an int")
        if not 1 <= self.repeats <= MAX_PERFORMANCE_REPEATS:
            raise ValueError("repeats outside supported range")
        if self.median_latency_seconds < 0 or self.max_latency_seconds < 0:
            raise ValueError("latency measurements cannot be negative")
        if self.peak_traced_bytes < 0:
            raise ValueError("peak traced bytes cannot be negative")
        if not isinstance(self.outputs_stable, bool):
            raise TypeError("outputs_stable must be bool")


def profile_public_request(payload: object, *, repeats: int = 3) -> PerformanceProfile:
    """Measure a validated public request without applying performance policy.

    No latency or memory threshold is authoritative. Correctness is checked by
    comparing every measured output with the first deterministic output.
    """

    if isinstance(repeats, bool) or not isinstance(repeats, int):
        raise TypeError("repeats must be an int")
    if not 1 <= repeats <= MAX_PERFORMANCE_REPEATS:
        raise ValueError("repeats outside supported range")

    validated = validate_public_request(payload)
    expected = execute_public_request(payload)

    started_tracing = not tracemalloc.is_tracing()
    if started_tracing:
        tracemalloc.start()
    before_current, _ = tracemalloc.get_traced_memory()

    latencies: list[float] = []
    stable = True
    try:
        for _ in range(repeats):
            start = time.perf_counter()
            current = execute_public_request(payload)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)
            if current != expected:
                stable = False
        after_current, peak = tracemalloc.get_traced_memory()
    finally:
        if started_tracing:
            tracemalloc.stop()

    return PerformanceProfile(
        contract_version=PERFORMANCE_CONTRACT_VERSION,
        authority=PERFORMANCE_AUTHORITY,
        mode=validated.mode,
        repeats=repeats,
        median_latency_seconds=statistics.median(latencies),
        max_latency_seconds=max(latencies),
        retained_bytes_delta=after_current - before_current,
        peak_traced_bytes=peak,
        outputs_stable=stable,
    )
