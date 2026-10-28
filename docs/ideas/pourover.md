---
title: pourOver
status: ready
type: app
depth: standard
created: 2026-10-13
last_stirred: 2026-10-14
stirs: 3
revisit_on:
reason:
merged_into:
score:
  value: 4
  effort: 4
  energy: 4
  reuse: 5
  total: 17
related: ["[[vikunja]]", "[[smart-mirror]]", "[[calicortado]]", "[[personal-ai-ecosystem]]", "[[kettle-ai-node]]", "[[meowgram]]"]
tags: [idea, purrbrews]
---

## The idea in one line
A thin translation layer: plain text from meowGram (ntfy as backup) → local model → well-formed Vikunja tasks. Vikunja does everything else. (Stir 3; was a lists app in stir 1, a full tasks app in stir 2.)

## Real goal behind it
Purpose: nothing with a time gets dropped, for both owner and partner, without anyone opening a heavy UI.
Goal: a text front door to purrBrews; this is its first route.
Side effect: local-LLM portfolio material (structured output, evals).

## Passes
### 2026-10-14 · Stir 1 · Ingest, Expand, Interrogate, Stress-test, Converge, Verdict
- Ingest: original idea (13 Oct) had per-topic pages customised by the model writing HTML/CSS, charts, templates, AI-ranked homepage, text control; voice/API/caliCortado/HA later. A full design set already exists in pourover-docs (README, requirements, architecture, design-spec, plan). Analysis on 14 Oct found three problems in it: v1 scope bigger than its success test, Mealie overlap, multi-user undo undesigned.
- Expand: four shapes. A as designed (own app, view-spec pages, 12–16 sessions); B command layer over Mealie/HA lists; C HA-native to-do + Assist; D MCP-first store. Reuse: llama-swap, Traefik/Authelia, scratchPost FastAPI+SQLite pattern, ntfy, Mealie, HA, Open WebUI. The 50-command eval set doubles as a portfolio piece.
- Interrogate: shape = A, staged. Pages use a fixed widget kit that the model picks from; no model-written markup, ever. Stage 1 keeps pourOver's own tiny store (not Mealie/HA), takes input by chat message (ntfy first, meowGram later), queues AI commands while roastery is off, and runs solo; the partner joins later.
- Note: choosing "own store" means this is really A, chat-first, not B. Fine, but the tap UI and the partner are now explicitly stage 2.
- Stress-test (pre-mortem, dead in 6 weeks because…):
  1. Input channel down: meowGram's server lived on roastery, formatted 7 Oct. → ntfy first; inputs sit behind one adapter interface.
  2. Solo + chat-only never grows into the shared list, so the purpose is never met. → Hard trigger: stage 2 (tap page + the partner) starts after 3 weeks of daily solo use.
  3. Freeze / job switch eats it, or it eats the job switch. → Build only at the plan's start gates; docs-only work until then.
  4. Queued AI results land after the shop trip. → Queue entries expire (default 6 h) and report "expired, nothing changed".
  5. ntfy topics are open by default, so anyone who can reach a topic can command the house. → ntfy access control with per-user tokens; the user comes from the token, never from message text.
  Cost: stage 1 ≈ 4–6 sessions, ₹0. Upkeep is moderate and tied to roastery's uptime. No deal-breaker.
- Converge: smallest version and out-of-scope below. Blocking question: none.

### 2026-10-14 · Stir 2 · Expand, Interrogate, Stress-test, Converge, Verdict
- Changed since stir 1: nothing new; the owner reframed the project as a reminders and tasks app.
- Expand: time becomes the core. Reminders and repeats move from out of scope into v1. The reliability bar jumps (one missed reminder breaks trust). Times can't wait on the AI queue: parse them with plain code and fire from an always-on node. The owner's notification rules (quiet hours 00–08, notify only when actionable now, the rest to the dashboard or mirror, low-energy mode) become product requirements. Overlap moves from Mealie to Vikunja, Nextcloud Tasks and phone reminders. Biggest risk: turning into Vikunja.
- Interrogate: for both owner and partner from day one (reverses stir 1's "solo first"). Own store + scheduler + ntfy (not CalDAV, not Vikunja's API). AI role is plan + prioritise + nag. Recurring is a simple set (daily, weekly on a day, monthly on a date, every N days).
- Stress-test (dead in 6 weeks because…):
  1. A reminder fails to fire, and trust is gone. → Scheduler on an always-on node (percolator after the restore test, never roastery); a minute tick; catch-up after downtime that says "fired late"; healthchecks.io dead-man; ntfy upstream relay for iOS.
  2. Too many nags, owner mutes the topic, and the whole system goes quiet. → A nag budget per day; nag only when actionable now; quiet hours; anything else goes to the morning plan, not a push; after 3 snoozes ask "drop, reschedule or break down?".
  3. The partner is on day one with a chat-only, half-finished tool and quits, which poisons stage 2. → She gets only her own and assigned tasks, uses tap-only ntfy buttons (Done / Snooze / Tomorrow), and is never nagged unless she opts in.
  4. It turns into Vikunja. → No priority field (AI ranks), no subtask tree (breakdown makes plain tasks tagged with a parent), no labels or projects beyond topics, no forms.
  5. Morning plan with roastery off. → A plain-code fallback plan: overdue, then due today, then oldest open.
  Cost: about 8–10 sessions (was 4–6). Upkeep is higher: reliability work and nag tuning. ₹0.
