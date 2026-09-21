/**
 * MockPaceClient — the only module allowed to touch the synthetic fixtures.
 *
 * All mutation state lives in memory for the lifetime of the page. Refreshing
 * the prototype resets it. Nothing is transmitted, persisted or stored.
 */

import { fixtures, planFixtures } from "./fixtures";
import {
  dashboardFixture,
  onboardingFixture,
  raceFixtures,
  settingsFixture,
  weeklyReviewFixtures,
} from "./fixtures-extra";
import type {
  CoachAction,
  CoachMessage,
  DashboardView,
  DashboardWindow,
  FeedbackDraft,
  MutationResult,
  OnboardingView,
  PaceClient,
  PlanHistoryEntry,
  PlanView,
  Race,
  RaceDraft,
  RacesView,
  RevisionResult,
  SessionDetailView,
  SettingsPatch,
  SettingsView,
  SlashCommand,
  SyncState,
  TodayView,
  WeeklyReviewState,
} from "./types";

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

const nowIso = () => new Date().toISOString();

let counter = 0;
const nextId = (prefix: string) => `${prefix}-live-${++counter}`;

/** Outcome cycle so every documented sync state is reachable from the UI. */
const SYNC_OUTCOMES: Exclude<SyncState["phase"], "idle" | "running">[] = [
  "completed",
  "partial",
  "rate_limited",
  "auth_required",
  "failed",
  "completed",
];

/** Taper follows race priority: A full, B partial, C none. */
const TAPER_BY_PRIORITY = {
  A: "Full taper: 10 days, volume reduced, one short quality session retained.",
  B: "Partial taper: 3 easy days before, no reduction in the week before that.",
  C: "No race taper. Treated as a hard training event.",
} as const;

export class MockPaceClient implements PaceClient {
  private today: TodayView = clone(fixtures.todayView);
  private conversation: CoachMessage[] = clone(fixtures.conversation);
  private sync: SyncState = clone(fixtures.syncState);
  private syncTicks = 0;
  private syncAttempt = 0;
  private contextConfirmFailedOnce = false;
  private plan: PlanView = clone(planFixtures.planView);
  private revisionAttempts = 0;
  private review: WeeklyReviewState = clone(weeklyReviewFixtures.absent);
  private reviewAttempts = 0;
  private races: Race[] = clone(raceFixtures);
  private settings: SettingsView = clone(settingsFixture);
  private garminReconnectAttempts = 0;
  private onboarding: OnboardingView = clone(onboardingFixture);
  private onboardingAttempts: Record<string, number> = {};
  private raceCounter = 0;

  async getToday(): Promise<TodayView> {
    await delay(220);
    return clone(this.today);
  }

  async getConversation(): Promise<CoachMessage[]> {
    await delay(180);
    return clone(this.conversation);
  }

  async getSlashCommands(): Promise<SlashCommand[]> {
    await delay(60);
    return clone(fixtures.slashCommands);
  }

  async sendCoachMessage(text: string): Promise<CoachMessage[]> {
    const trimmed = text.trim();
    this.conversation.push({
      id: nextId("msg"),
      role: "athlete",
      paragraphs: [trimmed],
      createdAt: nowIso(),
    });
    // Simulated model latency. No external call is made.
    await delay(900);
    this.conversation.push(this.composeReply(trimmed));
    return clone(this.conversation);
  }

  async confirmAction(actionId: string): Promise<CoachMessage[]> {
    const action = this.findAction(actionId);
    if (!action || action.status === "saved") return clone(this.conversation);

    action.status = "saving";
    delete action.error;
    await delay(850);

    if (action.kind === "record_context" && !this.contextConfirmFailedOnce) {
      this.contextConfirmFailedOnce = true;
      action.status = "failed";
      action.error =
        "Local validation rejected the write: the context date is outside the open window. Adjust and retry.";
      return clone(this.conversation);
    }

    action.status = "saved";
    action.savedAt = nowIso();

    if (action.kind === "record_feedback") {
      this.today.actionNeeded = this.today.actionNeeded.filter(
        (item) => !item.toLowerCase().includes("outcome"),
      );
      if (this.today.session) {
        this.today.session.feedback = {
          outcome: this.outcomeFromFields(action),
          rpe: this.rpeFromFields(action),
          note: "Recorded from the coach conversation.",
          savedAt: action.savedAt,
        };
      }
    }

    return clone(this.conversation);
  }

