# pourOver

Text a task in meowGram; it lands in Vikunja, filed properly. You pour text in, it brews a task.

```
meowGram bot ──► POST /inbound ──► fast path ──┐
                                   (no model)  ├─► validator ──► Vikunja (tasks, reminders, repeats)
                     llama-swap ◄── model path ┘        │
                     (JSON-schema plan only)            └─► reply in chat · ntfy for queued results and errors
```

Design and decisions live in the private `pourover-docs` folder; this repo is the code.

## What v1 does

| Message | Result |
| --- | --- |
| `remind me to pay rent tmrw evening` | Task in Bills, due and reminder Wed 18:00 |
| `kal shaam eggs aur bread lena hai` | Two tasks in Groceries, labelled shopping |
| `done electricity bill` | Marks the matching open task done |
| `done milk` | Asks which one, when two tasks match |
| `what's due today` / `anything overdue?` / `this week` | Lists everyone's open tasks, read only |
| `delete bike insurance` → `yes` | Deletes, only if the sender owns the task |
| `undo` | Offers to delete what pourOver just created for you |

Reminders ring on phones through Vikunja's CalDAV in the native reminders app. pourOver never schedules anything itself.

## How a message is handled

1. **Fast path** (plain code): what's due, done, delete, `add X to <project>`. No model call.
2. **Model path**: anything else goes to the model with the household snapshot (projects, labels, users, open tasks), the message fenced as data, and a date hint from the plain-code parser. Output is constrained to the plan JSON schema.
3. **Validator**: every plan, from either path, must point at existing projects, labels, users and open tasks. Deleting someone else's task is refused. Anything else: "Couldn't file that. Nothing changed."
4. **Model offline** (roastery off or in game mode): a message with a time is filed in Inbox straight away; one without a time waits in a queue, runs when the model is back, and reports on ntfy. It gives up after 6 hours.
5. Deletes always wait for `yes`. Every message, plan and outcome goes into the command log (SQLite, WAL).

## Run locally

```sh
pip install ".[dev]"
pytest -q
cp .env.example .env && cp config/users.example.yaml config/users.yaml   # fill in real values, never commit them
uvicorn pourover.app:create_app --factory --port 8000
```

`POST /inbound` with header `X-Pourover-Token` and body `{"sender": "<meowGram id>", "text": "..."}` returns `{"reply": "..."}`. `GET /healthz` is for Gatus.

## Eval

```sh
python -m pourover.evaluate --check --messages eval/messages.yaml          # lint the set
python -m pourover.evaluate --messages eval/messages.yaml \
    --llm-url http://roastery.lan:8080 --model gemma-4-12b                 # score a model
```

Runs the full planner (fast path, then model) against expected plans, with no Vikunja writes, and writes a report to `eval/results/<model>.json`. A model ships only with 100% valid plans, at least 90% exact, zero wrong deletes and zero writes from questions. Titles are compared without case, punctuation or articles.

| Set | Items | What |
| --- | --- | --- |
| `eval/messages.yaml` | 50 | Set A, the main gate (m001–m050) |
| `eval/messages-b.yaml` | 51 | Set B, a second opinion (m100–m150) |
| `eval/sample.yaml` | 4 | Smoke test for the runner |

Both sets were generated with the prompt in `pourover-docs/eval/` and reviewed by hand plus `--check`. Without `--llm-url` the runner scores the fast path and offline fallback alone (set A: 22% exact, no wrong deletes, no writes from questions): the floor a model has to beat.

## Status

v0.1, not deployed.

- **Vikunja: verified.** The client speaks Vikunja's API v2 and is checked against the real, pinned Vikunja 2.7.0 (the version purrBrews runs) by `scripts/contract-vikunja.sh`: it downloads the release binary, checks its sha256, starts it on localhost with a throwaway SQLite, and runs `tests/contract` (client calls plus the whole service end to end). Bump the version and `scripts/vikunja.sha256` together with the stack.
- **llama-swap:** accepts `response_format: json_schema` (first real eval runs on roastery, Oct 2026).
- **meowGram: built against the plan, not the code.** The adapter follows meowGram Release 2's planned bot API (Basic-auth bot, polling `GET /api/messages/sync`, `POST /api/messages` with an `Idempotency-Key`). Those endpoints aren't merged in meowGram yet; the send body `{"text_content": ...}` is an assumption to confirm when UST-2.4.2 lands.
- **To do:** the Compose stack in `purrbrews-containers` (internal only behind Traefik, Gatus check).

## meowGram

By default pourOver lives in meowGram's shared lounge and only answers messages that start with `@pourover` (`MEOWGRAM_TRIGGER`), replying addressed to the sender:

```
Ravi:     @pourover kal shaam eggs aur bread lena hai
pourOver: @ravi Added: Buy eggs → Groceries · Wed 11 Nov 18:00 · #shopping
          Added: Buy bread → Groceries · Wed 11 Nov 18:00 · #shopping
```

- **Own channel:** set `MEOWGRAM_CHANNEL` to a channel id and pourOver reads and posts only there (`channel_id` on sync and send; messages from other channels are dropped). In its own channel you can set `MEOWGRAM_TRIGGER=` (empty) so every message is a command. meowGram has no channels yet; `channel_id` (query parameter, send body field, message field) is the name meowGram should use when it adds them.
- It ignores other bots (itself included) and senders not in `config/users.yaml` (`meowgram_id` is the meowGram username).
- On first start it begins from "now"; it never replays old chat.
- The cursor and the ids of handled messages live in SQLite, so a restart resumes where it stopped and nothing is filed twice (at most once: a crash mid-message can lose a reply, never duplicate a task).
- 429/503 from meowGram are honoured with `Retry-After`; other errors back off up to 5 minutes.

## Vikunja notes

- API v2 (`/api/v2`). v1 is frozen at 2.4.0 and its `/tasks/all` already fails on 2.7.0.
- Labels belong to the user who made them, so pourOver creates its four labels (`chores`, `pourover`, `shopping`, `urgent`) for each user on first use.
- Anyone with write access to a shared project can delete any task in it. "Delete only your own tasks" is enforced by pourOver.
- Marking a repeating task done re-opens it with the next due date; the reply says when.
