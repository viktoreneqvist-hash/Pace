/**
 * Synthetic demo data for the Pace prototype.
 *
 * INTERNAL: only mock-client.ts may import this file. Routes and components
 * must go through the PaceClient adapter so a real HttpPaceClient can replace
 * it without touching the UI.
 *
 * All content here is invented for one fictional athlete. It contains no real
 * athlete data, no credentials, no provider payloads and no GPS or stream data.
 */

import type {
  CoachMessage,
  Fact,
  PlanHistoryEntry,
  PlanSession,
  PlanView,
  PlannedSession,
  TimelineWeek,
  SlashCommand,
  SyncState,
  TodayView,
} from "./types";

export const DEMO_TODAY = "2026-09-17";

const todaySession: PlannedSession = {
  id: "sess-2026-09-17",
  date: DEMO_TODAY,
  sport: "running",
  title: "Controlled 10 km specific repetitions",
  purpose:
    "One quality session in the week. Repetitions are paced by effort, not by an unverified race pace.",
  scope: "11 km / 55 min",
  mainTarget: "RPE 6-7 on the work blocks",
  blocks: [
    {
      id: "b1",
      kind: "warmup",
      amount: "15 min",
      target: "RPE 2-3",
      note: "Easy running until breathing is settled.",
    },
    {
      id: "b2",
      kind: "intervals",
      amount: "5 x 4 min",
      target: "RPE 6-7",
      note: "Even effort across all five. Do not race the first repetition.",
      recovery: { amount: "2 min jog", target: "RPE 1-2" },
    },
    {
      id: "b3",
      kind: "cooldown",
      amount: "10 min",
      target: "RPE 2",
      note: "Optional on this session; stop earlier if the legs are done.",
    },
  ],
};

const facts: Fact[] = [
  {
    id: "hrv",
    label: "HRV vs 28-day baseline",
    value: "-3",
    unit: "ms",
    detail: "58 ms against a 61 ms baseline. Inside normal day-to-day variation.",
    coverage: "28/28 days",
  },
  {
    id: "rhr",
    label: "Resting heart rate",
    value: "46",
    unit: "bpm",
    detail: "Baseline 45 bpm.",
    coverage: "28/28 days",
  },
  {
    id: "sleep",
    label: "Sleep, last night",
    value: "6:20",
    unit: "h:min",
    detail: "Two shorter nights in a row. 7-night mean is 7:05.",
    coverage: "27/28 nights",
  },
  {
    id: "load",
    label: "Run volume, 7 days",
    value: "38.4",
    unit: "km",
    detail: "Four runs. 84-day weekly mean is 36.1 km.",
    coverage: "7/7 days",
  },
  {
    id: "ride",
    label: "Ride volume, 7 days",
    value: "2:45",
    unit: "h:min",
    detail: "Two aerobic rides, no hard efforts recorded.",
    coverage: "7/7 days",
  },
  {
    id: "threshold",
    label: "Verified current 10 km pace",
    value: null,
    detail:
      "No race or test inside the last 12 weeks, so no current race pace exists. Repetitions are prescribed by effort instead.",
  },
];

const conversation: CoachMessage[] = [
  {
    id: "msg-1",
    role: "athlete",
    paragraphs: ["Legs feel a bit heavy today. Should I still do the repetitions?"],
    createdAt: "2026-09-17T06:41:00+02:00",
  },
  {
    id: "msg-2",
    role: "coach",
    paragraphs: [
      "Yes, with a decision point built in. Run the warm-up and the first two repetitions. If the effort at RPE 6-7 costs more than usual, stop at three and finish easy.",
    ],
    evidence: [
      "Two nights under 6:45 of sleep; 7-night mean 7:05.",
      "HRV 58 ms against a 61 ms baseline, inside normal variation.",
      "Run volume 38.4 km in 7 days, close to the 84-day weekly mean.",
    ],
    assessment: [
      "Heavy legs after two short nights is not a reason to cancel the only quality session of the week.",
      "A truncated session that keeps the quality intent is better than a full session run at the wrong effort.",
    ],
    uncertainty: [
      "Sleep is self-reported by the watch and one night is missing from the window.",
      "No verified current 10 km pace exists, so the target stays on effort.",
    ],
    createdAt: "2026-09-17T06:41:12+02:00",
  },
];

const slashCommands: SlashCommand[] = [
  { command: "/feedback", description: "Report the outcome of a session" },
  { command: "/context", description: "Record context such as travel, illness or stress" },
  { command: "/facts", description: "List the facts behind today's session" },
  { command: "/plan", description: "Explain the current plan window" },
];

