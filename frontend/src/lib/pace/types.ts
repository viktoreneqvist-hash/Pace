/**
 * Domain types for the Pace prototype.
 *
 * These mirror the shapes the local Python API is intended to expose at
 * /api/v1/*, so MockPaceClient can later be replaced by an HttpPaceClient
 * without touching any component.
 */

export type Sport = "running" | "cycling";

export type RacePriority = "A" | "B" | "C";

export type SessionOutcome = "completed" | "limited" | "skipped";

export type BlockKind = "warmup" | "steady" | "intervals" | "recovery" | "cooldown";

export interface SessionBlock {
  id: string;
  kind: BlockKind;
  /** Human label for the work, e.g. "38 min" or "4 x 1 min". */
  amount: string;
  target: string;
  note?: string;
  /** Only present on interval blocks that carry an explicit recovery. */
  recovery?: { amount: string; target: string };
}

export interface SessionFeedback {
  outcome: SessionOutcome;
  rpe: number | null;
  note?: string;
  /** Why the session was limited or skipped. */
  reason?: string;
  /** Kept out of coach prompts unless shareWithAi is true. */
  privateNote?: string;
  shareWithAi?: boolean;
  savedAt: string;
}

export interface PlannedSession {
  id: string;
  date: string;
  sport: Sport;
  title: string;
  purpose: string;
  scope: string;
  mainTarget: string;
  blocks: SessionBlock[];
  feedback?: SessionFeedback;
}

/** A single observed fact. `value === null` means unknown — never zero. */
export interface Fact {
  id: string;
  label: string;
  value: string | null;
  unit?: string;
  detail?: string;
  coverage?: string;
}

export type DataFreshness = "current" | "stale" | "partial" | "unknown";

export interface DataQuality {
  freshness: DataFreshness;
  lastSyncAt: string | null;
  coverageNote: string;
  warnings: string[];
}

export type CoachRole = "athlete" | "coach";

export type ActionKind = "record_feedback" | "record_context";

export type ActionStatus = "pending" | "saving" | "saved" | "failed";

export interface CoachAction {
  id: string;
  kind: ActionKind;
  title: string;
  /** Exactly what would be written locally, field by field. */
  fields: { label: string; value: string }[];
  status: ActionStatus;
  savedAt?: string;
  error?: string;
}

export interface CoachMessage {
  id: string;
  role: CoachRole;
  paragraphs: string[];
  /** Observed facts the reply leans on. */
  evidence?: string[];
  /** Coach judgment, kept visually separate from evidence. */
  assessment?: string[];
  /** What is not known. */
  uncertainty?: string[];
  createdAt: string;
  action?: CoachAction;
}

export type SyncPhase =
  "idle" | "running" | "completed" | "partial" | "rate_limited" | "auth_required" | "failed";

export interface SyncState {
  phase: SyncPhase;
  window: 7 | 80 | null;
  /** 0-100 while running, otherwise null. */
  progress: number | null;
  message: string;
  detail?: string;
  startedAt: string | null;
  finishedAt: string | null;
  lastSyncAt: string | null;
  /** Days actually covered by the last completed or partial run. */
  daysCovered: number | null;
}

export interface TodayView {
  athleteName: string;
  today: string;
  session: PlannedSession | null;
  rationale: string;
  facts: Fact[];
  dataQuality: DataQuality;
  goal: {
    label: string;
    raceDate: string | null;
    daysToRace: number | null;
    priority: RacePriority | null;
  };
  /** Whether the next 14 detailed days may be generated for the active plan. */
  revisionDue: boolean;
  actionNeeded: string[];
}

export interface SlashCommand {
  command: string;
  description: string;
}

// ------------------------------------------------------------------ plan area

/** What Garmin reported for a session. A match never proves interval compliance. */
export interface ObservedActivity {
  matched: boolean;
  matchNote: string;
  rows: { label: string; value: string | null }[];
}

export interface PlanSession extends PlannedSession {
  /** Why this session sits on this day. */
  rationale: string;
  observed?: ObservedActivity;
  assessment?: string[];
  uncertainty?: string[];
}

