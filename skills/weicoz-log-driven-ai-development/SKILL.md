---
name: weicoz-log-driven-ai-development
description: >
  Use this skill whenever the user wants to make development behavior observable through logs that
  capture key flows and outcomes for later AI analysis, querying, debugging, verification, or API/data
  integration work. Trigger on Chinese requests like 开发日志, 关键流程记录, 日志驱动开发, 用日志排查,
  修 bug 先加日志, AI 自己看日志验证, AI 查日志, 留日志给 AI 分析, 证据链不足,
  无法判断先补日志, 接口联调, 查订单/奖励/结算/状态流转问题. It enforces a log-driven loop:
  understand the business path, decide which events and outcomes must be queryable later, add or inspect
  minimum useful logs, run or request reproduction, read logs, modify code, rerun, and only finish when
  logs prove the behavior is correct.
---

# Log-Driven AI Development

Use this skill to make AI-assisted development observable, queryable, and verifiable.

The goal is not to add noisy logs everywhere. The goal is to capture a small, durable set of runtime
events that describe the key path, decisions, and results so the AI can later analyze, query, debug,
repair, and validate behavior instead of guessing from static code.

In this skill, logs are not only a debugging aid. They are part of the development output. A feature is
not fully delivered until the important flow and final result are visible in stable logs that can be
queried again later.

## Core Principle

Do not treat code changes as complete until runtime evidence supports them and the key flow can be
reconstructed from logs.

If a problem is hard to diagnose, the default assumption is not "the code is too complex." The default assumption is "the evidence chain is incomplete." Add targeted logs before continuing to modify behavior.

## Decision Rules

Apply these rules before deciding that a task is "done":

- If the path crosses more than one boundary such as request, job, queue, API, database write, or UI action, require `entry`, `decision`, and `result` logs.
- If the AI cannot answer one future path question from logs alone, add or upgrade logs before changing more code.
- If the final business outcome cannot be queried back by correlation id, add a stable `result` event before closing the task.
- If existing logs are noisy but not queryable, add one stable summary event instead of scattering more ad-hoc debug lines.
- If the data is sensitive, log ids, counts, statuses, branch names, and reasons first; do not jump to raw payload logging.

🔴 CHECKPOINT: If there is no stable `result` event for the path, treat the task as not fully verified.

Default loop:

1. Identify the business path and expected result.
2. Decide which key steps and outcomes must be queryable later.
3. Check whether current logs can explain and reconstruct the path.
4. If the issue is hard to diagnose, treat it as an evidence gap first.
5. Add the minimum useful logs at key points, error points, and uncertain points.
6. Reproduce or run the relevant workflow.
7. Read logs and locate the real failure point.
8. Change code.
9. Run again and read logs again.
10. Finish only when logs show expected behavior.
11. Decide which logs should stay, be downgraded, or be removed.

## When To Use

Use this skill for:

- Chinese trigger phrases: `用日志排查`, `日志驱动开发`, `修 bug 先加日志`, `AI 自己看日志验证`, `AI 查日志`, `留日志给 AI 分析`, `证据链不足`, `无法判断先补日志`, `接口联调`, `查订单`, `查奖励`, `查结算`, `查状态流转`.
- New feature development where behavior spans more than one function, request, job, queue, API, database write, or UI action.
- Bug fixes where the cause is not already proven.
- API integration and third-party callback handling.
- Order, reward, settlement, permission, payment, status-flow, import/export, or scheduled-task logic.
- Cases where the user says the AI should test, verify, inspect logs, trace behavior, or avoid guessing.
- Cases where the user wants key flow and result logs to remain available for later analysis, querying, or audits.

Do not use it heavily for:

- Pure copy changes.
- Static formatting.
- Simple one-line fixes with an obvious failing test.
- Documentation-only edits.

## Step 1: Define The Business Path

Before editing, write the path being recorded and verified in plain language.

Template:

```text
Business path:
- Entry:
- Key inputs:
- Important branches:
- Key checkpoints to log:
- External calls:
- State changes:
- Expected final result:
```

If the path is unclear, inspect the code first. If it is still unclear and the ambiguity affects behavior, ask a focused question.

🔴 CHECKPOINT: Do not edit behavior until the entry, key inputs, expected result, and at least one verification path are known.

## Step 2: Check Current Observability

Look for existing logs, traces, test output, request records, job records, database audit rows, or error reports.
Ask a second question at the same time: if the AI needs to answer "what happened in this run?" tomorrow,
would the current evidence be enough?

Classify observability:

- `enough`: existing evidence can prove the path and the final result can be queried back by id, event, or trace.
- `partial`: some steps are visible, but one or more key decisions are invisible.
- `missing`: the path cannot be diagnosed from runtime evidence.

