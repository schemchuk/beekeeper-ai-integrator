from datetime import UTC, datetime, timedelta, timezone

import pytest

from beekeeper.factory.calendar import (
    BERLIN,
    deadlines,
    is_release_slot,
    next_release_slot,
    release_slots,
)


def berlin(y, mo, d, h=0, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=BERLIN)


def test_next_slots_are_tuesday_and_thursday_8am():
    # Thursday 2026-11-26, 11:00
    slots = release_slots(berlin(2026, 11, 26, 11), 4)
    assert slots == [
        berlin(2026, 12, 1, 8),
        berlin(2026, 12, 3, 8),
        berlin(2026, 12, 8, 8),
        berlin(2026, 12, 10, 8),
    ]


def test_slot_on_the_same_day_before_8am_counts():
    assert next_release_slot(berlin(2026, 12, 1, 7, 59)) == berlin(2026, 12, 1, 8)


def test_slot_exactly_now_is_not_after():
    assert next_release_slot(berlin(2026, 12, 1, 8)) == berlin(2026, 12, 3, 8)


def test_input_in_other_timezone():
    kyiv_like = timezone(timedelta(hours=2))
    # 2026-12-01 08:30 at UTC+2 is 07:30 in Berlin: Tuesday's slot is still ahead
    assert next_release_slot(datetime(2026, 12, 1, 8, 30, tzinfo=kyiv_like)) == berlin(
        2026, 12, 1, 8
    )


def test_naive_datetime_refused():
    with pytest.raises(ValueError):
        next_release_slot(datetime(2026, 12, 1, 8))


def test_is_release_slot():
    assert is_release_slot(berlin(2026, 12, 3, 8))
    assert not is_release_slot(berlin(2026, 12, 2, 8))  # Wednesday
    assert not is_release_slot(berlin(2026, 12, 3, 9))


def test_deadlines_of_a_tuesday():
    d = deadlines(berlin(2026, 12, 8, 8))
    assert d.ask == berlin(2026, 12, 3, 8)
    assert d.ask_reply_by == berlin(2026, 12, 4, 20)
    assert d.script == berlin(2026, 12, 5, 2)
    assert d.send == berlin(2026, 12, 5, 7)
    assert d.accept == berlin(2026, 12, 7, 7)
    assert d.release == berlin(2026, 12, 8, 8)


def test_deadlines_refuse_a_non_slot():
    with pytest.raises(ValueError):
        deadlines(berlin(2026, 12, 9, 8))


def test_due_lists_passed_deadlines_for_catch_up():
    d = deadlines(berlin(2026, 12, 8, 8))
    assert d.due(berlin(2026, 12, 3, 7)) == []
    # laptop asleep from Thursday to Saturday 09:00: four deadlines are due at once
    assert d.due(berlin(2026, 12, 5, 9)) == ["ask", "ask_reply_by", "script", "send"]


def test_spring_dst_keeps_local_hours():
    # Summer time starts on Sunday 2027-03-28; release Tuesday 2027-03-30
    d = deadlines(berlin(2027, 3, 30, 8))
    assert d.script.utcoffset() == timedelta(hours=1)  # Saturday, still CET
    assert d.release.utcoffset() == timedelta(hours=2)  # CEST
    assert d.script.astimezone(UTC).hour == 1
    assert d.release.astimezone(UTC).hour == 6


def test_autumn_dst_keeps_local_hours():
    # Winter time starts on Sunday 2026-10-25; release Tuesday 2026-10-27
    d = deadlines(berlin(2026, 10, 27, 8))
    assert d.ask_reply_by.utcoffset() == timedelta(hours=2)  # Thursday 22nd, CEST
    assert d.accept.utcoffset() == timedelta(hours=1)  # Monday 26th, CET
    assert d.accept.astimezone(UTC).hour == 6


def test_slots_across_dst_are_always_8am_local():
    slots = release_slots(berlin(2027, 3, 20), 4)
    assert [s.astimezone(BERLIN).hour for s in slots] == [8, 8, 8, 8]
    assert [s.astimezone(UTC).hour for s in slots] == [7, 7, 6, 6]
