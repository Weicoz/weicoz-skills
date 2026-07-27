---
name: weicoz-toolify-month-rank-filter
description: >
  Use when the user wants to query Toolify's monthly AI-tool rankings for one month or a month-by-month set, filter by month_visited_count,
  growth, growth_rate, and Toolify category/site type, then return matching tools with both the Toolify detail page and the official website.
  Also use when the user mentions Toolify 月榜、month-top、月访问量、增长、增长率、网站类型、视频与动画、AI 工具排行、Toolify 官网、Toolify 详情页,
  or wants a repeatable workflow that can optionally be saved as Markdown after the table is shown.
---

# Toolify 月榜筛选

Use this skill for Toolify monthly ranking lookups only. Keep the workflow tight: fetch once per month, filter locally, then return a compact result table. If the user asks for multiple months, process each month separately and keep the sections clearly separated.

## Supported request shape

- Exactly one month per run.
- `month` should be normalized to `YYYY-MM`.
- Optional filters:
  - `month_visited_count`
  - `growth`
  - `growth_rate`
  - `site_type` / `category`
- Optional sort:
  - `sort_by`: `month_visited_count`, `growth`, or `growth_rate`
  - `direction`: `asc` or `desc`

Defaults:

- If `sort_by` is omitted, use `growth`.
- If `direction` is omitted, use `desc`.

Rules:

- If the user omits a filter, do not invent one.
- If the user provides multiple filters, all of them must match.
- Treat all ranges as inclusive.
- Accept `growth_rate` input as either a decimal or a percentage. Convert percentages like `10%` to `0.10` before filtering.
- Normalize natural month phrasing such as `2026年4月` or `April 2026` to `YYYY-MM`.
- Treat `site_type` as a Toolify category filter, not a free-form website tag.
- If the user provides multiple categories, process them as separate sections instead of merging them silently.
- Do not ask for sort order unless the user explicitly wants a non-default sort.

## Decision Rules

- Exactly one month per run. If the user asks for multiple months, process each month as a separate section or file.
- If `site_type` is provided, category resolution is required; do not silently ignore it.
- If the official website cannot be resolved from the detail page, fall back to the Toolify detail URL and say so explicitly.
- If the month ranking response is blocked or unexpected, prefer live-page inspection over guessing.

## Data source

1. Convert `YYYY-MM` to the first day of that month: `YYYY-MM-01`.
2. Fetch the monthly ranking JSON with `bb-browser fetch`:

```bash
bb-browser fetch "https://www.toolify.ai/self-api/v1/top/month-top?page=1&per_page=50&date=YYYY-MM-01&order_by=<sort_by>&direction=<direction>"
```

3. Read `data.data` from the JSON response.
4. If `site_type` is provided, resolve the matching Toolify category page from `https://www.toolify.ai/zh/Best-AI-Tools-Category`, extract all `/zh/tool/` handles from that page, and intersect them with the month rows.
5. Filter the returned rows locally using the user-specified numeric ranges.
6. Keep the result ordered by the selected sort field and direction.
7. For each matching row, build the Toolify detail URL from `handle`:

```text
https://www.toolify.ai/zh/tool/<handle>
```

8. Resolve the official website from the detail page:
   - Prefer the prominent `打开网站` / `访问网站` link near the top of the page.
   - Use the SSR HTML or the live tab DOM to extract the top CTA URL from the `to-view-btn` anchor.
   - Normalize the final URL by removing tracking params such as `utm_source`, `ref`, or `fpr` when safe.
   - If the official site cannot be resolved, fall back to the Toolify detail URL.

Prefer `bb-browser fetch` for both the month API and the detail page HTML. If a request returns a Cloudflare challenge or unexpected HTML, open the URL in a browser tab and inspect the live page text instead. Close any temporary tabs after extracting the URL.

## Failure Modes

| Trigger | First action | If still unclear |
| --- | --- | --- |
| Cloudflare challenge or unexpected HTML | Open the live page and inspect rendered text | Report the block and stop instead of guessing rows |
| Multiple months requested | Split into separate month sections | Do not merge months into one combined table |
| `site_type` / category ambiguous | Resolve from the best matching Toolify category page | If still ambiguous, return separate sections instead of silently merging |
| Official website cannot be resolved | Fall back to the Toolify detail URL | Make the fallback explicit in the final column |
| Filtered result is empty | Report the empty result honestly | Do not widen filters unless the user asks |

🔴 CHECKPOINT: The output is only valid if the month, filters, category resolution, and official-link fallback are all explicit.

## Output format

Return a compact table with these columns:

- `Name`
- `Website Type` when a category filter is used
- `Month Visits`
- `Growth`
- `Growth Rate`
- `Toolify URL`
- `Official Website URL`

If the official URL falls back to Toolify, make that explicit in the last column.

Keep the response short and operational. The user wants a filtered list they can act on, not a long explanation.

After the table, ask one short follow-up: whether the user wants the same result saved as a Markdown document.

## Markdown export

If the user answers yes, save one Markdown file per month under `playground/outputs/toolify-month-rank/`.

Use this filename pattern:

- Single month: `YYYY-MM.md`
- Month + category: `YYYY-MM-<category-slug>.md`

If multiple months or categories are requested, keep each export separate so the documents stay easy to reuse.

## Practical notes

- The month-top endpoint returns the full month list for this use case, so local filtering is enough after one fetch.
- Toolify detail pages usually expose the official link directly in the rendered HTML as a dofollow CTA.
- Use the tool handle as the stable key for composing detail URLs.
- The category hub page is enough to resolve the right website type when the user gives a Toolify category name in Chinese.

## Anti-Patterns

- Do not invent filters the user did not ask for.
- Do not merge multiple months silently into one table.
- Do not claim an official website URL when only the Toolify detail URL was available.
- Do not skip the follow-up question if the user asked for a Markdown export path.
- Do not treat a blocked fetch as a valid ranking extract.

## Example prompts

- `Toolify 2026-04 视频与动画类，筛出月访问量 50万到200万、月增长 20万以上，默认排序，给我结果表`
- `Toolify 2026-03 视频与动画类，筛出月访问量 50万到200万、月增长 20万以上，如果可以就顺手存成 Markdown`
- `Toolify 2026-04 图像生成与编辑类，筛出月访问量 100万到300万、增长率 10% 到 80%，给我官网和 Toolify 详情页`