const syncState: SyncState = {
  phase: "completed",
  window: 7,
  progress: null,
  message: "Last sync completed.",
  detail: "Running, cycling, sleep, HRV and resting heart rate for the last 7 days.",
  startedAt: "2026-09-17T06:12:00+02:00",
  finishedAt: "2026-09-17T06:12:41+02:00",
  lastSyncAt: "2026-09-17T06:12:41+02:00",
  daysCovered: 7,
};

const todayView: TodayView = {
  athleteName: "Demo Athlete (synthetic)",
  today: DEMO_TODAY,
  session: todaySession,
  rationale:
    "The 28-day window shows steady aerobic running plus two easy rides, complete recovery data and one fatigue-limited run. That supports a single controlled quality session, not several hard days.",
  facts,
  dataQuality: {
    freshness: "current",
    lastSyncAt: "2026-09-17T06:12:41+02:00",
    coverageNote: "Recovery data complete for 28 days except one missing sleep night.",
    warnings: [
      "One sleep night is missing in the 28-day window and is shown as unknown, not zero.",
      "Garmin activity matching does not prove interval compliance. Your explicit feedback is the durable outcome.",
    ],
  },
  goal: {
    label: "Autumn 10 km, synthetic demo race",
    raceDate: "2026-11-01",
    daysToRace: 45,
    priority: "A",
  },
  revisionDue: false,
  actionNeeded: [
    "Yesterday's easy ride has no reported outcome yet.",
    "The detailed window runs to 28 Sep. The next 14 days can be generated from 24 Sep.",
  ],
};

export const fixtures = {
  todayView,
  conversation,
  slashCommands,
  syncState,
};

// ------------------------------------------------------------------ plan area

