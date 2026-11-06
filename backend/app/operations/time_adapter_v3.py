"""Bound business UTC conversion before datetime arithmetic; never use timestamps."""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

EPOCH_AT: Final = datetime(2026, 10, 30, tzinfo=UTC)
BUSINESS_FACTOR: Final = 60
_MAX_DELTA: Final = datetime.max.replace(tzinfo=UTC) - EPOCH_AT
MAX_SIM_MS: Final = (_MAX_DELTA.days * 86400000 + _MAX_DELTA.seconds * 1000 + _MAX_DELTA.microseconds // 1000) // BUSINESS_FACTOR
MIN_SIM_MS: Final = -((EPOCH_AT - datetime.min.replace(tzinfo=UTC)).days * 86400000 // BUSINESS_FACTOR)


@dataclass(slots=True)  # noqa: MUTABLE_OK
class TimeAdapterError(ValueError):
    """Exception traceback fields remain mutable across context-manager boundaries."""
    code: str
    detail: str
    http_status: int = 422

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def utc_only(value: datetime) -> datetime:
    """Accept aware UTC only, without silently shifting nonzero offsets."""
    if value.utcoffset() != timedelta(0):
        raise TimeAdapterError("utc_required", value.isoformat())
    if value.microsecond % 1000:
        raise TimeAdapterError("time_out_of_range", "submillisecond UTC is unsupported")
    return value


def sim_ms_to_utc(sim_ms: int) -> datetime:
    """Convert exact integer simulation ms; signed values support UTC year one."""
    if type(sim_ms) is not int or not MIN_SIM_MS <= sim_ms <= MAX_SIM_MS:
        raise TimeAdapterError("time_out_of_range", str(sim_ms))
    return EPOCH_AT + timedelta(milliseconds=sim_ms * BUSINESS_FACTOR)


def canonical_utc(value: datetime) -> str:
    """Return platform-independent four-digit years and fixed millisecond precision."""
    value = utc_only(value)
    return f"{value.year:04d}-{value.month:02d}-{value.day:02d}T{value.hour:02d}:{value.minute:02d}:{value.second:02d}.{value.microsecond // 1000:03d}Z"


def sim_ms_to_iso(sim_ms: int) -> str:
    return canonical_utc(sim_ms_to_utc(sim_ms))
