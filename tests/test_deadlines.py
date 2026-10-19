from datetime import datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from requests_app.deadlines import CALENDARS, NAIROBI, add_working_time, is_holiday


def at(*args):
    return datetime(*args, tzinfo=NAIROBI)


def brute_force_working_seconds(start, end, calendar):
    """Count working seconds minute by minute: slow and obviously correct."""
    total = 0
    t = start
    while t < end:
        step_end = min(end, (t.replace(second=0, microsecond=0) + timedelta(minutes=1)))
        hours = CALENDARS[calendar].get(t.weekday())
        if hours and not is_holiday(t.date()) and hours[0] <= t.hour < hours[1]:
            total += (step_end - t).total_seconds()
        t = step_end
    return total


@pytest.mark.parametrize("calendar,start,hours,expected", [
    # The deadlines module docstring examples, in a week with no holiday (Friday 24 Oct 2025, 16:30).
    ("muwasco", at(2025, 10, 24, 16, 30), 12, at(2025, 10, 27, 15, 0)),
    ("county", at(2025, 10, 24, 16, 30), 12, at(2025, 10, 28, 10, 30)),
    # The week before, Monday 20 Oct is Mashujaa Day, so both move on a day.
    ("muwasco", at(2025, 10, 17, 16, 30), 12, at(2025, 10, 21, 15, 0)),
    ("county", at(2025, 10, 17, 16, 30), 12, at(2025, 10, 22, 10, 30)),
    # Reported before opening: the clock starts at 08:00.
    ("county", at(2025, 11, 3, 6, 0), 2, at(2025, 11, 3, 10, 0)),
    # Ends exactly at closing time: due at closing, not next morning.
    ("county", at(2025, 11, 3, 8, 0), 9, at(2025, 11, 3, 17, 0)),
    # MUWASCO works Saturday mornings; the county does not.
    ("muwasco", at(2025, 11, 8, 9, 0), 3, at(2025, 11, 8, 12, 0)),
    ("county", at(2025, 11, 8, 9, 0), 3, at(2025, 11, 10, 11, 0)),
    # What the browser showed on 19 Oct 2026: 14:59 Monday + 45 county hours, with Mashujaa Day (Tue 20th).
    ("county", at(2026, 10, 19, 14, 59), 45, at(2026, 10, 27, 14, 59)),
])
def test_worked_examples(calendar, start, hours, expected):
    assert add_working_time(start, timedelta(hours=hours), calendar) == expected


def test_christmas_and_boxing_day_are_skipped():
    # Wed 24 Dec 2025 16:00 + 2 county hours: 1 h on the 24th, then 25th and 26th are holidays.
    assert add_working_time(at(2025, 12, 24, 16, 0), timedelta(hours=2), "county") == at(2025, 12, 29, 9, 0)


starts = st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2026, 12, 1)).map(lambda d: d.replace(tzinfo=NAIROBI))


@settings(max_examples=150, deadline=None)
@given(start=starts, minutes=st.integers(min_value=1, max_value=60 * 30), calendar=st.sampled_from(list(CALENDARS)))
def test_due_time_contains_exactly_the_target_of_working_time(start, minutes, calendar):
    due = add_working_time(start, timedelta(minutes=minutes), calendar)
    assert due > start
    assert brute_force_working_seconds(start, due, calendar) == pytest.approx(minutes * 60)
    # and not a moment later than needed: the due time is inside (or at the end of) working hours
    hours = CALENDARS[calendar].get(due.weekday())
    assert hours and not is_holiday(due.date())
    assert (hours[0], 0) <= (due.hour, due.minute) <= (hours[1], 0)


@settings(max_examples=100, deadline=None)
@given(a=starts, b=starts, calendar=st.sampled_from(list(CALENDARS)))
def test_reporting_later_never_gives_an_earlier_deadline(a, b, calendar):
    early, late = sorted([a, b])
    d = timedelta(hours=12)
    assert add_working_time(early, d, calendar) <= add_working_time(late, d, calendar)