const planSessions: PlanSession[] = [
  {
    id: "sess-2026-09-15",
    date: "2026-09-15",
    sport: "running",
    title: "Easy continuous run",
    purpose: "Aerobic maintenance between quality days. One continuous effort, nothing else.",
    scope: "8 km / 45 min",
    mainTarget: "RPE 3",
    rationale: "Day after the long run. Volume is kept, intensity is not.",
    blocks: [
      {
        id: "s15-b1",
        kind: "steady",
        amount: "45 min continuous",
        target: "RPE 3",
        note: "One block. No warm-up or cooldown is prescribed for an easy run.",
      },
    ],
    observed: {
      matched: true,
      matchNote:
        "A Garmin run was matched by date and duration. A match confirms that an activity happened, not that the prescribed effort was held.",
      rows: [
        { label: "Duration", value: "46:12" },
        { label: "Distance", value: "8.3 km" },
        { label: "Average heart rate", value: "138 bpm" },
        { label: "Average pace", value: "5:34 /km" },
      ],
    },
    feedback: {
      outcome: "completed",
      rpe: 3,
      note: "Felt easy the whole way.",
      savedAt: "2026-09-15T19:04:00+02:00",
    },
    assessment: ["Reported RPE 3 against 138 bpm is consistent. This is a genuinely easy day."],
  },
  {
    id: "sess-2026-09-16",
    date: "2026-09-16",
    sport: "cycling",
    title: "Steady aerobic ride",
    purpose: "Aerobic volume without running load. Held at one intensity from start to finish.",
    scope: "1:30",
    mainTarget: "Cycling zone 2, confirmed zones",
    rationale: "Second aerobic stimulus of the week with no additional impact load.",
    blocks: [
      {
        id: "s16-b1",
        kind: "steady",
        amount: "1:30 continuous",
        target: "Zone 2, RPE 3-4",
        note: "One block. Roll straight into the effort; no structured warm-up is prescribed.",
      },
    ],
    observed: {
      matched: true,
      matchNote:
        "A Garmin ride was matched. Zone time is derived from your five confirmed cycling heart-rate zones.",
      rows: [
        { label: "Duration", value: "1:24" },
        { label: "Distance", value: "38.6 km" },
        { label: "Time in zone 2", value: "0:51" },
        { label: "Average power", value: null },
      ],
    },
    feedback: {
      outcome: "limited",
      rpe: 4,
      note: "Cut short by 6 minutes, had to be back for a work call.",
      savedAt: "2026-09-16T18:20:00+02:00",
    },
    assessment: ["Six missing minutes on an aerobic ride change nothing in the block."],
    uncertainty: [
      "Power was not recorded, so the intensity rests on heart rate and your report.",
      "Only 51 of 84 minutes fell in zone 2; the rest is unclassified and not counted as zero.",
    ],
  },
  {
    id: "sess-2026-09-17",
    date: "2026-09-17",
    sport: "running",
    title: "Controlled 10 km specific repetitions",
    purpose:
      "The one quality session of the week. Repetitions are paced by effort, not by an unverified race pace.",
    scope: "11 km / 55 min",
    mainTarget: "RPE 6-7 on the work blocks",
    rationale:
      "Race specificity six weeks out. Placed after two easy days so the effort can actually be held.",
    blocks: [
      {
        id: "s17-b1",
        kind: "warmup",
        amount: "15 min",
        target: "RPE 2-3",
        note: "Easy running until breathing is settled.",
      },
      {
        id: "s17-b2",
        kind: "intervals",
        amount: "5 x 4 min",
        target: "RPE 6-7",
        note: "Even effort across all five. Do not race the first repetition.",
        recovery: { amount: "2 min jog", target: "RPE 1-2" },
      },
      {
        id: "s17-b3",
        kind: "cooldown",
        amount: "10 min",
        target: "RPE 2",
        note: "Optional; stop earlier if the legs are done.",
      },
    ],
    uncertainty: ["No verified current 10 km pace exists, so the target stays on effort."],
  },
  {
    id: "sess-2026-09-19",
    date: "2026-09-19",
    sport: "running",
    title: "Easy run, no structure",
    purpose: "Recovery volume after the quality session.",
    scope: "6 km / 35 min",
    mainTarget: "RPE 2-3",
    rationale: "Keeps frequency without adding load two days after repetitions.",
    blocks: [{ id: "s19-b1", kind: "steady", amount: "35 min continuous", target: "RPE 2-3" }],
  },
  {
    id: "sess-2026-09-20",
    date: "2026-09-20",
    sport: "running",
    title: "Long run with steady finish",
    purpose: "Aerobic durability. The final section is firmer, not hard.",
    scope: "18 km / 1:35",
    mainTarget: "RPE 3 rising to RPE 5",
    rationale: "Longest run of the week on the day with the most available time.",
    blocks: [
      { id: "s20-b1", kind: "steady", amount: "1:10", target: "RPE 3" },
      {
        id: "s20-b2",
        kind: "steady",
        amount: "25 min",
        target: "RPE 5",
        note: "Firmer finish, still controlled.",
      },
    ],
  },
  {
    id: "sess-2026-09-22",
    date: "2026-09-22",
    sport: "cycling",
    title: "Easy spin",
    purpose: "Circulation only. No intensity of any kind.",
    scope: "50 min",
    mainTarget: "Zone 1-2, RPE 2",
    rationale: "Day after the long run; a ride loads the legs less than a run.",
    blocks: [
      { id: "s22-b1", kind: "steady", amount: "50 min continuous", target: "Zone 1-2, RPE 2" },
    ],
  },
  {
    id: "sess-2026-09-24",
    date: "2026-09-24",
    sport: "running",
    title: "Threshold repetitions on effort",
    purpose: "Second specific session of the window, longer repetitions at a lower effort ceiling.",
    scope: "13 km / 1:05",
    mainTarget: "RPE 6 on the work blocks",
    rationale: "Progression from 5 x 4 min toward race-length continuous effort.",
    blocks: [
      { id: "s24-b1", kind: "warmup", amount: "12 min", target: "RPE 2-3" },
      {
        id: "s24-b2",
        kind: "intervals",
        amount: "3 x 8 min",
        target: "RPE 6",
        note: "Hold the same effort on all three. Stop at two if the third would be a race.",
        recovery: { amount: "3 min jog", target: "RPE 1-2" },
      },
      { id: "s24-b3", kind: "cooldown", amount: "8 min", target: "RPE 2", note: "Optional." },
    ],
  },
  {
    id: "sess-2026-09-27",
    date: "2026-09-27",
    sport: "running",
    title: "Long run, flat effort",
    purpose: "Aerobic volume at one effort from start to finish.",
    scope: "19 km / 1:40",
    mainTarget: "RPE 3-4",
    rationale: "Last long run before the detailed window is extended.",
    blocks: [{ id: "s27-b1", kind: "steady", amount: "1:40 continuous", target: "RPE 3-4" }],
  },
];

const planTimeline: TimelineWeek[] = [
  {
    id: "w1",
    label: "Week 1",
    range: "15-21 Sep",
    phase: "specific",
    focus: "One quality session, aerobic volume",
    detailed: true,
    current: true,
  },
  {
    id: "w2",
    label: "Week 2",
    range: "22-28 Sep",
    phase: "specific",
    focus: "Longer repetitions on effort",
    detailed: true,
  },
  {
    id: "w3",
    label: "Week 3",
    range: "29 Sep-5 Oct",
    phase: "specific",
    focus: "Planned outline only",
  },
  {
    id: "w4",
    label: "Week 4",
    range: "6-12 Oct",
    phase: "sharpen",
    focus: "Race-effort continuous work",
  },
  {
    id: "w5",
    label: "Week 5",
    range: "13-19 Oct",
    phase: "sharpen",
    focus: "Highest quality density",
  },
  {
    id: "w6",
    label: "Week 6",
    range: "20-26 Oct",
    phase: "taper",
    focus: "Volume down, intensity retained",
  },
  {
    id: "w7",
    label: "Week 7",
    range: "27 Oct-1 Nov",
    phase: "race",
    focus: "Race week",
    race: { label: "Autumn 10 km (synthetic)", date: "2026-11-01", priority: "A" },
  },
];

