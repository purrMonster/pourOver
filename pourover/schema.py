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
    """JSON schema handed to llama.cpp so the model cannot return anything else."""
    return Plan.model_json_schema()
