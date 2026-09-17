# Design direction

## Design thesis

Pace should look like a modern endurance journal crossed with a sport-science
report: calm, exact, editorial, and built for repeated daily use. It should not
look like a generic AI SaaS dashboard.

## Visual system

### Colour

- Canvas: warm off-white, not pure white.
- Primary text: near-black ink.
- Structural colour: restrained forest green.
- Action/accent: one energetic lime or orange used sparingly.
- Running and cycling: distinct, accessible series colours used consistently.
- Recovery charts: individual colours only where they improve comparison.

### Typography

- Strong editorial display face or heavy grotesk for page headings.
- Highly legible sans-serif for body and data.
- Compact monospaced or narrow uppercase labels for metadata.
- Headings should establish hierarchy without consuming half the viewport.
- Tabular numerals for dates, durations, zones, and chart values.

### Geometry

- Visible grid, rules, and alignment.
- Square corners or a restrained 2–6 px radius.
- Cards exist only where grouping adds meaning.
- Avoid nested rounded cards, floating pills, glass effects, shadows, and
  decorative gradients.

### Density

- Desktop is intentionally information-rich.
- Use whitespace to separate decisions, not to create empty marketing space.
- A user should see today's session and its reason without scrolling.
- Charts should be large enough to read but never overwhelm their labels.

## Application shell

One persistent header across all views:

- Pace wordmark;
- Today/Coach, Dashboard, Plan, Weekly Review, Races, Settings;
- current local date;
- local-only status;
- compact sync status/action.

Use a centered maximum-width shell with sensible side padding. On small screens,
collapse navigation into an accessible menu but preserve quick access to Today,
Plan, and Sync.

## Chart requirements

- Always show axis labels, units, date ticks, legend, and window length.
- Never encode running and cycling as one undifferentiated training series.
- Tooltips and keyboard focus reveal the exact date and raw supplied values.
- Missing values create gaps or explicit missing markers, never zero bars.
- Include a table or textual summary for accessibility.
- Use SVG or a lightweight local chart library; no remote runtime dependency.

## Session presentation

The session purpose is the heading. Show date and sport first, then scope,
primary target, and outcome. Workout steps form a vertical sequence:

```text
Warm-up -> 5 x 1 km work / 90 s recovery -> Cooldown
```

A continuous 50-minute Z2 ride is one steady block. Do not invent warm-up and
cooldown sections just to fill a template. Work and recovery targets should be
visually distinct, with repetitions and dose scannable at a glance.

## Interaction principles

- Read-only facts and write actions must look different.
- Any AI, Garmin, or persistence action states its consequence before running.
- Confirmation cards disappear or become completed immediately after success.
- Errors explain what changed, what did not change, and the next safe action.
- Preserve page and conversation context across normal navigation while the
  local server is running.
- Never imply that an AI answer saved data unless the Python service confirms it.
