import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import { AppShell } from "@/components/pace/AppShell";
import { BlockTimeline } from "@/components/pace/BlockTimeline";
import { PlanSessionCard } from "@/components/pace/PlanSessionCard";
import { EvidenceList, PageHeader, Panel, StatTile } from "@/components/pace/primitives";
import {
  Busy,
  FailedState,
  LoadingState,
  NoticeState,
  StatusBadge,
} from "@/components/pace/states";
import { getPaceClient, IS_PROTOTYPE_DATA } from "@/lib/pace/client";
import {
  paceKeys,
  garminWorkoutExportsQuery,
  pendingVolumeExceptionQuery,
  planHistoryQuery,
  planQuery,
} from "@/lib/pace/queries";
import type { PlanView, RevisionResult } from "@/lib/pace/types";

export const Route = createFileRoute("/plan")({
  head: () => ({
    meta: [
      { title: "Plan - Pace local coaching system" },
      {
        name: "description",
        content:
          "The active plan: block timeline toward the goal race, the next 14 detailed days and structured session blocks.",
      },
      { property: "og:title", content: "Plan - Pace local coaching system" },
      {
        property: "og:description",
        content:
          "Active goal, race markers, detailed window and reported outcomes. Pace never changes the plan automatically.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: PlanPage,
});

const BTN =
  "border border-rule-strong px-3 py-1.5 font-mono text-xs uppercase tracking-[0.08em] disabled:opacity-40";
const BTN_PRIMARY = BTN + " bg-foreground text-background";

function PlanPage() {
  const queryClient = useQueryClient();
  const [revision, setRevision] = useState<RevisionResult | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);

  const plan = useQuery(planQuery());
  const history = useQuery(planHistoryQuery());
  const pendingException = useQuery(pendingVolumeExceptionQuery());

  const approveException = useMutation({
    mutationFn: (planId: string) => getPaceClient().approveVolumeException(planId),
    onSuccess: (result) => {
      if (result.status === "saved") {
        queryClient.invalidateQueries({ queryKey: paceKeys.plan });
        queryClient.invalidateQueries({ queryKey: paceKeys.planHistory });
        queryClient.invalidateQueries({ queryKey: paceKeys.pendingVolumeException });
      }
    },
  });

  const toggleDemo = useMutation({
    mutationFn: (due: boolean) => getPaceClient().setRevisionDueDemo(due),
    onSuccess: (next) => {
      setRevision(null);
      queryClient.setQueryData(paceKeys.plan, next);
    },
  });

  const generate = useMutation({
    mutationFn: () => getPaceClient().generateNextWindow(),
    onSuccess: (result) => {
      setRevision(result);
      if (result.status === "saved" && result.plan) {
        queryClient.setQueryData(paceKeys.plan, result.plan);
        queryClient.invalidateQueries({ queryKey: paceKeys.planHistory });
      }
      if (result.status === "pending_approval") {
        queryClient.invalidateQueries({ queryKey: paceKeys.pendingVolumeException });
        queryClient.invalidateQueries({ queryKey: paceKeys.planHistory });
      }
    },
  });

  return (
    <AppShell>
      <PageHeader
        eyebrow="Active plan"
        title="Plan"
        lede="One active plan toward the goal race. Only the next 14 days are detailed; later weeks stay an outline."
      />

      <div className="mt-8 space-y-6">
        {pendingException.data && (
          <Panel
            title="Race-volume exception requires approval"
            note={`Proposed plan ${pendingException.data.planId} for ${pendingException.data.raceName} is not active. Your current accepted plan remains unchanged.`}
            aside={<StatusBadge kind="pending" label="Not approved" />}
          >
            <p className="text-sm">{pendingException.data.rationale}</p>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[560px] border-collapse text-sm">
                <thead>
                  <tr>
                    <th className="border-b border-rule px-2 py-2 text-left">Calendar week</th>
                    <th className="border-b border-rule px-2 py-2 text-left">Boundary</th>
                    <th className="border-b border-rule px-2 py-2 text-right">Base ceiling</th>
                    <th className="border-b border-rule px-2 py-2 text-right">Proposed</th>
                  </tr>
                </thead>
                <tbody>
                  {pendingException.data.weeks.flatMap((week) =>
                    week.breaches.map((breach) => (
                      <tr key={`${week.weekStart}-${breach.metric}`}>
                        <td className="border-b border-rule px-2 py-2">
                          {week.weekStart} to {week.weekEnd}
                        </td>
                        <td className="border-b border-rule px-2 py-2">
                          {breach.metric.replaceAll("_", " ")}
                        </td>
                        <td className="border-b border-rule px-2 py-2 text-right">
                          {breach.ceiling} {breach.unit}
                        </td>
                        <td className="border-b border-rule px-2 py-2 text-right font-semibold">
                          {breach.proposed} {breach.unit}
                        </td>
                      </tr>
                    )),
                  )}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              This approval applies only to this race-plan version. It does not raise your saved
              base ceiling.
            </p>
            <button
              type="button"
              className={`${BTN_PRIMARY} mt-4`}
              disabled={approveException.isPending || approveException.data?.status === "saved"}
              onClick={() => approveException.mutate(pendingException.data!.planId)}
            >
              {approveException.isPending ? "Approving" : "Approve race-volume exception"}
            </button>
            {approveException.data && !approveException.isPending && (
              <div className="mt-3">
                {approveException.data.status === "saved" ? (
                  <NoticeState
                    kind="completed"
                    title={approveException.data.message}
                    description={approveException.data.detail}
                  />
                ) : (
                  <FailedState
                    title={approveException.data.message}
                    description={approveException.data.detail}
                  />
                )}
              </div>
            )}
          </Panel>
        )}
        {plan.isPending && (
          <Panel title="Active plan">
            <LoadingState label="Reading the active plan" />
          </Panel>
        )}

        {plan.isError && (
          <FailedState
            title="The active plan could not be read"
            description="The local plan store did not answer. Nothing was changed."
            action={
              <button type="button" className={BTN} onClick={() => plan.refetch()}>
                Retry
              </button>
            }
          />
        )}

        {plan.data && (
          <>
            <Panel
              title="Goal and window"
              note={`Plan version ${plan.data.version}, accepted ${plan.data.acceptedAt.slice(0, 10)}. Mode: ${
                plan.data.mode === "race" ? "explicitly chosen race" : "general plan"
              }.`}
              aside={
                <StatusBadge
                  kind={plan.data.revisionDue ? "pending" : "current"}
                  label={plan.data.revisionDue ? "Revision due" : "Revision not due"}
                />
              }
            >
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <StatTile
                  label="Goal"
                  value={plan.data.goal.label}
                  detail={`Sport: running only for this goal.`}
                />
                <StatTile
                  label="Race date and priority"
                  value={`${plan.data.goal.raceDate ?? "-"} - ${plan.data.goal.priority ?? "-"}`}
                  detail={`${plan.data.goal.daysToRace ?? "?"} days out. Priority A means primary goal with a full taper.`}
                />
                <StatTile
                  label="Desired time"
                  value={plan.data.goal.targetTime}
                  detail="Athlete ambition. Not a prediction from verified data."
                />
                <StatTile label="Taper policy" value={plan.data.goal.taperPolicy} />
                <StatTile
                  label="Detailed window"
                  value={`${plan.data.detailedWindow.start} to ${plan.data.detailedWindow.end}`}
                  detail={`${plan.data.detailedWindow.sessionCount} prescribed sessions.`}
                />
                <StatTile
                  label="Next window generatable from"
                  value={plan.data.detailedWindow.generatableFrom}
                  detail={plan.data.revisionNote}
                />
              </div>
            </Panel>

            <Panel title="Block timeline" note="Today to race day, one column per week.">
              <BlockTimeline weeks={plan.data.timeline} />
            </Panel>

            <Panel
              title="Next 14 detailed days"
              note="Generation is explicit. Nothing is replaced before local validation succeeds."
              aside={
                <div className="flex flex-wrap items-center gap-2">
                  {IS_PROTOTYPE_DATA && (
                    <button
                      type="button"
                      className={BTN}
                      disabled={toggleDemo.isPending}
                      onClick={() => toggleDemo.mutate(!plan.data.revisionDue)}
                    >
                      {plan.data.revisionDue ? "Show not-due state" : "Show revision-due state"}
                    </button>
                  )}
                  <button
                    type="button"
                    className={BTN_PRIMARY}
                    disabled={!plan.data.revisionDue || generate.isPending}
                    onClick={() => generate.mutate()}
                  >
                    {generate.isPending ? "Generating" : "Generate next 14 days"}
                  </button>
                </div>
              }
            >
              <div className="space-y-3">
                {!plan.data.revisionDue && (
                  <NoticeState
                    kind="pending"
                    badgeLabel="Not due"
                    title="Revision is not due"
                    description={`${plan.data.revisionNote} Generation stays disabled until then. A first plan can be created at any time after you select a target; this restriction applies only to extending an existing plan.`}
                  />
                )}

                {generate.isPending && (
                  <div className="border border-rule bg-background px-4 py-3">
                    <Busy label="Building the proposed window and running local validation" />
                    <p className="mt-1.5 text-sm text-muted-foreground">
                      The active plan is untouched while this runs.
                    </p>
                  </div>
                )}

                {revision?.status === "failed" && !generate.isPending && (
                  <FailedState
                    title={revision.message}
                    description={revision.detail}
                    action={
                      plan.data.revisionDue ? (
                        <button type="button" className={BTN} onClick={() => generate.mutate()}>
                          Retry generation
                        </button>
                      ) : undefined
                    }
                  />
                )}

                {revision?.status === "pending_approval" && !generate.isPending && (
                  <NoticeState
                    kind="pending"
                    title={revision.message}
                    description={revision.detail}
                  />
                )}

                {revision?.status === "saved" && !generate.isPending && (
                  <NoticeState
                    kind="completed"
                    title={revision.message}
                    description={revision.detail}
                  />
                )}

                <p className="text-xs text-muted-foreground">
                  Sections below separate the prescribed session, what Garmin observed, your own
                  feedback and the coach assessment. A matched Garmin activity does not prove
                  interval compliance.
                </p>
              </div>
            </Panel>

            <div className="space-y-4">
              {plan.data.sessions.map((session) => (
                <PlanSessionCard key={session.id} session={session} />
              ))}
            </div>

            <GarminExportPanel plan={plan.data} />

            <section className="border border-rule bg-surface px-4 py-4">
              <div className="grid gap-4 lg:grid-cols-2">
                <EvidenceList kind="assessment" items={plan.data.assessment} />
                <EvidenceList kind="uncertainty" items={plan.data.uncertainty} />
              </div>
            </section>

            <section className="border border-rule bg-surface-sunken/40">
              <button
                type="button"
                className="flex w-full flex-wrap items-center justify-between gap-2 px-4 py-3 text-left"
                aria-expanded={historyOpen}
                onClick={() => setHistoryOpen((open) => !open)}
              >
                <span>
                  <span className="label-micro-strong">Plan history</span>
                  <span className="mt-1 block text-xs text-muted-foreground">
                    Accepted plans are immutable. They are kept for reference, not for editing.
                  </span>
                </span>
                <span className="font-mono text-xs uppercase tracking-[0.08em]">
                  {historyOpen ? "Hide" : "Show"}
                </span>
              </button>
              {historyOpen && (
                <div className="border-t border-rule px-4 py-3">
                  {history.isPending && <LoadingState label="Reading plan history" />}
                  {history.data && (
                    <ol className="space-y-2">
                      {history.data.map((entry) => (
                        <li
                          key={entry.id}
                          className="flex flex-wrap items-baseline justify-between gap-2 border-b border-rule pb-2 text-sm"
                        >
                          <span className="font-mono text-xs">
                            v{entry.version} - {entry.acceptedAt} - {entry.windowLabel}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {entry.sessionCount} sessions - {entry.note}
                          </span>
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </AppShell>
  );
}

function GarminExportPanel({ plan }: { plan: PlanView }) {
  const queryClient = useQueryClient();
  const status = useQuery(garminWorkoutExportsQuery(plan.planId));
  const [selected, setSelected] = useState<string[]>([]);
  const [pushToDevice, setPushToDevice] = useState(false);

  const exportMutation = useMutation({
    mutationFn: () => getPaceClient().exportGarminWorkouts(plan.planId, selected, pushToDevice),
    onSuccess: (value) => {
      queryClient.setQueryData(paceKeys.garminWorkoutExports(plan.planId), value);
      setSelected([]);
    },
  });

  const statusBySession = new Map(
    (status.data?.sessions ?? []).map((item) => [item.sessionId, item]),
  );
  const available = plan.sessions.filter(
    (session) =>
      !statusBySession.has(session.id) ||
      ["not_exported", "uploaded"].includes(statusBySession.get(session.id)!.status),
  );

  return (
    <Panel
      title="Garmin workouts"
      note="Nothing is sent automatically. Select sessions, review the dates, then confirm one external write. Retrying never creates duplicates."
      aside={<StatusBadge kind="current" label="Explicit export" />}
    >
      {status.isPending && <LoadingState label="Reading Garmin export status" />}
      {status.isError && (
        <FailedState
          title="Garmin export status could not be read"
          description="No workout was sent."
          action={
            <button type="button" className={BTN} onClick={() => status.refetch()}>
              Retry
            </button>
          }
        />
      )}
      {status.data && (
        <div className="space-y-3">
          {plan.sessions.map((session) => {
            const item = statusBySession.get(session.id);
            const exported = item && ["scheduled", "scheduled_and_pushed"].includes(item.status);
            const needsRetry = item?.status === "uploaded";
            return (
              <label
                key={session.id}
                className="grid cursor-pointer grid-cols-[auto_1fr_auto] items-start gap-3 border-b border-rule py-2 text-sm"
              >
                <input
                  type="checkbox"
                  className="mt-1 size-4"
                  disabled={Boolean(exported) || exportMutation.isPending}
                  checked={selected.includes(session.id)}
                  onChange={(event) =>
                    setSelected((current) =>
                      event.target.checked
                        ? [...current, session.id]
                        : current.filter((id) => id !== session.id),
                    )
                  }
                />
                <span>
                  <span className="font-semibold">
                    {session.date} · {session.title}
                  </span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    {session.scope} · {session.mainTarget}
                  </span>
                </span>
                <span className="font-mono text-xs uppercase tracking-[0.08em]">
                  {exported
                    ? item.pushedToDevice
                      ? "On device"
                      : "Scheduled"
                    : needsRetry
                      ? "Retry schedule"
                      : "Local only"}
                </span>
              </label>
            );
          })}

          {available.length > 0 && (
            <button
              type="button"
              className={BTN}
              disabled={exportMutation.isPending}
              onClick={() => setSelected(available.map((session) => session.id))}
            >
              Select all not exported
            </button>
          )}

          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-1 size-4"
              checked={pushToDevice}
              disabled={exportMutation.isPending}
              onChange={(event) => setPushToDevice(event.target.checked)}
            />
            <span>
              Also send to my last-used Garmin device
              <span className="block text-xs text-muted-foreground">
                Scheduling in the Garmin calendar works without this extra device push.
              </span>
            </span>
          </label>

          <button
            type="button"
            className={BTN_PRIMARY}
            disabled={selected.length === 0 || exportMutation.isPending}
            onClick={() => exportMutation.mutate()}
          >
            {exportMutation.isPending
              ? "Sending to Garmin"
              : `Confirm export of ${selected.length} session${selected.length === 1 ? "" : "s"}`}
          </button>
          {exportMutation.isError && (
            <FailedState
              title="Garmin export did not complete"
              description={
                exportMutation.error instanceof Error
                  ? exportMutation.error.message
                  : "No duplicate will be created when you retry."
              }
            />
          )}
          {exportMutation.isSuccess && (
            <NoticeState
              kind="completed"
              title="Garmin export completed"
              description="The confirmed sessions are now marked as scheduled."
            />
          )}
        </div>
      )}
    </Panel>
  );
}
