import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { AppShell } from "@/components/pace/AppShell";
import { EvidenceList, PageHeader, Panel, StatTile } from "@/components/pace/primitives";
import {
  Busy,
  EmptyState,
  FailedState,
  LoadingState,
  NoticeState,
  StatusBadge,
} from "@/components/pace/states";
import { getPaceClient, IS_PROTOTYPE_DATA } from "@/lib/pace/client";
import { paceKeys, weeklyReviewQuery } from "@/lib/pace/queries";
import type { Fact } from "@/lib/pace/types";

export const Route = createFileRoute("/weekly-review")({
  head: () => ({
    meta: [
      { title: "Weekly review - Pace local coaching system" },
      {
        name: "description",
        content:
          "One dated, immutable weekly snapshot separating Pace facts, Garmin-owned facts, coaching assessment, recommendations and uncertainty.",
      },
      { property: "og:title", content: "Weekly review - Pace local coaching system" },
      {
        property: "og:description",
        content: "A dated weekly snapshot that is never recalculated when the page is opened.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: WeeklyReviewPage,
});

function FactRows({ facts }: { facts: Fact[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {facts.map((fact) => (
        <StatTile
          key={fact.id}
          label={fact.label}
          value={fact.value}
          unit={fact.unit}
          detail={[fact.detail, fact.coverage ? `Coverage: ${fact.coverage}` : null]
            .filter(Boolean)
            .join(" ")}
        />
      ))}
    </div>
  );
}

function WeeklyReviewPage() {
  const queryClient = useQueryClient();
  const { data, isPending, isError, refetch } = useQuery(weeklyReviewQuery());

  const generate = useMutation({
    mutationFn: () => getPaceClient().generateWeeklyReview(),
    onSuccess: (state) => queryClient.setQueryData(paceKeys.weeklyReview, state),
  });

  const reset = useMutation({
    mutationFn: () => getPaceClient().resetWeeklyReviewDemo(),
    onSuccess: (state) => {
      generate.reset();
      queryClient.setQueryData(paceKeys.weeklyReview, state);
    },
  });

  const running = generate.isPending || data?.status === "running";
  const snapshot = data?.snapshot ?? null;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Dated snapshot"
        title="Weekly review"
        lede="One explicit snapshot per week. Opening this page reads the stored snapshot and never runs the coach again."
      />

      <div className="mt-6 space-y-6">
        {isPending && (
          <Panel title="Reading the stored snapshot">
            <LoadingState label="Loading the weekly review" />
          </Panel>
        )}

        {isError && (
          <FailedState
            title="The stored snapshot could not be read"
            description="Nothing was changed or regenerated."
            action={
              <button
                type="button"
                onClick={() => void refetch()}
                className="border border-rule-strong px-3 py-1.5 font-mono text-[0.72rem] uppercase tracking-[0.08em]"
              >
                Retry
              </button>
            }
          />
        )}

        {data && (
          <Panel
            title="Snapshot status"
            note="Generation happens only when you ask for it. Saving feedback later never rewrites a stored snapshot."
            aside={
              <StatusBadge
                kind={
                  data.status === "saved"
                    ? "completed"
                    : data.status === "failed"
                      ? "failed"
                      : running
                        ? "loading"
                        : "empty"
                }
                label={
                  data.status === "saved"
                    ? "Saved snapshot"
                    : data.status === "failed"
                      ? "Generation failed"
                      : running
                        ? "Generating"
                        : "No snapshot yet"
                }
              />
            }
          >
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                disabled={running}
                onClick={() => generate.mutate()}
                className="border border-rule-strong bg-forest px-3 py-2 font-mono text-[0.72rem] uppercase tracking-[0.08em] text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
              >
                {data.status === "failed" ? "Retry weekly review" : "Generate weekly review"}
              </button>
              {IS_PROTOTYPE_DATA && data.status === "saved" && (
                <button
                  type="button"
                  disabled={reset.isPending}
                  onClick={() => reset.mutate()}
                  className="border border-rule px-3 py-2 font-mono text-[0.72rem] uppercase tracking-[0.08em] disabled:opacity-50"
                >
                  Show the no-snapshot state
                </button>
              )}
              {running && <Busy label="Reading the week and composing one snapshot" />}
            </div>

            {running && (
              <div className="mt-4">
                <LoadingState label="Composing the snapshot. Nothing is stored until it completes" />
              </div>
            )}

            {data.status === "failed" && (
              <div className="mt-4">
                <FailedState
                  title="No snapshot was written"
                  description={data.error ?? "The generation failed and nothing was stored."}
                />
              </div>
            )}

            {data.status === "absent" && !running && (
              <div className="mt-4">
                <EmptyState
                  title="No review exists for this week yet"
                  description="A weekly review is a dated snapshot you request explicitly. Until you generate one, this page stays empty rather than showing an estimate."
                />
              </div>
            )}
          </Panel>
        )}

        {snapshot && (
          <>
            <NoticeState
              kind="completed"
              title={`${snapshot.weekLabel} - generated ${snapshot.generatedAt.slice(0, 16).replace("T", " ")}`}
              description={snapshot.immutableNote}
            />

            <Panel title="Summary">
              <div className="space-y-2 text-sm leading-relaxed">
                {snapshot.summary.map((line) => (
                  <p key={line}>{line}</p>
                ))}
              </div>
            </Panel>

            <div className="grid gap-4 xl:grid-cols-2">
              <Panel
                title="Pace facts"
                note="Calculated by Pace from imported activities and your reports."
              >
                <FactRows facts={snapshot.paceFacts} />
              </Panel>
              <Panel
                title="Garmin-owned facts"
                note="Measured and derived by Garmin. Pace stores them but does not recompute them."
              >
                <FactRows facts={snapshot.garminFacts} />
              </Panel>
            </div>

            <Panel
              title="Coaching judgment"
              note="Interpretation, kept separate from the facts above."
            >
              <div className="space-y-4">
                <EvidenceList kind="assessment" items={snapshot.assessment} />
                <div className="border-l-2 border-l-forest pl-3">
                  <p className="label-micro-strong">Recommended actions</p>
                  <ul className="mt-1.5 space-y-1 text-sm leading-relaxed">
                    {snapshot.recommendations.map((item) => (
                      <li key={item} className="flex gap-2">
                        <span aria-hidden className="text-muted-foreground">
                          -
                        </span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <EvidenceList kind="uncertainty" items={snapshot.uncertainties} />
              </div>
            </Panel>

            <Panel title="Knowledge support" note="Reviewed notes the assessment leans on.">
              <ul className="space-y-3">
                {snapshot.knowledge.map((item) => (
                  <li key={item.title} className="border border-rule px-3 py-2">
                    <p className="text-sm font-semibold">{item.title}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{item.note}</p>
                  </li>
                ))}
              </ul>
            </Panel>
          </>
        )}

        {data && data.history.length > 0 && (
          <Panel
            title="Earlier snapshots"
            note="Immutable history. Opening an entry never recalculates it."
            className="opacity-90"
          >
            <ul className="divide-y divide-rule text-sm">
              {data.history.map((entry) => (
                <li
                  key={entry.id}
                  className="flex flex-wrap items-center justify-between gap-2 py-2"
                >
                  <span className="font-medium">{entry.weekLabel}</span>
                  <span className="font-mono text-xs text-muted-foreground">
                    {entry.generatedAt.slice(0, 16).replace("T", " ")}
                  </span>
                </li>
              ))}
            </ul>
          </Panel>
        )}
      </div>
    </AppShell>
  );
}
