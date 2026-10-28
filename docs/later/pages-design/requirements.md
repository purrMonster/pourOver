# Requirements

v1 is done when every Must below passes its acceptance check, the model clears the eval thresholds, and the stack meets the non-functional list.

## Functional requirements

| ID | Requirement | Priority | Acceptance |
| --- | --- | --- | --- |
| FR-01 | Create a topic from text, optionally from a template | Must | "open a new topic for grocery shopping" creates Groceries from the grocery template |
| FR-02 | Ship 5 templates (groceries, checklist, tracker, reading list, project), each with fields, a default view and model instructions | Must | Each template makes a working topic with no edits |
| FR-03 | Rename, pin, unpin and archive topics by text or tap | Must | Archive asks for confirmation first |
| FR-04 | Per-topic fields: text, number, date, choice, yes/no, quantity with unit; changeable by text | Must | "add a price field to groceries" adds a number field; existing items keep their data |
| FR-05 | Add many items in one command | Must | "add milk, eggs to groceries" adds 2 items |
| FR-06 | Expand an instruction into items with category and quantity | Must | Palak paneer adds categorised items, each marked AI-suggested until edited or ticked |
| FR-07 | Edit, complete and reopen items by text or tap | Must | A tap toggles an item with no model call |
| FR-08 | Remove or clear items only after a preview | Must | "clear done items" lists what goes before anything changes |
| FR-09 | Merge duplicates when adding | Should | Adding milk twice keeps one item; quantities sum when units match |
| FR-10 | Fast path for common commands, no model needed | Must | 20 listed patterns pass with the model unreachable |
| FR-11 | Model path: free text to a validated operation plan | Must | Invalid plans are rejected and never applied |
| FR-12 | Additive changes apply at once with undo; destructive ones wait for confirmation | Must | Remove, archive and field deletion always show a confirm step |
| FR-13 | Undo the last command | Must | Undo restores items, fields and view exactly |
| FR-14 | Log every command: text, user, plan, model, result, time | Must | Every change in the UI traces to one log entry |
| FR-15 | Answer questions about topics without changing them | Should | "what's left on weekend chores?" lists open items; the log shows no writes |
| FR-16 | Change a topic's view by text | Must | "show groceries as a table by category" switches the view; items untouched |
| FR-17 | Widgets: checklist, table, bar chart | Must | Each renders from a view spec at 360 px and desktop widths |
| FR-18 | Per-topic theme from fixed tokens: accent, density, icon | Should | "make groceries green and compact" changes tokens only |
| FR-19 | Homepage: command box, pinned, needs attention, all topics | Must | Loads in under 1 s on the LAN |
| FR-20 | Needs-attention ranking from overdue, due soon, open-item age and recent activity | Must | Each listed topic shows its reason, e.g. "3 overdue" |
| FR-21 | Two users through SSO; shared topics; items record who added and completed them | Must | The second user's ticks show their name |
| FR-22 | Export a topic as Markdown and JSON | Should | Export holds every field, item and the view spec |
| FR-23 | Search across topics and items | Could | Finds an item by any word in its title |

## Non-functional requirements

All are Musts. Timing figures are targets to confirm in M0, not measurements.

| ID | Area | Requirement |
| --- | --- | --- |
| NFR-01 | Privacy | Model calls stay on the LAN. No cloud model unless the owner switches one on per topic. The public repo holds no personal data |
| NFR-02 | Availability | Taps, fast-path commands and viewing work with the model offline; a banner says when AI is unavailable |
| NFR-03 | Performance | Page load under 1 s on the LAN; fast-path command under 300 ms; model command under 10 s at p90 on the GPU |
| NFR-04 | Security | Only reachable through Traefik and Authelia; user identity taken only from forward-auth headers; model output is never rendered as markup; all text escaped; CSRF tokens on writes |
| NFR-05 | Data safety | SQLite in WAL mode on a named volume; included in the purrBrews backup; a restore is tested before production |
| NFR-06 | Operations | Docker Compose, pinned image versions, healthcheck, restart unless-stopped, Gatus check, runbook entry and MAP update |
| NFR-07 | Mobile | Usable one-handed at 360 px wide, because the grocery list gets used in a shop |
| NFR-08 | Accessibility | WCAG 2.1 AA contrast, 44 px tap targets, full keyboard use on desktop |
| NFR-09 | Portability | Model endpoint is any OpenAI-compatible URL; models swap by config, not code |
| NFR-10 | Testability | pytest covers plan validation, the fast path and the renderer; CI runs on every PR |
| NFR-11 | Lightness | Light by feel, not by feature count. Taps respond in under 100 ms; the first item needs one line or one tap with no setup; the default page shows only the list and the command box. Every other feature lives in the command box or a menu, or appears only when it applies: no blank fields, no icon toolbars. Test: the second user adds, ticks and clears groceries without being shown how |

## Model acceptance

The model path ships only if it passes a fixed eval set of 50 real commands. The thresholds are proposals; tighten them, don't loosen them.

- 100% of outputs are valid against the plan schema (grammar-constrained, so anything less is a bug).
- At least 90% of plans match the expected operations exactly.
- Zero destructive operations applied without a confirm step.
- Zero writes from "ask" commands.
- The eval set covers: create topic, add items, ingredient expansion, edits by fuzzy name, view changes, field changes, clears, questions, and 5 nonsense inputs that must produce no plan.
- Results are committed to the repo per model, so a model swap reruns the same set.

## Out of scope for v1

- Voice, public API, MCP server, context export to other models
- Home Assistant, Mealie and caliCortado integrations
- Notifications and reminders
- Recurring tasks, attachments, offline sync
- Custom CSS or any model-written markup
- Cloud models
- More than one household

## Assumptions

- Authelia forward auth passes the signed-in user to the app through Traefik.
- llama-swap serves an OpenAI-compatible endpoint, and llama.cpp can constrain output to a JSON schema.
- Two users. A third user is a v2 conversation.
- The phone browser is the main client; no native app.