If observability is `partial` or `missing`, add targeted logs before attempting speculative fixes.

If a problem cannot be diagnosed or feels unusually hard to diagnose, assume the current evidence chain is incomplete. Do not keep guessing. Add logs at:

- Key points where business state changes.
- Error points where the workflow fails, exits early, or returns unexpected output.
- Uncertain points where the AI cannot tell which branch, value, dependency, or state caused the behavior.

The purpose is to produce enough evidence for the next run to answer: what happened, where it happened,
why it happened, which result was produced, and which logs can be queried later to reconstruct the same path.

Use this if-then table when diagnosis stalls:

| Trigger | First action | If still unclear |
|---|---|---|
| The workflow result is wrong but no error appears | Add logs around branch selection and intermediate business values | Add logs before and after the suspected state change |
| The workflow exits early | Log the early-return condition and the input fields that caused it | Log the previous decision point that led to that condition |
| External API output looks wrong | Log sanitized request keys and response status/summary | Add a redacted sample payload only if safe |
| Database result is empty or unexpected | Log query filters, lookup keys, and matched row count | Log the upstream value used to build the query |
| AI cannot decide between two causes | Add one log that distinguishes the two causes | Rerun before modifying code |

🔴 CHECKPOINT: If observability is `missing`, add evidence logs before fixing code. If observability is `partial`, add only the logs needed to disambiguate the next decision.

## Step 3: Add Minimum Useful Logs

At minimum, make three kinds of events queryable:

- `entry`: the path started with these key inputs.
- `decision`: an important branch, lookup, or dependency result changed the direction.
- `result`: the final business outcome was success, failure, empty, skipped, or partial.

Minimum query contract:

| Event type | Must answer | Minimum fields |
|---|---|---|
| `entry` | Did the path start, and with which key inputs? | `event`, one correlation id, key input fields |
| `decision` | Which branch, lookup, or dependency changed the path? | `event`, one correlation id, `branch` or equivalent, decision summary |
| `result` | What business outcome was finally produced? | `event`, one correlation id, `result`, `reason` when not success |

Prefer logs that answer specific questions:

- Did this request/job/action enter the path?
- What key parameters were used?
- Which branch was selected?
- What intermediate result was computed?
- What external API/database operation happened?
- What was the final result?
- Why did it fail or stop early?
- Which stable event should future queries and analyses use to find this step again?

For each log, include:

- Stable event name.
- Correlation identifier if available, such as order id, user id, request id, job id, trace id, or task id.
- Key business fields, not entire payloads by default.
- Failure reason for early returns and exceptions.
- Enough structure for later filtering, grouping, and comparison across reruns.
- A clear result field when the step produces a business outcome.

Avoid:

- Dumping secrets, tokens, passwords, cookies, private keys, or full authorization headers.
- Logging entire request or response bodies unless the payload is already safe and needed.
- Adding many vague logs like `here`, `debug`, or `step1`.
- Leaving high-volume logs at info level after the issue is solved.

Use event names that stay stable across reruns. Prefer names like:

```text
order.reward.calculate.entry
order.reward.calculate.branch_selected
order.reward.calculate.external_result
order.reward.calculate.state_changed
order.reward.calculate.failed
order.reward.calculate.success
```

Also prefer stable field names such as:

```text
event
request_id
order_id
user_id
branch
result
reason
duration_ms
```

## Failure Branches

If the normal loop cannot continue cleanly, use one of these explicit branches:

- If you cannot run the target workflow locally, stop changing behavior and give the user one exact command, one expected event name, and one correlation id or lookup key to return.
- If you cannot safely add logs in the target environment, add the smallest safe summary event locally or in staging, then state what evidence is still missing.
- If the codebase has no structured logging helper, standardize one stable event name plus one correlation id first, then continue.
- If high log volume is a risk, log only boundary summaries at `entry`, `decision`, and `result` points; do not add per-loop chatter.
- If the only available evidence is a symptom report, convert it into an evidence request before proposing a fix.

## Step 4: Run Or Reproduce

Use the cheapest reliable verification path available:

- Existing automated test.
- Targeted script.
- Local API request.
- Queue/job runner.
- UI workflow.
- User-provided reproduction steps.

If the project has a standard test or run command, use that. If the runtime requires a specific container, environment, or service, follow the project instructions.

If you cannot run the workflow locally, tell the user exactly what command or action to run and what log file/output to send back.

🔴 CHECKPOINT: A run without inspected output is not verification. Always inspect test output, command output, log file, trace row, or returned response.

