/**
 * Synthetic demo data for the Dashboard, Weekly Review, Races, Settings and
 * Onboarding areas.
 *
 * INTERNAL: only mock-client.ts may import this file. Routes and components go
 * through the PaceClient adapter, so a real HttpPaceClient can replace it.
 *
 * Everything here is invented for one fictional athlete. No real athlete data,
 * no credentials, no provider payloads, no GPS or per-second streams.
 */

import { DEMO_TODAY } from "./fixtures";
import type {
  ChartPanel,
  ConnectionStatus,
  CyclingZone,
  DashboardView,
  DashboardWindow,
  Fact,
  OnboardingView,
  Race,
  SeriesPoint,
  SettingsView,
  WeeklyReviewSnapshot,
  WeeklyReviewState,
} from "./types";

// ------------------------------------------------------------------- helpers

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const dayMs = 86_400_000;

const isoToDate = (iso: string) => new Date(`${iso}T00:00:00Z`);

const shortLabel = (iso: string) => {
  const d = isoToDate(iso);
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
};

/** Deterministic pseudo-random in [0,1) so the demo never changes between runs. */
const rand = (seed: number) => {
  const x = Math.sin(seed * 12.9898) * 43758.5453;
  return x - Math.floor(x);
};

/** ISO dates for the last `n` days, oldest first, ending on the demo today. */
const lastDays = (n: number) => {
  const end = isoToDate(DEMO_TODAY).getTime();
  return Array.from({ length: n }, (_, i) =>
    new Date(end - (n - 1 - i) * dayMs).toISOString().slice(0, 10),
  );
};

/** Days where recovery data is genuinely missing — shown as unknown, never zero. */
const MISSING_SLEEP = new Set(["2026-09-03", "2026-08-11", "2026-07-19"]);
const MISSING_HRV = new Set(["2026-08-24", "2026-07-02"]);

const point = (iso: string, value: number | null, note?: string): SeriesPoint => ({
  x: iso,
  label: shortLabel(iso),
  value,
  ...(note ? { note } : {}),
});

const round1 = (v: number) => Math.round(v * 10) / 10;

// --------------------------------------------------------------- daily series

const hrvPoints = (days: string[]) =>
  days.map((iso, i) =>
    MISSING_HRV.has(iso)
      ? point(iso, null, "No overnight recording")
      : point(iso, Math.round(59 + rand(i + 3) * 8 - 4)),
  );

const rhrPoints = (days: string[]) =>
  days.map((iso, i) =>
    MISSING_HRV.has(iso)
      ? point(iso, null, "No overnight recording")
      : point(iso, Math.round(45 + rand(i + 17) * 4 - 1)),
  );

const sleepPoints = (days: string[]) =>
  days.map((iso, i) =>
    MISSING_SLEEP.has(iso)
      ? point(iso, null, "Watch not worn")
      : point(iso, round1(6.4 + rand(i + 41) * 1.8)),
  );

const rpePoints = (days: string[]) =>
  days.map((iso, i) => {
    const r = rand(i + 71);
    // Roughly five reported sessions a week; other days have no session at all.
    if (r < 0.28) return point(iso, null, "No session planned");
    if (r < 0.36) return point(iso, null, "Session done, no outcome reported");
    return point(iso, Math.round(2 + rand(i + 91) * 5));
  });

/** Weekly volume buckets, Monday-anchored, oldest first. */
const weekBuckets = (window: DashboardWindow) => {
  const weeks = window / 7;
  const end = isoToDate(DEMO_TODAY).getTime();
  return Array.from({ length: weeks }, (_, i) => {
    const start = new Date(end - (weeks - 1 - i) * 7 * dayMs);
    const iso = start.toISOString().slice(0, 10);
    return { x: iso, label: `w/c ${shortLabel(iso)}` };
  });
};

const runVolume = (window: DashboardWindow): SeriesPoint[] =>
  weekBuckets(window).map((b, i) => ({
    ...b,
    value: i === 1 && window === 84 ? null : round1(30 + rand(i + 5) * 14),
    ...(i === 1 && window === 84 ? { note: "Watch not synced that week; volume unknown" } : {}),
  }));

const rideVolume = (window: DashboardWindow): SeriesPoint[] =>
  weekBuckets(window).map((b, i) => ({ ...b, value: round1(1.2 + rand(i + 23) * 2.6) }));

// ------------------------------------------------------------------ dashboard

