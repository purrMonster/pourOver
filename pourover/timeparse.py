"""Plain-code date, time and repeat parsing. No model involved.

Anything with a time must work while roastery is off, so this module carries
the whole "when" part of a message. The rules match section 3 of
eval/generate-eval-set.prompt.md:

- a named weekday is the next one strictly after today ("Tuesday" said on a
  Tuesday means next week);
- no time given -> 09:00; morning 09:00, afternoon 14:00, evening 18:00,
  night/tonight 21:00;
- a bare hour with no am/pm: 1-7 -> pm, 8-11 -> am, 12 -> noon;
- "in N hours/minutes" counts from the message time.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Optional

from .schema import Repeat

WEEKDAYS = {
    "mon": 0, "monday": 0,
    "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "weds": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}
WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_WD = r"(mon|monday|tue|tues|tuesday|wed|weds|wednesday|thu|thur|thurs|thursday|fri|friday|sat|saturday|sun|sunday)"

PART_OF_DAY = {
    "morning": time(9), "subah": time(9),
    "afternoon": time(14), "dopahar": time(14),
    "evening": time(18), "shaam": time(18), "sham": time(18),
    "night": time(21), "tonight": time(21), "raat": time(21),
}

DEFAULT_TIME = time(9)

# Typos people actually make. Exact fixes for short words; one-letter fuzzy
# matching only for longer words where a near miss can't be another word
# ("daily" is left out on purpose: "dairy" is one letter away).
TYPO_FIXES = {"evry": "every", "evrey": "every", "eveyr": "every", "tmrow": "tomorrow", "tomrow": "tomorrow"}
FUZZY_WORDS = [
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "tomorrow", "monthly", "weekly", "morning", "evening", "afternoon", "tonight",
]


def _one_edit(a: str, b: str) -> bool:
    if a == b or abs(len(a) - len(b)) > 1:
        return a == b
    if len(a) == len(b):
        diffs = [i for i in range(len(a)) if a[i] != b[i]]
        if len(diffs) == 1:
            return True
        # one swap of neighbours ("tomorow" vs "tommorow" is handled by length, this covers "fridya")
        return len(diffs) == 2 and diffs[1] == diffs[0] + 1 and a[diffs[0]] == b[diffs[1]] and a[diffs[1]] == b[diffs[0]]
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def _fix_word(m: re.Match) -> str:
    word = m.group(0)
    low = word.lower()
    if low in TYPO_FIXES:
        return TYPO_FIXES[low]
    if len(low) >= 5 and low not in WEEKDAYS:
        for good in FUZZY_WORDS:
            if low != good and _one_edit(low, good):
                return good
    return word


def fix_typos(text: str) -> str:
    return re.sub(r"[A-Za-z]+", _fix_word, text)


@dataclass
class TimeResult:
    due: Optional[datetime] = None
    repeat: Optional[Repeat] = None
    rest: str = ""  # the message with the time words removed
    matched: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.due is not None or self.repeat is not None


class _Text:
    """Mutable lowercase text; matched spans are blanked out so they can't match twice."""

    def __init__(self, text: str):
        self.original = text
        self.low = text.lower()
        self.mask = list(self.low)

    def find(self, pattern: str):
        s = "".join(self.mask)
        return re.search(pattern, s)

    def take(self, m: re.Match, matched: list[str]) -> None:
        matched.append(self.original[m.start():m.end()].strip())
        for i in range(m.start(), m.end()):
            self.mask[i] = " "

    def rest(self) -> str:
        kept = [" " if (k == " " and lo != " ") else o for o, lo, k in zip(self.original, self.low, self.mask)]
        out = re.sub(r"\s+", " ", "".join(kept))
        out = re.sub(r"\s+([,.;:!?])", r"\1", out)
        return out.strip(" ,.;:-")


def _next_weekday(today: date, weekday: int, include_today: bool = False) -> date:
    delta = (weekday - today.weekday()) % 7
    if delta == 0 and not include_today:
        delta = 7
    return today + timedelta(days=delta)