const planFacts: Fact[] = [
  {
    id: "p-sessions",
    label: "Sessions in detailed window",
    value: "8",
    detail: "5 running, 2 cycling, 1 long run with a steady finish.",
  },
  {
    id: "p-reported",
    label: "Outcomes reported",
    value: "2 of 3",
    detail: "Sessions before today. One completed, one completed with limitations.",
  },
  {
    id: "p-volume",
    label: "Planned run volume, window",
    value: "75",
    unit: "km",
    detail: "84-day weekly mean is 36.1 km.",
  },
  {
    id: "p-racepace",
    label: "Verified race pace",
    value: null,
    detail: "No race or test in the last 12 weeks, so all targets are prescribed by effort.",
  },
];

const planView: PlanView = {
  planId: "plan-2026-09-14-v3",
  version: 3,
  acceptedAt: "2026-09-14T20:10:00+02:00",
  mode: "race",
  goal: {
    label: "Autumn 10 km (synthetic demo race)",
    sport: "running",
    raceDate: "2026-11-01",
    priority: "A",
    targetTime: "39:30 (desired, not verified)",
    taperPolicy: "Full taper: 10 days, volume reduced, one short quality session retained.",
    daysToRace: 45,
  },
  detailedWindow: {
    start: "2026-09-15",
    end: "2026-09-28",
    generatableFrom: "2026-09-24",
    sessionCount: 8,
  },
  revisionDue: false,
  revisionNote:
    "The detailed window runs to 28 Sep. The next 14 detailed days can be generated from 24 Sep.",
  timeline: planTimeline,
  sessions: planSessions,
  assessment: [
    "The block is built once toward race day, but only the next 14 days are detailed. Later weeks stay an outline on purpose.",
    "One quality session per week until week 4, then two, because reported outcomes so far show no repeated negative response.",
  ],
  uncertainty: [
    "The desired 39:30 is your ambition, not a prediction derived from verified data.",
    "A matched Garmin activity does not prove interval compliance; your explicit feedback is the durable outcome.",
    "Sessions after 28 Sep are an outline and will change when the next window is generated.",
  ],
  facts: planFacts,
};

const planHistory: PlanHistoryEntry[] = [
  {
    id: "plan-2026-09-14-v3",
    version: 3,
    acceptedAt: "2026-09-14",
    mode: "race",
    windowLabel: "15-28 Sep 2026",
    sessionCount: 8,
    note: "Active plan. Targets the Autumn 10 km, priority A.",
  },
  {
    id: "plan-2026-08-31-v2",
    version: 2,
    acceptedAt: "2026-08-31",
    mode: "race",
    windowLabel: "1-14 Sep 2026",
    sessionCount: 8,
    note: "Accepted history. Kept unchanged; outcomes were reported against these sessions.",
  },
  {
    id: "plan-2026-08-17-v1",
    version: 1,
    acceptedAt: "2026-08-17",
    mode: "general",
    windowLabel: "18-31 Aug 2026",
    sessionCount: 7,
    note: "General plan, no race target selected at the time.",
  },
];

/** The plan produced when simulated validation of the next window succeeds. */
const shift14 = (iso: string) => {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 14);
  return d.toISOString().slice(0, 10);
};

/** The proposed window reuses the same session structures on shifted dates and
 *  carries no observed data or feedback, because those days have not happened. */
const revisedSessions: PlanSession[] = planSessions.map((session) => {
  const { observed, feedback, assessment, ...rest } = session;
  void observed;
  void feedback;
  void assessment;
  return { ...rest, id: `${session.id}-v4`, date: shift14(session.date) };
});

const revisedPlanView: PlanView = {
  ...planView,
  sessions: revisedSessions,
  planId: "plan-2026-09-24-v4",
  version: 4,
  acceptedAt: "2026-09-24T09:02:00+02:00",
  detailedWindow: {
    start: "2026-09-29",
    end: "2026-10-12",
    generatableFrom: "2026-10-08",
    sessionCount: 8,
  },
  revisionDue: false,
  revisionNote:
    "The detailed window now runs to 12 Oct. The next 14 detailed days can be generated from 8 Oct.",
  assessment: [
    "Version 4 replaced version 3 only after local validation passed. Version 3 stays in history unchanged.",
    "Two quality sessions per week start in this window, as the reported outcomes support it.",
  ],
};

export const planFixtures = { planView, revisedPlanView, planHistory };