const charts = (window: DashboardWindow): ChartPanel[] => {
  const days = lastDays(window);
  return [
    {
      id: "run-volume",
      title: "Running volume per week",
      note: "Running only. Weeks are Monday-anchored. A week with no completed sync stays unknown rather than zero.",
      kind: "bar",
      unit: "km",
      xLabel: "Week commencing",
      yLabel: "Distance (km)",
      coverage: window === 84 ? "11 of 12 weeks covered" : "4 of 4 weeks covered",
      reference: { label: "84-day weekly mean 36.1 km", value: 36.1 },
      series: [
        {
          id: "run",
          label: "Running distance",
          unit: "km",
          color: "run",
          points: runVolume(window),
        },
      ],
    },
    {
      id: "ride-volume",
      title: "Cycling volume per week",
      note: "Cycling only, reported as moving time because distance depends on terrain.",
      kind: "bar",
      unit: "h",
      xLabel: "Week commencing",
      yLabel: "Time (hours)",
      coverage: window === 84 ? "12 of 12 weeks covered" : "4 of 4 weeks covered",
      series: [
        { id: "ride", label: "Cycling time", unit: "h", color: "ride", points: rideVolume(window) },
      ],
    },
    {
      id: "hrv",
      title: "Heart rate variability",
      note: "Garmin-owned overnight measurement. Gaps are nights without a recording.",
      kind: "line",
      unit: "ms",
      xLabel: "Date",
      yLabel: "HRV (ms)",
      coverage: window === 84 ? "82 of 84 nights" : "28 of 28 nights",
      reference: { label: "28-day baseline 61 ms", value: 61 },
      series: [
        { id: "hrv", label: "Overnight HRV", unit: "ms", color: "run", points: hrvPoints(days) },
      ],
    },
    {
      id: "rhr",
      title: "Resting heart rate",
      note: "Garmin-owned overnight measurement.",
      kind: "line",
      unit: "bpm",
      xLabel: "Date",
      yLabel: "Resting heart rate (bpm)",
      coverage: window === 84 ? "82 of 84 nights" : "28 of 28 nights",
      reference: { label: "28-day baseline 45 bpm", value: 45 },
      series: [
        {
          id: "rhr",
          label: "Resting heart rate",
          unit: "bpm",
          color: "forest",
          points: rhrPoints(days),
        },
      ],
    },
    {
      id: "sleep",
      title: "Sleep duration",
      note: "Watch-reported sleep. Nights where the watch was not worn are unknown, not zero.",
      kind: "bar",
      unit: "h",
      xLabel: "Night",
      yLabel: "Sleep (hours)",
      coverage: window === 84 ? "81 of 84 nights" : "27 of 28 nights",
      reference: { label: "7-night mean 7:05", value: 7.08 },
      series: [
        {
          id: "sleep",
          label: "Sleep duration",
          unit: "h",
          color: "ride",
          points: sleepPoints(days),
        },
      ],
    },
    {
      id: "rpe",
      title: "Reported effort per session",
      note: "Your own reported RPE. Days without a bar had no session, or a session with no outcome reported.",
      kind: "bar",
      unit: "RPE",
      xLabel: "Date",
      yLabel: "Reported RPE (1-10)",
      coverage: window === 84 ? "48 of 54 sessions reported" : "16 of 18 sessions reported",
      series: [
        {
          id: "rpe",
          label: "Reported RPE",
          unit: "RPE",
          color: "warning",
          points: rpePoints(days),
        },
      ],
    },
  ];
};

const runTiles = (window: DashboardWindow): Fact[] => [
  {
    id: "run-weekly",
    label: "Running, weekly mean",
    value: window === 28 ? "37.6" : "36.1",
    unit: "km",
    detail: window === 28 ? "Four weeks, 12 runs." : "Twelve weeks, 34 runs. One week unknown.",
    coverage: window === 28 ? "4/4 weeks" : "11/12 weeks",
  },
  {
    id: "run-long",
    label: "Longest run in window",
    value: "19.4",
    unit: "km",
    detail: "6 Sep 2026, reported RPE 4.",
    coverage: "Reported",
  },
  {
    id: "run-quality",
    label: "Quality running sessions",
    value: window === 28 ? "4" : "11",
    detail: "Sessions with a work block above RPE 5.",
  },
  {
    id: "run-pace",
    label: "Verified 10 km pace",
    value: null,
    detail: "No race or test in the last 12 weeks, so no current race pace exists.",
  },
];

