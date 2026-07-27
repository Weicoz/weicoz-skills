---
name: weicoz-codex-context-window-override
description: Use this skill when the user wants to patch Codex CLI model context-window limits with model_catalog_json, especially for making gpt-5.5 report a larger 1M context window, or when they ask how to back up, verify, or roll back a Codex context-window override. This is an experimental client-side override workflow and must always include backup, verification, and rollback steps.
---

# Codex Context Window Override

Use this skill to apply or remove an experimental Codex CLI `model_catalog_json` override. The known use case is changing the local Codex model catalog so `gpt-5.5` reports `context_window = 1000000` and `max_context_window = 1000000`.

This workflow changes only local Codex client configuration. It does not prove that the Codex server supports the larger window. Treat it as an experiment, not a guaranteed product unlock.

## Safety Rules

1. Always tell the user this is a client-side catalog override, not a guaranteed server-side capability.
2. Always back up `~/.codex/config.toml` before editing it.
3. Never edit `~/.codex/models_cache.json` in place.
4. Store patched catalogs under `~/.codex/model-catalog-overrides/`.
5. Store backups under `~/.codex/backups/codex-context-window-override/`.
6. Verify with `codex debug models`; do not start a long production session just to test the patch.
7. Provide the exact rollback command after applying the patch.

## Quick Actions

### Apply the default gpt-5.5 1M override

Run:

```bash
bash "${CLAUDE_SKILL_DIR:-/Users/weicoz/.agents/skills/weicoz-codex-context-window-override}/scripts/apply.sh"
```

This defaults to:

- model slug: `gpt-5.5`
- context window: `1000000`
- Codex config: `~/.codex/config.toml`
- source catalog: the current `model_catalog_json` override when one exists, otherwise `~/.codex/models_cache.json`

### Apply a custom model/window override

Run:

```bash
bash "${CLAUDE_SKILL_DIR:-/Users/weicoz/.agents/skills/weicoz-codex-context-window-override}/scripts/apply.sh" gpt-5.4-mini 400000
```

Arguments:

1. model slug, for example `gpt-5.5`
2. window size, for example `1000000`

The script layers new changes on top of the currently configured `model_catalog_json` if one exists. This prevents a second model override from accidentally removing an earlier one.

### Roll back the latest override

Run:

```bash
bash "${CLAUDE_SKILL_DIR:-/Users/weicoz/.agents/skills/weicoz-codex-context-window-override}/scripts/rollback.sh"
```

This restores the latest config backup created by `scripts/apply.sh`. It does not delete patched catalog files; leaving them is safer and keeps the history auditable.

## Manual Workflow

Use the scripts by default. If you need to do it manually, follow this exact sequence.

1. Inspect current state:

```bash
rg -n "model_catalog_json|model_context_window|model_auto_compact_token_limit|^model =" ~/.codex/config.toml
codex debug models | jq '.models[] | select(.slug=="gpt-5.5") | {slug,context_window,max_context_window,effective_context_window_percent}'
```

2. Create backup and patch directories:

```bash
ts=$(date +%Y%m%d-%H%M%S)
mkdir -p ~/.codex/backups/codex-context-window-override ~/.codex/model-catalog-overrides
cp ~/.codex/config.toml ~/.codex/backups/codex-context-window-override/config.toml."$ts".bak
```

3. Create a patched catalog:

```bash
jq '(.models[] | select(.slug=="gpt-5.5") | .context_window)=1000000 | (.models[] | select(.slug=="gpt-5.5") | .max_context_window)=1000000' \
  "${existing_override:-$HOME/.codex/models_cache.json}" \
  > ~/.codex/model-catalog-overrides/gpt-5.5-1m-"$ts".json
```

4. Add or replace `model_catalog_json` in `~/.codex/config.toml`:

```toml
model_catalog_json = "/Users/weicoz/.codex/model-catalog-overrides/gpt-5.5-1m-YYYYMMDD-HHMMSS.json"
```

5. Verify:

```bash
codex debug models | jq '.models[] | select(.slug=="gpt-5.5") | {slug,context_window,max_context_window,effective_context_window_percent}'
```

Expected result:

```text
context_window = 1000000
max_context_window = 1000000
```

## Diagnosis

If `codex debug models` still shows `272000`:

1. Confirm `model_catalog_json` points to an existing file.
2. Confirm the patched catalog is valid JSON:

```bash
jq empty ~/.codex/model-catalog-overrides/<file>.json
```

3. Confirm the slug exists:

```bash
jq '.models[] | select(.slug=="gpt-5.5") | {slug,context_window,max_context_window}' ~/.codex/model-catalog-overrides/<file>.json
```

4. Re-run `scripts/apply.sh`.

## Rollback

Use the script first:

```bash
bash "${CLAUDE_SKILL_DIR:-/Users/weicoz/.agents/skills/weicoz-codex-context-window-override}/scripts/rollback.sh"
```

Manual rollback:

```bash
cp ~/.codex/backups/codex-context-window-override/config.toml.<timestamp>.bak ~/.codex/config.toml
```

Then verify:

```bash
rg -n "model_catalog_json|model_context_window|model_auto_compact_token_limit|^model =" ~/.codex/config.toml
codex debug models | jq '.models[] | select(.slug=="gpt-5.5") | {slug,context_window,max_context_window,effective_context_window_percent}'
```

## Final Response Pattern

After applying, report:

- config backup path
- patched catalog path
- changed config line
- `codex debug models` verification result
- rollback command
- clear warning that this does not guarantee server-side 1M support

After rolling back, report:

- restored backup path
- current verification result
- whether `model_catalog_json` is gone or still present
