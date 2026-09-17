# Lovable master prompt

Build a high-fidelity frontend prototype for **Pace**, a local-first AI running
and cycling coach. First read and obey the Project Knowledge. Before changing
code, return a concise implementation plan covering the application shell,
routes, component system, mock-data adapter, chart strategy, responsive layout,
and accessibility.

## Build scope

Create these navigable product areas:

1. Today / Coach
2. Dashboard
3. Plan
4. Weekly Review
5. Races
6. Settings
7. Resumable first-run onboarding
8. Session detail and feedback

Use React, TypeScript, and the project's normal Lovable frontend stack. Build a
typed `PaceClient` adapter with a synthetic `MockPaceClient`. Components must
depend on the adapter, not import fixtures directly. Do not build a backend.
Do not enable Lovable Cloud, Supabase, authentication, telemetry, external
APIs, or remote storage. Do not ask for real credentials. All prototype data
must be obviously synthetic.

## Experience goal

The first viewport should tell the athlete what today's session is, why it is
appropriate, whether data is current, and whether action is needed. The app is
for a serious endurance athlete, so make it information-rich without becoming
cluttered. It should feel like a well-designed training journal and sport-
science report, not a generic AI SaaS dashboard.

## Visual constraints

- English product text.
- Warm off-white background, near-black text, restrained forest green, and one
  energetic accent.
- Square or lightly rounded geometry with visible rules and a strong grid.
- Persistent navigation and the same shell on every screen.
- Centered responsive maximum-width content.
- Dense, legible typography with sensible heading sizes.
- No default dark theme, gradients, glass, glows, excessive rounded cards,
  pill-heavy navigation, giant empty hero sections, or oversized metrics.
- Use icons only when they improve recognition; do not decorate every label.

## Dashboard requirements

Create useful charts with real axes, units, dates, legends, hover and keyboard
tooltips, missing-data gaps, and accessible tabular alternatives. Separate run
and ride training. Support 28-day and 84-day views. Include HRV, resting heart
rate, sleep, feedback/RPE, data coverage, and last-sync state. Never combine all
training into one unexplained score.

## Plan requirements

Represent both simple and structured sessions correctly. A 50-minute easy ride
can be one steady block. An interval session can contain warm-up, repeated work
and recovery, and cooldown. Warm-up and cooldown are optional, not mandatory.
Show the block timeline toward a race or general goal, next 14 detailed days,
race priority, coach assessment, uncertainty, outcomes, and revision-due state.

## Interaction requirements

Prototype the complete state transitions for:

- Garmin 7-day and 80-day sync, including progress, partial failure, rate limit,
  authentication-required, retry, and completion;
- coach reply with a separate confirmable feedback or context action card;
- successful confirmation that disables/removes the action and visibly marks
  it saved;
- creating a general plan or explicitly choosing one stored A/B/C race;
- recording completed, completed-with-limitations, or skipped feedback;
- creating the next 14 detailed days only when revision is due;
- weekly review absent, running, failed, and saved as a dated snapshot.

No mock action may pretend to have succeeded before its simulated server result.
Use clear busy states and prevent duplicate submissions.

## Content and trust

Keep observed facts, coach judgment, and uncertainty visually distinct. The
coach voice is direct and factual, not flattering or therapeutic. Never present
Pace as medical software. Show missing data as unknown, not zero. Explain that
Garmin matching does not prove interval compliance and that explicit athlete
feedback is the durable outcome.

Use the uploaded Pace screenshots to understand existing information and
workflow only. Improve their hierarchy, navigation, responsiveness, density,
and charts substantially; do not copy their existing styling blindly.

After the plan is approved, implement screen by screen, beginning with the
shared shell, Today / Coach, Plan, and Dashboard. Keep every screen populated
with coherent synthetic data for one fictional athlete and one upcoming 10 km
race.
