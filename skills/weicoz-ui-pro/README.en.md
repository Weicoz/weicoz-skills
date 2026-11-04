[中文](README.md) · English

# weicoz-ui-pro

> weicoz login-free edition: content is synced from the upstream `oil-ui-pro` as-is, with only account login, update checks, and paid credit-based image generation removed. When the upstream is installed locally, using this Skill checks and syncs automatically; you can also run `python3 scripts/sync_upstream.py --apply`.

An interface design method for AI agents. It recommends one strong direction and refines it against real screenshots, or explores several side by side when you ask to compare. It works for websites, apps, dashboards, and components, and it can also just review a design.

## Usage

Tell your agent what you need, for example:

- “Use weicoz-ui-pro to explore a few design directions for this course booking product and build pages I can preview.”
- “Create three designs with different typography, colors, and compositions. Put them on a comparison page so I can choose.”
- “Keep the current brand and layout. Improve this form’s hierarchy, error messages, and mobile experience.”
- “Polish this page using the project’s existing design guidelines.”
- “Review these interfaces and explain what to change and how. Leave the files untouched.”

Share any brand assets, screenshots, or existing project you have. It can start without references and only asks you questions when the deliverable is unclear.

Intermediate candidates, screenshots, and media caches live in the project’s `.oil-ui` workspace. Final code and production assets are still written back to the project, and existing project conventions take precedence.

## How it works

- **One recommendation by default, more when you ask to compare.** It understands the product and its references, selects the strongest internal candidate for your confirmation, then refines it against real screens. When you explicitly ask to compare directions, levels of change, or layouts, it puts the previews on one comparison page and develops only the one you choose.
- **Leave one moment people remember.** Instead of pushing every part of the page, it makes one or two details exceptional, such as the response to a tap, a successful payment, AI at work, or a 404 page. Everything else stays quiet.
- **Refine against real screenshots.** It checks the result at desktop and mobile sizes, then brings in a reviewer who hasn't seen the work in progress to find problems and give a score. It revises and reviews again, aiming for 9/10 within three rounds. With several directions, a side-by-side review catches sections that look alike; for new interfaces, the reviewer actually completes real tasks on the page.
- **Make interfaces easy to use.** Interactions and states, forms, dialogs and popovers, and desktop and mobile layouts each come with concrete practices. For dashboards and tools, it picks a workspace layout that fits what the product handles, and carries the style from the first screen all the way down.
- **Polish a single component to the extreme.** It starts with a visual anchor, such as a realistic product render, takes the palette from it, and picks one graphic motif to carry throughout. From two or three sketches it develops just one: every state gets its own visual, and the main interaction acts directly on the anchor, so results appear as you drag. Review rounds check it up close, and it finishes with a showcase image plus an interaction frame sequence or a page the reviewer can operate directly. It records video only when normal-speed feel needs checking and the reviewer can play it.
- **Start an existing project by working out what you want.** If it looks dated, it first decides whether the current design system is worth keeping, then recommends one level of change; explicit comparisons can cover anything from a light cleanup to a full reshape. If it's hard to use, it walks through the real task itself, finds out why the extra steps exist, and fixes the structure instead of adding a hint. For a new feature, it learns the product's existing habits first, then proposes genuinely different ways to do the job while keeping the current visual system. Changes go into shared components and design tokens; something as small as a single button gets changed directly.
- **Keep the design system in the project.** After the first page of a new product, or once you pick a direction for an existing one, it writes the confirmed rules into `DESIGN.md` at the project root, so the next conversation and other agents follow the same system. When rules are scattered and contradict each other, it lists every conflict and how it plans to resolve it, then merges them into one file after a single confirmation, without touching product pages.
- **Grow one page into a full set.** When there are several pages to build, it first draws a page map, makes one reference page per page type, pulls shared variables and components out of them, and records them in the design spec. Pages then roll out in batches; after each batch it lines the pages up side by side, finds drift in navigation, buttons and spacing, and fixes it at the source.
- **Revise with a method.** When you say "make it feel more premium", it finds which parts of the screen cause the feeling and turns them into concrete changes. Every round comes with a before/after image and a check that the things you already approved are still intact. When the same comment keeps coming back or comments contradict each other, it tells you the problem is the direction, and suggests two quick drafts to reset it instead of polishing details forever.

There are methods for visual hierarchy, typography, color, spacing, imagery, motion, scroll storytelling, and effects such as light trails, dot patterns, and flowing gradients. It won't push every product into the same style, and it won't add generated images, animation, or effects to every page. It uses them only where they help.

## Built-in style comparison page

When you want to compare designs, it puts them side by side on one page. They can be HTML files, images, or running development pages, and the current version can go first as a baseline. You can switch between desktop and mobile sizes, open each one at actual size, and browse with the arrow keys. Click “Select” on the one you like, paste the copied sentence into your agent, and it carries on from there.

## Use with

- [oil-motion](https://github.com/oil-oil/oil-motion): Turn generated videos or frame sequences into web animation controlled by scrolling or dragging, such as product teardowns or camera fly-throughs. Use it for a striking opening animation.
- [oil-tone](https://github.com/oil-oil/oil-tone): Rewrites headings, descriptions and intro copy so they read naturally and clearly, in Chinese or English. Use it when the copy feels machine-written or awkward.