- Converge: see the handoff. Blocking question: none. The partner's buy-in is now a day-one assumption, so check it before building.
- Score: value 5 (daily procrastination relief, both users, feeds the mirror and the job-switch steps); effort 2 (scheduler, repeats, policy engine, two users); energy 2 (reliability work you own, nag tuning); reuse 5 (ntfy, healthchecks, llama-swap, the mirror's morning brief, HA later, portfolio agent loop). Total 14, unchanged; different shape.

### 2026-10-14 · Stir 3 · Interrogate (autonomous), Stress-test, Converge, Verdict
- Changed since stir 2: owner changed his mind. pourOver becomes a translation layer between meowGram and Vikunja, with ntfy as support. The AI only turns plain text into ideal Vikunja tasks; everything else goes to other apps or later versions. Owner asked for autonomous decisions.
- Decisions (autonomous, from known preferences: boring and reliable, reuse over rebuild, light by feel, actionable-only notifications):
  - Vikunja (percolator, currently set aside) is the store, the reminder engine, the repeat engine, the sharing and the UI. Its UI being heavy no longer matters, because nobody has to open it to add things.
  - Reminders reach phones through Vikunja's CalDAV → the phone's native reminders app (zero code, reliable, the partner never sees Vikunja). This replaces stir 2's own scheduler, policy engine and nags.
  - meowGram is the main input. ntfy is the backup input while meowGram is down, and the channel for pourOver's own errors. Both call one `/inbound` endpoint (text, user, channel). The meowGram bot adapter lives in the meowGram repo, as a separate PR.
  - Identity: meowGram/ntfy user → mapped Vikunja user, each with its own API token (secret, never committed). The partner's messages create tasks as her.
  - v1 verbs: add (one or many), done, what's due (read-only), undo (deletes only tasks pourOver itself just created). Edits, moves and deletes happen in Vikunja or the phone.
  - "Ideal manner" = clean title, an existing project only, due and reminder times, repeat, existing labels only, assignee, a short description if the message carries detail; multi-task messages are split. Every write gets a "pourover" label.
  - Times are parsed in plain code first; the model fills in the rest. Messages with a time but no AI need still work with roastery off; AI-needing messages queue (6 h expiry) and reply "queued".
  - Every reply echoes exactly what was created (project, due, reminder, repeat) plus one-word undo, so a wrong guess shows up straight away.
  - pourOver keeps only a small SQLite: command log, undo journal, queue. Stateless otherwise. Host: grinder for the beta, percolator later.
- Stress-test (dead in 6 weeks because…):
  1. meowGram not rebuilt after the move → no input. → ntfy works from day one; "meowGram running" added to the start gates.
  2. Model misfiles silently (wrong project or date). → Echo on every reply, the "pourover" label, one-word undo, a 50-message eval of expected Vikunja payloads.
  3. A Vikunja upgrade breaks the API. → Pin the Vikunja version; a contract test in CI against a pinned container.
  4. The partner finds it heavy. → She only texts in meowGram and gets native phone reminders; she never needs Vikunja's UI.
  5. Scope creeps back to stir 2. → The later-versions list below is the only place new ideas go.
  Cost: about 3–4 sessions (was 8–10). ₹0. Upkeep is low: three dependencies (meowGram, Vikunja, roastery), but no state worth backing up beyond Vikunja itself.
- Score: value 4 (reliable capture and reminders for both users, but no planning or nagging); effort 4 (thin service, create-mostly); energy 4 (stateless; the pain sits in its dependencies); reuse 5 (revives Vikunja, gives meowGram a job, ntfy, CalDAV, llama-swap, eval portfolio, the seam for MCP and voice). Total 17.

## Assumptions to confirm
- Chat input: ntfy or meowGram first → assumed ntfy first (meowGram's server is down since the roastery format); meowGram adapter when meowGram is rebuilt
- Queue expiry → assumed 6 hours (stir 2: AI commands only; anything with a time never queues)
- Stage 2 trigger → (stir 1) assumed 3 weeks of daily solo use; superseded in stir 2: stage 2 = the tap/web page, triggered by 3 weeks of daily use by both users
- the partner wants reminders from it on day one → assumed yes, opt-in to nags only (stir 2; ask her)
- Morning plan time → assumed 08:30 IST via ntfy (stir 2)
- Nag budget → assumed at most 3 pushes a day for the owner outside the morning plan (stir 2)
- Scheduler host → assumed grinder for beta, percolator after the restore test (stir 2; stir 3: no scheduler, same hosts for pourOver)
- Reminder delivery → assumed Vikunja CalDAV to native phone reminders (stir 3)
- v1 verbs → assumed add, done, what's due, undo-own-creates only (stir 3)
- New start gate → assumed "meowGram server running after the move" (stir 3)
- Vikunja version → assumed pinned to whatever percolator runs at rebuild (stir 3)
- Build start → assumed unchanged: the start gates in pourover-docs/plan.md

- 2026-10-14 confirmed by owner: CalDAV reminders yes; delete allowed for the sender's own tasks only (confirm step), what's due reports all tasks; meowGram is the input (bot hook treated as available), ntfy is output only; own repo yes. Start gates cleared (gate 2 bypassed: any free time until 8 Nov, then weekly slot only)

## Verdict
ready (17/20) · Stir 3: a thin meowGram/ntfy → AI → Vikunja translator. Vikunja and the phone handle storage and reminders. Smallest and best-scoring shape so far. Building still waits for the start gates.

## Handoff
# pourOver v1 (translator): requirements brief
**Goal:** text a task in meowGram, and it lands in Vikunja correctly filed, with reminders on your phone.
**Users:** owner and the partner, each mapped to their own Vikunja account.
**Smallest useful version:**
- FastAPI service with one `/inbound` endpoint (text, user, channel); input: meowGram bot (next meowGram release, treated as available); output: meowGram replies plus ntfy for errors and queued results
- Plain-code time parsing first; fast path for simple adds and dones with no model
- Model path (llama-swap, JSON-schema plan): split multi-task messages, clean titles, choose an existing project and labels, due/reminder/repeat, assignee, description
- Validator: existing projects, labels and users only; schema check; anything else → "couldn't file that, nothing changed"
- Vikunja client: create task(s), mark done, list what's due (all tasks), delete the sender's own tasks after a confirm; every write labelled "pourover"
- Reply echoes what was created, plus undo (deletes pourOver's own last creates)
- Queue for AI-needing messages while roastery is off (6 h expiry); errors go to the owner via ntfy
- SQLite: command log, undo journal, queue
- 50-message eval set (Hinglish and typos included) with expected Vikunja payloads; results committed per model
**Delegated to other apps:** storage, reminders, repeats, sharing, editing, UI → Vikunja; reminder alerts → phone native apps over CalDAV; uptime → Gatus
**Later versions:** morning plan and prioritising (v2, via n8n or the mirror), nags, edits and moves by text, Mealie groceries, HA and voice, MCP/API, own pages and widgets (the original pourover-docs design, now shelved)
**Constraints:** purrBrews conventions (Compose, pinned, healthcheck, restart unless-stopped, Traefik internal only, Gatus, runbook, MAP); public repo, no personal data; LAN-only model; weekly slot
**Reuses:** Vikunja (percolator), meowGram, ntfy (sieve), llama-swap (roastery), the scratchPost pattern, the plan/validator design from pourover-docs/architecture.md
**Risks and mitigations:** see stir 3's stress-test
**Open questions:** does meowGram have a bot/webhook hook, or does the adapter need a meowGram change? CalDAV on the partner's phone: which app?
**First step:** paper only. Rewrite pourover-docs to the translator shape (most of the current design moves to "later"). Ask the partner whether native phone reminders suit her. No code until the start gates (now including meowGram running) are ticked.
