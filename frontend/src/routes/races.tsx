import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import { AppShell } from "@/components/pace/AppShell";
import { PageHeader, Panel } from "@/components/pace/primitives";
import {
  Busy,
  EmptyState,
  FailedState,
  LoadingState,
  NoticeState,
  StatusBadge,
} from "@/components/pace/states";
import { getPaceClient } from "@/lib/pace/client";
import { paceKeys, racesQuery } from "@/lib/pace/queries";
import type { MutationResult, Race, RaceDraft, RacePriority, Sport } from "@/lib/pace/types";

export const Route = createFileRoute("/races")({
  head: () => ({
    meta: [
      { title: "Races - Pace local coaching system" },
      {
        name: "description",
        content:
          "Register, edit and cancel future races with A, B or C priority and taper policy. Registering a race never selects it as the plan target.",
      },
      { property: "og:title", content: "Races - Pace local coaching system" },
      {
        property: "og:description",
        content: "Future races with priority, desired time and taper policy, stored locally.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: RacesPage,
});

const PRIORITY_TEXT: Record<RacePriority, string> = {
  A: "A - primary goal, full taper",
  B: "B - hard secondary race, partial taper",
  C: "C - hard training event, no race taper",
};

const BUTTON =
  "border border-rule-strong px-3 py-2 font-mono text-[0.72rem] uppercase tracking-[0.08em] disabled:cursor-not-allowed disabled:opacity-50";
const FIELD = "mt-1 w-full border border-rule bg-surface px-2 py-1.5 text-sm";

function ResultNotice({ result, title }: { result: MutationResult; title: string }) {
  return result.status === "saved" ? (
    <NoticeState kind="completed" title={result.message} description={result.detail} />
  ) : (
    <FailedState title={title} description={`${result.message} ${result.detail}`} />
  );
}

function RaceRow({ race, activeTargetId }: { race: Race; activeTargetId: string | null }) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState<"target" | "cancel" | null>(null);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: paceKeys.races });

  const setTarget = useMutation({
    mutationFn: () => getPaceClient().setPlanTarget(race.id),
    onSuccess: () => {
      setConfirming(null);
      void invalidate();
    },
  });

  const cancel = useMutation({
    mutationFn: () => getPaceClient().cancelRace(race.id),
    onSuccess: () => {
      setConfirming(null);
      void invalidate();
    },
  });

  const busy = setTarget.isPending || cancel.isPending;
  const eligible = race.status === "planned";

  return (
    <li className="border border-rule bg-surface px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold">{race.name}</p>
          <p className="mt-0.5 font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">
            {race.date} - {race.distance} - {race.sport === "running" ? "Running" : "Cycling"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {race.id === activeTargetId && <StatusBadge kind="current" label="Plan target" />}
          {race.status === "cancelled" && <StatusBadge kind="empty" label="Cancelled" />}
          {race.status === "completed" && <StatusBadge kind="completed" label="Completed" />}
          <StatusBadge kind="pending" label={`Priority ${race.priority}`} />
        </div>
      </div>

      <dl className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
        <div className="flex gap-2">
          <dt className="label-micro pt-0.5">Priority</dt>
          <dd>{PRIORITY_TEXT[race.priority]}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="label-micro pt-0.5">Desired time</dt>
          <dd className={race.desiredTime ? "" : "font-mono text-xs uppercase text-unknown"}>
            {race.desiredTime ?? "Unknown"}
          </dd>
        </div>
        <div className="flex gap-2 sm:col-span-2">
          <dt className="label-micro pt-0.5">Taper</dt>
          <dd>{race.taperPolicy}</dd>
        </div>
      </dl>

      {race.note && <p className="mt-2 text-xs text-muted-foreground">{race.note}</p>}

      {eligible && (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-rule pt-3">
          {race.id !== activeTargetId &&
            (confirming === "target" ? (
              <>
                <span className="text-sm">
                  Make this the plan target? The active plan is not rewritten.
                </span>
                <button
                  type="button"
                  className={BUTTON}
                  disabled={busy}
                  onClick={() => setTarget.mutate()}
                >
                  Confirm target
                </button>
                <button
                  type="button"
                  className={BUTTON}
                  disabled={busy}
                  onClick={() => setConfirming(null)}
                >
                  Keep current
                </button>
              </>
            ) : (
              <button
                type="button"
                className={BUTTON}
                disabled={busy}
                onClick={() => setConfirming("target")}
              >
                Select as plan target
              </button>
            ))}

          {confirming === "cancel" ? (
            <>
              <span className="text-sm">Cancel this race? It stays as history.</span>
              <button
                type="button"
                className={BUTTON}
                disabled={busy}
                onClick={() => cancel.mutate()}
              >
                Confirm cancellation
              </button>
              <button
                type="button"
                className={BUTTON}
                disabled={busy}
                onClick={() => setConfirming(null)}
              >
                Keep race
              </button>
            </>
          ) : (
            <button
              type="button"
              className={BUTTON}
              disabled={busy}
              onClick={() => setConfirming("cancel")}
            >
              Cancel race
            </button>
          )}

          {busy && <Busy label="Writing locally" />}
        </div>
      )}

      {setTarget.data && (
        <div className="mt-3">
          <ResultNotice result={setTarget.data} title="The plan target was not changed" />
        </div>
      )}
      {cancel.data && (
        <div className="mt-3">
          <ResultNotice result={cancel.data} title="The race was not cancelled" />
        </div>
      )}
    </li>
  );
}

const EMPTY_DRAFT: RaceDraft = {
  name: "",
  sport: "running",
  date: "",
  distance: "",
  priority: "B",
  desiredTime: "",
};

function AddRaceForm() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<RaceDraft>(EMPTY_DRAFT);

  const add = useMutation({
    mutationFn: (value: RaceDraft) => getPaceClient().addRace(value),
    onSuccess: (result) => {
      if (result.status === "saved") setDraft(EMPTY_DRAFT);
      void queryClient.invalidateQueries({ queryKey: paceKeys.races });
    },
  });

  return (
    <Panel
      title="Register a race"
      note="Registration stores the race only. It never makes the race the plan target and never changes the active plan."
    >
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (add.isPending) return;
          add.mutate(draft);
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="label-micro">Race name</span>
            <input
              className={FIELD}
              value={draft.name}
              required
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
            />
          </label>
          <label className="block text-sm">
            <span className="label-micro">Date</span>
            <input
              type="date"
              className={FIELD}
              value={draft.date}
              required
              onChange={(event) => setDraft({ ...draft, date: event.target.value })}
            />
          </label>
          <label className="block text-sm">
            <span className="label-micro">Sport</span>
            <select
              className={FIELD}
              value={draft.sport}
              onChange={(event) => setDraft({ ...draft, sport: event.target.value as Sport })}
            >
              <option value="running">Running</option>
              <option value="cycling">Cycling</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="label-micro">Distance</span>
            <input
              className={FIELD}
              placeholder="10 km"
              value={draft.distance}
              onChange={(event) => setDraft({ ...draft, distance: event.target.value })}
            />
          </label>
          <label className="block text-sm">
            <span className="label-micro">Priority</span>
            <select
              className={FIELD}
              value={draft.priority}
              onChange={(event) =>
                setDraft({ ...draft, priority: event.target.value as RacePriority })
              }
            >
              {(["A", "B", "C"] as RacePriority[]).map((priority) => (
                <option key={priority} value={priority}>
                  {PRIORITY_TEXT[priority]}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="label-micro">Desired time (optional)</span>
            <input
              className={FIELD}
              placeholder="39:30"
              value={draft.desiredTime}
              onChange={(event) => setDraft({ ...draft, desiredTime: event.target.value })}
            />
          </label>
        </div>

        <p className="text-xs text-muted-foreground">
          A desired time is recorded as your ambition, never as a prediction. The taper policy
          follows the priority you choose.
        </p>

        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" className={BUTTON} disabled={add.isPending}>
            {add.isPending ? "Saving" : "Register race"}
          </button>
          {add.isPending && <Busy label="Validating and writing locally" />}
        </div>

        {add.data && !add.isPending && (
          <ResultNotice result={add.data} title="The race was not registered" />
        )}
      </form>
    </Panel>
  );
}

function RacesPage() {
  const { data, isPending, isError, refetch } = useQuery(racesQuery());

  const planned = data?.races.filter((race) => race.status === "planned") ?? [];
  const other = data?.races.filter((race) => race.status !== "planned") ?? [];

  return (
    <AppShell>
      <PageHeader
        eyebrow="Targets and history"
        title="Races"
        lede="Registered races with priority, desired time and taper policy. Choosing the plan target is always a separate action."
      />

      <div className="mt-6 space-y-6">
        {isPending && (
          <Panel title="Reading races">
            <LoadingState label="Loading registered races" />
          </Panel>
        )}

        {isError && (
          <FailedState
            title="Races could not be read"
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
              title="Registration and targeting are separate"
              description={data.note}
            />

            <Panel
              title="Future races"
              note="Eligible for cancellation and for selection as the plan target."
            >
              {planned.length === 0 ? (
                <EmptyState
                  title="No future races registered"
                  description="Add a race below, or keep training on a general plan. A general plan never silently targets a stored race."
                />
              ) : (
                <ul className="space-y-3">
                  {planned.map((race) => (
                    <RaceRow key={race.id} race={race} activeTargetId={data.activeTargetId} />
                  ))}
                </ul>
              )}
            </Panel>

            <AddRaceForm />

            <Panel
              title="Cancelled and completed"
              note="Immutable history. Kept rather than deleted."
              className="opacity-90"
            >
              {other.length === 0 ? (
                <EmptyState
                  title="No history yet"
                  description="Cancelled and completed races appear here."
                />
              ) : (
                <ul className="space-y-3">
                  {other.map((race) => (
                    <RaceRow key={race.id} race={race} activeTargetId={data.activeTargetId} />
                  ))}
                </ul>
              )}
            </Panel>
          </>
        )}
      </div>
    </AppShell>
  );
}
