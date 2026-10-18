"""Eval runner (backlog S1.2.2): messages -> real planner -> score vs expected.

    python -m pourover.evaluate --messages eval/messages.yaml \
        --llm-url http://roastery:8080 --model gemma-4-12b

Runs the same pipeline as the live service (fast path first, then the model),
with no Vikunja writes. Without --llm-url it scores the fast path and offline
fallback only, which is useful as a baseline.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from .model import ModelClient
from .planner import make_plan
from .schema import Plan
from .world import World, load_world

THRESHOLDS = {"valid": 1.0, "exact": 0.9, "wrong_deletes": 0, "query_writes": 0}
CATEGORY_MIX = {"add_simple": 5, "add_time": 10, "add_multi": 5, "add_repeat": 5, "done": 5,
                "query": 5, "delete": 5, "nonsense": 5, "add_assign": 5}


def norm_title(title: str) -> str:
    """Titles are compared without case, punctuation or articles: "Call the vet" == "call vet"."""
    words = re.findall(r"[a-z0-9]+", title.lower())
    return " ".join(w for w in words if w not in ("the", "a", "an"))


def _canon(plan: Optional[Plan]) -> Optional[dict]:
    if plan is None:
        return None
    ops = []
    for op in plan.ops or []:
        d = op.model_dump()
        if op.op == "create_task":
            d["title"] = norm_title(d["title"])
            d["labels"] = sorted(d["labels"])
            d.pop("description", None)  # free text, not scored
        ops.append(d)
    return {"kind": plan.kind, "reason": plan.reason, "candidates": sorted(plan.candidates or []) or None,
            "ops": ops or None}


def _deletes(plan: Optional[Plan]) -> set[int]:
    return {op.task_id for op in (plan.ops if plan and plan.ops else []) if op.op == "delete_task"}


def score(items: list[dict], world: World, model: Optional[ModelClient], progress: bool = False) -> dict:
    rows = []
    for it in items:
        now = datetime.fromisoformat(it["sent_at"])
        expected = Plan.model_validate(it["expected"])
        started = time.monotonic()
        result = make_plan(it["text"], it["sender"], world, now, model)
        seconds = round(time.monotonic() - started, 2)
        actual = result.plan
        exact = _canon(actual) == _canon(expected)
        wrong_delete = bool(_deletes(actual) - _deletes(expected))
        query_write = it.get("category") == "query" and bool(actual and actual.writes)
        rows.append({
            "id": it["id"], "category": it.get("category"), "text": it["text"], "path": result.path,
            "valid": result.path not in ("invalid",), "exact": exact, "wrong_delete": wrong_delete,
            "query_write": query_write, "errors": result.errors,
            "expected": _canon(expected), "actual": _canon(actual), "seconds": seconds,
            "raw": model.last_raw if (model and result.path in ("model", "invalid")) else None,
        })
        if progress:
            mark = "✓" if exact else "✗"
            print(f"  {mark} {it['id']} [{result.path}] {seconds:.1f}s", flush=True)
    n = len(rows) or 1
    by_cat = defaultdict(lambda: [0, 0])
    for r in rows:
        by_cat[r["category"]][0] += r["exact"]
        by_cat[r["category"]][1] += 1
    summary = {
        "count": len(rows),
        "valid": sum(r["valid"] for r in rows) / n,
        "exact": sum(r["exact"] for r in rows) / n,
        "wrong_deletes": sum(r["wrong_delete"] for r in rows),
        "query_writes": sum(r["query_write"] for r in rows),
        "paths": dict(Counter(r["path"] for r in rows)),
        "by_category": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_cat.items())},
        "median_seconds": sorted(r["seconds"] for r in rows)[len(rows) // 2] if rows else 0,
    }
    summary["go"] = (summary["valid"] >= THRESHOLDS["valid"] and summary["exact"] >= THRESHOLDS["exact"]
                     and summary["wrong_deletes"] == 0 and summary["query_writes"] == 0)
    return {"summary": summary, "rows": rows}


def check(items: list[dict], world: World) -> list[str]:
    """Dataset lint: structure, references into the world, and the category mix."""
    from .timeparse import iso, parse

    problems, warnings = [], []
    ids = [it.get("id") for it in items]
    if len(ids) != len(set(ids)):
        problems.append("duplicate ids")
    open_ids = {t.id for t in world.open_tasks()}
    for it in items:
        pid = it.get("id", "?")
        try:
            plan = Plan.model_validate(it["expected"])
        except Exception as exc:
            problems.append(f"{pid}: expected is not a valid plan: {str(exc).splitlines()[0]}")
            continue
        if it.get("sender") not in world.users:
            problems.append(f"{pid}: unknown sender {it.get('sender')!r}")
        if plan.kind != "plan" and plan.ops:
            problems.append(f"{pid}: ops on a {plan.kind}")
        for cid in plan.candidates or []:
            if cid not in open_ids:
                problems.append(f"{pid}: candidate {cid} is not an open task")
        hint = parse(it["text"], datetime.fromisoformat(it["sent_at"]))
        for op in plan.ops or []:
            if op.op == "create_task":
                if op.project not in world.projects:
                    problems.append(f"{pid}: unknown project {op.project!r}")
                if "pourover" not in op.labels or set(op.labels) - set(world.labels):
                    problems.append(f"{pid}: labels {op.labels}")
                if op.reminder_at != op.due_at:
                    problems.append(f"{pid}: reminder_at differs from due_at")
                if op.assignee not in world.users:
                    problems.append(f"{pid}: unknown assignee {op.assignee!r}")
                if op.due_at != iso(hint.due):
                    warnings.append(f"{pid}: due {op.due_at}, date parser says {iso(hint.due)}")
            elif op.op in ("complete_task", "delete_task"):
                task = world.task(op.task_id)
                if task is None or task.id not in open_ids:
                    problems.append(f"{pid}: task {op.task_id} is not an open task")
                elif op.op == "delete_task" and task.owner != it["sender"]:
                    problems.append(f"{pid}: deletes a task the sender doesn't own")
    mix = Counter(it.get("category") for it in items)
    for cat, n in CATEGORY_MIX.items():
        if mix.get(cat, 0) < n:
            warnings.append(f"category {cat}: {mix.get(cat, 0)} (want at least {n})")
    return problems + [f"warning: {w}" for w in warnings]


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--messages", default="eval/messages.yaml")
    ap.add_argument("--world", default="eval/world.yaml")
    ap.add_argument("--llm-url")
    ap.add_argument("--model", default="none")
    ap.add_argument("--out", default="eval/results")
    ap.add_argument("--check", action="store_true", help="only lint the dataset, run nothing")
    args = ap.parse_args(argv)

    items = yaml.safe_load(Path(args.messages).read_text(encoding="utf-8"))
    world = load_world(args.world)
    if args.check:
        found = check(items, world)
        for line in found:
            print(line)
        errors = [f for f in found if not f.startswith("warning:")]
        print(f"{args.messages}: {len(items)} items, {len(errors)} problems, {len(found) - len(errors)} warnings")
        return 1 if errors else 0
    model = ModelClient(args.llm_url, args.model, timeout=120) if args.llm_url else None
    report = score(items, world, model, progress=model is not None)
    report["summary"].update({"model": args.model if model else "none (fast path + fallback only)",
                              "messages": args.messages, "run_at": datetime.now().isoformat(timespec="seconds")})

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name = args.model if model else "no-model"
    (out / f"{name}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    s = report["summary"]
    print(f"{s['model']}: {s['count']} messages · valid {s['valid']:.0%} · exact {s['exact']:.0%} · "
          f"wrong deletes {s['wrong_deletes']} · query writes {s['query_writes']} · median {s['median_seconds']}s · "
          f"{'GO' if s['go'] else 'NO GO'}")
    print("by category:", s["by_category"], "· paths:", s["paths"])
    for r in report["rows"]:
        if not r["exact"]:
            print(f"  ✗ {r['id']} [{r['path']}] {r['text']!r}")
    return 0 if s["go"] else 1


if __name__ == "__main__":
    sys.exit(main())
