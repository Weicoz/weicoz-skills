---
name: weicoz-page-layout-ascii-guide
version: 1.0.0
description: Guide users who know what content they need on a page but do not know how to structure the page, choose layout skeletons, or produce a wireframe. Use this whenever the user is unclear about UI layout, page structure, information hierarchy, first-screen composition, module order, or asks for help turning content into an ASCII page skeleton.
---

# weicoz-page-layout-ascii-guide

Use this skill when user says things like:
- "我知道要展示什么，但不会排页面"
- "不知道怎么做页面布局"
- "不知道页面结构怎么定"
- "帮我先做页面骨架"
- "先出 ASCII 原型图"

Goal:
- take user's raw content list
- convert it into page goal and information hierarchy
- choose layout skeleton
- output ASCII wireframe

Do not jump straight into drawing boxes.
First solve structure. ASCII is final artifact, not first step.

## Core product-flow rule

Page structure and any user-operation-related content must follow one principle:

- use fewest reasonable steps to get user to target action

Apply this to:
- navigation depth
- click count
- form step count
- confirmation hops
- view switches
- hidden actions behind tabs or extra pages

If two layouts both work, choose shorter path unless longer path clearly reduces confusion, risk, or error.

## Core rule

When user does not know layout, guide them through one fixed flow:

1. page must answer what question
2. content gets priority tiers
3. choose layout skeleton
4. output ASCII

If any step is skipped, layout will become arbitrary. Do not skip.

## Trigger conditions

Use this skill when user has content but lacks structure.

Do not use this skill when:
- user already has a clear wireframe
- user asks for visual polish only
- user asks for implementation only and layout is already decided

If request is actually about branding, visual style, color, motion, or component skinning, say layout skeleton is already solved and switch to design work instead.

## Intake

If user has not given enough input, ask for these fields in one compact batch:

1. 页面类型
2. 目标用户
3. 页面目标
4. 必须展示内容
5. 用户 first 5 秒最该看到什么
6. 页面最重要动作是什么

Optional but useful:
- 次要动作
- 现有参考页面
- 平台限制（web / mobile / dashboard / landing / form）

If user already gave enough context, do not ask again. Move forward.

## Workflow

### 1. Define page question

First determine what question page must answer.

Common question types:
- 我现在状态如何？
- 我下一步点哪？
- 我为什么要相信这个内容？
- 我应该选哪个？
- 我如何完成这个流程？

Output:
- `Page question`
- `Primary action`
- `Shortest successful user path`

If more than one primary question exists, force user into priority order. One page can have support questions, but one main question.

Also state shortest successful path in plain language, for example:
- arrive -> understand -> click CTA
- scan list -> choose item -> inspect detail -> confirm
- read summary -> fill fields -> submit

### 2. Tier content

Convert raw content into four tiers:

- `P0` 核心信息  
  User must see this first. Without it page fails.

- `P1` 决策信息  
  Helps user decide or act.

- `P2` 证明信息  
  Evidence, examples, screenshots, metrics, testimonials, comparisons.

- `P3` 补充信息  
  FAQ, edge cases, notes, extra links, low-priority detail.

Do not preserve the user's original order blindly. Reorder by decision value.

If an item does not support page question or primary action, call it out as removable noise.

### 3. Choose layout skeleton

Choose from these skeletons only. Prefer smallest one that fits.

#### Single column

Use when:
- flow is sequential
- content is read top to bottom
- page is onboarding, article, landing, form, settings, detail page

Pattern:
- header
- hero / core message
- P0
- P1
- P2
- P3

#### Main + sidebar

Use when:
- one area is primary
- one area is support
- user needs utility panel, summary, filters, metadata, checklist

Pattern:
- main content = P0/P1
- sidebar = summary / proof / actions / meta

#### Card grid

Use when:
- several peer modules have equal weight
- user scans multiple options
- content is a set, not a story

Pattern:
- short overview
- repeated cards
- optional detail expansion

#### Tabs

Use when:
- same region has multiple peer views
- user does not need all views at once
- switching context is acceptable

Never put core first-screen message inside tabs.

#### List-detail