const rideTiles = (window: DashboardWindow): Fact[] => [
  {
    id: "ride-weekly",
    label: "Cycling, weekly mean",
    value: window === 28 ? "2:24" : "2:11",
    unit: "h:min",
    detail: "Aerobic riding only; no hard efforts recorded.",
    coverage: window === 28 ? "4/4 weeks" : "12/12 weeks",
  },
  {
    id: "ride-long",
    label: "Longest ride in window",
    value: "2:38",
    unit: "h:min",
    detail: "30 Aug 2026, zone 2 for 1:52.",
  },
  {
    id: "ride-zones",
    label: "Zone data available",
    value: "Yes",
    detail: "Derived from your five confirmed cycling heart-rate zones.",
  },
  {
    id: "ride-power",
    label: "Cycling power",
    value: null,
    detail: "No power meter recorded in this window, so ride intensity rests on heart rate.",
  },
];

const recoveryTiles = (window: DashboardWindow): Fact[] => [
  {
    id: "d-hrv",
    label: "HRV vs baseline",
    value: "-3",
    unit: "ms",
    detail: "58 ms against a 61 ms baseline. Inside normal day-to-day variation.",
    coverage: window === 28 ? "28/28 nights" : "82/84 nights",
  },
  {
    id: "d-rhr",
    label: "Resting heart rate",
    value: "46",
    unit: "bpm",
    detail: "Baseline 45 bpm.",
    coverage: window === 28 ? "28/28 nights" : "82/84 nights",
  },
  {
    id: "d-sleep",
    label: "Sleep, 7-night mean",
    value: "7:05",
    unit: "h:min",
    detail: "Two shorter nights most recently.",
    coverage: window === 28 ? "27/28 nights" : "81/84 nights",
  },
  {
    id: "d-rpe",
    label: "Mean reported RPE",
    value: "4.1",
    detail: "Across reported sessions only. Unreported sessions are excluded, not counted as zero.",
    coverage: window === 28 ? "16/18 sessions" : "48/54 sessions",
  },
];

const coverage = (window: DashboardWindow): Fact[] => [
  {
    id: "cov-activities",
    label: "Activity coverage",
    value: window === 28 ? "100" : "92",
    unit: "%",
    detail:
      window === 28
        ? "Every day in the window has been imported."
        : "One week in July was never synced.",
  },
  {
    id: "cov-sleep",
    label: "Sleep coverage",
    value: window === 28 ? "96" : "96",
    unit: "%",
    detail: window === 28 ? "One night missing." : "Three nights missing.",
  },
  {
    id: "cov-hrv",
    label: "HRV coverage",
    value: window === 28 ? "100" : "98",
    unit: "%",
    detail: "Overnight recordings present.",
  },
  {
    id: "cov-sync",
    label: "Last sync",
    value: "2026-09-17 06:12",
    detail: "7-day window. Sync only runs when you start it.",
  },
];

export const dashboardFixture = (window: DashboardWindow): DashboardView => ({
  window,
  generatedAt: "2026-09-17T06:12:41+02:00",
  runTiles: runTiles(window),
  rideTiles: rideTiles(window),
  recoveryTiles: recoveryTiles(window),
  charts: charts(window),
  coverage: coverage(window),
  dataQuality: {
    freshness: window === 28 ? "current" : "partial",
    lastSyncAt: "2026-09-17T06:12:41+02:00",
    coverageNote:
      window === 28
        ? "The 28-day window is complete apart from one missing sleep night."
        : "The 84-day window has one unsynced week in July and three missing sleep nights.",
    warnings:
      window === 28
        ? ["One sleep night is missing and is shown as unknown, not zero."]
        : [
            "One week in July was never synced. Its running volume is unknown and is excluded from the weekly mean.",
            "Three sleep nights are missing across the window.",
          ],
  },
  assessment: [
    "Running volume is stable around the 84-day mean, with one quality session most weeks.",
    "Cycling adds aerobic time without impact load, which is consistent with the current sport role.",
  ],
  uncertainty: [
    "There is no single training score on this page on purpose. Each number is shown with its own coverage.",
    "Sleep and HRV are watch-derived and owned by Garmin, not calculated by Pace.",
    "This is synthetic demo data and describes no real athlete.",
  ],
});

// --------------------------------------------------------------- weekly review

