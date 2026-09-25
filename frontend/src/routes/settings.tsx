import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/pace/AppShell";
import { SyncCard } from "@/components/pace/SyncCard";
import { PageHeader, Panel } from "@/components/pace/primitives";
import {
  Busy,
  FailedState,
  LoadingState,
  NoticeState,
  StatusBadge,
} from "@/components/pace/states";
import { getPaceClient } from "@/lib/pace/client";
import { paceKeys, settingsQuery } from "@/lib/pace/queries";
import type { Ambition, MutationResult, SettingsView, SportRole } from "@/lib/pace/types";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings - Pace local coaching system" },
      {
        name: "description",
        content:
          "Sport role, coaching ambition, available weekdays and time caps, five confirmed cycling heart-rate zones, local connections and explicit 7-day or 80-day sync.",
      },
      { property: "og:title", content: "Settings - Pace local coaching system" },
      {
        property: "og:description",
        content: "Athlete-controlled settings that apply to future plan generation only.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: SettingsPage,
});

const BUTTON =
  "border border-rule-strong px-3 py-2 font-mono text-[0.72rem] uppercase tracking-[0.08em] disabled:cursor-not-allowed disabled:opacity-50";
const FIELD = "w-full border border-rule bg-surface px-2 py-1.5 text-sm";

const SPORT_ROLES: { value: SportRole; label: string; detail: string }[] = [
  { value: "run_only", label: "Run only", detail: "Cycling is ignored in every calculation." },
  {
    value: "run_primary",
    label: "Run primary",
    detail: "Running drives the plan; cycling adds aerobic time.",
  },
  { value: "balanced", label: "Balanced", detail: "Running and cycling weigh equally." },
  {
    value: "ride_primary",
    label: "Ride primary",
    detail: "Cycling drives the plan; running supports it.",
  },
  { value: "ride_only", label: "Ride only", detail: "Running is ignored in every calculation." },
];

const AMBITIONS: { value: Ambition; label: string; detail: string }[] = [
  {
    value: "cautious",
    label: "Cautious",
    detail: "Slower progression, more easy days, quality added late.",
  },
  {
    value: "balanced",
    label: "Balanced",
    detail: "One quality session per week, progression when outcomes allow.",
  },
  {
    value: "ambitious",
    label: "Ambitious",
    detail: "Two quality sessions sooner, less tolerance for missed volume.",
  },
];

function ResultNotice({ result, title }: { result: MutationResult; title: string }) {
  return result.status === "saved" ? (
    <NoticeState kind="completed" title={result.message} description={result.detail} />
  ) : (
    <FailedState title={title} description={`${result.message} ${result.detail}`} />
  );
}

