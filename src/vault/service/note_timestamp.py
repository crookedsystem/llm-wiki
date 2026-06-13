from datetime import date, datetime
from typing import Annotated, TypeAlias

from pydantic import AfterValidator, BeforeValidator, WithJsonSchema

from common.helper.time_helper import TimeHelper

NOTE_TIMESTAMP_UTC_Z_PATTERN = TimeHelper.UTC_TIMESTAMP_Z_PATTERN
_NOTE_TIMESTAMP_FIELD_NAME = "created and updated"


def validate_note_timestamp_input(value: object) -> object:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        raise ValueError(f"{_NOTE_TIMESTAMP_FIELD_NAME} must include time down to seconds")
    if isinstance(value, str) and not TimeHelper.is_utc_timestamp_z(value):
        raise ValueError(
            f"{_NOTE_TIMESTAMP_FIELD_NAME} must use UTC ISO datetime format with seconds "
            "and trailing Z (YYYY-MM-DDTHH:MM:SSZ)"
        )
    return value


def normalize_note_timestamp_to_utc(value: datetime) -> datetime:
    return TimeHelper.normalize_utc_timestamp(value, field_name=_NOTE_TIMESTAMP_FIELD_NAME)


def format_note_timestamp(value: datetime) -> str:
    return TimeHelper.format_utc_timestamp(value, field_name=_NOTE_TIMESTAMP_FIELD_NAME)


NoteTimestamp: TypeAlias = Annotated[
    datetime,
    BeforeValidator(validate_note_timestamp_input),
    AfterValidator(normalize_note_timestamp_to_utc),
    WithJsonSchema(
        {
            "type": "string",
            "format": "date-time",
            "pattern": f"^{NOTE_TIMESTAMP_UTC_Z_PATTERN}$",
            "examples": ["2026-06-12T09:30:45Z"],
        }
    ),
]
