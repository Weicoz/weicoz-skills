---
name: weicoz-reddit-research-automation
version: 1.0.0
description: >
  Use this skill when the user wants a scheduled or repeatable Reddit research workflow that mines Reddit threads and comments, turns them into evidence-backed markdown reports, and writes dated outputs into projects/reddit-research. Also use when the user asks to automate Reddit signal monitoring, run a recurring research job, archive results, or build a Codex-driven Reddit report pipeline. Do not use this skill for one-off Reddit pain evidence or Reddit+Semrush validation; use the dedicated Reddit evidence or Reddit opportunity skills for those jobs.
---

# Reddit Research Automation

This skill turns Reddit research into a repeatable Codex job with a fixed output contract.

It is intentionally narrow:

- It listens for repeatable Reddit signals.
- It extracts evidence from posts and comments.
- It writes markdown artifacts into `projects/reddit-research`.
- It preserves one run per dated folder so the history stays auditable.

## Operating rules

1. Use browser tools in this fixed order: `ego-browser` -> `browser-skill` -> `@Chrome`.
2. Move to the next layer only when the current layer is unavailable or cannot fetch the post body/comments; record the failure signal before moving.
3. Keep the workflow read-heavy. Do not drift into automatic posting or commenting.
4. Keep Semrush work out of this skill. If keyword validation is needed, hand off to the Reddit + Semrush skill.
5. Save outputs instead of narrating them. The point is a durable document trail, not a chat summary.

## Default job shape

The scheduled job should always answer the same questions:

- What subreddit or topic cluster was checked?
- What threads showed repeated pain or operational friction?
- What comments added real evidence instead of hype?
- What wedge looks narrow enough to be actionable?
- What changed since the last run?

## Input contract

Use a small config set:

- topic name
- subreddit list
- keyword list
- cadence
- lookback window
- output root

If the user does not provide these, use the project defaults under `projects/reddit-research/config`.

## Output contract

Every run must write a fresh folder under `projects/reddit-research/runs/`:

- `report.md` for the final synthesized result
- `evidence.md` for thread and comment evidence
- `raw-links.md` for canonical URLs and source notes
- `run-state.json` for status, timestamps, counts, and errors
- `codex.log` for the automation log when the run is launched by the shell wrapper

Use a timestamped folder name so runs never overwrite each other.

## Report format

The report should stay compact and repeatable:

1. Title
2. Scope
3. Summary conclusion
4. Evidence table
5. Repeated pain patterns
6. Weak or rejected signals
7. Narrow wedge
8. Next run suggestion
9. Source links

When useful, add a short `GO / HOLD / NO-GO` decision.

## Evidence rules

- Do not rely on title-only evidence.
- Prefer comments that add a workaround, time cost, money cost, or repeated frustration.
- Treat isolated praise as weak evidence.
- Treat repeated operational pain as stronger evidence than a broad idea statement.
- Keep direct quotes short and only when they materially improve the report.

## Run flow

1. Read the config for topics and cadence.
2. Collect candidate threads for each topic.
3. Open the thread and read the OP plus comments.
4. Extract evidence into a markdown block.
5. Synthesize a narrow wedge and a short decision.
6. Write the run artifacts.
7. Update `run-state.json` with success or failure.

## Failure branches

If the run cannot fetch a thread or comment tree:

- record the source URL,
- note the fetch failure,
- keep the run folder,
- and continue with the other sources instead of silently dropping the topic.

If a topic is too broad:

- shrink it to one user type,
- one recurring task,
- and one measurable output artifact.

If the evidence is too thin:

- write `HOLD`,
- explain why the signal was weak,
- and do not force a product conclusion.

## Anti-patterns

- Turning this into a generic research platform.
- Mixing in Semrush keyword validation.
- Producing only notes in chat and not writing files.
- Overwriting yesterday's report instead of creating a new run folder.
- Automatically posting, commenting, or DMing from Reddit accounts.

## Example run directory

```text
projects/reddit-research/
  runs/
    2026-06-05-083000/
      report.md
      evidence.md
      raw-links.md
      run-state.json
      codex.log
```

## When to trigger

Use this skill when the user asks for:

- scheduled Reddit research
- recurring Reddit pain monitoring
- a Codex-driven Reddit report pipeline
- a markdown archive of Reddit research runs
- an automated, repeatable version of the Reddit workflow
