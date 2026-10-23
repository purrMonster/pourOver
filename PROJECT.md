---
project: pourOver
status: active
status_reason: v0.1 built and an image published from main; not tagged, not deployed, model accuracy below the eval gate
resume_trigger: n/a
last_activity: 2026-10-22
last_reviewed: 2026-10-23
repo: https://github.com/purrMonster/pourOver
related: ["[[meowGram]]", "[[purrbrews-containers]]", "[[pourover-docs]]"]
tags: [project]
---

# pourOver

## What it is
A translation layer: a plain-text message in meowGram ("kal shaam eggs lena hai") becomes well-filed
Vikunja tasks (project, labels, due, reminder, repeat). A local model on llama-swap writes a JSON plan,
plain code checks it and parses dates, then pourOver files and replies. Vikunja does the rest.
Stack: Python 3.13, FastAPI, SQLite (WAL), httpx, Pydantic; Docker image on GHCR; pytest + GitHub Actions.

## Current state
| Area | State | Evidence |
|---|---|---|
| Code | built: fast path, model path, validator, queue, Vikunja v2 client, meowGram polling bot, ntfy output | [README](README.md), PRs [#1](https://github.com/purrMonster/pourOver/pull/1)–[#7](https://github.com/purrMonster/pourOver/pull/7) on main |
| Release | no tag; image `ghcr.io/purrmonster/pourover:sha-5e4e801` only | [release run](https://github.com/purrMonster/pourOver/actions/runs/39811031983), [release.yml](.github/workflows/release.yml), `git tag` is empty |
| Deployment | not deployed; grinder stack merged with a placeholder digest | purrbrews-containers [runbook 2026-10-21](https://github.com/purrMonster/purrbrews-containers/blob/main/runbook.md) ("Nothing on a node changed"), [stack](https://github.com/purrMonster/purrbrews-containers/tree/main/stacks/grinder/pourover) |
| Tests / CI | passing on main (`ci` and `release` green on 5e4e801); Vikunja contract test runs locally only | [ci.yml](.github/workflows/ci.yml), [contract-vikunja.sh](scripts/contract-vikunja.sh) |
| Model quality | below gate: Gemma 4 12B scored 32% then 36% on set A (gate ≥90% exact); fixes merged in #5, rerun not recorded | [PR #5](https://github.com/purrMonster/pourOver/pull/5); `eval/results/` is empty |

## Open points
1. Tag `v0.1.0` so release.yml publishes `0.1.0`; then pin its digest in purrbrews-containers
   (its `main` fails `test_images_are_pinned` until then).
2. Rerun the gate eval (set A) on Gemma 4 12B and Qwen3.5 9B; commit the reports to `eval/results/`.
   If no model reaches the gate, v1 runs fast path + offline fallback only.
3. Check pourOver's meowGram adapter against meowGram 2.0.0's real bot API (it was written against the
   planned API: sync cursor, `POST /api/messages` body `text_content`, `Idempotency-Key`, `channel_id`).
4. Bring-up on grinder (LLM service account, Vikunja tokens, setup, Gatus alert test): purrbrews-containers
   [stacks/grinder/pourover/README.md](https://github.com/purrMonster/purrbrews-containers/blob/main/stacks/grinder/pourover/README.md).
5. Turn on meowGram's bot sign-in (a separate auth change in purrbrews-containers, per its 2026-10-23 entry).
6. CalDAV reminders on both users' phones (configuration, no code).
7. Decide whether the Vikunja contract test joins CI.
8. Known weakness: messages with several tasks are rarely split into separate tasks by the model.

## Branches
- `app/v0.1-translator`: v0.1 code, merged in #1. Stale.
- `eval/m0-dataset`: eval sets, merged in #2 and #5. Stale.
- `fix/model-schema`: model wire schema fixes, merged via #3/#5. Stale.
- `vikunja/api-v2`: Vikunja API v2 client, merged in #4. Stale.
- `meowgram/adapter`: meowGram bot, merged in #6. Stale.
- `release/ghcr-image`: release workflow and LLM Basic auth, merged in #7. Stale.

## Key decisions
- 2026-10-14 · v1 is a translator only (meowGram → model → Vikunja); Vikunja owns storage, reminders, repeats · pourover-docs `ideas/pourover.md` (private)
- 2026-10-18 · Eval gate: 100% valid, ≥90% exact, 0 wrong deletes, 0 writes from questions · [README → Eval](README.md#eval)
- 2026-10-18 · Plain-code parser owns dates and repeats; the model may not invent them · [abde943](https://github.com/purrMonster/pourOver/commit/abde943)
- 2026-10-19 · Vikunja API v2, pinned to 2.7.0, with a live contract test · [PR #4](https://github.com/purrMonster/pourOver/pull/4)
- 2026-10-19 · "Delete only your own tasks" enforced by pourOver, not Vikunja · [README → Vikunja notes](README.md#vikunja-notes)
- 2026-10-19 · meowGram bot polls, at most once, `@pourover` trigger, channel configurable · [PR #6](https://github.com/purrMonster/pourOver/pull/6)
- 2026-10-20 · Nodes pull a published image, never build; no `latest` tag · [PR #7](https://github.com/purrMonster/pourOver/pull/7)
- 2026-10-21 · Runs on grinder as an optional app, no Traefik route, port for Gatus only · purrbrews-containers [runbook 2026-10-21](https://github.com/purrMonster/purrbrews-containers/blob/main/runbook.md)

## How to resume
1. `git pull` on main, then `git tag v0.1.0 && git push origin v0.1.0`; confirm `0.1.0` appears on GHCR.
2. In purrbrews-containers, pin the digest (`python3 scripts/images.py ghcr.io/purrmonster/pourover:0.1.0`) in a small PR.
3. On roastery, run the gate eval:
   `python -m pourover.evaluate --messages eval/messages.yaml --llm-url http://localhost:9292 --model gemma-4-12b`
   and commit the report.
4. Read meowGram 2.0.0's bot API and adjust `pourover/meowgram.py` if its names differ.
5. Bring up on grinder per the stack README, then the Gatus alert test.

## Decisions to remake
- **Where the runbook lives.** Decisions, backlog and the dated log are in the private `pourover-docs`
  folder, not in this repo, and the repo has no AGENTS.md. Agents and meowmery reading only the repo
  miss the history. Consider moving the runbook (minus anything personal) into `docs/`.
- **The 90% gate.** If the rerun lands well below it (a replay estimate said about 76%), decide
  between shipping fast path + fallback only, a different model, or a different bar.
- **Channel and trigger defaults.** Chosen before meowGram had channels; recheck against 2.0.0.
- **Polling every 3 s.** Fine for the planned API; recheck against meowGram's real rate limits.

## Questions for Roastmaster
- What did the Gemma rerun after #5 score, if it ran? Nothing is committed in `eval/results/`.
- When do you want `v0.1.0` tagged, now or after the eval rerun?
- Does meowGram 2.0.0's bot sync and send match the contract pourOver expects (field and header names, `channel_id`)? Does 2.0.0 have channels?
- Is Vikunja 2.7.0 running on percolator now, so the grinder bring-up can use it?
- Has the second user agreed to native-app reminders and texting through meowGram?
- Should the six merged branches above be deleted?
- Should pourover-docs (or its runbook) move into this repo?

## Card history
- 2026-10-23 · created by Claude
