# pourOver

A self-hosted tasks app where every topic is its own page, shaped by a local model and driven by typed instructions.

**Status:** design only, parked. No code exists. Nothing gets built until the start gates in [plan.md](plan.md) are met.

| Doc | What it holds |
| --- | --- |
| [requirements.md](requirements.md) | What v1 must do, with acceptance criteria |
| [architecture.md](architecture.md) | Components, data model, command pipeline, view spec, deployment, security |
| [design-spec.md](design-spec.md) | Screens, widgets, theme tokens, interactions, copy |
| [plan.md](plan.md) | Start gates, milestones, estimates, risks |
| [examples/](examples/) and [templates/](templates/) | The plan, view-spec and template formats as standalone files |

## Summary

Two instructions show the idea. "Open a new topic for grocery shopping" creates a Groceries page. "Add the ingredients for palak paneer" fills it with items grouped by veg, dairy and staples, quantities in metric.

Working name: pourOver. You pour text in, it brews a page.

## Problem and goals

Vikunja is too heavy and too loaded for day-to-day lists, so it sits unused. Task apps also give every list the same shape, and changing anything means tapping through forms. The other purrBrews apps each cover one slice: Vikunja (tasks, too heavy), Mealie (recipes and shopping lists), Homepage (links). None take plain instructions or reshape a page to fit what's on it.

Goals for v1:

- Create and change topics and items with plain text; forms optional.
- Give each topic a layout that fits it (checklist, table or bar chart), chosen by text.
- Run fully on purrBrews with a local model. No data leaves the LAN.
- Stay usable when the model is offline: taps and simple commands always work.
- Be reliable enough for shared household lists.
- Full of features, light by feel: lightness is how it feels to use, not how few features it has.

Non-goals:

- Project management: no dependencies, sprints or time tracking.
- Model-written HTML, CSS or JavaScript in v1 ([architecture.md](architecture.md) explains why).
- Cloud models by default.
- Replacing caliCortado. pourOver holds lists, not notes or documents.

## Users and use cases

Two users: the owner (admin) and a second household member. No guest access.

| Use case | Instruction | Result |
| --- | --- | --- |
| Groceries | "Add the ingredients for palak paneer to groceries" | Items grouped by category, metric quantities, marked as AI-suggested |
| Quick capture | "add milk, eggs to groceries" | Two items added through the fast path, no model call |
| Reshape | "show groceries as a table by category" | View changes; data untouched |
| Track | "new topic: books, track pages read per week as a bar chart" | Topic with a number field and a bar chart |
| Tidy | "clear everything done from groceries" | Preview of the items affected, confirm, then archived |
| Ask | "what's left on weekend chores?" | Read-only answer listing open items |

## Where it fits

pourOver is a purrBrews app, and it may become the command surface for the wider personal AI setup.

- **purrBrews:** one Compose stack behind Traefik and Authelia. Model calls go to llama-swap on roastery, later to an always-on AI node.
- **caliCortado:** topics and items are structured records the second brain can read later. pourOver never stores notes.
- **Mealie:** stays the recipe store. A v2 integration pulls a recipe's ingredients into a grocery topic.
- **Vikunja:** pourOver would replace it for household lists. Decide once v1 is in daily use.
- **Freeze:** these docs are the only pourOver work allowed until the plan's start gates are met.

## Release scope

v1 is text only: a command box, three widgets and one local model. Everything else waits for v1 to earn daily use.

| Release | Scope | Starts when |
| --- | --- | --- |
| v1 Text | Command box, topics, items, templates, checklist / table / bar widgets, fast path, preview and confirm, command log with undo, two users, homepage with pinned and needs-attention topics | Plan start gates met |
| v1.1 Polish | Line, stat, progress and kanban widgets; private topics; due-date pushes via ntfy (actionable only) | v1 used daily by both users for 4 weeks |
| v2 Reach | REST API and MCP server so other agents can operate it; context export for other models; voice through Home Assistant Assist; wall-screen and mirror view; Mealie import; Home Assistant to-do lists | v1.1 stable; always-on AI node decided |
| v3 Brain | caliCortado integration, AI-ranked homepage, scoped per-topic custom CSS | caliCortado running |

## Decisions

Everything below is a proposed default until the owner confirms it.

| Decision | Options | Proposed default | Settled by |
| --- | --- | --- | --- |
| Who writes the page | Model writes HTML/CSS; model writes a JSON view spec | View spec, fixed renderer | Owner, before M3 |
| Model | Gemma 4 12B; Qwen3.5 9B | Whichever wins the M0 eval | M0 results |
| Host node | grinder; percolator | grinder for beta, percolator after restore test | Owner, before M5 |
| Sharing | Shared by default; private by default | Shared by default, private topics in v1.1 | Owner, before M1 |
| Vikunja | Keep; retire for household lists | Retire once v1 is in daily use | Owner, after 4 weeks of use |
| Repo | Own repo; folder in purrbrews-containers | Own public repo under purrMonster, stack in purrbrews-containers | Owner, before M1 |
| AI while roastery is off | Fast path only; wake roastery; always-on AI node | Fast path only until the AI node exists | AI node decision |
