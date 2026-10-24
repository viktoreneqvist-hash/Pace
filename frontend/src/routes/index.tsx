import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";

import { AppShell } from "@/components/pace/AppShell";
import { CoachConversation } from "@/components/pace/CoachConversation";
import { PageHeader, Panel, StatTile } from "@/components/pace/primitives";
import { SessionCard } from "@/components/pace/SessionCard";
import { SyncCard } from "@/components/pace/SyncCard";
import { EmptyState, LoadingState, NoticeState, StatusBadge } from "@/components/pace/states";
import { todayQuery } from "@/lib/pace/queries";
import type { DataFreshness } from "@/lib/pace/types";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Today - Pace local coaching system" },
      {
        name: "description",
        content:
          "Today's planned running or cycling session, current recovery facts, sync state and a bounded coach conversation. Local-first and synthetic in this prototype.",
      },
      { property: "og:title", content: "Today - Pace local coaching system" },
      {
        property: "og:description",
        content:
          "Today's session, the facts behind it, and a coach conversation where nothing is written without explicit confirmation.",
      },
    ],
  }),
  component: TodayPage,
});

const FRESHNESS: Record<DataFreshness, "current" | "stale" | "partial" | "unknown"> = {
  current: "current",
  stale: "stale",
  partial: "partial",
  unknown: "unknown",
};

function TodayPage() {
  const { data: today, isPending } = useQuery(todayQuery());

  return (
    <AppShell>
      <PageHeader
        eyebrow="Today / Coach"
        title="Today"
        lede="What the session is, why it is appropriate, whether the data is current, and whether anything needs your action."
      />

      {isPending || !today ? (
        <div className="mt-8">
          <Panel title="Today">
            <LoadingState label="Reading today's session and facts" />
          </Panel>
        </div>
      ) : (
        <div className="mt-8 space-y-6">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="Goal"
              value={today.goal.label}
              detail={
                today.goal.raceDate
                  ? `${today.goal.raceDate} - priority ${today.goal.priority} - ${today.goal.daysToRace} days away`
                  : "General plan, no race target"
              }
            />
            <StatTile
              label="Today"
              value={today.today}
              detail={
                today.session
                  ? `${today.session.sport === "running" ? "Running" : "Cycling"} - ${today.session.scope}`
                  : "No session planned"
              }
            />
            <StatTile
              label="Data freshness"
              value={
                today.dataQuality.freshness === "current" ? "Current" : today.dataQuality.freshness
              }
              detail={today.dataQuality.coverageNote}
            />
            <StatTile
              label="Detailed window"
              value={today.revisionDue ? "Revision due" : "Up to date"}
              detail={
                today.revisionDue
                  ? "The next 14 detailed days can be generated now."
                  : "The next 14 detailed days are not due yet."
              }
            />
          </div>

          {today.actionNeeded.length > 0 && (
            <NoticeState
              kind="pending"
              title="Action needed"
              description={today.actionNeeded.join(" ")}
            />
          )}

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
            <div className="space-y-6">
              <Panel
                title="Today's session"
                note="Reported feedback is the durable outcome. Garmin matching cannot prove interval compliance."
                aside={<StatusBadge kind={FRESHNESS[today.dataQuality.freshness]} />}
              >
                {today.session ? (
                  <SessionCard session={today.session} />
                ) : (
                  <EmptyState
                    title="No session planned for today"
                    description="Rest is part of the plan. Open Plan to see the rest of the detailed window."
                    action={
                      <Link
                        to="/plan"
                        className="border border-rule-strong px-3 py-1.5 font-mono text-[0.72rem] uppercase tracking-[0.08em]"
                      >
                        Open plan
                      </Link>
                    }
                  />
                )}
                <p className="mt-4 border-l-2 border-l-forest pl-3 text-sm leading-relaxed">
                  <span className="label-micro-strong block">Why this session today</span>
                  {today.rationale}
                </p>
              </Panel>

              <CoachConversation />
            </div>

            <div className="space-y-6">
              <Panel
                title="Current facts"
                note="Observed locally. Missing data is shown as unknown, never as zero."
              >
                <div className="grid gap-3 sm:grid-cols-2">
                  {today.facts.map((fact) => (
                    <StatTile
                      key={fact.id}
                      label={fact.label}
                      value={fact.value}
                      {...(fact.unit ? { unit: fact.unit } : {})}
                      {...(fact.detail
                        ? {
                            detail: fact.coverage
                              ? `${fact.detail} Coverage: ${fact.coverage}.`
                              : fact.detail,
                          }
                        : {})}
                    />
                  ))}
                </div>
              </Panel>

              <SyncCard />

              <Panel title="Data quality warnings">
                <ul className="space-y-2 text-sm leading-relaxed">
                  {today.dataQuality.warnings.map((warning) => (
                    <li key={warning} className="border-l-2 border-l-warning pl-3">
                      {warning}
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-xs text-muted-foreground">
                  Pace is a training tool, not medical software, and does not diagnose anything.
                </p>
              </Panel>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
