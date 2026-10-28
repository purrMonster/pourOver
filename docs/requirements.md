# Requirements: pourOver v1 (translator)

v1 is done when every Must passes its acceptance check, the model clears the eval thresholds, and the stack meets the non-functional list. Story IDs refer to [planning/backlog.md](planning/backlog.md).

## Functional

| ID | Requirement | Priority | Acceptance | Stories |
| --- | --- | --- | --- | --- |
| FR-01 | Create one or more tasks from one message | Must | "buy eggs, call mom and pay rent" creates three tasks in order | S2.3.1 |
| FR-02 | File each task well: verb-first title, an existing project, existing labels (always `pourover`), assignee, due, reminder, repeat, short description | Must | Eval exact-match ≥ 90% | S2.2.3, S2.3.1 |
| FR-03 | Parse dates, times and repeats in plain code, including Hinglish ("kal shaam", "parso", "har sunday") | Must | Time unit tests pass 100% | S2.2.1 |
| FR-04 | Assign to the other person when the message says so | Must | "ask Meera to book the cab" assigns to Meera | S2.3.1 |
| FR-05 | Mark a task done by naming it | Must | "done electricity bill" completes the one open match | S2.3.2 |
| FR-06 | Ask which one when two or more open tasks match | Must | "done milk" lists both matches and changes nothing | S2.3.2 |
| FR-07 | Report what's due: today (with overdue), overdue only, or this week, across everyone's tasks | Must | Read only; the log shows no writes | S2.3.3 |
| FR-08 | Delete only the sender's own tasks, only after "yes" | Must | Someone else's task is refused; nothing goes without a yes | S2.3.4 |
| FR-09 | Undo: offer to delete the tasks pourOver just created for the sender | Should | "undo" then "yes" removes them | S2.3.4 |
| FR-10 | Reply to every message with exactly what was filed, or that nothing changed | Must | Every reply matches Vikunja | S2.4.1 |
| FR-11 | Model offline: a message with a time is filed in Inbox at once; others wait up to 6 h and report on ntfy | Must | Stop llama-swap, send, start it: task created, result on ntfy | S2.2.5, S3.2.1 |
| FR-12 | Refuse nonsense and instructions hidden in messages | Must | Injection message produces no plan | S2.2.4 |
| FR-13 | Log every message: text, sender, path, plan, outcome, reply, latency | Must | Every change traces to one log row | S2.1.1 |
| FR-14 | meowGram adapter: messages in, replies back to the same chat | Must | A message in meowGram creates a task and gets a reply | S3.1.1 |

## Non-functional

| ID | Area | Requirement |
| --- | --- | --- |
| NFR-01 | Privacy | Model calls stay on the LAN. Public repo holds no personal data; real users, tokens and topics live in git-ignored config |
| NFR-02 | Safety | The model has no tools and returns one plan. Plans may only point at existing projects, labels, users and open tasks. Message text is fenced as data |
| NFR-03 | Availability | Fast path and timed messages work with roastery off |
| NFR-04 | Performance | Fast path under 300 ms; model path under 10 s at p90 on the GPU (targets, to confirm in M0) |
| NFR-05 | Security | Internal only behind Traefik; `/inbound` needs the shared adapter token; unknown senders refused; secrets only via env |
| NFR-06 | Data | SQLite in WAL mode on a named volume, in the purrBrews backup, restore tested before percolator |
| NFR-07 | Operations | Compose stack in purrbrews-containers, pinned images, healthcheck, restart unless-stopped, Gatus, runbook entry, MAP update |
| NFR-08 | Portability | Any OpenAI-compatible model URL; model swaps by config |
| NFR-09 | Testability | pytest in CI on every PR; Vikunja contract test against the pinned version |

## Model acceptance

The model path ships only if it passes the 50-message eval set (generated with [eval/generate-eval-set.prompt.md](eval/generate-eval-set.prompt.md)). Tighten these, never loosen them:

- 100% of outputs valid against the plan schema
- At least 90% exact match with the expected plan
- Zero deletes that weren't expected, zero writes from questions
- Results committed per model, so a model swap reruns the same set

## Assumptions

- Vikunja's v1 API (filter syntax, reminders, labels, assignees) matches the client; the contract test confirms it before deploy.
- llama-swap accepts `response_format: json_schema`.
- meowGram's next release adds a bot hook that can POST messages and show replies.
- Two users. A third is a later conversation.
