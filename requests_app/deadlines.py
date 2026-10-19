"""
Charter deadlines.

"12 working hours" in the MUWASCO charter means hours inside MUWASCO's published opening
times, skipping Sundays and Kenyan public holidays. County departments use standard public
service hours. A report made at 16:30 on a Friday with a 12 working-hour target is due at
15:00 the next Monday at MUWASCO (Friday already closed at 16:00; Saturday 08:00-13:00 uses
5 hours; Sunday is closed; Monday supplies the other 7), but at 10:30 on Tuesday at the
county (30 minutes on Friday, 9 hours on Monday, 2.5 on Tuesday).
"""

from datetime import datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

import holidays

NAIROBI = ZoneInfo("Africa/Nairobi")

# weekday() -> (opens, closes). Missing weekdays are closed all day.
CALENDARS = {
    # https://muwasco.co.ke/services.html, "Working Hours"
    "muwasco": {0: (8, 17), 1: (8, 17), 2: (8, 17), 3: (8, 17), 4: (8, 16), 5: (8, 13)},
    # Kenyan public service office hours
    "county": {0: (8, 17), 1: (8, 17), 2: (8, 17), 3: (8, 17), 4: (8, 17)},
}


@lru_cache(maxsize=32)
def _holidays(year):
    return holidays.Kenya(years=year)


def is_holiday(day):
    return day in _holidays(day.year)


def _opening_window(day, calendar):
    """(open, close) as aware datetimes for one calendar day, or None if closed."""
    hours = CALENDARS[calendar].get(day.weekday())
    if hours is None or is_holiday(day):
        return None
    opens, closes = hours
    return (
        datetime.combine(day, time(opens), tzinfo=NAIROBI),
        datetime.combine(day, time(closes), tzinfo=NAIROBI),
    )


def add_working_time(start, duration, calendar):
    """The moment at which `duration` of working time has elapsed after `start`."""
    remaining = duration
    cursor = start.astimezone(NAIROBI)
    # Bounded so a misconfigured calendar can't spin forever: no real target is a year long.
    for _ in range(366 * 2):
        window = _opening_window(cursor.date(), calendar)
        if window:
            opens, closes = window
            begin = max(cursor, opens)
            if begin < closes:
                available = closes - begin
                if remaining <= available:
                    return begin + remaining
                remaining -= available
        cursor = datetime.combine(cursor.date() + timedelta(days=1), time(0), tzinfo=NAIROBI)
    raise ValueError(f"calendar {calendar!r} has no working time within two years of {start}")


def due_at(created_at, category):
    duration = timedelta(hours=category.sla_hours)
    if category.sla_basis == "working":
        return add_working_time(created_at, duration, category.department.calendar)
    return created_at + duration