  async getSyncState(): Promise<SyncState> {
    await delay(80);
    return clone(this.sync);
  }

  async startSync(window: 7 | 80): Promise<SyncState> {
    if (this.sync.phase === "running") return clone(this.sync);
    this.syncTicks = 0;
    this.sync = {
      phase: "running",
      window,
      progress: 0,
      message: `Reading the last ${window} days from Garmin.`,
      detail: "Runs, rides, sleep, HRV and resting heart rate.",
      startedAt: nowIso(),
      finishedAt: null,
      lastSyncAt: this.sync.lastSyncAt,
      daysCovered: null,
    };
    await delay(150);
    return clone(this.sync);
  }

  async pollSync(): Promise<SyncState> {
    await delay(120);
    if (this.sync.phase !== "running") return clone(this.sync);

    this.syncTicks += 1;
    const progress = Math.min(100, this.syncTicks * 22);
    this.sync.progress = progress;
    this.sync.message =
      progress < 100
        ? `Reading the last ${this.sync.window} days from Garmin. ${progress}% of the window processed.`
        : this.sync.message;

    if (progress < 100) return clone(this.sync);

    const outcome = SYNC_OUTCOMES[this.syncAttempt % SYNC_OUTCOMES.length];
    this.syncAttempt += 1;
    const window = this.sync.window ?? 7;
    const finishedAt = nowIso();

    const base = { progress: null, finishedAt, window } as const;

    switch (outcome) {
      case "completed":
        this.sync = {
          ...this.sync,
          ...base,
          phase: "completed",
          message: "Sync completed.",
          detail: `${window} of ${window} days imported.`,
          lastSyncAt: finishedAt,
          daysCovered: window,
        };
        break;
      case "partial":
        this.sync = {
          ...this.sync,
          ...base,
          phase: "partial",
          message: "Sync finished with gaps.",
          detail: `${window - 2} of ${window} days imported. Two days returned no recovery data and stay unknown.`,
          lastSyncAt: finishedAt,
          daysCovered: window - 2,
        };
        break;
      case "rate_limited":
        this.sync = {
          ...this.sync,
          ...base,
          phase: "rate_limited",
          message: "Garmin rate limit reached.",
          detail: "The provider refused further requests. Retry in a few minutes.",
          daysCovered: null,
        };
        break;
      case "auth_required":
        this.sync = {
          ...this.sync,
          ...base,
          phase: "auth_required",
          message: "Garmin connection needs to be re-authorised.",
          detail:
            "The stored local connection is no longer accepted. Reconnect in Settings. This demo never asks for real credentials.",
          daysCovered: null,
        };
        break;
      default:
        this.sync = {
          ...this.sync,
          ...base,
          phase: "failed",
          message: "Sync failed.",
          detail: "The local sync job stopped before any day was imported. Nothing was written.",
          daysCovered: null,
        };
    }

    return clone(this.sync);
  }

  async getPlan(): Promise<PlanView> {
    await delay(240);
    return clone(this.plan);
  }

  async getPlanHistory(): Promise<PlanHistoryEntry[]> {
    await delay(140);
    return clone(planFixtures.planHistory);
  }

  async getPendingVolumeException() {
    await delay(120);
    return null;
  }

  async approveVolumeException(): Promise<MutationResult> {
    return {
      status: "failed",
      message: "No exception is pending.",
      detail: "The synthetic plan stays unchanged.",
    };
  }

