# pourOver

Text a task in meowGram; it lands in Vikunja, filed properly. You pour text in, it brews a task.

**Status (19 Oct 2026):** PRs #1–#6 merged, 128 tests green. Not deployed. Vikunja client verified against the real Vikunja 2.7.0; model eval rerun pending; meowGram bot API not merged yet.

| Doc | What it holds |
| --- | --- |
| [requirements.md](requirements.md) | What v1 must do, with acceptance checks |
| [architecture.md](architecture.md) | Components, message flow, plan format, safety rules, deployment |
| [plan.md](plan.md) | Start gates, milestones, risks, good-enough line |
| [runbook.md](runbook.md) | Decisions, dated log, release readiness, next step |
| [planning/](planning/) | Backlog: epics, features, stories and their status |
| [ideas/pourover.md](ideas/pourover.md) | How the idea got here (three stirs) and every assumption |
| [eval/](eval/) | Prompt for generating the 50-message eval set |
| [later/](later/) | Shelved designs (own pages, widgets, themes); not v1 |

Code: this repo ([purrMonster/pourOver](https://github.com/purrMonster/pourOver)); its top-level README is the technical reference. These planning docs lived in a separate local `pourover-docs` folder until 2026-10-28.

## The idea

pourOver is a thin translation layer. A message like "remind me to pay rent tmrw evening" or "kal shaam eggs aur bread lena hai" comes in from meowGram. A local model turns it into a plan, the app checks the plan, and the tasks appear in Vikunja with the right project, labels, due time, reminder and repeat. Vikunja then does everything else: storage, reminders, repeats, sharing, editing.

**Purpose:** nothing with a time attached gets dropped, for both of us, without anyone opening a heavy app.
**Goal:** the first route of a text front door to purrBrews.
**Side effect:** local-LLM work for the AI track (structured output, evals, a guarded agent loop).

## Who does what

| Part | Job |
| --- | --- |
| meowGram | Where messages are typed (input) and where replies appear |
| pourOver | Understands the text, checks it, files it, replies |
| llama-swap on roastery | The model, behind an OpenAI-compatible endpoint |
| Vikunja (percolator) | The store: tasks, projects, labels, reminders, repeats, sharing |
| Phones' native reminders | Ring the reminders, through Vikunja's CalDAV |
| ntfy | Output only: results of queued messages, and errors |
| Gatus | Watches `/healthz` |

## Not in v1

Morning plan and prioritising, nagging, editing or moving tasks by text, Mealie groceries, Home Assistant, voice, MCP or a public API, own pages and widgets ([later/](later/)), cloud models.
