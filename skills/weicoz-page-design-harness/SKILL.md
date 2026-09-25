---
name: weicoz-page-design-harness
description: 设计、审查或实现项目页面与应用界面，从现有产品、用户任务、设计系统和约束确定布局与验收。适用于页面设计与优化；只有关键业务信息无法查证时才澄清，不要求先填写完整问卷。
---

# weicoz-page-design-harness

Repeatable workflow for designing any project page or screen.

Use this skill when the user wants:
- A new page or screen designed
- An existing page redesigned or reviewed
- A page layout turned into a structured brief, wireframe, or implementation plan
- A design workflow that must first collect required inputs before any layout work starts

This skill is stack-agnostic. Do not assume React, Vue, Flutter, HTML, or any other implementation stack unless the user says so.

## Core rule

先从用户请求、当前页面和项目约定提取目标与约束。只有目标页面、核心业务行为或授权范围无法确定且影响交付时才集中澄清；仅暂停依赖答案的工作。参考图、次要任务、品牌素材等非关键缺项采用现有约定或说明假设，不把整张问卷作为开工门槛。用户明确要求先访谈时遵循其节奏。

## Required intake

以下字段用于检查已有证据，按任务相关性选取，不要求用户逐项填写：

| Field | Why it matters |
|---|---|
| Project name or repo/path | Anchors the work to the right product |
| Page or screen name | Clarifies scope |
| Product goal | Defines what the page must achieve |
| Primary user type | Shapes content, hierarchy, and tone |
| Main user task | Identifies the key action to optimize |
| Secondary tasks | Prevents the page from overfitting to one action |
| Platform and device target | Changes layout constraints |
| Stack or delivery format | Controls output format and implementation shape |
| Existing brand or design system | Keeps output consistent |
| Hard constraints | Prevents invalid ideas |
| Reference pages or anti-references | Gives concrete taste boundaries |
| Acceptance criteria | Makes the result measurable |
| Content/data inputs | Avoids designing around fake content |

Nice to have, but not mandatory:
- Analytics or conversion target
- Accessibility requirements
- Locale or language constraints
- Deadline or release context
- Known pain points from users or PM review

## Intake question format

只询问从上下文和页面证据无法确定、且实质影响本次结果的问题。以下是候选问题，不是必问清单：

1. What page or screen are we designing?
2. What is the product goal for this page?
3. Who is the primary user?
4. What is the single most important task?
5. What constraints or existing system must we follow?
6. What are the acceptance criteria?

用户只说“优化页面”时，已有明确页面就先审查并完成已授权的改进；目标页面无法定位时才询问位置。

## Execution workflow

### 1. Restate the brief

Summarize the page in one compact brief:
- audience
- goal
- primary action
- constraints
- success criteria

未知项按影响分为关键待决和可说明假设；只有关键待决阻塞依赖它的部分。

### 2. Build information hierarchy

Define:
- first thing user must understand
- first thing user must do
- supporting information
- optional information
- distractions to remove

Prefer utility over decoration. Keep the first viewport focused on the main task.

### 3. Choose page structure

Design the layout from task flow, not from visual style first.

Work in this order:
- entry point
- main content area
- supporting content
- actions
- empty/error/loading states

If multiple layout options exist, present the smallest option that still solves the task.

### 4. Define content and copy

Write the page copy only after structure is clear.

Rules:
- Use plain language
- Make button labels action-oriented
- Avoid marketing filler unless the page is explicitly marketing-focused
- Keep labels short and unambiguous

### 5. Define acceptance criteria

Turn vague satisfaction into testable checks.

At minimum include:
- User can identify purpose of page quickly
- User can find primary action without guidance
- Layout works on target devices
- Empty/error/loading states exist where relevant
- Text fits without overlap or truncation
- Page matches stated constraints

If the page is user-facing, add a first-time-user check:
- Can a new user complete main task without explanation?

### 6. Produce output

Choose the output based on what user asked for:
- design brief
- wireframe or layout plan
- implementation-ready spec
- component inventory
- page review with issues and fixes
- acceptance checklist

If the user wants implementation, produce the smallest code or structure that matches the brief. Do not invent extra screens or flows.

## Output contract

按用户交付要求选择相关内容，不要求每次输出以下全部章节：

1. `Brief`
2. `Missing info` or `Assumptions`
3. `Layout`
4. `Copy`
5. `States`
6. `Acceptance criteria`
7. `Open questions`

If nothing is missing, replace `Missing info` with `Assumptions`.

## Quality bar

Treat the page as acceptable only if:
- hierarchy is obvious
- primary action is visible
- user has a clear next step
- layout matches product type
- design does not rely on vague taste language
- acceptance criteria are specific enough to verify later

If a request is really about broader product strategy, stop at the page level and call that out explicitly instead of pretending the page can solve product ambiguity.

## When to ask the user instead of deciding alone

以下选择仅在改变已约定业务含义、外部契约或任务范围且证据无法确定时询问；常规文案、布局和响应式实现自行决定：
- primary CTA wording
- onboarding vs direct action
- dense dashboard vs guided flow
- marketing-first vs utility-first layout
- hard validation vs soft guidance
- mobile-first vs desktop-first priority

## Good trigger examples

- "把这个项目首页做成适合首次用户的布局"
- "基于现有功能做一个管理台页面，先帮我定验收标准"
- "把这个页面设计成可以让 PM 直接评审的版本"
- "做一个通用页面设计流程，先问我需要哪些信息"

## Bad inputs

If the user only says:
- "帮我设计一个页面"
- "做得好看点"
- "优化一下 UI"

先检查当前上下文是否已有页面和目标；能定位就继续，无法定位时只补问关键缺项。
