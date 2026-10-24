# Proposed React data contracts

These contracts describe the intended frontend boundary. They are not yet
implemented endpoints. Before integration, each contract must be mapped to the
existing Python services and covered by API tests.

## Adapter principle

The React application imports one typed `PaceClient` interface. Prototype mode
uses `MockPaceClient` with synthetic fixtures. Integrated mode uses
`HttpPaceClient` with same-origin requests. Components never import mock data or
HTTP directly.

```ts
interface PaceClient {
  getBootstrap(): Promise<BootstrapView>;
  getToday(): Promise<TodayView>;
  getDashboard(days: 28 | 84): Promise<DashboardView>;
  getActivePlan(): Promise<PlanView | null>;
  getWeeklyReview(): Promise<WeeklyReviewView | null>;
  getRaces(): Promise<RaceView[]>;
  getSettings(): Promise<SettingsView>;
}
```

Mutation methods are explicit and return server-confirmed results. They never
mutate local canonical state optimistically.

```ts
interface PaceActions {
  sendCoachMessage(input: CoachMessageInput): Promise<CoachTurnResult>;
  confirmAction(input: ConfirmationInput): Promise<ConfirmationResult>;
  startSync(input: { days: 7 | 80 }): Promise<SyncOperation>;
  saveFeedback(input: FeedbackInput): Promise<FeedbackResult>;
  saveContext(input: ContextInput): Promise<ContextResult>;
  createPlan(input: PlanTargetInput): Promise<PlanResult>;
  revisePlan(input: { planId: number }): Promise<PlanResult>;
  updateSettings(input: SettingsInput): Promise<SettingsView>;
  addRace(input: RaceInput): Promise<RaceView>;
  updateRace(id: number, input: RaceInput): Promise<RaceView>;
  cancelRace(id: number): Promise<RaceView>;
}
```

## Proposed routes

Read routes:

- `GET /api/v1/bootstrap`
- `GET /api/v1/today`
- `GET /api/v1/dashboard?days=28|84`
- `GET /api/v1/plans/active`
- `GET /api/v1/weekly-reviews/latest`
- `GET /api/v1/races`
- `GET /api/v1/settings`

Explicit mutation routes:

- `POST /api/v1/coach/messages`
- `POST /api/v1/confirmations`
- `POST /api/v1/syncs`
- `POST /api/v1/feedback`
- `POST /api/v1/context-events`
- `POST /api/v1/plans`
- `POST /api/v1/plans/{id}/revisions`
- `PATCH /api/v1/settings`
- `POST/PATCH/DELETE /api/v1/races`

The final route names may change during implementation. Service ownership and
security semantics may not.

## Shared response rules

Every response includes normalized display-ready facts and machine-readable
codes. Dates use ISO `YYYY-MM-DD`; instants use UTC ISO 8601. Durations use
seconds, distances use metres, and display formatting happens in the UI.

Missing data is `null`, never `0` or an empty invented string. Each important
metric can carry:

```ts
type DataQuality = {
  status: "ready" | "limited" | "stale" | "missing";
  observed?: number;
  expected?: number;
  latestDate?: string | null;
  limitations: string[];
};
```

Long-running syncs use one operation contract:

```ts
type SyncOperation = {
  id: string;
  status: "queued" | "running" | "completed" | "partial" | "failed";
  completedBatches: number;
  totalBatches: number;
  coveredStartDate: string | null;
  coveredEndDate: string | null;
  message: string;
  retryable: boolean;
};
```

## Data that must never cross the browser boundary

- OpenAI API key;
- Garmin email, password, MFA value after request handling, or token content;
- raw Garmin payloads;
- GPS coordinates, routes, or per-second streams;
- SQLite paths, ORM entities, or database dumps;
- private note text outside an explicit editing/confirmation flow;
- provider implementation errors or stack traces.

## Synthetic fixture requirements

Prototype fixtures must cover:

- ready and incomplete onboarding;
- run-only, balanced, and ride-primary settings;
- general plan and A/B/C race targets;
- steady, interval, and mixed workout structures;
- completed, limited, skipped, and unreported outcomes;
- full, missing, stale, and partial recovery data;
- successful, partial, rate-limited, and authentication-required syncs;
- plan revision due and not due;
- weekly review present and absent.