  async setRevisionDueDemo(due: boolean): Promise<PlanView> {
    await delay(120);
    this.plan.revisionDue = due;
    this.plan.revisionNote = due
      ? "The detailed window ends on 28 Sep and is now inside the revision window. The next 14 detailed days can be generated."
      : clone(planFixtures.planView).revisionNote;
    return clone(this.plan);
  }

  async generateNextWindow(): Promise<RevisionResult> {
    if (!this.plan.revisionDue) {
      return {
        status: "failed",
        message: "Revision is not due.",
        detail:
          "The current detailed window still has days left. Nothing was generated and the active plan is unchanged.",
      };
    }

    // Simulated generation and local validation. The active plan is only
    // replaced after validation succeeds.
    await delay(1400);
    this.revisionAttempts += 1;

    if (this.revisionAttempts === 1) {
      return {
        status: "failed",
        message: "Local validation rejected the proposed window.",
        detail:
          "Two quality sessions landed on consecutive days (6 and 7 Oct) and one session fell on an unavailable weekday. The active plan was not replaced. Retry to generate a corrected window.",
      };
    }

    this.plan = clone(planFixtures.revisedPlanView);
    return {
      status: "saved",
      message: "Next 14 detailed days accepted as version 4.",
      detail:
        "Validation passed and the active plan was replaced. Version 3 stays in history unchanged.",
      plan: clone(this.plan),
    };
  }

  // ------------------------------------------------------------------ dashboard

  async getDashboard(window: DashboardWindow): Promise<DashboardView> {
    await delay(320);
    return dashboardFixture(window);
  }

  // -------------------------------------------------------------- weekly review

  /** Pure read. Opening the page never triggers generation. */
  async getWeeklyReview(): Promise<WeeklyReviewState> {
    await delay(200);
    return clone(this.review);
  }

  async generateWeeklyReview(): Promise<WeeklyReviewState> {
    if (this.review.status === "running") return clone(this.review);
    this.review = { ...clone(this.review), status: "running", snapshot: null };
    delete this.review.error;
    await delay(1600);
    this.reviewAttempts += 1;

    if (this.reviewAttempts === 1) {
      this.review = {
        ...clone(this.review),
        status: "failed",
        snapshot: null,
        error:
          "The local model call returned no usable snapshot. Nothing was written, so no dated review exists for this week yet. Retry when you want.",
      };
      return clone(this.review);
    }

    const snapshot = clone(weeklyReviewFixtures.snapshot);
    this.review = {
      status: "saved",
      snapshot,
      history: [
        { id: snapshot.id, weekLabel: snapshot.weekLabel, generatedAt: snapshot.generatedAt },
        ...clone(weeklyReviewFixtures.absent.history),
      ],
    };
    return clone(this.review);
  }

  async resetWeeklyReviewDemo(): Promise<WeeklyReviewState> {
    await delay(120);
    this.reviewAttempts = 0;
    this.review = clone(weeklyReviewFixtures.absent);
    return clone(this.review);
  }

  // ------------------------------------------------------------------- races

  async getRaces(): Promise<RacesView> {
    await delay(180);
    return {
      races: clone(this.races),
      activeTargetId: this.races.find((race) => race.isPlanTarget)?.id ?? null,
      note: "Registering a race never changes the plan target. Selecting a target is a separate, explicit action.",
    };
  }

