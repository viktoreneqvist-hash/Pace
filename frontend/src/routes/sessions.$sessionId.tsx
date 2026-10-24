import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";

import { AppShell } from "@/components/pace/AppShell";
import { FeedbackForm } from "@/components/pace/FeedbackForm";
import { PlanSessionCard } from "@/components/pace/PlanSessionCard";
import { EvidenceList, PageHeader, Panel, StatTile } from "@/components/pace/primitives";
import { EmptyState, FailedState, LoadingState, NoticeState } from "@/components/pace/states";
import { sessionQuery } from "@/lib/pace/queries";
import type { Fact } from "@/lib/pace/types";

export const Route = createFileRoute("/sessions/$sessionId")({
  head: () => ({
    meta: [
      { title: "Session detail - Pace local coaching system" },
      {
        name: "description",
        content:
          "One planned session in full: prescribed blocks, Garmin-owned observations, coach reasoning and explicit feedback with outcome, RPE, reason and a private note.",
      },
      { property: "og:title", content: "Session detail - Pace local coaching system" },
      {
        property: "og:description",
        content:
          "Prescribed session, observed activity, coach reasoning and your own reported outcome.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: SessionPage,
});

const BUTTON =
  "border border-rule-strong px-3 py-2 font-mono text-[0.72rem] uppercase tracking-[0.08em]";

function FactGrid({ facts }: { facts: Fact[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {facts.map((fact) => (
        <StatTile
          key={fact.id}
          label={fact.label}
          value={fact.value}
          unit={fact.unit}
          detail={fact.detail}
        />
      ))}
    </div>
  );
}

function SessionPage() {
  const { sessionId } = Route.useParams();
  const { data, isPending, isError, refetch } = useQuery(sessionQuery(sessionId));

  return (
    <AppShell>
      <PageHeader
        eyebrow="Session detail"
        title={data?.session.title ?? "Session"}
        lede="Prescribed session, what Garmin observed, the coach's reasoning and your own reported outcome, kept separate."
      />

      <div className="mt-6 space-y-6">
        <Link to="/plan" className={`${BUTTON} inline-block`}>
          Back to plan
        </Link>

        {isPending && (
          <Panel title="Reading the session">
            <LoadingState label="Loading the session" />
          </Panel>
        )}

        {isError && (
          <FailedState
            title="The session could not be read"
            description="Nothing was changed."
            action={
              <button type="button" className={BUTTON} onClick={() => void refetch()}>
                Retry
              </button>
            }
          />
        )}

        {!isPending && !isError && !data && (
          <Panel title="Not found">
            <EmptyState
              title="This session is not in the active detailed window"
              description="Sessions outside the current window are outlines only, and older accepted plans stay as immutable history."
              action={
                <Link to="/plan" className={BUTTON}>
                  Open the plan
                </Link>
              }
            />
          </Panel>
        )}

        {data && (
          <>
            <NoticeState
              kind="pending"
              badgeLabel="Context"
              title={data.planLabel}
              description="Reporting an outcome never changes the plan by itself."
            />

            <PlanSessionCard session={data.session} />

            <div className="grid gap-4 xl:grid-cols-2">
              <Panel title="Pace facts" note="Derived by Pace from the plan and your reports.">
                <FactGrid facts={data.paceFacts} />
              </Panel>
              <Panel title="Garmin-owned facts" note="Measured by Garmin and stored unchanged.">
                <FactGrid facts={data.garminFacts} />
                <div className="mt-4">
                  <EvidenceList kind="uncertainty" items={[data.garminNote]} />
                </div>
              </Panel>
            </div>

            <FeedbackForm
              sessionId={data.session.id}
              existing={data.session.feedback}
              note={data.feedbackNote}
            />
          </>
        )}
      </div>
    </AppShell>
  );
}