## Step 5: Read Logs Before Changing More Code

After each run, inspect the relevant logs before making the next code change.

Determine:

- Last confirmed successful step.
- First missing, wrong, or failed step.
- Whether the problem is input, branch logic, state, external dependency, persistence, or output formatting.
- Whether more logs are needed before changing behavior.

Do not keep editing based only on a theory if logs contradict it or do not support it.

If logs do not prove a cause, write the next smallest diagnostic log and rerun. Do not make broad rewrites to "see if it helps."

## Step 6: Fix And Verify Again

Make the smallest code change that explains the observed failure.

Then run again and compare logs:

- Expected entry appeared.
- Expected branch was selected.
- Expected intermediate values appeared.
- Expected final result appeared.
- Unexpected error or early return disappeared.

If the logs show a new failure, continue the loop from Step 5.

## Scenario: New Feature

For new feature work, include logs while building the path, not only after it fails.

Minimum useful log checkpoints:

- Feature entry.
- Validated key inputs.
- Major branch decision.
- External dependency result summary.
- Database write or state transition summary.
- Final success or controlled failure.
- Final business result that an AI can query later without replaying the full path.

Before finishing, state which checkpoints prove the feature works.

## Scenario: Bug Fix

For bug fixes, avoid rewriting code until the failing point is proven or strongly narrowed.

Bug fix flow:

1. Reproduce the bug or identify the closest available reproduction.
2. Check whether logs already show the failure point.
3. Add targeted logs if the failure point is invisible.
4. Run again.
5. Fix the smallest proven cause.
6. Run again.
7. Confirm logs show the corrected behavior.

If the bug cannot be reproduced, leave a diagnostic log or test hook when appropriate and explain what evidence is still missing.

If the user provides only a symptom, convert it into an evidence request:

```text
Need one of:
- exact reproduction steps
- relevant log excerpt
- affected order/user/job/request id
- expected result vs actual result
```

## Scenario: API Or Data Investigation

For API and data issues, logs must connect request, parameters, query, and result.

Useful checkpoints:

- API endpoint or job name.
- Sanitized request parameters.
- Query filters or business lookup keys.
- Count of matched records.
- Important external response fields.
- Reason for empty or unexpected results.
- Final response status and business result.

For sensitive systems, log identifiers and counts first. Add raw payload logging only when explicitly safe or when redaction is implemented.

## Scenario: AI Query And Analysis

If the user wants the AI to analyze or query logs later, design logs as a reusable evidence surface rather
than a one-time debug print.

Minimum requirements:

- One stable event name per important business step.
- One correlation id that can pull the whole path together.
- One result field that tells whether the business outcome was success, failure, skipped, or empty.
- Enough business fields to answer common questions without reopening the code.

Ask whether a future query like the following can be answered from logs alone:

```text
- Did order X enter the reward path?
- Which branch was selected for request Y?
- Why did task Z stop early?
- What final result was produced for user A?
```

## Long-Term Log Cleanup

At the end of the task, classify new logs:

- `keep`: useful for future diagnosis and low-volume enough to keep.
- `downgrade`: useful only during debugging, should become debug-level.
- `remove`: temporary noise that should not remain.

Prefer keeping:

- Entry/exit logs for critical jobs.
- Controlled failure reasons.
- State transitions.
- External API failure summaries.
- Final result logs that make business outcomes queryable by id.

Prefer downgrading or removing:

- High-frequency loop logs.
- Full payload dumps.
- Repeated intermediate values that no longer help diagnosis.

## Anti-Patterns

Do not:

- Patch business logic repeatedly without new runtime evidence.
- Treat "hard to debug" as a reason to rewrite a module.
- Add broad full-payload logs before trying identifiers, counts, statuses, and branch values.
- Log secrets, credentials, tokens, cookies, private keys, or authorization headers.
- Leave temporary high-volume debug logs at info level.
- Finish by saying "should work" without a run result or log evidence.
- Replace tests with logs when an automated test can directly prove the behavior.
- Add logs that are human-readable in the moment but impossible for AI to query later because event names and fields drift every run.
- Log five branch details but omit the final business `result`, leaving the path unanswerable for later queries.
- Add one-off `print` or `console.log` probes and call the path "observable" without creating stable summary events.

## Response Format

When using this skill, report work in this structure:

```text
Goal:
[What path or bug is being verified]

Logs:
[What evidence exists or what logs were added]

Result:
[What the logs proved and what code changed]

Verify:
[Command/workflow run and final evidence]

Next:
[Logs to keep/downgrade/remove, or remaining blocker]
```

Keep the final response concise. The important part is the evidence loop, not a long narration.
