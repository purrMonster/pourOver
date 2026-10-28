# Runbook

pourOver's single record of decisions, changes, work done and work planned. Newest entries first. Every session ends with a dated log entry and a **Where we stopped / next step** line. Story IDs (S…) refer to [planning/backlog.md](planning/backlog.md).

**Status (19 Oct 2026):** main is green (128 tests passed, 6 skipped) with PRs #1–#6 merged. Not deployed. Vikunja client verified against the real Vikunja 2.7.0. Model accuracy not yet at the gate. meowGram adapter built against meowGram's planned bot API, which is not merged yet.

## Where we stopped / next step

1. Owner: `git pull` on roastery, then rerun the gate eval on Gemma, then Qwen3.5 9B (S1.2.3):
   `.\.venv\Scripts\python -m pourover.evaluate --messages eval/messages.yaml --llm-url http://localhost:9292 --model gemma-4-12b`
2. Owner: merge pourOver #7, tag `v0.1.0`, make the GHCR package public; then purrbrews-containers #76 gets its digest and the bring-up starts.
3. Owner: yes or no on adding the Vikunja contract test to CI (S5.2.1).
4. Owner: ask the partner about reminders in her phone's own app and texting via meowGram (S0.1.3).

## Release 1 readiness (19 Oct 2026)

A passing eval is not a release. v1 is releasable when all of these hold:

