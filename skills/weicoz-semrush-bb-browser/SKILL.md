---
name: weicoz-semrush-bb-browser
description: >
  Use when the user wants to operate a configured Semrush proxy through `bb-browser`, especially for Keyword Magic Tool,
  Keyword Overview, or Keyword Strategy Builder / keywordmanager.
  Always use this skill when the user mentions `Semrush 代理站`, `bb-browser`, `keywordmagic`, `keywordoverview`,
  `keywordmanager`, or keyword filtering like `KD < 29`, `Volume > 100`, `CPC > 0.1`, or wants the workflow turned into repeatable CLI usage
  instead of one-off browser clicking.
---

# Semrush Proxy via bb-browser

Use the existing private `bb-browser site` adapters under `$WEICOZ_BB_BROWSER_ROOT/sites/sem3ue/`.
Do not rebuild ad-hoc browser scripts if the adapter already covers the task.

## Coverage

This skill currently covers:

- `sem3ue/keywordmagic`
- `sem3ue/keywordoverview`
- `sem3ue/keywordmanager`

The adapter source files live here:

- `$WEICOZ_BB_BROWSER_ROOT/sites/sem3ue/keywordmagic.js`
- `$WEICOZ_BB_BROWSER_ROOT/sites/sem3ue/keywordoverview.js`
- `$WEICOZ_BB_BROWSER_ROOT/sites/sem3ue/keywordmanager.js`

## Core rule

Prefer `bb-browser site ...` over raw `bb-browser click/fill/snapshot` when the adapter exists.

For keyword research and opportunity validation, use **only** `sem3ue/keywordmagic` as the data source. Do not query or use `keywordoverview` as a fallback, supplement, or decision input unless the user explicitly requests Keyword Overview.

Use manual browser interaction only when:

- the user wants to create a new workflow not yet covered by the adapter
- the adapter returns only shell HTML and you need to open a live result tab first
- the page has fallen back to a builder/start page and you need to recover the right live result page

## Important runtime constraint

`bb-browser site` has a CLI parsing quirk:

- unknown `--flag` names may be swallowed by the CLI before reaching the adapter
- the adapter layer now contains compatibility handling for the current `keywordmagic` filters
- still, when possible, prefer the already validated command patterns from this skill

Also:

- `keywordmagic` and `keywordoverview` are most reliable when run against a live rendered result tab
- plain fetch often only returns the shell HTML and not the front-end rendered table

## Failure Modes

| Trigger | First action | If still unclear |
| --- | --- | --- |
| Adapter returns shell HTML only | Open the live result page and rerun with `--tab <tab-id>` | Report the shell page and stop instead of faking rows |
| Wrong stale previous query appears | Check tab title and `location.href` before extraction | Do not reuse the wrong query output |
| Filter flags seem ignored | Re-run with the validated named form or positional compatibility form | Report the unsupported flag combination |
| `keywordmanager/list` falls back to builder | Report that the list page is not stably preserved | Return builder/list URLs instead of pretending extraction succeeded |
| Temporary tab was opened for extraction | Persist the data first, then close only that temp tab | Never close a user tab you did not open |

🔴 CHECKPOINT: If the adapter did not return the intended live result, do not treat the run as successful. Verify title, URL, and rendered content first.

## Workflow

1. Check whether the relevant Keyword Magic result tab is already open.
2. If not, open the target Keyword Magic URL using `$WEICOZ_SEMRUSH_PROXY_HOST`.
3. Confirm the title and URL are the intended query/page, not a stale previous query.
4. Run `bb-browser site sem3ue/keywordmagic ...`.
5. If the result is empty and the page is front-end rendered, rerun against the live tab with `--tab <tab-id>`.
6. Do not fall back to Keyword Overview. Report an unavailable Keyword Magic result as unavailable.
7. If this workflow opened a temporary Semrush tab, close that tab after the data has been extracted and persisted.

## Temporary tab cleanup

Treat Semrush result tabs opened only for extraction as disposable.

Rules:

- Close only tabs opened by the current run.
- Do not close pre-existing user tabs, even if they are on the configured proxy host.
- Before closing, ensure the extracted data has already been saved or included in the response.
- In batch runs, track every temporary tab opened by the run. `bb-browser open ... --tab` returns a full Tab ID; use `bb-browser tab list --json` to resolve its current tab index before cleanup.
- If a cleanup command fails, report the tab id/index and continue; do not rerun the whole extraction just to close tabs.

Manual cleanup pattern:

```bash
bb-browser open "https://${WEICOZ_SEMRUSH_PROXY_HOST}/analytics/keywordmagic/?q=assessment&db=us&fid=${WEICOZ_SEMRUSH_FID}" --tab
bb-browser site sem3ue/keywordmagic assessment us "${WEICOZ_SEMRUSH_FID}" --json --tab <tab-id>
bb-browser tab list --json
bb-browser tab close <tab-index>
```

For scripts, keep a `temporary_tabs` list containing the tab index or enough URL/query metadata to find the tab again, and close it in a `finally` block.
Prefer `bb-browser tab close <tab-index>` after verifying the tab title and URL in `bb-browser tab list --json`.

