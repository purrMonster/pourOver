# Planning

Backlog for pourOver v1, the translator: meowGram text → local model → Vikunja tasks, with ntfy as output. Source of truth for scope: [../ideas/pourover.md](../ideas/pourover.md) (stir 3) and the start gates in [../plan.md](../plan.md).

## Hierarchy

| Level | ID | Meaning | Done when |
| --- | --- | --- | --- |
| Epic | E1 | One outcome, usually one milestone | All its features are done |
| Feature | F1.2 | A shippable slice inside an epic | All its stories pass acceptance |
| Story | S1.2.3 | One sitting or less of work | Its acceptance check passes, with evidence in the PR |

Size: **S** under 1 hour, **M** 1–3 hours (one session). Anything bigger gets split.

## Where this lives

- **Now:** this folder, in Markdown. Open-book rule; no tooling needed before the repo exists.
- **When the pourOver repo exists (M1):** move to GitHub. Each story becomes an issue, nested under its feature and epic as sub-issues, on one GitHub Project board for the purrMonster org. PRs close stories. This file then only points to the board.
- **Not Vikunja.** Vikunja is the product's backend: keep development work out of the data pourOver acts on. Using it yourself to dogfood personal tasks is a separate thing.

## Budget (owner's guardrail)

Any free time until 8 Nov; from 9 Nov, only the weekly purrBrews slot, max 4 sessions for v1, never in place of the job-switch sprint. The estimate in [backlog.md](backlog.md) is about 5 sessions, so plan to finish E1 and part of E2 before 8 Nov.

## Log

Moved to [../runbook.md](../runbook.md), which holds decisions, the dated log and the next step.
