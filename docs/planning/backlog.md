# Backlog: pourOver v1 (translator)

Status: `todo` · `doing` · `built` (code + tests exist, not yet in a merged PR) · `built*` (built, tested against fakes only: needs a real Vikunja / model run) · `done` · `cut`. Milestone column matches the build order: M0 eval → M1 service → M2 channels → M3 harden.

## E0 Docs alignment (paper, before M0)

| ID | Story | Acceptance | Size | MS | Status |
| --- | --- | --- | --- | --- | --- |
| S0.1.1 | Rewrite README, requirements, architecture to the translator shape; move the page/widget design to "later" | No doc describes own store, view specs or widgets as v1 | M | – | done |
| S0.1.2 | Rewrite plan.md milestones to M0–M3 below | Milestones match this backlog | S | – | done |
| S0.1.3 | Ask the partner: reminders in her phone's own app, texting via meowGram OK? | Answer recorded on the idea card | S | – | todo |

## E1 Eval and model (M0)

**F1.1 Eval set**

| ID | Story | Acceptance | Size | MS | Status |
| --- | --- | --- | --- | --- | --- |
| S1.1.1 | Write 50 messages from real tasks: Hinglish, typos, multi-task, times, repeats, done, what's due, deletes, 5 nonsense | 50 messages in `eval/messages.yaml`, no personal data (rewritten where needed) | M | M0 | done |
| S1.1.2 | Expected result per message (Vikunja payload or "no plan") | Every message has an expected result | M | M0 | done |

**F1.2 Plan schema and runner**