function SettingsForm({ settings }: { settings: SettingsView }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<SettingsView>(settings);

  useEffect(() => {
    setDraft(settings);
  }, [settings]);

  const save = useMutation({
    mutationFn: (value: SettingsView) =>
      getPaceClient().saveSettings({
        sportRole: value.sportRole,
        ambition: value.ambition,
        availability: value.availability,
        volumeBoundaries: value.volumeBoundaries,
        cyclingZones: value.cyclingZones,
        zonesConfirmed: value.zonesConfirmed,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: paceKeys.settings }),
  });

  const dirty = JSON.stringify(draft) !== JSON.stringify(settings);

  return (
    <form
      className="space-y-6"
      onSubmit={(event) => {
        event.preventDefault();
        if (save.isPending) return;
        save.mutate(draft);
      }}
    >
      <Panel
        title="Sport role"
        note="Which sports enter coaching calculations, and how they are weighted."
      >
        <fieldset className="space-y-2">
          <legend className="sr-only">Sport role</legend>
          {SPORT_ROLES.map((role) => (
            <label
              key={role.value}
              className="flex items-start gap-3 border border-rule px-3 py-2 text-sm"
            >
              <input
                type="radio"
                name="sportRole"
                className="mt-1"
                checked={draft.sportRole === role.value}
                onChange={() => setDraft({ ...draft, sportRole: role.value })}
              />
              <span>
                <span className="font-semibold">{role.label}</span>
                <span className="mt-0.5 block text-muted-foreground">{role.detail}</span>
              </span>
            </label>
          ))}
        </fieldset>
      </Panel>

      <Panel title="Coaching ambition" note="How aggressively the coach progresses the block.">
        <fieldset className="grid gap-2 md:grid-cols-3">
          <legend className="sr-only">Coaching ambition</legend>
          {AMBITIONS.map((option) => (
            <label
              key={option.value}
              className="flex items-start gap-3 border border-rule px-3 py-2 text-sm"
            >
              <input
                type="radio"
                name="ambition"
                className="mt-1"
                checked={draft.ambition === option.value}
                onChange={() => setDraft({ ...draft, ambition: option.value })}
              />
              <span>
                <span className="font-semibold">{option.label}</span>
                <span className="mt-0.5 block text-muted-foreground">{option.detail}</span>
              </span>
            </label>
          ))}
        </fieldset>
      </Panel>

      <Panel
        title="Base training volume boundaries"
        note="Hard weekly ceilings for ordinary base training. These are lifestyle boundaries, not targets or evidence of capacity."
      >
        <div className="grid gap-4 md:grid-cols-3">
          {draft.sportRole !== "ride_only" && (
            <label className="text-sm">
              <span className="font-semibold">Running</span>
              <span className="mt-0.5 block text-xs text-muted-foreground">
                Maximum kilometres per calendar week
              </span>
              <input
                type="number"
                min={1}
                max={1000}
                step="0.5"
                className={`${FIELD} mt-2`}
                value={draft.volumeBoundaries.runningKmPerWeek ?? ""}
                placeholder="No athlete cap"
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    volumeBoundaries: {
                      ...draft.volumeBoundaries,
                      runningKmPerWeek:
                        event.target.value === "" ? null : Number(event.target.value),
                    },
                  })
                }
              />
            </label>
          )}
          {draft.sportRole !== "run_only" && (
            <label className="text-sm">
              <span className="font-semibold">Cycling</span>
              <span className="mt-0.5 block text-xs text-muted-foreground">
                Maximum hours per calendar week
              </span>
              <input
                type="number"
                min={0.5}
                max={168}
                step="0.5"
                className={`${FIELD} mt-2`}
                value={draft.volumeBoundaries.cyclingHoursPerWeek ?? ""}
                placeholder="No athlete cap"
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    volumeBoundaries: {
                      ...draft.volumeBoundaries,
                      cyclingHoursPerWeek:
                        event.target.value === "" ? null : Number(event.target.value),
                    },
                  })
                }
              />
            </label>
          )}
          <label className="text-sm">
            <span className="font-semibold">Combined training</span>
            <span className="mt-0.5 block text-xs text-muted-foreground">
              Maximum total hours per calendar week
            </span>
            <input
              type="number"
              min={0.5}
              max={168}
              step="0.5"
              className={`${FIELD} mt-2`}
              value={draft.volumeBoundaries.totalHoursPerWeek ?? ""}
              placeholder="No athlete cap"
              onChange={(event) =>
                setDraft({
                  ...draft,
                  volumeBoundaries: {
                    ...draft.volumeBoundaries,
                    totalHoursPerWeek:
                      event.target.value === "" ? null : Number(event.target.value),
                  },
                })
              }
            />
          </label>
        </div>
        <div className="mt-4 border-l-2 border-accent px-3 text-sm text-muted-foreground">
          A general plan cannot cross these boundaries. A race-directed plan may propose a temporary
          exception, but it stays inactive until you explicitly approve it. Approval does not change
          these saved base boundaries.
        </div>
      </Panel>

      <Panel
        title="Availability and time caps"
        note="Sessions are only placed on available days, and never longer than the cap you set."
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[420px] border-collapse text-sm">
            <thead>
              <tr>
                <th scope="col" className="border-b border-rule px-2 py-2 text-left font-semibold">
                  Day
                </th>
                <th scope="col" className="border-b border-rule px-2 py-2 text-left font-semibold">
                  Available
                </th>
                <th scope="col" className="border-b border-rule px-2 py-2 text-left font-semibold">
                  Time cap (minutes)
                </th>
              </tr>
            </thead>
            <tbody>
              {draft.availability.map((day, index) => (
                <tr key={day.day}>
                  <th
                    scope="row"
                    className="border-b border-rule px-2 py-1.5 text-left font-normal"
                  >
                    {day.day}
                  </th>
                  <td className="border-b border-rule px-2 py-1.5">
                    <input
                      type="checkbox"
                      aria-label={`${day.day} available`}
                      checked={day.available}
                      onChange={(event) => {
                        const availability = [...draft.availability];
                        availability[index] = { ...day, available: event.target.checked };
                        setDraft({ ...draft, availability });
                      }}
                    />
                  </td>
                  <td className="border-b border-rule px-2 py-1.5">
                    <input
                      type="number"
                      min={20}
                      max={360}
                      className={`${FIELD} max-w-28`}
                      aria-label={`${day.day} time cap in minutes`}
                      placeholder="No cap"
                      value={day.capMinutes ?? ""}
                      disabled={!day.available}
                      onChange={(event) => {
                        const availability = [...draft.availability];
                        availability[index] = {
                          ...day,
                          capMinutes: event.target.value === "" ? null : Number(event.target.value),
                        };
                        setDraft({ ...draft, availability });
                      }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          An empty cap means no limit, which is different from zero minutes.
        </p>
      </Panel>

      <Panel
        title="Cycling heart-rate zones"
        note="Five zones, confirmed by you. Ride targets are only prescribed in zones once these are confirmed."
        aside={
          <StatusBadge
            kind={draft.zonesConfirmed ? "completed" : "pending"}
            label={draft.zonesConfirmed ? "Confirmed" : "Not confirmed"}
          />
        }
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {draft.cyclingZones.map((zone, index) => (
            <div key={zone.id} className="border border-rule px-3 py-2">
              <p className="label-micro">{zone.label}</p>
              <div className="mt-1.5 flex items-center gap-2">
                <input
                  type="number"
                  className={FIELD}
                  aria-label={`${zone.label} lower bound in bpm`}
                  value={zone.from ?? ""}
                  onChange={(event) => {
                    const cyclingZones = [...draft.cyclingZones];
                    cyclingZones[index] = {
                      ...zone,
                      from: event.target.value === "" ? null : Number(event.target.value),
                    };
                    setDraft({ ...draft, cyclingZones });
                  }}
                />
                <span aria-hidden className="text-muted-foreground">
                  to
                </span>
                <input
                  type="number"
                  className={FIELD}
                  aria-label={`${zone.label} upper bound in bpm`}
                  value={zone.to ?? ""}
                  onChange={(event) => {
                    const cyclingZones = [...draft.cyclingZones];
                    cyclingZones[index] = {
                      ...zone,
                      to: event.target.value === "" ? null : Number(event.target.value),
                    };
                    setDraft({ ...draft, cyclingZones });
                  }}
                />
                <span className="label-micro">bpm</span>
              </div>
            </div>
          ))}
        </div>
        <label className="mt-3 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={draft.zonesConfirmed}
            onChange={(event) => setDraft({ ...draft, zonesConfirmed: event.target.checked })}
          />
          I confirm these five zones are current.
        </label>
      </Panel>

      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" className={BUTTON} disabled={save.isPending || !dirty}>
          {save.isPending ? "Saving" : dirty ? "Save settings" : "No changes to save"}
        </button>
        {dirty && !save.isPending && <span className="label-micro">Unsaved changes</span>}
        {save.isPending && <Busy label="Validating and writing locally" />}
      </div>

      {save.data && !save.isPending && (
        <ResultNotice result={save.data} title="Settings were not saved" />
      )}
    </form>
  );
}

function Connections({ settings }: { settings: SettingsView }) {
  return (
    <Panel
      title="Connections"
      note="Credentials stay on this machine and are never shown here. Pace opens its hardened local setup form for connection changes."
    >
      <ul className="space-y-3">
        {settings.connections.map((connection) => (
          <li key={connection.id} className="border border-rule px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold">{connection.label}</p>
              <StatusBadge
                kind={
                  connection.state === "connected"
                    ? "completed"
                    : connection.state === "needs_reauth"
                      ? "stale"
                      : "empty"
                }
                label={
                  connection.state === "connected"
                    ? "Connected"
                    : connection.state === "needs_reauth"
                      ? "Needs re-authorisation"
                      : "Not connected"
                }
              />
            </div>
            <p className="mt-1 text-sm text-muted-foreground">{connection.detail}</p>
          </li>
        ))}
      </ul>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <a href="/legacy/setup" className={BUTTON}>
          Manage local connections
        </a>
      </div>
    </Panel>
  );
}

function DetailedGarminSync() {
  const queryClient = useQueryClient();
  const sync = useMutation({
    mutationFn: () => getPaceClient().syncActivityDetails(),
    onSuccess: (result) => {
      if (result.status === "saved") {
        queryClient.invalidateQueries({ queryKey: ["pace", "dashboard"] });
      }
    },
  });
  return (
    <Panel
      title="Activity detail and heart-rate zones"
      note="Separate from the normal sync to limit Garmin requests. Reads only the latest seven days and stores normalized summaries, splits and aggregate time in zones — never routes or second-by-second streams."
    >
      <button
        type="button"
        className={BUTTON}
        disabled={sync.isPending}
        onClick={() => sync.mutate()}
      >
        {sync.isPending ? "Syncing detailed facts" : "Sync latest 7 days of detailed facts"}
      </button>
      {sync.data && !sync.isPending && (
        <div className="mt-3">
          <ResultNotice result={sync.data} title="Detailed Garmin sync failed" />
        </div>
      )}
    </Panel>
  );
}

function SettingsPage() {
  const { data, isPending, isError, refetch } = useQuery(settingsQuery());

  return (
    <AppShell>
      <PageHeader
        eyebrow="Athlete controls"
        title="Settings"
        lede="Sport role, ambition, availability, cycling zones, local connections and explicit Garmin sync."
      />

      <div className="mt-6 space-y-6">
        {isPending && (
          <Panel title="Reading settings">
            <LoadingState label="Loading local settings" />
          </Panel>
        )}

        {isError && (
          <FailedState
            title="Settings could not be read"
            description="Nothing was changed."
            action={
              <button type="button" className={BUTTON} onClick={() => void refetch()}>
                Retry
              </button>
            }
          />
        )}

        {data && (
          <>
            <NoticeState
              kind="pending"
              badgeLabel="Rule"
              title="Changes affect future plans only"
              description={data.note}
            />
            <SettingsForm settings={data} />
            <Connections settings={data} />
            <SyncCard />
            <DetailedGarminSync />
          </>
        )}
      </div>
    </AppShell>
  );
}