  async addRace(draft: RaceDraft): Promise<MutationResult> {
    await delay(900);

    if (!draft.name.trim()) {
      return {
        status: "failed",
        message: "Local validation rejected the race.",
        detail: "A race needs a name.",
      };
    }
    if (!draft.date || draft.date <= fixtures.todayView.today) {
      return {
        status: "failed",
        message: "Local validation rejected the race.",
        detail:
          "Only future dates are eligible. The demo date is 17 Sep 2026, so pick a later date. Nothing was written.",
      };
    }
    if (this.races.some((race) => race.date === draft.date && race.status === "planned")) {
      return {
        status: "failed",
        message: "Local validation rejected the race.",
        detail: "A planned race already exists on that date. Nothing was written.",
      };
    }

    this.raceCounter += 1;
    this.races = [
      ...this.races,
      {
        id: `race-new-${this.raceCounter}`,
        name: draft.name.trim(),
        sport: draft.sport,
        date: draft.date,
        distance: draft.distance.trim() || "Distance not stated",
        priority: draft.priority,
        desiredTime: draft.desiredTime.trim()
          ? `${draft.desiredTime.trim()} (desired, not verified)`
          : null,
        taperPolicy: TAPER_BY_PRIORITY[draft.priority],
        status: "planned",
        isPlanTarget: false,
        note: "Registered. Not the plan target; selecting a target is a separate action.",
      },
    ];

    return {
      status: "saved",
      message: "Race registered.",
      detail: "The race is stored locally. The active plan target is unchanged.",
    };
  }

  async cancelRace(raceId: string): Promise<MutationResult> {
    await delay(700);
    const race = this.races.find((item) => item.id === raceId);
    if (!race)
      return { status: "failed", message: "Race not found.", detail: "Nothing was written." };
    if (race.status !== "planned") {
      return {
        status: "failed",
        message: "This race cannot be cancelled.",
        detail: "Only future planned races are eligible. Completed races are immutable history.",
      };
    }
    if (race.isPlanTarget) {
      return {
        status: "failed",
        message: "Local validation rejected the change.",
        detail:
          "This race is the active plan target. Select another target or a general plan first. Nothing was written.",
      };
    }
    race.status = "cancelled";
    race.note = "Cancelled by you. Kept as history rather than deleted.";
    return {
      status: "saved",
      message: "Race cancelled.",
      detail: "The race stays visible as cancelled history.",
    };
  }

  async setPlanTarget(raceId: string): Promise<MutationResult> {
    await delay(900);
    const race = this.races.find((item) => item.id === raceId);
    if (!race || race.status !== "planned") {
      return {
        status: "failed",
        message: "This race cannot be a plan target.",
        detail: "Only future planned races are eligible. Nothing was written.",
      };
    }
    this.races = this.races.map((item) => ({ ...item, isPlanTarget: item.id === raceId }));
    return {
      status: "saved",
      message: `Plan target set to ${race.name}.`,
      detail:
        "The target is stored. The active plan is not rewritten; the next generated plan version uses this target.",
    };
  }

  // ----------------------------------------------------------------- settings

  async getSettings(): Promise<SettingsView> {
    await delay(180);
    return clone(this.settings);
  }

  async saveSettings(patch: SettingsPatch): Promise<MutationResult> {
    await delay(950);
    const next: SettingsView = { ...clone(this.settings), ...clone(patch) };

    if (!next.availability.some((day) => day.available)) {
      return {
        status: "failed",
        message: "Local validation rejected the change.",
        detail:
          "At least one weekday must be available, otherwise no plan can be generated. Nothing was saved.",
      };
    }

    const zones = next.cyclingZones;
    for (let i = 0; i < zones.length; i += 1) {
      const zone = zones[i]!;
      if (zone.from === null || zone.to === null || zone.from >= zone.to) {
        return {
          status: "failed",
          message: "Local validation rejected the cycling zones.",
          detail: `${zone.label} needs a lower bound below its upper bound. Nothing was saved.`,
        };
      }
      const previous = zones[i - 1];
      if (previous && previous.to !== null && zone.from <= previous.to) {
        return {
          status: "failed",
          message: "Local validation rejected the cycling zones.",
          detail: `${zone.label} starts at or below the top of ${previous.label}. Zones must not overlap. Nothing was saved.`,
        };
      }
    }

    this.settings = next;
    return {
      status: "saved",
      message: "Settings saved.",
      detail: "Applied to future plan generation. Accepted plans and past sessions are unchanged.",
    };
  }

