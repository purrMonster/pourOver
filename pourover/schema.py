"""The plan: the only thing the model (or the fast path) is allowed to produce.

Same shape as the `expected` block in eval/generate-eval-set.prompt.md, so
eval results and live behaviour are judged against one format.
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Repeat(_Strict):
    every: int = Field(ge=1, le=365)
    unit: Literal["day", "week", "month"]
    weekday: Optional[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]] = None


class CreateTask(_Strict):
    op: Literal["create_task"] = "create_task"
    title: str = Field(min_length=1, max_length=120)
    project: str
    labels: list[str]
    assignee: str
    due_at: Optional[str] = None  # ISO 8601 with offset
    reminder_at: Optional[str] = None
    repeat: Optional[Repeat] = None
    description: Optional[str] = None


class CompleteTask(_Strict):
    op: Literal["complete_task"] = "complete_task"
    task_id: int


class ListDue(_Strict):
    op: Literal["list_due"] = "list_due"
    scope: Literal["all"] = "all"
    window: Literal["today", "overdue", "week"] = "today"


class DeleteTask(_Strict):
    op: Literal["delete_task"] = "delete_task"
    task_id: int
    requires_confirm: Literal[True] = True


Op = Annotated[Union[CreateTask, CompleteTask, ListDue, DeleteTask], Field(discriminator="op")]

Kind = Literal["plan", "no_plan", "needs_clarification", "refused"]


class Plan(_Strict):
    kind: Kind
    reason: Optional[Literal["not_owner"]] = None
    candidates: Optional[list[int]] = None
    ops: Optional[list[Op]] = None

    @property
    def writes(self) -> bool:
        return any(op.op in ("create_task", "complete_task", "delete_task") for op in self.ops or [])

    @property
    def destructive(self) -> bool:
        return any(op.op == "delete_task" for op in self.ops or [])


def plan_json_schema() -> dict:
    """Full Pydantic schema (documentation, validation)."""
    return Plan.model_json_schema()


_DROP_KEYS = {"default", "title", "minLength", "maxLength", "minimum", "maximum", "discriminator"}


def _wire(node):
    if isinstance(node, dict):
        out = {k: _wire(v) for k, v in node.items() if k not in _DROP_KEYS or k == "properties"}
        if "properties" in node:
            # every property required, in declaration order. llama.cpp's grammar puts required
            # keys first and optional ones after, so an optional "op" could never open an object
            # and the model was steered into list_due (the only variant with nothing required).
            out["properties"] = {k: _wire(v) for k, v in node["properties"].items()}
            out["required"] = list(node["properties"])
            out["additionalProperties"] = False
        return out
    if isinstance(node, list):
        return [_wire(v) for v in node]
    return node


def wire_schema() -> dict:
    """Schema sent to the model as the response grammar.

    Same shape as plan_json_schema(), but grammar-friendly: every key required (nullable ones
    as null), keys in a fixed order with "op" first, and no length limits, which llama.cpp turns
    into huge repetition rules that make sampling crawl. Pydantic still validates the result.
    """
    return _wire(plan_json_schema())
