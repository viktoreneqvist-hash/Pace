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
import { paceKeys, planHistoryQuery, planQuery } from "@/lib/pace/queries";
import type { RevisionResult } from "@/lib/pace/types";

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

            <Panel title="Facts behind this plan">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {plan.data.facts.map((fact) => (
                  <StatTile
                    key={fact.id}
                    label={fact.label}
                    value={fact.value}
                    unit={fact.unit}
                    detail={fact.detail}
                  />
                ))}
              </div>
              <div className="mt-4 space-y-3">
                <EvidenceList kind="assessment" items={plan.data.assessment} />
                <EvidenceList kind="uncertainty" items={plan.data.uncertainty} />
              </div>
            </Panel>

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