const weeklySnapshot: WeeklyReviewSnapshot = {
  id: "review-2026-09-14",
  weekLabel: "Week 8-14 Sep 2026",
  generatedAt: "2026-09-14T21:05:00+02:00",
  summary: [
    "Four runs and two rides completed. One run was cut short by fatigue and reported as limited.",
    "Recovery data was complete for the whole week apart from one short night.",
  ],
  paceFacts: [
    {
      id: "wr-vol",
      label: "Running volume",
      value: "38.4",
      unit: "km",
      detail: "Four runs. 84-day weekly mean 36.1 km.",
      coverage: "7/7 days",
    },
    {
      id: "wr-ride",
      label: "Cycling time",
      value: "2:45",
      unit: "h:min",
      detail: "Two aerobic rides.",
      coverage: "7/7 days",
    },
    {
      id: "wr-rep",
      label: "Outcomes reported",
      value: "5 of 6",
      detail: "One ride has no outcome.",
      coverage: "Reported by you",
    },
    {
      id: "wr-pace",
      label: "Verified race pace",
      value: null,
      detail: "No test or race in 12 weeks.",
    },
  ],
  garminFacts: [
    {
      id: "wr-hrv",
      label: "HRV, week mean",
      value: "59",
      unit: "ms",
      detail: "Baseline 61 ms.",
      coverage: "7/7 nights",
    },
    {
      id: "wr-rhr",
      label: "Resting heart rate, week mean",
      value: "46",
      unit: "bpm",
      detail: "Baseline 45 bpm.",
      coverage: "7/7 nights",
    },
    {
      id: "wr-sleep",
      label: "Sleep, week mean",
      value: "6:52",
      unit: "h:min",
      detail: "One night under 6:00.",
      coverage: "6/7 nights",
    },
    {
      id: "wr-load",
      label: "Garmin training status",
      value: null,
      detail: "Not imported by Pace; Pace does not reuse provider scores.",
    },
  ],
  assessment: [
    "One limited session in a week of otherwise complete work is normal variation, not a repeated negative response.",
    "Continuity is the strongest fact in this week: six sessions in seven days at controlled effort.",
    "The block does not need changing. Keep one quality session next week.",
  ],
  recommendations: [
    "Keep next week's structure as planned; do not add a second quality session yet.",
    "Report the outcome of the missing ride so the week is complete.",
    "Protect sleep before the next repetition session rather than adjusting the session itself.",
  ],
  uncertainties: [
    "Sleep is watch-reported and one night is missing.",
    "Matched Garmin activities confirm that sessions happened, not that interval targets were met.",
    "No verified current 10 km pace exists, so all effort targets stay on RPE.",
  ],
  knowledge: [
    {
      title: "Reviewed note: weekly quality density",
      note: "One quality session per week is sufficient while weekly volume is near the long-term mean.",
    },
    {
      title: "Reviewed note: short sleep and quality work",
      note: "A single short night is not a reason to cancel a planned quality session; two or more consecutive short nights justify a decision point inside the session.",
    },
  ],
  immutableNote:
    "This snapshot is dated and immutable. It is not recalculated when you open this page, and it does not change when you later save feedback or context.",
};

export const weeklyReviewFixtures = {
  absent: {
    status: "absent",
    snapshot: null,
    history: [
      {
        id: "review-2026-09-07",
        weekLabel: "Week 1-7 Sep 2026",
        generatedAt: "2026-09-07T20:40:00+02:00",
      },
      {
        id: "review-2026-08-31",
        weekLabel: "Week 25-31 Aug 2026",
        generatedAt: "2026-08-31T21:12:00+02:00",
      },
    ],
  } satisfies WeeklyReviewState,
  snapshot: weeklySnapshot,
};

// -------------------------------------------------------------------- races

export const raceFixtures: Race[] = [
  {
    id: "race-1",
    name: "Autumn 10 km (synthetic demo race)",
    sport: "running",
    date: "2026-11-01",
    distance: "10 km",
    priority: "A",
    desiredTime: "39:30 (desired, not verified)",
    taperPolicy: "Full taper: 10 days, volume reduced, one short quality session retained.",
    status: "planned",
    isPlanTarget: true,
    note: "Current plan target. Chosen explicitly when version 3 of the plan was accepted.",
  },
  {
    id: "race-2",
    name: "Harbour 5 km (synthetic)",
    sport: "running",
    date: "2026-10-10",
    distance: "5 km",
    priority: "B",
    desiredTime: null,
    taperPolicy: "Partial taper: 3 easy days before, no reduction in the week before that.",
    status: "planned",
    isPlanTarget: false,
    note: "Hard secondary race. Registered but not the plan target.",
  },
  {
    id: "race-3",
    name: "Forest gravel 60 km (synthetic)",
    sport: "cycling",
    date: "2026-10-24",
    distance: "60 km",
    priority: "C",
    desiredTime: null,
    taperPolicy: "No race taper. Treated as a hard training event.",
    status: "planned",
    isPlanTarget: false,
  },
  {
    id: "race-4",
    name: "Summer 10 km (synthetic)",
    sport: "running",
    date: "2026-06-20",
    distance: "10 km",
    priority: "B",
    desiredTime: null,
    taperPolicy: "Partial taper.",
    status: "completed",
    isPlanTarget: false,
    note: "Historical result kept unchanged. More than 12 weeks old, so it does not count as a verified current pace.",
  },
];