| ID | Story | Acceptance | Size | MS | Status |
| --- | --- | --- | --- | --- | --- |
| S1.2.1 | Define the plan JSON schema: create_tasks, complete, list_due, delete | Schema file plus 3 example plans that validate | S | M0 | done |
| S1.2.2 | Eval runner: messages → llama-swap with the schema enforced → score vs expected | One command runs all 50 and prints a score | M | M0 | done |
| S1.2.3 | Run on Gemma 4 12B, Qwen3.5 9B and the game-mode 4B; commit the report | Report per model in `eval/results/`; go if ≥90% exact, 100% valid, 0 wrong deletes | S | M0 | doing (Gemma 32% → 36%, fixes merged #5, rerun pending) |

## E2 Translator service (M1)

**F2.1 Skeleton**

| ID | Story | Acceptance | Size | MS | Status |
| --- | --- | --- | --- | --- | --- |
| S2.1.1 | FastAPI app: `/inbound` (text, user, channel), `/healthz`; SQLite (WAL): command log, queue, pending confirms | curl to `/inbound` writes a command-log row | S | M1 | done |

**F2.2 Understanding text**

| ID | Story | Acceptance | Size | MS | Status |
| --- | --- | --- | --- | --- | --- |
| S2.2.1 | Time parsing in plain code (today, tomorrow 9, Fri evening, in 2 hours, every Sunday) | Unit tests: 100% on the time cases from the eval set | M | M1 | done |
| S2.2.2 | Fast path for simple add / done / what's due, no model | These work with llama-swap stopped | S | M1 | done |
| S2.2.3 | Model path: context (existing projects, labels, users) + text fenced as data → plan | Eval set passes through the real service at the M0 score | M | M1 | built* (needs the model at the M0 score) |
| S2.2.4 | Validator: schema, existing projects/labels/users only; anything else → "couldn't file that, nothing changed" | Nonsense and invented-project cases produce no writes | S | M1 | done |
| S2.2.5 | Queue for AI-needing messages while roastery is off; 6 h expiry; anything with a time never queues | Stop llama-swap, send, start it: task created and result sent | S | M1 | built* (needs a live stop/start test) |

**F2.3 Vikunja client**

| ID | Story | Acceptance | Size | MS | Status |
| --- | --- | --- | --- | --- | --- |
| S2.3.1 | Create tasks (title, project, due, reminder, repeat, labels, assignee, description), each labelled "pourover" | A multi-task message creates N correct tasks | M | M1 | done |
| S2.3.2 | Mark done | "done renew insurance" completes the matching task; two matches → ask which | S | M1 | done |
| S2.3.3 | What's due: reports all tasks the sender can see, due today and overdue first | Read only; the command log shows no writes | S | M1 | done |
| S2.3.4 | Delete: only the sender's own tasks, after "reply yes" | Deleting someone else's task is refused; nothing goes without a yes | S | M1 | done |
| S2.3.5 | User mapping: meowGram user → Vikunja user and token (secrets in .env, placeholders in .env.example) | The partner's messages create tasks as her | S | M1 | done |

**F2.4 Replies**

| ID | Story | Acceptance | Size | MS | Status |
| --- | --- | --- | --- | --- | --- |
| S2.4.1 | Reply echoes what was filed: project, due, reminder, repeat | Every write has a reply that matches Vikunja | S | M1 | done |

## E3 Channels (M2)

| ID | Story | Acceptance | Size | MS | Status |
| --- | --- | --- | --- | --- | --- |
| S3.1.1 | meowGram adapter: bot messages in → `/inbound`, replies back to the same chat (hook assumed available) | A message in meowGram creates a task and gets a reply | M | M2 | built* (merged #6; waits for meowGram bot API) |
| S3.1.2 | Write meowGram's requirements for the bot API (auth, sync, idempotent send, channels) | Doc handed to meowGram with acceptance checks | S | M2 | done ([doc](https://claude.ai/code/artifact/e808ef01-c438-4057-8009-54b3715ef2f2)) |
| S3.2.1 | ntfy output: errors and queued results to the sender's topic with an access token | A queued result arrives on ntfy; topic not readable without the token | S | M2 | built* |

## E4 Reminders via CalDAV (config, no code)

| ID | Story | Acceptance | Size | MS | Status |
| --- | --- | --- | --- | --- | --- |
| S4.1.1 | Owner's phone: Vikunja CalDAV in the native reminders app | A pourOver task with a reminder rings on the phone | S | M2 | todo |
| S4.1.2 | The partner's phone, same (after S0.1.3) | Her reminder rings on her phone | S | M2 | todo |

## E5 Ops and hardening (M3)

| ID | Story | Acceptance | Size | MS | Status |
| --- | --- | --- | --- | --- | --- |
| S5.1.0 | Publish the image from pourOver: CI builds the Dockerfile after tests pass and pushes to GHCR, tagged `vX.Y.Z` and `sha-<commit>` | A tagged release shows up in GHCR and `docker pull` works on grinder without a login | S | M3 | built ([PR #7](https://github.com/purrMonster/pourOver/pull/7); also adds LLM Basic auth) |
| S5.1.1 | Compose stack in purrbrews-containers: pinned GHCR image (no local build), healthcheck, restart unless-stopped, internal only behind Traefik | Deploys on grinder from main | S | M3 | built (purrbrews-containers [#76](https://github.com/purrMonster/purrbrews-containers/pull/76), draft until the image digest) |
| S5.1.2 | Gatus check on `/healthz` | Stopping the container alerts | S | M3 | built (purrbrews-containers [#76](https://github.com/purrMonster/purrbrews-containers/pull/76), draft until the image digest) |
| S5.2.1 | CI: pytest (time parser, validator, fast path) + Vikunja contract test against a pinned container | CI green on the PR | M | M3 | built (pytest in CI; contract step waits for owner OK) |
| S5.3.1 | SQLite in the purrBrews backup; restore drill | Restore tested, evidence in the runbook | S | M3 | todo |
| S5.3.2 | Runbook entry + MAP update; promote to percolator | Dated entry; MAP shows pourOver | S | M3 | todo |

## Later (not v1, no stories until v1 is in daily use)

Morning plan and prioritising · nags · edits and moves by text · Mealie groceries · Home Assistant · voice · MCP/API · own pages and widgets (shelved design in ../architecture.md and ../design-spec.md)

## Estimate

E1 ≈ 1.5 sessions · E2 ≈ 2.5 · E3 ≈ 0.5 · E4 ≈ config time · E5 ≈ 1. **Total ≈ 5–6 sessions**, slightly over the 4-session cap after 8 Nov, so use the pre-8 Nov window for E0 and E1.