export type BlockPhase = "base" | "specific" | "sharpen" | "taper" | "race";

export interface TimelineWeek {
  id: string;
  label: string;
  range: string;
  phase: BlockPhase;
  focus: string;
  /** Marks the week that contains the target race. */
  race?: { label: string; date: string; priority: RacePriority };
  detailed?: boolean;
  current?: boolean;
}

export interface PlanView {
  planId: string;
  version: number;
  acceptedAt: string;
  mode: "race" | "general";
  goal: {
    label: string;
    sport: Sport;
    raceDate: string | null;
    priority: RacePriority | null;
    targetTime: string | null;
    taperPolicy: string;
    daysToRace: number | null;
  };
  detailedWindow: {
    start: string;
    end: string;
    generatableFrom: string;
    sessionCount: number;
  };
  revisionDue: boolean;
  revisionNote: string;
  timeline: TimelineWeek[];
  sessions: PlanSession[];
  facts: Fact[];
  assessment: string[];
  uncertainty: string[];
}

export interface PlanHistoryEntry {
  id: string;
  version: number;
  acceptedAt: string;
  mode: "race" | "general";
  windowLabel: string;
  sessionCount: number;
  note: string;
}

export interface RevisionResult {
  status: "saved" | "failed";
  message: string;
  detail: string;
  /** Present only when validation succeeded and the plan was replaced. */
  plan?: PlanView;
}

// ------------------------------------------------------------- dashboard area

/** A single point in a chart series. `value === null` is a genuine gap. */
export interface SeriesPoint {
  x: string;
  /** Short axis label, e.g. "17 Sep". */
  label: string;
  value: number | null;
  note?: string;
}

export type SeriesColor = "run" | "ride" | "forest" | "accent" | "warning";

export interface ChartSeries {
  id: string;
  label: string;
  unit: string;
  color: SeriesColor;
  points: SeriesPoint[];
}

export interface ChartPanel {
  id: string;
  title: string;
  note: string;
  kind: "bar" | "line";
  unit: string;
  xLabel: string;
  yLabel: string;
  series: ChartSeries[];
  /** Optional horizontal reference, e.g. a 28-day baseline. */
  reference?: { label: string; value: number };
  coverage: string;
}

export type DashboardWindow = 28 | 84;

export interface DashboardView {
  window: DashboardWindow;
  generatedAt: string;
  runTiles: Fact[];
  rideTiles: Fact[];
  recoveryTiles: Fact[];
  charts: ChartPanel[];
  coverage: Fact[];
  dataQuality: DataQuality;
  assessment: string[];
  uncertainty: string[];
}

// ---------------------------------------------------------- weekly review area

export type WeeklyReviewStatus = "absent" | "running" | "failed" | "saved";

export interface WeeklyReviewSnapshot {
  id: string;
  weekLabel: string;
  generatedAt: string;
  summary: string[];
  /** Facts Pace computed itself. */
  paceFacts: Fact[];
  /** Facts owned by Garmin, kept separate from Pace's own calculations. */
  garminFacts: Fact[];
  assessment: string[];
  recommendations: string[];
  uncertainties: string[];
  knowledge: { title: string; note: string }[];
  immutableNote: string;
}

export interface WeeklyReviewState {
  status: WeeklyReviewStatus;
  snapshot: WeeklyReviewSnapshot | null;
  error?: string;
  history: { id: string; weekLabel: string; generatedAt: string }[];
}

// ------------------------------------------------------------------ race area

export type RaceStatus = "planned" | "cancelled" | "completed";

export interface Race {
  id: string;
  name: string;
  sport: Sport;
  date: string;
  distance: string;
  priority: RacePriority;
  desiredTime: string | null;
  taperPolicy: string;
  status: RaceStatus;
  /** A registered race never becomes the plan target implicitly. */
  isPlanTarget: boolean;
  note?: string;
}

export interface RaceDraft {
  name: string;
  sport: Sport;
  date: string;
  distance: string;
  priority: RacePriority;
  desiredTime: string;
}

export interface RacesView {
  races: Race[];
  activeTargetId: string | null;
  note: string;
}

// -------------------------------------------------------------- settings area

