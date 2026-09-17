# Screen specifications

## 1. Today / Coach

### Purpose

The daily decision surface. It answers what to do, why, and whether the athlete
must act.

### Required content

- Today's date, sync freshness, and local-only state.
- Today's planned session with structured workout steps.
- Concise recovery and context signals with data-quality labels.
- Next race or general-plan goal.
- Recent non-persistent coach dialogue.
- Suggested questions and the reviewed slash-command palette.
- Confirmation cards for feedback, context, sync, review, and plan creation.

### Important states

- Rest day.
- Planned session, no matching Garmin activity yet.
- Recent synced activity available.
- Feedback already recorded.
- Stale data / authentication required / rate limited.
- Model unavailable; plan and local facts remain unchanged.

## 2. Dashboard

### Purpose

Expose current facts and trends without an AI call.

### Required content

- 28-day and 84-day window selector.
- Training hours over time, run and ride separated.
- Run distance, ride duration/distance, frequency, and active days.
- HRV, resting heart rate, and sleep charts with 28-day baselines.
- Explicit feedback and RPE summary.
- Current Garmin-owned values labelled as Garmin facts, not Pace rules.
- Coverage, last sync, missing-data, and limitation panel.

### Chart behaviour

Visible axes and units, responsive size, pointer and keyboard tooltips, missing
data gaps, and an accessible raw-values table or disclosure.

## 3. Plan

### Purpose

Show the currently active coaching commitment and the next executable sessions.

### Required content

- Goal header: general or selected race, priority, distance, date, desired time,
  and taper policy where applicable.
- Block timeline from now to goal.
- Detailed-window dates and revision status.
- Structured session cards with date, sport, purpose, scope, main target,
  workout steps, and outcome.
- Coach assessment separated into facts, inference, rationale, uncertainties,
  principles, and knowledge support.
- A visible `Create next 14 days` action only when the server marks it due.
- Previous plan versions in a secondary history view.

## 4. Weekly Review

### Purpose

Present one immutable, explicitly created weekly AI assessment.

### Required content

- Week-ending date and creation timestamp.
- What happened.
- Training response and recovery observations.
- Coach assessment and next actions.
- Uncertainties, missing feedback, and data-quality limitations.
- Selected knowledge references.
- Clear action to create a new review; opening the page never creates one.

## 5. Races

### Purpose

Manage future goal options without making every stored race a plan target.

### Required content

- Active future races sorted by date.
- Add/edit/cancel forms with name, sport, date, distance, A/B/C priority,
  optional desired time, and taper choice.
- Explain why a referenced race may be immutable.
- Plan creation always offers `General plan` separately from each active race.

## 6. Settings

### Purpose

Keep normal use out of the terminal.

### Sections

- Sport role and coaching ambition.
- Weekly availability and optional per-day time caps.
- Cycling heart-rate zones.
- Garmin connection and 7-/80-day sync controls.
- OpenAI key replacement and model/cost explanation.
- Privacy, version, diagnostics, and export-safe support information.

## 7. Onboarding

### Purpose

Guide a first-time user from clone to first active plan.

### Sequence

1. Welcome and local privacy model.
2. OpenAI key.
3. Garmin login and optional MFA.
4. Sport role, ambition, availability.
5. Cycling zones when cycling is enabled.
6. 80-day history sync with progress and safe retry.
7. Optional races.
8. Explicit general/race target selection.
9. First plan generation and validation.

The flow is resumable. Completed steps remain complete after restart. Optional
steps are visibly optional, and errors never erase earlier progress.

## 8. Session detail and feedback

### Purpose

Connect prescription, observed activity, and explicit athlete response.

### Required content

- Full planned workout and purpose.
- Same-day same-sport Garmin comparison when available.
- Clear warning that Garmin splits do not prove interval compliance.
- Outcome: completed, completed with limitations, or skipped.
- Optional RPE, structured reason, private note, and explicit share-with-AI
  control.
- Server-confirmed saved state that prevents duplicate submissions.