  async reconnectGarminDemo(): Promise<MutationResult> {
    await delay(1100);
    this.garminReconnectAttempts += 1;
    if (this.garminReconnectAttempts === 1) {
      this.settings.connections = this.settings.connections.map((connection) =>
        connection.id === "garmin"
          ? {
              ...connection,
              state: "needs_reauth",
              detail:
                "The local authorisation was refused. Nothing was stored. Retry the reconnect.",
            }
          : connection,
      );
      return {
        status: "failed",
        message: "Reconnect failed.",
        detail:
          "The simulated authorisation was refused. No credentials were requested, sent or stored.",
      };
    }
    this.settings.connections = this.settings.connections.map((connection) =>
      connection.id === "garmin"
        ? {
            ...connection,
            state: "connected",
            detail:
              "Connected locally with a synthetic demo connection. Tokens never reach the interface.",
          }
        : connection,
    );
    return {
      status: "saved",
      message: "Garmin reconnected.",
      detail: "A synthetic local connection is active. You still have to start any sync yourself.",
    };
  }

  // --------------------------------------------------------------- onboarding

  async getOnboarding(): Promise<OnboardingView> {
    await delay(200);
    return clone(this.onboarding);
  }

  async completeOnboardingStep(stepId: string): Promise<MutationResult> {
    const step = this.onboarding.steps.find((item) => item.id === stepId);
    if (!step)
      return { status: "failed", message: "Step not found.", detail: "Nothing was written." };
    if (step.state === "blocked") {
      const blocker = this.onboarding.steps.find((item) => item.id === step.blockedBy);
      return {
        status: "failed",
        message: "This step is blocked.",
        detail: `Finish "${blocker?.title ?? "the previous step"}" first. Nothing was written.`,
      };
    }

    await delay(1200);
    const attempts = (this.onboardingAttempts[stepId] ?? 0) + 1;
    this.onboardingAttempts[stepId] = attempts;

    if (stepId === "history" && attempts === 1) {
      return {
        status: "failed",
        message: "The 80-day import stopped early.",
        detail:
          "Garmin refused further requests after 31 days. The partial import was discarded and this step is still open. Retry when you want.",
      };
    }

    const wasRequired = step.state !== "optional";
    step.state = "complete";
    step.detail = "Completed in this session. Refreshing the prototype resets it.";
    delete step.actionLabel;

    // Unblock whatever waited on this step.
    for (const other of this.onboarding.steps) {
      if (other.blockedBy === stepId && other.state === "blocked") {
        other.state = "todo";
        other.detail = `Ready now that "${step.title}" is complete.`;
        delete other.blockedBy;
      }
    }

    if (wasRequired) {
      this.onboarding.requiredComplete = Math.min(
        this.onboarding.requiredTotal,
        this.onboarding.requiredComplete + 1,
      );
    }
    this.onboarding.resumeStepId =
      this.onboarding.steps.find((item) => item.state === "in_progress" || item.state === "todo")
        ?.id ?? null;

    return {
      status: "saved",
      message: `${step.title} is complete.`,
      detail: "Stored in memory for this session only.",
    };
  }

  // ------------------------------------------------------- session and feedback