export type SportRole = "run_only" | "run_primary" | "balanced" | "ride_primary" | "ride_only";

export type Ambition = "cautious" | "balanced" | "ambitious";

export interface AvailabilityDay {
  day: string;
  available: boolean;
  /** Minutes, or null when no cap is set. */
  capMinutes: number | null;
}

export interface CyclingZone {
  id: string;
  label: string;
  from: number | null;
  to: number | null;
}

export interface ConnectionStatus {
  id: string;
  label: string;
  state: "connected" | "needs_reauth" | "not_connected";
  detail: string;
}

export interface SettingsView {
  sportRole: SportRole;
  ambition: Ambition;
  availability: AvailabilityDay[];
  cyclingZones: CyclingZone[];
  zonesConfirmed: boolean;
  connections: ConnectionStatus[];
  note: string;
}

export interface SettingsPatch {
  sportRole?: SportRole;
  ambition?: Ambition;
  availability?: AvailabilityDay[];
  cyclingZones?: CyclingZone[];
  zonesConfirmed?: boolean;
}

export interface MutationResult {
  status: "saved" | "failed";
  message: string;
  detail: string;
}

// ------------------------------------------------------------ onboarding area

export type StepState = "complete" | "in_progress" | "blocked" | "optional" | "todo";

export interface OnboardingStep {
  id: string;
  title: string;
  description: string;
  state: StepState;
  detail: string;
  blockedBy?: string;
  actionLabel?: string;
}

export interface OnboardingView {
  steps: OnboardingStep[];
  requiredComplete: number;
  requiredTotal: number;
  resumeStepId: string | null;
  note: string;
}

// --------------------------------------------------- session detail & feedback

export interface FeedbackDraft {
  outcome: SessionOutcome;
  rpe: number | null;
  reason: string;
  privateNote: string;
  /** The private note is only sent to the coaching model when this is true. */
  shareWithAi: boolean;
}

export interface SessionDetailView {
  session: PlanSession;
  planLabel: string;
  /** Facts Pace derived for this session. */
  paceFacts: Fact[];
  garminFacts: Fact[];
  garminNote: string;
  feedbackNote: string;
}

export interface PaceClient {
  getToday(): Promise<TodayView>;
  getConversation(): Promise<CoachMessage[]>;
  getSlashCommands(): Promise<SlashCommand[]>;
  sendCoachMessage(text: string): Promise<CoachMessage[]>;
  confirmAction(actionId: string): Promise<CoachMessage[]>;
  getSyncState(): Promise<SyncState>;
  startSync(window: 7 | 80): Promise<SyncState>;
  pollSync(): Promise<SyncState>;
  getPlan(): Promise<PlanView>;
  getPlanHistory(): Promise<PlanHistoryEntry[]>;
  /** Prototype-only switch between the revision-not-due and revision-due states. */
  setRevisionDueDemo(due: boolean): Promise<PlanView>;
  /** Simulated generation of the next 14 detailed days. Fails local validation once. */
  generateNextWindow(): Promise<RevisionResult>;
  getDashboard(window: DashboardWindow): Promise<DashboardView>;
  /** Reading the weekly review never regenerates it. */
  getWeeklyReview(): Promise<WeeklyReviewState>;
  generateWeeklyReview(): Promise<WeeklyReviewState>;
  resetWeeklyReviewDemo(): Promise<WeeklyReviewState>;
  getRaces(): Promise<RacesView>;
  addRace(draft: RaceDraft): Promise<MutationResult>;
  cancelRace(raceId: string): Promise<MutationResult>;
  /** Explicit, separate from registration. */
  setPlanTarget(raceId: string): Promise<MutationResult>;
  getSettings(): Promise<SettingsView>;
  saveSettings(patch: SettingsPatch): Promise<MutationResult>;
  reconnectGarminDemo(): Promise<MutationResult>;
  getOnboarding(): Promise<OnboardingView>;
  completeOnboardingStep(stepId: string): Promise<MutationResult>;
  getSession(sessionId: string): Promise<SessionDetailView | null>;
  saveSessionFeedback(sessionId: string, draft: FeedbackDraft): Promise<MutationResult>;
}