def _end_of_month(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def _first_of_next_month(d: date) -> date:
    return (d.replace(day=1) + timedelta(days=32)).replace(day=1)


def _bare_hour(h: int) -> int:
    if 1 <= h <= 7:
        return h + 12
    return h  # 8-11 am, 12 noon


def parse(text: str, now: datetime) -> TimeResult:
    t = _Text(fix_typos(text))
    res = TimeResult()
    today = now.date()
    day: Optional[date] = None
    at: Optional[time] = None
    absolute: Optional[datetime] = None

    # --- repeats -------------------------------------------------------
    for pattern, builder in (
        (r"\bevery\s+(\d{1,3})\s+days?\b", lambda m: Repeat(every=int(m.group(1)), unit="day")),
        (r"\bevery\s+(\d{1,2})\s+weeks?\b", lambda m: Repeat(every=int(m.group(1)), unit="week")),
        (r"\b(?:every|har)\s+" + _WD + r"\b", lambda m: Repeat(every=1, unit="week", weekday=WEEKDAY_KEYS[WEEKDAYS[m.group(1)]])),
        (r"\b(?:every\s*day|everyday|daily|har\s+roz|roz)\b", lambda m: Repeat(every=1, unit="day")),
        (r"\b(?:every|har)\s+(?=(?:morning|afternoon|evening|night|subah|dopahar|shaam|raat)\b)", lambda m: Repeat(every=1, unit="day")),
        (r"\b(?:every\s+week|weekly|har\s+hafte|har\s+hafta)\b", lambda m: Repeat(every=1, unit="week")),
        (r"\b(?:every\s+month|monthly|har\s+mahine|har\s+mahina)\b", lambda m: Repeat(every=1, unit="month")),
    ):
        m = t.find(pattern)
        if m:
            res.repeat = builder(m)
            t.take(m, res.matched)
            break

    # --- relative offsets ("in 2 hours") ------------------------------
    m = t.find(r"\bin\s+(\d{1,3})\s*(hours?|hrs?|h|minutes?|mins?|m)\b")
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        delta = timedelta(hours=n) if unit.startswith("h") else timedelta(minutes=n)
        absolute = (now + delta).replace(second=0, microsecond=0)
        t.take(m, res.matched)

    # --- dates ---------------------------------------------------------
    if absolute is None:
        for pattern, resolver in (
            (r"\b(?:day\s+after\s+tomorrow|parso|parson)\b", lambda m: today + timedelta(days=2)),
            (r"\b(?:tomorrow|tmrw|tmrrw|tomorow|tommorow|tommorrow|tmr|kal)\b", lambda m: today + timedelta(days=1)),
            (r"\b(?:today|aaj|tonight)\b", lambda m: today),
            (r"\b(?:end\s+of\s+(?:the\s+)?month|month\s*end)\b", lambda m: _end_of_month(today)),
            (r"\b(?:1st|first)\s+of\s+next\s+month\b|\bnext\s+month\b", lambda m: _first_of_next_month(today)),
            (r"\b(?:this\s+)?weekend\b", lambda m: _next_weekday(today, 5, include_today=False)),
            (r"\b(?:next\s+week|agle\s+hafte|agle\s+week|next\s+wk)\b", lambda m: _next_weekday(today, 0)),
            (r"\b(?:on\s+)?(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\b(?:\s+of\b)?", lambda m: _day_of_month(today, int(m.group(1)))),
            (r"\b(?:next\s+|this\s+|on\s+)?" + _WD + r"\b", lambda m: _next_weekday(today, WEEKDAYS[m.group(1)])),
        ):
            m = t.find(pattern)
            if m:
                resolved = resolver(m)
                if resolved is None:
                    continue
                day = resolved
                # "tonight" also carries a time; leave the word for the time pass
                if m.group(0).strip() == "tonight":
                    at = PART_OF_DAY["tonight"]
                t.take(m, res.matched)
                break

    # --- times ---------------------------------------------------------
    if absolute is None:
        m = t.find(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b")
        if m:
            h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
            if 1 <= h <= 12 and mi < 60:
                h = h % 12 + (12 if ap == "pm" else 0)
                at = time(h, mi)
                t.take(m, res.matched)
        if at is None:
            m = t.find(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*baje\b") or t.find(r"\bat\s+(\d{1,2})(?::(\d{2}))?\b")
            if m:
                h, mi = int(m.group(1)), int(m.group(2) or 0)
                if 0 <= h <= 23 and mi < 60:
                    at = time(_bare_hour(h) if h <= 12 else h, mi)
                    t.take(m, res.matched)
        m = t.find(r"\b(?:in\s+the\s+)?(morning|subah|afternoon|dopahar|evening|shaam|sham|night|tonight|raat)\b")
        if m:
            if at is None:
                at = PART_OF_DAY[m.group(1)]
            t.take(m, res.matched)

    # --- combine -------------------------------------------------------
    tz = now.tzinfo
    if absolute is not None:
        res.due = absolute
    elif day is None and at is not None and res.repeat is not None:
        res.due = _first_repeat(res.repeat, now, at)
    elif day is not None or at is not None:
        d = day or today
        clock = at or DEFAULT_TIME
        due = datetime.combine(d, clock, tzinfo=tz)
        if day is None and due <= now:  # only a time, already past -> tomorrow
            due += timedelta(days=1)
        res.due = due
    elif res.repeat is not None:
        res.due = _first_repeat(res.repeat, now)

    res.rest = t.rest()
    return res


def _day_of_month(today: date, n: int) -> Optional[date]:
    """"the 12th": this month if still ahead (or today), else next month."""
    if not 1 <= n <= 31:
        return None
    if n >= today.day and n <= calendar.monthrange(today.year, today.month)[1]:
        return today.replace(day=n)
    nxt = _first_of_next_month(today)
    return nxt.replace(day=min(n, calendar.monthrange(nxt.year, nxt.month)[1]))


def _first_repeat(rep: Repeat, now: datetime, clock: time = DEFAULT_TIME) -> datetime:
    """Next matching occurrence for a repeat with no date in the message."""
    tz = now.tzinfo
    today = now.date()
    if rep.unit == "week" and rep.weekday:
        d = _next_weekday(today, WEEKDAY_KEYS.index(rep.weekday), include_today=True)
        due = datetime.combine(d, clock, tzinfo=tz)
        return due if due > now else due + timedelta(days=7)
    due = datetime.combine(today, clock, tzinfo=tz)
    if due > now:
        return due
    if rep.unit == "month":
        nxt = _first_of_next_month(today)
        day = min(today.day, calendar.monthrange(nxt.year, nxt.month)[1])
        return datetime.combine(nxt.replace(day=day), clock, tzinfo=tz)
    return due + timedelta(days=1)


def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat(timespec="seconds") if dt else None
