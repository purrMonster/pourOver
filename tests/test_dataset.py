"""The committed eval sets must stay internally consistent."""

import pytest
import yaml

from pourover.evaluate import check, norm_title
from pourover.world import load_world

from .conftest import ROOT


@pytest.mark.parametrize("name", ["messages.yaml", "messages-b.yaml", "sample.yaml"])
def test_eval_sets_lint_clean(name):
    items = yaml.safe_load((ROOT / "eval" / name).read_text(encoding="utf-8"))
    world = load_world(str(ROOT / "eval" / "world.yaml"))
    problems = [p for p in check(items, world) if not p.startswith("warning:")]
    assert problems == []


def test_date_parser_agrees_with_main_set():
    items = yaml.safe_load((ROOT / "eval" / "messages.yaml").read_text(encoding="utf-8"))
    world = load_world(str(ROOT / "eval" / "world.yaml"))
    assert [p for p in check(items, world) if "date parser" in p] == []


def test_title_normalisation():
    assert norm_title("Call the vet") == norm_title("call vet") == "call vet"
    assert norm_title("Buy AA batteries!") == "buy aa batteries"
