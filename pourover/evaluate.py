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
import sys
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


def _canon(plan: Optional[Plan]) -> Optional[dict]:
    if plan is None:
        return None
    ops = []
    for op in plan.ops or []:
        d = op.model_dump()
        if op.op == "create_task":
            d["title"] = d["title"].strip().lower()
            d["labels"] = sorted(d["labels"])
            d.pop("description", None)  # free text, not scored
        ops.append(d)
    return {"kind": plan.kind, "reason": plan.reason, "candidates": sorted(plan.candidates or []) or None,
            "ops": ops or None}


def _deletes(plan: Optional[Plan]) -> set[int]:
    return {op.task_id for op in (plan.ops if plan and plan.ops else []) if op.op == "delete_task"}


def score(items: list[dict], world: World, model: Optional[ModelClient]) -> dict:
    rows = []
    for it in items:
        now = datetime.fromisoformat(it["sent_at"])
        expected = Plan.model_validate(it["expected"])
        result = make_plan(it["text"], it["sender"], world, now, model)
        actual = result.plan
        exact = _canon(actual) == _canon(expected)
        wrong_delete = bool(_deletes(actual) - _deletes(expected))
        query_write = it.get("category") == "query" and bool(actual and actual.writes)
        rows.append({
            "id": it["id"], "category": it.get("category"), "text": it["text"], "path": result.path,
            "valid": result.path not in ("invalid",), "exact": exact, "wrong_delete": wrong_delete,
            "query_write": query_write, "errors": result.errors,
            "expected": _canon(expected), "actual": _canon(actual),
        })
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
    }
    summary["go"] = (summary["valid"] >= THRESHOLDS["valid"] and summary["exact"] >= THRESHOLDS["exact"]
                     and summary["wrong_deletes"] == 0 and summary["query_writes"] == 0)
    return {"summary": summary, "rows": rows}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--messages", default="eval/messages.yaml")
    ap.add_argument("--world", default="eval/world.yaml")
    ap.add_argument("--llm-url")
    ap.add_argument("--model", default="none")
    ap.add_argument("--out", default="eval/results")
    args = ap.parse_args(argv)

    items = yaml.safe_load(Path(args.messages).read_text(encoding="utf-8"))
    world = load_world(args.world)
    model = ModelClient(args.llm_url, args.model, timeout=120) if args.llm_url else None
    report = score(items, world, model)
    report["summary"].update({"model": args.model if model else "none (fast path + fallback only)",
                              "messages": args.messages, "run_at": datetime.now().isoformat(timespec="seconds")})

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name = args.model if model else "no-model"
    (out / f"{name}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    s = report["summary"]
    print(f"{s['model']}: {s['count']} messages · valid {s['valid']:.0%} · exact {s['exact']:.0%} · "
          f"wrong deletes {s['wrong_deletes']} · query writes {s['query_writes']} · {'GO' if s['go'] else 'NO GO'}")
    print("by category:", s["by_category"], "· paths:", s["paths"])
    for r in report["rows"]:
        if not r["exact"]:
            print(f"  ✗ {r['id']} [{r['path']}] {r['text']!r}")
    return 0 if s["go"] else 1


if __name__ == "__main__":
    sys.exit(main())