  async getSession(sessionId: string): Promise<SessionDetailView | null> {
    await delay(240);
    const session = this.plan.sessions.find((item) => item.id === sessionId);
    if (!session) return null;

    return {
      session: clone(session),
      planLabel: `Plan version ${this.plan.version}, detailed window ${this.plan.detailedWindow.start} to ${this.plan.detailedWindow.end}`,
      paceFacts: [
        {
          id: "sd-blocks",
          label: "Prescribed blocks",
          value: String(session.blocks.length),
          detail:
            session.blocks.length === 1 ? "A single continuous block." : "Structured session.",
        },
        {
          id: "sd-scope",
          label: "Prescribed scope",
          value: session.scope,
          detail: session.mainTarget,
        },
        {
          id: "sd-reported",
          label: "Outcome reported",
          value: session.feedback ? "Yes" : null,
          detail: session.feedback
            ? `Saved ${session.feedback.savedAt.slice(0, 10)}.`
            : "No outcome has been reported for this session yet.",
        },
      ],
      garminFacts: session.observed
        ? clone(session.observed.rows).map((row, index) => ({
            id: `sd-g-${index}`,
            label: row.label,
            value: row.value,
            detail: "Reported by Garmin, not calculated by Pace.",
          }))
        : [
            {
              id: "sd-g-none",
              label: "Matched activity",
              value: null,
              detail: "No Garmin activity has been matched to this session.",
            },
          ],
      garminNote:
        session.observed?.matchNote ??
        "A matched Garmin activity confirms that an activity happened. It does not prove that interval targets were met.",
      feedbackNote:
        "Your explicit feedback is the durable outcome of a session. The private note is stored locally and is only sent to the coaching model if you allow it.",
    };
  }

  async saveSessionFeedback(sessionId: string, draft: FeedbackDraft): Promise<MutationResult> {
    const session = this.plan.sessions.find((item) => item.id === sessionId);
    if (!session)
      return { status: "failed", message: "Session not found.", detail: "Nothing was written." };

    await delay(1000);

    if (draft.outcome !== "completed" && !draft.reason.trim()) {
      return {
        status: "failed",
        message: "Local validation rejected the feedback.",
        detail:
          draft.outcome === "skipped"
            ? "A skipped session needs a reason, otherwise the history cannot be interpreted later. Nothing was written."
            : "A limited session needs a reason describing the limitation. Nothing was written.",
      };
    }
    if (draft.rpe !== null && (draft.rpe < 1 || draft.rpe > 10)) {
      return {
        status: "failed",
        message: "Local validation rejected the feedback.",
        detail: "RPE must be between 1 and 10, or left unknown. Nothing was written.",
      };
    }

    session.feedback = {
      outcome: draft.outcome,
      rpe: draft.rpe,
      ...(draft.reason.trim() ? { reason: draft.reason.trim() } : {}),
      ...(draft.privateNote.trim() ? { privateNote: draft.privateNote.trim() } : {}),
      shareWithAi: draft.shareWithAi,
      savedAt: nowIso(),
    };

    if (this.today.session?.id === sessionId) {
      this.today.session.feedback = clone(session.feedback);
    }
    this.today.actionNeeded = this.today.actionNeeded.filter(
      (item) => !item.toLowerCase().includes("outcome"),
    );

    return {
      status: "saved",
      message: "Feedback saved.",
      detail: draft.shareWithAi
        ? "Stored locally. The private note may be used by the coach because you allowed it."
        : "Stored locally. The private note is withheld from the coaching model.",
    };
  }

  // ---------------------------------------------------------------- internals

  private findAction(actionId: string): CoachAction | undefined {
    for (const message of this.conversation) {
      if (message.action?.id === actionId) return message.action;
    }
    return undefined;
  }

  private outcomeFromFields(action: CoachAction) {
    const value = action.fields.find((f) => f.label === "Outcome")?.value ?? "";
    if (value.toLowerCase().includes("skip")) return "skipped" as const;
    if (value.toLowerCase().includes("limit")) return "limited" as const;
    return "completed" as const;
  }

  private rpeFromFields(action: CoachAction) {
    const raw = action.fields.find((f) => f.label === "Reported RPE")?.value ?? "";
    const match = raw.match(/\d+/);
    return match ? Number(match[0]) : null;
  }

