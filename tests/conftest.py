from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pourover.world import load_world

IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime(2026, 11, 10, 9, 15, tzinfo=IST)  # Tuesday, same clock as the eval set
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def now():
    return NOW


@pytest.fixture
def world():
    return load_world(str(ROOT / "eval" / "world.yaml"))