| Blocker | Owner | Story | State |
| --- | --- | --- | --- |
| Model eval run and reported; if no model reaches the gate, v1 runs fast path + fallback only | Owner | S1.2.3 | First runs 32% → 36%; fixes merged (#5); replay estimate 76%; rerun pending |
| meowGram bot API (bot auth, sender_kind, bot sync, idempotent send) merged | meowGram | S3.1.1 | Not merged; requirements doc handed over |
| The partner agrees to native reminders and texting via meowGram | Owner | S0.1.3 | To ask |
| CalDAV reminders ring on both phones | Owner, partner | S4.1.1–2 | To do (config only) |
| Compose stack on grinder + Gatus check | Claude (PR), owner merges | S5.1.1–2 | To do |
| SQLite in backup, restore drill, MAP, promote to percolator | Both | S5.3.1–2 | To do |
| Contract test in CI | Owner decides | S5.2.1 | Waiting for OK |

Recommended order (owner to pick): do the hardening now (about 2 sessions, fits before 8 Nov) and go live the day meowGram's bot API merges. Not recommended: building meowGram's bot stories inside the pourOver budget (scope creep).

Good enough after release: both use it for two weeks and every reminder that should have rung did. Stop there.

## Decisions

| Date | Decision | Why / note | By |
| --- | --- | --- | --- |
| 2026-10-14 | v1 is a translation layer: meowGram text → local model → well-filed Vikunja tasks. Vikunja does storage, reminders, repeats, sharing | Stir 3; everything else lives in other apps or later versions | Owner |
| 2026-10-14 | Gate 2 bypassed with a guardrail: any free time until 8 Nov; from 9 Nov only the weekly purrBrews slot, max 4 sessions, never in place of the job-switch sprint | If something slips, pourOver slips | Owner |
| 2026-10-14 | Model runs on roastery via llama-swap (about 99% uptime); kettle is a later upgrade; model pick settled by the eval | | Owner |
| 2026-10-14 | v1 commands: add / done / what's due (reports all tasks) / delete (sender's own tasks only, with a yes confirm) | | Owner |
| 2026-10-14 | meowGram is the input (its bot hook treated as available); ntfy is output only (replies to queued messages, errors) | | Owner |
| 2026-10-14 | Reminders through Vikunja CalDAV in the phones' native apps; no own scheduler | | Owner |
| 2026-10-14 | Own public repo `purrMonster/pourOver`; deploy stack in purrbrews-containers | | Owner |
| 2026-10-18 | Planning in Markdown here; move to a GitHub Project once stories are many; never in Vikunja (it is the product's data) | | Owner |
| 2026-10-18 | Eval gate: 100% valid plans, ≥90% exact, 0 wrong deletes, 0 writes on queries. Set A (50) is the gate, set B (51) a cross-check | If no model passes, v1 runs fast path + fallback only | Owner |
| 2026-10-18 | Plain-code parser owns dates, times and repeats; the model may not invent dates | Models invented dates in the first runs | Claude, merged by owner |
| 2026-10-18 | Offline: a message with a time goes to Inbox via the fallback; others queue for 6 h; a message ending in "?" is never filed | | Claude, merged by owner |
| 2026-10-19 | Vikunja client uses API v2, pinned to Vikunja 2.7.0, with a live contract test | v1's `/tasks/all` returns 400 on 2.7.0 | Claude, merged by owner (#4) |
| 2026-10-19 | "Delete own tasks only" is enforced by pourOver | Vikunja lets anyone with write access delete any task in a shared project | Claude, merged by owner (#4) |
| 2026-10-19 | Model gets a grammar-friendly wire schema (every key required, `op` first, no length limits); the app fills `reminder_at` | Optional `op` made llama.cpp's grammar force list_due | Claude, merged by owner (#5) |
| 2026-10-19 | Trust the model's operations over its label; `chores` only on repeating tasks; `pourover` label always added | Fixed bad envelopes in the Gemma run | Claude, merged by owner (#5) |
| 2026-10-19 | meowGram adapter is a polling bot (sync every 3 s), at most once, starts from "now" on first run, ignores bots and unknown senders, replies `@username …` with a retry-safe key | | Claude, merged by owner (#6) |
| 2026-10-19 | Channel is configurable (`MEOWGRAM_CHANNEL`); trigger `@pourover` by default, and can be switched off in a dedicated channel (`MEOWGRAM_TRIGGER=`) | Owner can add channels in meowGram | Owner asked, merged (#6) |
| 2026-10-19 | Contract proposed to meowGram: field and parameter `channel_id`, header `Idempotency-Key`, body `text_content`. Eight open questions in the requirements doc | [meowGram requirements for pourOver](https://claude.ai/code/artifact/e808ef01-c438-4057-8009-54b3715ef2f2) | Pending owner (meowGram side) |
| 2026-10-20 | purrbrews-containers pulls a prebuilt image published by the pourOver repo; nodes never build from source | Owner's call. Proposed (not approved): CI builds after tests and pushes to GHCR `ghcr.io/purrmonster/pourover`, tagged by version and commit; Compose pins a version | Owner |

## Log

- **2026-10-21** · Image and stack built. pourOver [PR #7](https://github.com/purrMonster/pourOver/pull/7): release workflow (tests, then GHCR `ghcr.io/purrmonster/pourover`; `sha-<commit>` on main, `X.Y.Z` on a `v` tag, no `latest`, matching the fleet's pins) and Basic auth plus `LLM_TIMEOUT_S` for the model behind Authelia; 129 tests. purrbrews-containers [PR #76](https://github.com/purrMonster/purrbrews-containers/pull/76) (draft): `stacks/grinder/pourover/`, optional in `fleet.json`, no route, port 8790 open to sieve only for a new Gatus check; 112 fleet tests pass, the image pin waits for the digest.
  **Where we stopped / next step:** owner merges #7, tags `v0.1.0`, makes the GHCR package public; Claude puts the digest into #76; owner names and creates the LLM service account, makes both Vikunja tokens, then the bring-up in that stack's README.

- **2026-10-19 (evening)** · PRs [#5](https://github.com/purrMonster/pourOver/pull/5) (model fixes) and [#6](https://github.com/purrMonster/pourOver/pull/6) (meowGram adapter with configurable channel) merged by owner. main: 128 passed, 6 skipped. Wrote the doc [meowGram requirements for pourOver](https://claude.ai/code/artifact/e808ef01-c438-4057-8009-54b3715ef2f2): 10 requirements with acceptance checks, exact API calls, mapping to meowGram Release 2 (7 of 10 planned; channels are new), 8 open questions. Release 1 readiness reviewed (table above). Safety-net check-in on #5/#6 removed. Backlog and plan statuses updated. This runbook created; the old log in [planning/README.md](planning/README.md) moved here.
  Note: the roastery clone shows 6 files modified on `fix/model-schema`; the change is line endings only (no content), safe to discard with `git checkout -- .` before `git switch main`.
  **Where we stopped / next step:** see the top of this file.
- **2026-10-19** · PRs #2–#4 merged; #3 had landed on the stacked base branch, so [PR #5](https://github.com/purrMonster/pourOver/pull/5) brings its model fixes into main. meowGram adapter (S3.1.1) built as a polling bot against meowGram Release 2's planned bot API: [PR #6](https://github.com/purrMonster/pourOver/pull/6). Gemma runs on roastery: 32% (grammar forced list_due), then 36% (envelope, invented dates); both causes fixed in #5. Median about 15 s a message: check llama-swap runs Gemma with `-ngl 99`.
  **Where we stopped / next step:** owner merges #5, reviews #6; Gemma rerun on main; next build item is the Compose stack (S5.1.1).
- **2026-10-19** · Vikunja contract test (S5.2.1) run against the real Vikunja 2.7.0 that purrBrews pins: the v0.1 client used v1's `/tasks/all`, which 2.7.0 rejects, so every message would have failed. Client moved to API v2; 6 live tests pass, including the service end to end. [PR #4](https://github.com/purrMonster/pourOver/pull/4).
  **Where we stopped / next step:** owner reviews PRs #2–#4, reruns the Gemma eval, decides on the contract test in CI.
- **2026-10-18** · Eval sets added from the owner's generated output: set A (50, the gate) and set B (51); a third set dropped. Cross-checking them fixed parser gaps and an offline bug that filed greetings and questions as tasks. [PR #2](https://github.com/purrMonster/pourOver/pull/2), 103 tests. roastery set up for evals (Python 3.13 via winget, venv).
  **Where we stopped / next step:** owner reviews PR #2; then run both sets on roastery.
- **2026-10-18** · Repo created by owner; v0.1 pushed and [PR #1](https://github.com/purrMonster/pourOver/pull/1) merged. Docs rewritten to the translator shape (S0.1.1–S0.1.2); old design moved to `later/pages-design/`.
  **Where we stopped / next step:** M0 eval set and runs.
- **2026-10-18** · v0.1 code built in a session sandbox: schema, time parser, fast path, model client, validator, planner, Vikunja client, store, queue, replies, FastAPI app, eval runner, Dockerfile, CI. 72 tests against fakes.
  **Where we stopped / next step:** owner creates the repo.
- **2026-10-14** · Stir 3 of the idea; start gates cleared (gate 2 bypassed with the guardrail). Planning folder with epics, features and stories created.
  **Where we stopped / next step:** build v0.1.
