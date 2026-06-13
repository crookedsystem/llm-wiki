from datetime import UTC, datetime, timedelta, timezone

import pytest

from common.helper.time_helper import TimeHelper


def test_utc_z_timestamp_문자열_형식을_판별한다() -> None:
    assert TimeHelper.is_utc_timestamp_z("2026-06-12T09:30:45Z") is True
    assert TimeHelper.is_utc_timestamp_z("2026-06-12T09:30:45") is False
    assert TimeHelper.is_utc_timestamp_z("2026-06-12T18:30:45+09:00") is False


def test_utc_timestamp는_초단위_utc_datetime만_정규화한다() -> None:
    # Given: UTC-aware datetime이 있다.
    value = datetime(2026, 6, 12, 9, 30, 45, tzinfo=UTC)

    # When: UTC timestamp로 정규화한다.
    normalized = TimeHelper.normalize_utc_timestamp(value)

    # Then: UTC-aware datetime이 유지된다.
    assert normalized == value
    assert normalized.tzinfo == UTC


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 6, 12, 9, 30, 45),
        datetime(2026, 6, 12, 18, 30, 45, tzinfo=timezone(timedelta(hours=9))),
        datetime(2026, 6, 12, 9, 30, 45, 123, tzinfo=UTC),
    ],
)
def test_utc_timestamp는_naive_offset_subsecond를_거부한다(value: datetime) -> None:
    with pytest.raises(ValueError):
        TimeHelper.normalize_utc_timestamp(value)


def test_utc_timestamp는_z_suffix로_렌더링한다() -> None:
    rendered = TimeHelper.format_utc_timestamp(datetime(2026, 6, 12, 9, 30, 45, tzinfo=UTC))

    assert rendered == "2026-06-12T09:30:45Z"
