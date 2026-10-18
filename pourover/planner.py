"""Text in, validated plan out. No side effects: the service applies plans,
the eval runner only scores them."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional

from .fastpath import create_from_text, fast_plan
from .model import InvalidPlan, ModelClient, ModelUnavailable
from .schema import Plan
from .timeparse import parse
from .validator import check, normalise, not_owned_deletes
from .world import World

Path = Literal["fast", "model", "fallback", "queue", "invalid"]


@dataclass
class PlanResult:
    plan: Optional[Plan]
    path: Path
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.plan is not None and not self.errors


def make_plan(text: str, sender: str, world: World, now: datetime, model: Optional[ModelClient]) -> PlanResult:
    plan = fast_plan(text, sender, world, now)
    path: Path = "fast"

    if plan is None:
        hint = parse(text, now)
        try:
            if model is None:
                raise ModelUnavailable("no model configured")
            plan = model.plan(text, sender, world, now, hint)
            path = "model"
        except InvalidPlan as exc:
            return PlanResult(None, "invalid", [f"model output unusable: {exc}"])
        except ModelUnavailable:
            if not hint.found or text.rstrip().endswith("?") or not hint.rest.strip():
                return PlanResult(None, "queue")
            # Anything with a time never waits for the model: file it in Inbox now.
            plan = Plan(kind="plan", ops=[create_from_text(text, text, sender, "Inbox", world, now)])
            path = "fallback"

    plan = normalise(plan)
    if plan.kind == "plan" and not_owned_deletes(plan, sender, world):
        return PlanResult(Plan(kind="refused", reason="not_owner"), path)
    errors = check(plan, sender, world)
    return PlanResult(plan if not errors else None, path if not errors else "invalid", errors)
