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
  PendingVolumeException,
  PlanView,
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

type JsonObject = Record<string, unknown>;

const nowIso = () => new Date().toISOString();

/** Same-origin adapter for the local Python process. No external URL is used. */
export class HttpPaceClient implements PaceClient {
  private csrfToken: string | null = null;
  private messages: CoachMessage[] = [];
  private actions = new Map<string, { endpoint: string; payload: JsonObject }>();
  private sync: SyncState = {
    phase: "idle",
    window: null,
    progress: null,
    message: "No sync is running.",
    startedAt: null,
    finishedAt: null,
    lastSyncAt: null,
    daysCovered: null,
  };

  private async bootstrap(): Promise<string> {
    if (this.csrfToken) return this.csrfToken;
    const value = await this.get<{ csrfToken: string }>("/api/v1/bootstrap");
    this.csrfToken = value.csrfToken;
    return value.csrfToken;
  }

  private async get<T>(path: string): Promise<T> {
    const response = await fetch(path, { credentials: "same-origin" });
    return this.read<T>(response);
  }

  private async mutate<T>(path: string, body: JsonObject, method = "POST"): Promise<T> {
    const csrf = await this.bootstrap();
    const response = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Pace-CSRF": csrf },
      body: JSON.stringify(body),
    });
    return this.read<T>(response);
  }

  private async read<T>(response: Response): Promise<T> {
    const value = (await response.json().catch(() => ({}))) as JsonObject;
    if (!response.ok) {
      throw new Error(
        typeof value["detail"] === "string"
          ? value["detail"]
          : `Pace request failed (${response.status}).`,
      );
    }
    return value as T;
  }

  getToday() {
    return this.get<TodayView>("/api/v1/today");
  }
  async getConversation() {
    return [...this.messages];
  }
  async getSlashCommands(): Promise<SlashCommand[]> {
    return [
      { command: "/today", description: "Show today's planned session." },
      { command: "/state", description: "Summarise current Pace state." },
      { command: "/analysis", description: "Show the current fact summary." },
      { command: "/sync", description: "Prepare a seven-day Garmin sync." },
      { command: "/review weekly", description: "Prepare a weekly review." },
    ];
  }

  async sendCoachMessage(text: string): Promise<CoachMessage[]> {
    const athlete: CoachMessage = {
      id: crypto.randomUUID(),
      role: "athlete",
      paragraphs: [text.trim()],
      createdAt: nowIso(),
    };
    this.messages.push(athlete);
    if (text.trim().startsWith("/")) {
      const result = await this.mutate<JsonObject>("/api/command", { command: text.trim() });
      this.messages.push({
        id: crypto.randomUUID(),
        role: "coach",
        paragraphs: [String(result["answer"] ?? "Command completed.")],
        createdAt: nowIso(),
      });
      return [...this.messages];
    }

    const answer = await this.mutate<JsonObject>("/api/chat", { question: text.trim() });
    const action = this.actionFromAnswer(answer);
    const coachMessage: CoachMessage = {
      id: crypto.randomUUID(),
      role: "coach",
      paragraphs: [String(answer["answer"] ?? "")],
      createdAt: nowIso(),
    };
    const evidence = asStrings(answer["observations"]);
    const uncertainty = asStrings(answer["uncertainties"]);
    if (evidence) coachMessage.evidence = evidence;
    if (uncertainty) coachMessage.uncertainty = uncertainty;
    if (action) coachMessage.action = action;
    this.messages.push(coachMessage);
    return [...this.messages];
  }

  private actionFromAnswer(answer: JsonObject): CoachAction | undefined {
    const feedback = objectOrNull(answer["feedback_draft"]);
    const context = objectOrNull(answer["context_event_draft"]);
    const draft = feedback ?? context;
    if (!draft) return undefined;
    const id = crypto.randomUUID();
    const endpoint = feedback ? "/api/feedback/confirm" : "/api/context/confirm";
    this.actions.set(id, { endpoint, payload: draft });
    return {
      id,
      kind: feedback ? "record_feedback" : "record_context",
      title: feedback ? "Record session feedback" : "Record context",
      fields: Object.entries(draft).map(([label, value]) => ({
        label: label.replaceAll("_", " "),
        value: value == null ? "unknown" : String(value),
      })),
      status: "pending",
    };
  }

  async confirmAction(actionId: string): Promise<CoachMessage[]> {
    const saved = this.actions.get(actionId);
    if (!saved) return [...this.messages];
    const action = this.messages.find((item) => item.action?.id === actionId)?.action;
    if (!action || action.status === "saved") return [...this.messages];
    action.status = "saving";
    try {
      await this.mutate<JsonObject>(saved.endpoint, saved.payload);
      action.status = "saved";
      action.savedAt = nowIso();
      this.actions.delete(actionId);
    } catch (error) {
      action.status = "failed";
      action.error = error instanceof Error ? error.message : "The action was not saved.";
    }
    return [...this.messages];
  }

  async getSyncState() {
    return { ...this.sync };
  }
  async startSync(window: 7 | 80): Promise<SyncState> {
    const startedAt = nowIso();
    this.sync = {
      ...this.sync,
      phase: "running",
      window,
      progress: null,
      message: `Syncing ${window} days from Garmin.`,
      startedAt,
      finishedAt: null,
    };
    try {
      if (window === 7) {
        await this.mutate<JsonObject>("/api/command/confirm", { action: "sync" });
      } else {
        await this.mutate<JsonObject>("/api/setup/history/confirm", { days: 80 });
      }
      const finishedAt = nowIso();
      this.sync = {
        ...this.sync,
        phase: "completed",
        progress: null,
        message: "Sync completed.",
        finishedAt,
        lastSyncAt: finishedAt,
        daysCovered: window,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : "Sync failed.";
      const phase = /rate.?limit/i.test(message)
        ? "rate_limited"
        : /auth|login|session/i.test(message)
          ? "auth_required"
          : "failed";
      this.sync = {
        ...this.sync,
        phase,
        progress: null,
        message,
        finishedAt: nowIso(),
        daysCovered: null,
      };
    }
    return { ...this.sync };
  }
  async pollSync() {
    return { ...this.sync };
  }

  async getPlan(): Promise<PlanView> {
    const plan = await this.get<PlanView | null>("/api/v1/plans/active");
    if (!plan) throw new Error("No active plan exists yet. Create one from Races or Onboarding.");
    return plan;
  }
  getPlanHistory() {
    return this.get<PlanHistoryEntry[]>("/api/v1/plans/history");
  }
  getPendingVolumeException() {
    return this.get<PendingVolumeException | null>("/api/v1/plans/pending-volume-exception");
  }
  async approveVolumeException(planId: string): Promise<MutationResult> {
    try {
      await this.mutate<JsonObject>("/api/v1/plans/volume-exception/approve", {
        plan_id: Number(planId),
      });
      return ok("Race-volume exception approved.", "The proposed plan is now active.");
    } catch (error) {
      return failed(error);
    }
  }
  getDashboard(window: DashboardWindow) {
    return this.get<DashboardView>(`/api/v1/dashboard?days=${window}`);
  }
  getWeeklyReview() {
    return this.get<WeeklyReviewState>("/api/v1/weekly-reviews/latest");
  }
  getRaces() {
    return this.get<RacesView>("/api/v1/races");
  }
  getSettings() {
    return this.get<SettingsView>("/api/v1/settings");
  }
  getSession(sessionId: string) {
    return this.get<SessionDetailView | null>(`/api/v1/sessions/${encodeURIComponent(sessionId)}`);
  }

  async setRevisionDueDemo(): Promise<PlanView> {
    return this.getPlan();
  }
  async generateNextWindow(): Promise<RevisionResult> {
    const current = await this.getPlan();
    try {
      const result = await this.mutate<JsonObject>("/api/plan/revise/confirm", {
        plan_id: Number(current.planId),
      });
      if (result["status"] === "volume_exception_pending") {
        return {
          status: "pending_approval",
          message: "The proposed plan needs your approval.",
          detail: "It exceeds a base-volume boundary and has not replaced the active plan.",
        };
      }
      return {
        status: "saved",
        message: "The next detailed window was created.",
        detail: "The previous plan remains in history.",
        plan: await this.getPlan(),
      };
    } catch (error) {
      return { status: "failed", message: "No revision was saved.", detail: errorMessage(error) };
    }
  }
  async generateWeeklyReview(): Promise<WeeklyReviewState> {
    await this.mutate<JsonObject>("/api/command/confirm", { action: "weekly_review" });
    return this.getWeeklyReview();
  }
  async resetWeeklyReviewDemo() {
    return this.getWeeklyReview();
  }

  async addRace(draft: RaceDraft): Promise<MutationResult> {
    try {
      await this.mutate<JsonObject>("/api/v1/races", {
        name: draft.name,
        sport: draft.sport,
        date: draft.date,
        distance_km: Number.parseFloat(draft.distance),
        priority: draft.priority,
        desired_time_seconds: durationSeconds(draft.desiredTime),
        taper_override: null,
      });
      return ok("Race saved.", "It is available as an explicit plan target.");
    } catch (error) {
      return failed(error);
    }
  }
  async cancelRace(raceId: string): Promise<MutationResult> {
    try {
      await this.mutate<JsonObject>(`/api/v1/races/${raceId}/cancel`, {});
      return ok("Race cancelled.", "Existing plan history was not rewritten.");
    } catch (error) {
      return failed(error);
    }
  }
  async setPlanTarget(raceId: string): Promise<MutationResult> {
    try {
      const result = await this.mutate<JsonObject>("/api/plan/draft/confirm", {
        race_id: Number(raceId),
      });
      if (result["status"] === "volume_exception_pending") {
        return ok(
          "Plan created for review.",
          "It exceeds a base-volume boundary and is not active until you approve the exception on Plan.",
        );
      }
      return ok("Plan created and activated.", "The selected race is now the explicit target.");
    } catch (error) {
      return failed(error);
    }
  }

  async saveSettings(patch: SettingsPatch): Promise<MutationResult> {
    try {
      const current = await this.getSettings();
      const next = { ...current, ...patch };
      await this.mutate<JsonObject>("/api/setup/preferences", {
        sport_role: next.sportRole,
        coaching_ambition: next.ambition,
        available_days: next.availability
          .filter((item) => item.available)
          .map((item) => `${item.day}:${item.capMinutes ?? "any"}`),
        base_running_distance_ceiling_km: next.volumeBoundaries.runningKmPerWeek,
        base_cycling_duration_ceiling_hours: next.volumeBoundaries.cyclingHoursPerWeek,
        base_total_duration_ceiling_hours: next.volumeBoundaries.totalHoursPerWeek,
      });
      if (
        next.zonesConfirmed &&
        next.cyclingZones.every((item) => item.from != null && item.to != null)
      ) {
        await this.mutate<JsonObject>("/api/setup/zones", {
          zones: next.cyclingZones.map((item, index) => `${index + 1}:${item.from}-${item.to}`),
        });
      }
      return ok("Settings saved.", "The next planning request will use these athlete preferences.");
    } catch (error) {
      return failed(error);
    }
  }
  async reconnectGarminDemo() {
    return {
      status: "failed" as const,
      message: "Use Onboarding to reconnect Garmin.",
      detail: "Pace never inserts demo credentials.",
    };
  }

  async getOnboarding(): Promise<OnboardingView> {
    const home = await this.get<JsonObject>("/api/home");
    const state = objectOrNull(home["onboarding"]) ?? {};
    const flags: Array<[string, string, string, boolean, boolean]> = [
      [
        "openai",
        "Connect OpenAI",
        "Store an API key locally.",
        Boolean(state["openai_configured"]),
        false,
      ],
      [
        "garmin",
        "Connect Garmin",
        "Create a local Garmin session.",
        Boolean(state["garmin_connected"]),
        false,
      ],
      [
        "preferences",
        "Set training preferences",
        "Choose sport role, ambition and availability in Settings.",
        Boolean(state["preferences_configured"]),
        false,
      ],
      [
        "zones",
        "Confirm cycling zones",
        "Required unless running is your only sport.",
        Boolean(state["ride_zones_configured"]) || !state["ride_zones_required"],
        true,
      ],
      [
        "history",
        "Sync training history",
        "Import up to 80 days in safe batches.",
        Boolean(state["history_ready"]),
        false,
      ],
      [
        "plan",
        "Create the first plan",
        "Choose a general plan or an explicit stored race.",
        Boolean(home["active_plan"]),
        false,
      ],
    ];
    const steps = flags.map(([id, title, description, complete, optional]) => {
      const step = {
        id,
        title,
        description,
        state: complete
          ? ("complete" as const)
          : optional
            ? ("optional" as const)
            : ("todo" as const),
        detail: complete ? "Complete." : "Not completed yet.",
      };
      return step;
    });
    const required = steps.filter((item) => item.state !== "optional");
    return {
      steps,
      requiredComplete: required.filter((item) => item.state === "complete").length,
      requiredTotal: required.length,
      resumeStepId: steps.find((item) => item.state === "todo")?.id ?? null,
      note: "Setup state is read from the local Pace installation.",
    };
  }
  async completeOnboardingStep(): Promise<MutationResult> {
    return {
      status: "failed",
      message: "Open the relevant form to complete this step.",
      detail: "Credentials and targets require explicit input and are never invented.",
    };
  }

  async saveSessionFeedback(sessionId: string, draft: FeedbackDraft): Promise<MutationResult> {
    try {
      await this.mutate<JsonObject>("/api/feedback/confirm", {
        session_id: Number(sessionId),
        outcome: draft.outcome === "limited" ? "completed_limited" : draft.outcome,
        perceived_exertion: draft.rpe,
        reason_code: draft.reason || null,
        note: draft.privateNote || null,
        share_note_with_ai: draft.shareWithAi,
      });
      return ok(
        "Feedback saved.",
        "This explicit athlete report is now the durable session outcome.",
      );
    } catch (error) {
      return failed(error);
    }
  }
}

function objectOrNull(value: unknown): JsonObject | null {
  return value != null && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonObject)
    : null;
}
function asStrings(value: unknown): string[] | undefined {
  return Array.isArray(value) ? value.map(String) : undefined;
}
function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The local request failed.";
}
function ok(message: string, detail: string): MutationResult {
  return { status: "saved", message, detail };
}
function failed(error: unknown): MutationResult {
  return { status: "failed", message: "Nothing was saved.", detail: errorMessage(error) };
}
function durationSeconds(value: string): number | null {
  if (!value.trim()) return null;
  const parts = value.split(":").map(Number);
  if (parts.some(Number.isNaN)) return null;
  return parts.reduce((total, part) => total * 60 + part, 0);
}
