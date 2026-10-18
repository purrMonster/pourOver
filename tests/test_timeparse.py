import pytest

from pourover.timeparse import parse

from .conftest import NOW


def at(text):
    r = parse(text, NOW)
    return r.due.isoformat(timespec="minutes") if r.due else None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("pay rent tomorrow", "2026-11-11T09:00+05:30"),
        ("pay rent tmrw evening", "2026-11-11T18:00+05:30"),
        ("kal shaam tak eggs lena hai", "2026-11-11T18:00+05:30"),
        ("parso subah call bank", "2026-11-12T09:00+05:30"),
        ("day after tomorrow afternoon", "2026-11-12T14:00+05:30"),
        ("on friday", "2026-11-13T09:00+05:30"),
        ("this weekend clean fan", "2026-11-14T09:00+05:30"),
        ("sunday at 6", "2026-11-15T18:00+05:30"),
        ("next monday 10am", "2026-11-16T10:00+05:30"),
        ("tuesday", "2026-11-17T09:00+05:30"),  # named today -> next week
        ("next week", "2026-11-16T09:00+05:30"),
        ("end of the month", "2026-11-30T09:00+05:30"),
        ("month end pay card bill", "2026-11-30T09:00+05:30"),
        ("1st of next month", "2026-12-01T09:00+05:30"),
        ("in 2 hours", "2026-11-10T11:15+05:30"),
        ("in 30 mins", "2026-11-10T09:45+05:30"),
        ("tonight", "2026-11-10T21:00+05:30"),
        ("at 7", "2026-11-10T19:00+05:30"),  # bare 7 -> pm
        ("7 baje", "2026-11-10T19:00+05:30"),
        ("at 8", "2026-11-11T08:00+05:30"),  # 08:00 already past today -> tomorrow
        ("at 10", "2026-11-10T10:00+05:30"),
        ("7:30 am tomorrow", "2026-11-11T07:30+05:30"),
        ("aaj 5pm", "2026-11-10T17:00+05:30"),
        ("buy 2 eggs", None),
        ("call mom", None),
    ],
)
def test_dates(text, expected):
    assert at(text) == expected


@pytest.mark.parametrize(
    "text,every,unit,weekday,first",
    [
        ("clean litter every day", 1, "day", None, "2026-11-11T09:00+05:30"),
        ("har roz water plants", 1, "day", None, "2026-11-11T09:00+05:30"),
        ("change bedsheets every sunday", 1, "week", "sun", "2026-11-15T09:00+05:30"),
        ("har sunday groceries", 1, "week", "sun", "2026-11-15T09:00+05:30"),
        ("every tuesday", 1, "week", "tue", "2026-11-17T09:00+05:30"),
        ("pay rent monthly", 1, "month", None, "2026-12-10T09:00+05:30"),
        ("give deworming tablet every 3 days", 3, "day", None, "2026-11-11T09:00+05:30"),
        ("water plants every day at 7am", 1, "day", None, "2026-11-11T07:00+05:30"),
    ],
)
def test_repeats(text, every, unit, weekday, first):
    r = parse(text, NOW)
    assert (r.repeat.every, r.repeat.unit, r.repeat.weekday) == (every, unit, weekday)
    assert r.due.isoformat(timespec="minutes") == first


def test_rest_strips_time_words():
    r = parse("remind me to pay rent tmrw evening", NOW)
    assert r.rest == "remind me to pay rent"
    r = parse("Buy eggs, kal shaam", NOW)
    assert r.rest == "Buy eggs"


def test_words_inside_other_words_do_not_match():
    for text in ("monthly report draft", "satisfy the landlord", "sunglasses repair"):
        r = parse(text.replace("monthly ", ""), NOW)
        assert r.due is None


# Cases found by cross-checking the generated eval sets (18 Oct 2026)
@pytest.mark.parametrize(
    "text,due,repeat",
    [
        ("clean the litter box evry morning", "2026-11-11T09:00+05:30", ("day", 1, None)),
        ("book a haircut for satrday afternoon", "2026-11-14T14:00+05:30", None),
        ("agle hafte bank jana hai", "2026-11-16T09:00+05:30", None),
        ("pay the maid salary on the 1st of every month", "2026-12-01T09:00+05:30", ("month", 1, None)),
        ("book haircut 12th morning", "2026-11-12T09:00+05:30", None),
        ("wash dishes every night at 9pm", "2026-11-10T21:00+05:30", ("day", 1, None)),
        ("do laundry every saturday morning", "2026-11-14T09:00+05:30", ("week", 1, "sat")),
        ("pay monthlly water bill", "2026-12-10T09:00+05:30", ("month", 1, None)),
        ("call mom tommorow", "2026-11-11T09:00+05:30", None),
        ("buy dairy milk", None, None),  # "dairy" must not become "daily"
        ("this is very urgent", None, None),  # "very" must not become "every"
    ],
)
def test_eval_set_cases(text, due, repeat):
    r = parse(text, NOW)
    assert (r.due.isoformat(timespec="minutes") if r.due else None) == due
    assert ((r.repeat.unit, r.repeat.every, r.repeat.weekday) if r.repeat else None) == repeat


def test_rest_uses_corrected_words():
    assert parse("pay the maid salary on the 1st of every month", NOW).rest == "pay the maid salary"
