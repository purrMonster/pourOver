# Architecture: pourOver v1 (translator)

One small FastAPI service with SQLite. It owns no tasks: Vikunja does. The model never acts: it returns one JSON plan, and the app checks that plan before anything changes. The code's README in [purrMonster/pourOver](https://github.com/purrMonster/pourOver) is the technical reference; this page is the shape.

## Message flow

```
meowGram bot ──► POST /inbound (adapter token, sender id, text)
                    │
                    ▼
          pending "yes"? ──► apply the waiting delete
                    │ no
                    ▼
            fast path ──────────────┐   what's due · done X · delete X · add X to <project> · undo
                    │ no match      │
                    ▼               │
            model path ─────────────┤   llama-swap, JSON-schema plan, date hint from the parser
                    │ model down    │
                    ▼               │
        has a time? ─ yes ─► Inbox ─┤
                    │ no            │
                    ▼               ▼
            queue (≤ 6 h)      validator ──► needs clarification / refused / no plan → reply, nothing changed
                    │               │
                    │               ▼
                    │          delete? ──► ask "yes" first
                    │               │
                    │               ▼
                    │          Vikunja (create · done · list · delete)
                    │               │
                    └──► ntfy       └──► reply in meowGram, row in the command log
```

## Components (modules in the repo)

| Module | Job |
| --- | --- |
| `timeparse` | Dates, times, repeats in plain code, Hinglish included. The "when" never waits for the model |
| `fastpath` | Common commands with no model call; returns nothing when unsure, so the model decides |
| `model` | OpenAI-compatible client; builds the prompt from the household snapshot; schema-constrained output |
| `validator` | Normalises (pourover label, reminder = due) and rejects anything outside the snapshot |
| `planner` | Text → validated plan, no side effects. Shared by the service and the eval runner |
| `vikunja` | REST client, one per user token, so tasks are created as the sender |
| `service` | Confirm flow, undo, applying plans, replies, queue draining |
| `store` | SQLite (WAL): command log, pending confirms, queue |
| `ntfy` | Output only |
| `evaluate` | Scores the planner against the eval set; writes a report per model |

## The plan

The only thing the model (or the fast path) may produce. Same format as the eval set's expected results.

| kind | Meaning |
| --- | --- |
| `plan` | One or more operations: `create_task`, `complete_task`, `list_due`, `delete_task` (always `requires_confirm`) |
| `needs_clarification` | Two or more tasks match (candidates listed), or none |
| `refused` | Delete of a task the sender doesn't own (`not_owner`) |
| `no_plan` | Nonsense, greetings, off-topic, instructions to the system |

## Safety

- **The model is untrusted input.** It has no tools, no network, no database: it returns one plan.
- **Fenced text.** The message enters the prompt between markers, labelled as data.
- **Closed world.** Plans may only name existing projects, labels, users and open tasks.
- **Deletes.** Own tasks only, checked twice (planner and at apply time), and only after "yes".
- **Identity.** The adapter sends the meowGram sender id with a shared token; pourOver maps it to a Vikunja user and token. Unknown senders are refused.
- **Secrets.** Only in env; `.env.example` and `config/users.example.yaml` hold placeholders.

## Deployment

| Part | Choice |
| --- | --- |
| Host | grinder for beta, percolator after the restore drill |
| Stack | One Compose stack in purrbrews-containers: pinned image, `/healthz`, restart unless-stopped, internal only behind Traefik |
| Data | SQLite on a named volume, in the purrBrews backup |
| Model | llama-swap on roastery; the model name is config |
| Monitoring | Gatus on `/healthz`; errors also go to the owner's ntfy topic |

## Later

The operation layer is the seam for later work: MCP/API tools reuse the same plans and validator; voice produces text for the same pipeline; a morning plan reads Vikunja and posts to the mirror. The shelved pages-and-widgets design is in [later/pages-design/](later/pages-design/).