Use when:
- user browses many items then opens one
- left side selects, right side explains
- tables, CRM, CMS, admin tools

Pattern:
- list / filters
- selected item detail

### 4. Build module order

Default module sequence:

1. title
2. one-line explanation
3. primary action
4. P0
5. P1
6. P2
7. P3

If user asks for dashboard/admin tool:
- top summary first
- main working area second
- proof or history third
- edge/support areas last

If user asks for marketing / landing:
- promise first
- why it matters second
- proof third
- FAQ last

If user asks for form / setup:
- instructions short
- inputs central
- helper text near inputs
- summary / next step visible

At this step, simplify path:
- merge steps when split adds no value
- move primary action earlier once user has enough context
- avoid forcing users through tabs before they can act
- avoid putting key action below long proof blocks unless trust is blocker
- avoid multi-screen flow if one screen can safely finish job

### 5. Output ASCII

After structure is decided, output ASCII wireframe.

Rules:
- label regions by meaning, not visual decoration
- show hierarchy clearly
- include CTA position
- include main vs support grouping
- keep ASCII low fidelity
- no fake lorem ipsum

Preferred format:

```text
[Page Title]          [Primary CTA]
[One-line explanation]

-----------------------------------
[P0 Hero / Core Information]
-----------------------------------

[P1 Section A]
[P1 Section B]

-----------------------------------
[P2 Proof / Examples / Metrics]
-----------------------------------

[P3 FAQ / Notes / Extra]
```

For main + sidebar:

```text
[Page Title]                    [Primary CTA]
[One-line explanation]

---------------------------------------------------------
| Main: P0 / P1                         | Sidebar        |
| - core content                        | - summary      |
| - main workflow                       | - proof        |
| - decision details                    | - next step    |
---------------------------------------------------------

[P2 Proof / Cases / Comparison]

[P3 FAQ / Notes]
```

For list-detail:

```text
[Title]                     [Primary CTA]

---------------------------------------------------------
| List / Filters            | Detail Panel              |
| - item 1                  | - selected item summary   |
| - item 2                  | - key info                |
| - item 3                  | - actions                 |
---------------------------------------------------------
```

## Output contract

Default response structure:

1. `Page question`
2. `Primary action`
3. `Content tiers`
4. `Chosen layout skeleton`
5. `Why this skeleton fits`
6. `Shortest path simplification`
7. `ASCII wireframe`
8. `Open questions`

If context is incomplete, include:
- `Missing info`

instead of pretending certainty.

## Decision heuristics

Use these practical rules:

- If user must read in order, use single column.
- If one region is doing main work and one region is support, use main + sidebar.
- If modules are equal siblings, use card grid.
- If views are alternative faces of same data, use tabs.
- If user browses many records then inspects one, use list-detail.

More rules:

- first screen shows P0 + primary action
- first usable action appears as early as clarity allows
- proof belongs after understanding, not before
- FAQ belongs low unless trust risk is blocking conversion
- do not hide P0 in accordion or tabs
- do not use cards just because cards look modern
- do not add screens, clicks, or steps unless they reduce confusion, risk, or error
- if A -> B -> C can happen in one visible flow, prefer one flow
- if action path is longer than needed, call it out and simplify it

## When user is overwhelmed

If user gives too much content and feels lost:

1. restate page question in one line
2. pick one primary action
3. cut content into P0-P3
4. choose one skeleton only
5. shorten operation path
6. output one ASCII draft

Do not give three competing layouts unless user explicitly asks.

## Good response example

If user says:
"我有产品介绍、功能点、案例、价格、FAQ，不知道首页怎么排"

Good behavior:
- identify page question: "why should I trust and try this product?"
- set primary action: "start trial" or "contact sales"
- define shortest path: "understand -> trust -> click start trial"
- tier content:
  - P0 promise + key CTA
  - P1 features + use cases
  - P2 cases / metrics / testimonial
  - P3 pricing details / FAQ
- choose single column
- output ASCII

## Bad behavior

Do not:
- jump into colors or style
- list abstract UX principles with no layout choice
- output only bullets and no ASCII
- produce visually fancy mockup language instead of structure
- keep every user-provided content item at same priority