  private composeReply(text: string): CoachMessage {
    const lower = text.toLowerCase();
    const createdAt = nowIso();

    if (lower.startsWith("/feedback") || /skipped|limited|completed|felt/.test(lower)) {
      const outcome = /skip/.test(lower)
        ? "Skipped"
        : /limit|cut|short|heavy|fatigue/.test(lower)
          ? "Completed with limitations"
          : "Completed";
      return {
        id: nextId("msg"),
        role: "coach",
        paragraphs: [
          "Understood. I have prepared the outcome below. Nothing is written until you confirm it.",
        ],
        evidence: [
          "Today's planned session: controlled 10 km specific repetitions, RPE 6-7.",
          "Garmin activity matching cannot verify interval compliance; your report is the durable record.",
        ],
        assessment: [
          outcome === "Skipped"
            ? "A single skipped session does not change the block. Do not compensate for it later in the week."
            : "One session at this effort is consistent with the current window. No plan change is needed.",
        ],
        createdAt,
        action: {
          id: nextId("act"),
          kind: "record_feedback",
          title: "Record session feedback",
          fields: [
            { label: "Session", value: "17 Sep 2026 - controlled 10 km repetitions" },
            { label: "Outcome", value: outcome },
            { label: "Reported RPE", value: /rpe\s*(\d+)/.exec(lower)?.[1] ?? "6" },
            { label: "Note", value: text.replace(/^\/feedback\s*/i, "") || "-" },
          ],
          status: "pending",
        },
      };
    }

    if (lower.startsWith("/context") || /travel|sick|illness|stress|work/.test(lower)) {
      return {
        id: nextId("msg"),
        role: "coach",
        paragraphs: [
          "Noted as context, not as a plan change. Confirm the card to store it locally.",
        ],
        evidence: [
          "Context events are stored separately from sessions and never overwrite history.",
        ],
        assessment: [
          "Context explains a deviation. It does not by itself justify moving or removing a session.",
        ],
        uncertainty: ["Context is self-reported and is not verified against any device data."],
        createdAt,
        action: {
          id: nextId("act"),
          kind: "record_context",
          title: "Record context event",
          fields: [
            { label: "Date", value: "17 Sep 2026" },
            { label: "Type", value: "Athlete-reported context" },
            { label: "Detail", value: text.replace(/^\/context\s*/i, "") || "-" },
          ],
          status: "pending",
        },
      };
    }

    if (lower.startsWith("/facts")) {
      return {
        id: nextId("msg"),
        role: "coach",
        paragraphs: ["These are the facts behind today's session."],
        evidence: [
          "Run volume 38.4 km in 7 days against a 36.1 km weekly mean over 84 days.",
          "HRV 58 ms against a 61 ms baseline; resting heart rate 46 bpm against 45 bpm.",
          "Sleep 6:20 last night; one night in the 28-day window is unknown.",
        ],
        assessment: ["Continuity supports one controlled quality session this week."],
        uncertainty: ["No verified current 10 km pace exists, so targets stay on effort."],
        createdAt,
      };
    }

    if (lower.startsWith("/plan")) {
      return {
        id: nextId("msg"),
        role: "coach",
        paragraphs: [
          "The active plan targets the synthetic Autumn 10 km on 1 Nov 2026, priority A. The detailed window covers 15-28 Sep 2026.",
        ],
        evidence: ["Seven planned sessions in the window; one outcome reported so far."],
        assessment: [
          "The next 14 detailed days are generated only when the window is due, on 24 Sep. Older accepted plans stay as immutable history.",
        ],
        createdAt,
      };
    }

    return {
      id: nextId("msg"),
      role: "coach",
      paragraphs: [
        "Here is what the current data supports. Nothing in this reply changes your plan; every change needs an explicit confirmation.",
      ],
      evidence: [
        "28-day window: 14 run or ride sessions, complete HRV and resting heart rate coverage.",
        "One fatigue-limited run reported in the last 28 days.",
      ],
      assessment: [
        "A single limited session is not a repeated negative response. Keep the quality session and keep easy days genuinely easy.",
      ],
      uncertainty: [
        "This demo runs on synthetic data only, so no conclusion here describes a real athlete.",
      ],
      createdAt,
    };
  }
}