// ------------------------------------------------------------------ settings

const cyclingZones: CyclingZone[] = [
  { id: "z1", label: "Zone 1", from: 95, to: 118 },
  { id: "z2", label: "Zone 2", from: 119, to: 136 },
  { id: "z3", label: "Zone 3", from: 137, to: 150 },
  { id: "z4", label: "Zone 4", from: 151, to: 163 },
  { id: "z5", label: "Zone 5", from: 164, to: 182 },
];

const connections: ConnectionStatus[] = [
  {
    id: "garmin",
    label: "Garmin",
    state: "connected",
    detail: "Connected locally. Tokens stay on this machine and are never shown in the interface.",
  },
  {
    id: "openai",
    label: "Coaching model key",
    state: "connected",
    detail:
      "A key is present locally. This prototype accepts demo values only and transmits nothing.",
  },
];

export const settingsFixture: SettingsView = {
  sportRole: "run_primary",
  ambition: "balanced",
  volumeBoundaries: {
    runningKmPerWeek: 55,
    cyclingHoursPerWeek: 5,
    totalHoursPerWeek: 8,
  },
  availability: [
    { day: "Monday", available: false, capMinutes: null },
    { day: "Tuesday", available: true, capMinutes: 75 },
    { day: "Wednesday", available: true, capMinutes: 60 },
    { day: "Thursday", available: true, capMinutes: 75 },
    { day: "Friday", available: false, capMinutes: null },
    { day: "Saturday", available: true, capMinutes: 150 },
    { day: "Sunday", available: true, capMinutes: 120 },
  ],
  cyclingZones,
  zonesConfirmed: true,
  connections,
  note: "Changes apply to future plan generation. They never rewrite accepted plans or past sessions.",
};

// ---------------------------------------------------------------- onboarding

export const onboardingFixture: OnboardingView = {
  requiredComplete: 4,
  requiredTotal: 7,
  resumeStepId: "history",
  note: "Everything runs on your own machine. You can leave and return; completed steps stay completed.",
  steps: [
    {
      id: "local",
      title: "Local privacy check",
      description:
        "Pace runs on this machine only, reachable from this computer, with no accounts and no cloud copy.",
      state: "complete",
      detail: "Confirmed. No data leaves the machine in this prototype.",
    },
    {
      id: "key",
      title: "Coaching model key",
      description: "Stored locally and used only when you ask the coach something.",
      state: "complete",
      detail: "A synthetic demo value is stored. Real keys are never accepted or transmitted here.",
    },
    {
      id: "garmin",
      title: "Connect Garmin",
      description: "Authorise reading of runs, rides, sleep, HRV and resting heart rate.",
      state: "complete",
      detail: "Connected locally with a synthetic demo connection.",
    },
    {
      id: "role",
      title: "Sport role and ambition",
      description:
        "How running and cycling are weighted, and how aggressive the coaching should be.",
      state: "complete",
      detail: "Running primary, balanced ambition.",
    },
    {
      id: "availability",
      title: "Availability and time caps",
      description: "Which weekdays are available and how long a session may be.",
      state: "in_progress",
      detail: "Five days marked available. Time caps are set for three of them.",
      actionLabel: "Finish availability",
    },
    {
      id: "zones",
      title: "Cycling heart-rate zones",
      description: "Five confirmed zones, required before cycling intensity is prescribed.",
      state: "optional",
      detail:
        "Optional for run-only athletes. Your role is running primary, so cycling zones improve ride targets.",
      actionLabel: "Confirm zones",
    },
    {
      id: "history",
      title: "Import 80 days of history",
      description:
        "The first long sync builds the baselines every fact on the Dashboard depends on.",
      state: "blocked",
      detail: "Blocked until availability is finished, because the first plan needs both.",
      blockedBy: "availability",
      actionLabel: "Start 80-day sync",
    },
    {
      id: "races",
      title: "Add races",
      description: "Register the races you know about. Registering does not select a plan target.",
      state: "optional",
      detail: "Three future races registered.",
    },
    {
      id: "plan",
      title: "Create the first plan",
      description:
        "Choose one registered race or a general plan, then let local validation accept it.",
      state: "blocked",
      detail:
        "Blocked until history has been imported. A first plan may be created as soon as a target is chosen and validation passes.",
      blockedBy: "history",
      actionLabel: "Choose target and create plan",
    },
  ],
};
