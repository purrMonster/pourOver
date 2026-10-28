# Plan

All start gates cleared 2026-10-14 (gate 2 bypassed with a guardrail). v0.1 code merged to main ([PR #1](https://github.com/purrMonster/pourOver/pull/1), 18 Oct 2026); PRs #2–#6 merged by 19 Oct. Decisions and the dated log are in [runbook.md](runbook.md).

## Start gates

Revised 2026-10-14 for the stir-3 translator shape (see [ideas/pourover.md](ideas/pourover.md)). M0 starts when every box is ticked or explicitly bypassed.

- [x] purrBrews rebuilt, with a restore-tested backup (owner, 2026-10-14)
- [x] ~~Owner's higher-priority commitments clear~~ Bypassed by owner, 2026-10-14. Guardrail (owner's choice): until 8 Nov, pourOver may use any free time, but unfinished work then waits; from 9 Nov it gets only the weekly purrBrews slot, max 4 sessions for v1, and never displaces the job-switch sprint
- [x] Model path: roastery on demand (about 99% uptime since joining the fleet); kettle stays a later upgrade. Model pick is settled by the M0 eval
- [x] Stir-3 defaults confirmed (owner, 2026-10-14): reminders via Vikunja CalDAV to native phone apps; v1 commands are add / done / what's due (reports all tasks) / delete (sender's own tasks only, with a confirm step); meowGram is the input (treat its bot hook as available), ntfy is output only (replies, errors, queued results); own public repo under purrMonster, stack in purrbrews-containers
- [x] meowGram running (on cellar); its bot hook ships with the next release and is treated as available

## Milestones

Each ends in evidence, not a feeling. A session is one 2–3 hour block. Stories are in [planning/backlog.md](planning/backlog.md).

| ID | Scope | Exit evidence | Sessions | Status |
| --- | --- | --- | --- | --- |
| M0 Eval | 50-message eval set; plan schema; runner; run on Gemma 4 12B, Qwen3.5 9B and the game-mode 4B | Eval report per model committed; go if one model meets the thresholds, otherwise v1 runs fast path + fallback only | 1.5 | Eval sets, schema and runner done; Gemma 32% → 36%, fixes merged, rerun pending |
| M1 Service | Time parser, fast path, model path, validator, queue, Vikunja client, replies | The eval set passes through the real service; a real Vikunja (pinned) gets correct tasks; every delete stops at "yes" | 2.5 | Merged; verified against real Vikunja 2.7.0; model at the gate still to prove |
| M2 Channels | meowGram adapter, ntfy output, CalDAV reminders on both phones | A meowGram message creates a task, gets a reply, and the reminder rings | 0.5 + config | meowGram adapter and ntfy merged; waits for meowGram bot API; CalDAV on phones to do |
| M3 Harden | Compose stack, Gatus, CI with Vikunja contract test, backup and restore drill, runbook and MAP, move to percolator | Restore drill passes; dated runbook entry | 1 | CI with unit tests built; contract test step waits for OK; rest to do |

Total about 5–6 sessions.

## Time budget

Any free time until 8 Nov (the move is on 1 Nov); from 9 Nov only the weekly purrBrews slot, at most 4 sessions for v1, never in place of the job-switch sprint. If something has to slip, pourOver slips.

## Risks

| Risk | Cost | Mitigation |
| --- | --- | --- |
| Small model files tasks wrongly | Wrong project or date, lost trust | Eval gate, schema-constrained output, date hint from plain code, every reply echoes what was filed, undo |
| Vikunja API differs from the client | Writes fail or land wrong | Pin Vikunja; contract test against the pinned container before deploy |
| meowGram bot hook slips | No input channel | Service is testable over HTTP; the adapter is a thin, separate story |
| roastery off or gaming | AI messages wait | Fast path and timed messages still work; queue with 6 h expiry and ntfy results |
| Scope creep back to the old designs | v1 never ships | Later work lives in README "Not in v1" and [later/](later/); new ideas go there, not the build |
| Polishing loop | Weeks on details nobody asked for | Each milestone stops at its exit evidence |
| Deleting the wrong thing | Lost tasks | Own tasks only, checked twice, "yes" required |

## Good enough, and next step

v1 is good enough when both of us use it for two weeks and every reminder that should have rung did. Stop there; later work starts only after that.

Next step: rerun the M0 eval on main, then M3 hardening while meowGram ships its bot API. Release blockers: [runbook.md](runbook.md#release-1-readiness-19-oct-2026).
