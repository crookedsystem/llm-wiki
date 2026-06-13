import re
from datetime import UTC, datetime, timedelta
from typing import ClassVar


class TimeHelper:
    UTC_TIMESTAMP_Z_PATTERN: ClassVar[str] = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
    _UTC_TIMESTAMP_Z: ClassVar[re.Pattern[str]] = re.compile(UTC_TIMESTAMP_Z_PATTERN)

    @classmethod
    def is_utc_timestamp_z(cls, value: str) -> bool:
        return cls._UTC_TIMESTAMP_Z.fullmatch(value) is not None

    @staticmethod
    def normalize_utc_timestamp(
        value: datetime,
        *,
        field_name: str = "timestamp",
    ) -> datetime:
        if value.microsecond:
            raise ValueError(f"{field_name} must not include sub-second precision")
        if value.tzinfo is None:
            raise ValueError(f"{field_name} must use UTC timezone")
        if value.utcoffset() != timedelta(0):
            raise ValueError(f"{field_name} must use UTC timezone")
        return value.astimezone(UTC)

    @classmethod
    def format_utc_timestamp(
        cls,
        value: datetime,
        *,
        field_name: str = "timestamp",
    ) -> str:
        normalized = cls.normalize_utc_timestamp(value, field_name=field_name)
        return normalized.isoformat(timespec="seconds").replace("+00:00", "Z")
