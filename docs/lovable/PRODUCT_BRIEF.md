# Pace product brief

## One-sentence description

Pace is a private, local-first AI running and cycling coach that turns actual
Garmin history, recovery data, life context, goals, and explicit feedback into
reviewable training decisions.

## The problem

Most consumer training-plan products ask athletes to describe their own volume,
capacity, and personal bests, then generate a schedule from those claims. That
is convenient but easy to overstate and weak at recognising interrupted
training. Other products show large quantities of wearable data without making
a concrete coaching decision.

Pace uses imported history as evidence. It distinguishes a recent interruption
from an established baseline, keeps uncertainty visible, and does not let one
high or low week define capacity by itself.

## Product promise

Pace should answer five questions quickly:

1. What am I doing today?
2. Why is that the right session now?
3. What has changed in my training or recovery?
4. Does the plan need a deliberate revision?
5. What does Pace know, infer, and still not know?

## Product character

- Direct, not soothing.
- Evidence-led, not falsely precise.
- Information-rich, not visually noisy.
- Athlete-controlled, not autonomous.
- Private by architecture, not by a marketing promise.

## Differentiation

- Actual Garmin history replaces manually declared recent volume.
- Multi-horizon continuity reduces sensitivity to a single unusual week.
- Python calculates facts; the model makes labelled coaching judgments.
- Structured workouts can represent both simple endurance and real intervals.
- Athlete feedback and context can influence later drafts without rewriting
  historical plans.
- The full system runs on the athlete's own computer and uses their own keys.

## Current limitations that the UI must state honestly

- Garmin Connect access is unofficial and can rate-limit or change.
- Pace is not medical software and does not diagnose injury or illness.
- Garmin synchronization is explicit, not continuous in the background.
- AI requests use the athlete's own OpenAI API key and may incur a small cost.
- Missing feedback stays unknown; Pace does not infer non-completion from silence.
- GPS routes and per-second sensor streams are not model context.
- v0.1 supports one local athlete, macOS-first, running and cycling only.