## Keyword Magic

Use for keyword table extraction from:

- `https://${WEICOZ_SEMRUSH_PROXY_HOST}/analytics/keywordmagic/...`

### Supported output

- `keyword`
- `intent`
- `volume`
- `kd`
- `cpc_usd`
- `sf` when available
- `updated`
- `_raw` full mapped row

### Supported filters

- `minVolume`
- `maxKd`
- `minCpc`

The validated filter semantics are:

- `volume > minVolume`
- `kd < maxKd`
- `cpc > minCpc`

### Recommended usage

First open the live result page:

```bash
bb-browser open "https://${WEICOZ_SEMRUSH_PROXY_HOST}/analytics/keywordmagic/?q=assessment&db=us&fid=${WEICOZ_SEMRUSH_FID}&__gmitm=..."
```

Then extract against the live tab:

```bash
bb-browser site sem3ue/keywordmagic assessment us "${WEICOZ_SEMRUSH_FID}" --json --tab <tab-id>
```

After extraction, close the temporary live tab:

```bash
bb-browser tab list --json
bb-browser tab close <tab-index>
```

With filters:

```bash
bb-browser site sem3ue/keywordmagic assessment us "${WEICOZ_SEMRUSH_FID}" --minVolume 100 --maxKd 29 --minCpc 0.1 --json --tab <tab-id>
```

### Verified-filter runner

When Semrush's page-level filter controls need to be preserved without modifying the `bb-browser` runtime, use the outer runner. It copies the native Semrush `filter` state from a verified seed tab, waits until the target page visibly shows the requested filter labels, then delegates extraction to this adapter.

```bash
node "$WEICOZ_SKILLS_ROOT/weicoz-semrush-bb-browser/scripts/keywordmagic-filter-runner.mjs" \
  --query generador --db mx --fid "${WEICOZ_SEMRUSH_FID}" \
  --tab <temporary-target-tab-id> --seedTab <verified-filter-tab-id> \
  --maxKd 40 --minCpc 0.1 --limit 20
```

The seed tab must already display the exact desired filters. The runner fails if the target UI labels do not match, and it does not apply local row filtering.

The current adapter also supports the positional compatibility form:

```bash
bb-browser site sem3ue/keywordmagic assessment us "${WEICOZ_SEMRUSH_FID}" 100 29 0.1 --json --tab <tab-id>
```

Prefer the named form in documentation and examples.

## Keyword Overview

Use for:

- `https://${WEICOZ_SEMRUSH_PROXY_HOST}/analytics/keywordoverview/...`

### Supported output

- `summary`
- `countries`
- `keyword_variations`
- `questions`
- `clusters`

### Recommended usage

Open a real result page first:

```bash
bb-browser open "https://${WEICOZ_SEMRUSH_PROXY_HOST}/analytics/keywordoverview/?q=ai+change+clothes&db=us&fid=${WEICOZ_SEMRUSH_FID}&__gmitm=..."
```

Then extract:

```bash
bb-browser site sem3ue/keywordoverview "ai change clothes" us "${WEICOZ_SEMRUSH_FID}" --json --tab <tab-id>
```

This is preferred over shell-fetch mode because the result widgets are front-end rendered.
Close the temporary live tab after extraction.

## Keyword Manager

Use for:

- `https://${WEICOZ_SEMRUSH_PROXY_HOST}/analytics/keywordmanager/...`
- `https://${WEICOZ_SEMRUSH_PROXY_HOST}/analytics/keywordmanager/list?...`

### Current support level

This adapter currently focuses on:

- builder URL construction
- list URL construction
- current builder page state reading

Validated usage:

```bash
bb-browser site sem3ue/keywordmanager --mode builder
bb-browser site sem3ue/keywordmanager --listId "6460399/444444444" --tab 0 --clusterView 1 --mode url
```

### Limitation

`keywordmanager/list` may bounce back to the builder page in the current session/profile.
Do not promise stable list table extraction unless you have a live tab that truly remains on the list result page.

If the user wants full list extraction:

1. have them keep a real `keywordmanager/list` result page open
2. inspect that exact live tab
3. extend the adapter only after confirming the page does not auto-fallback

## Troubleshooting

If a Semrush adapter returns only shell HTML:

1. open the target result page in a fresh tab
2. inspect title and `location.href`
3. rerun the adapter with `--tab <tab-id>`

If the wrong previous query appears:

1. get the tab title
2. get the tab URL
3. confirm the tab actually navigated to the requested `q=...`

If `keywordmanager/list` falls back:

- report that the current session is not stably preserving the list result page
- return builder/list URLs instead of faking extraction

## Anti-Patterns

- Do not rebuild ad-hoc browser scripts when the adapter already covers the task.
- Do not promise stable list extraction if the live list page is not actually open.
- Do not use raw click/fill/snapshot when `bb-browser site` already supports the flow.
- Do not treat shell HTML as a successful keyword table.
- Do not leave temporary Semrush tabs open after the data has been saved.

## Output rule

When the user asks for a quick check, return the filtered rows or a short summary directly.
When they ask for reusable workflow or automation, respond with the exact `bb-browser site ...` commands they can rerun.
