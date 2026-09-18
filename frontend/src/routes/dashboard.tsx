import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import { AppShell } from "@/components/pace/AppShell";
import { PaceChart } from "@/components/pace/PaceChart";
import { EvidenceList, PageHeader, Panel, StatTile } from "@/components/pace/primitives";
import { FailedState, LoadingState, NoticeState } from "@/components/pace/states";
import { dashboardQuery } from "@/lib/pace/queries";
import type { DashboardWindow, Fact } from "@/lib/pace/types";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Dashboard - Pace local coaching system" },
      {
        name: "description",
        content:
          "Local training and recovery facts: running and cycling separately, HRV, resting heart rate, sleep, reported effort and data coverage over 28 or 84 days.",
      },
      { property: "og:title", content: "Dashboard - Pace local coaching system" },
      {
        property: "og:description",
        content:
          "Training and recovery facts over 28 and 84 days, every chart with keyboard values and a raw table.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: DashboardPage,
});

function TileGrid({ tiles }: { tiles: Fact[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {tiles.map((fact) => (
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

function DashboardPage() {
  const [window, setWindow] = useState<DashboardWindow>(28);
  const { data, isPending, isError, refetch } = useQuery(dashboardQuery(window));

  return (
    <AppShell>
      <PageHeader
        eyebrow="Current fact view"
        title="Dashboard"
        lede="Observed training and recovery facts. No AI runs on this page and no single combined score is shown."
      />

      <div className="mt-6 flex flex-wrap items-center gap-2">
        <span className="label-micro">Window</span>
        <div className="flex" role="group" aria-label="Fact window">
          {([28, 84] as DashboardWindow[]).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={window === option}
              onClick={() => setWindow(option)}
              className={`border px-3 py-1.5 font-mono text-[0.72rem] uppercase tracking-[0.08em] ${
                window === option
                  ? "border-rule-strong bg-accent text-accent-foreground"
                  : "border-rule text-muted-foreground hover:text-foreground"
              }`}
            >
              {option} days
            </button>
          ))}
        </div>
      </div>

      <div className="mt-6 space-y-6">
        {isPending && (
          <Panel title="Reading local facts">
            <LoadingState label="Loading the fact window" />
          </Panel>
        )}

        {isError && (
          <FailedState
            title="The local fact window could not be read"
            description="Nothing was changed. Try reading it again."
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
          <>
            {data.dataQuality.freshness === "partial" && (
              <NoticeState
                kind="partial"
                title="This window has gaps"
                description={data.dataQuality.coverageNote}
              />
            )}

            <Panel title="Running" note="Running only. Cycling is never merged into these numbers.">
              <TileGrid tiles={data.runTiles} />
            </Panel>

            <Panel
              title="Cycling"
              note="Cycling only, reported as time because distance depends on terrain."
            >
              <TileGrid tiles={data.rideTiles} />
            </Panel>

            <Panel
              title="Recovery and reported effort"
              note="Sleep, HRV and resting heart rate are Garmin-owned measurements. Reported RPE is yours."
            >
              <TileGrid tiles={data.recoveryTiles} />
            </Panel>

            <div className="grid gap-4 xl:grid-cols-2">
              {data.charts.map((panel) => (
                <PaceChart key={panel.id} panel={panel} />
              ))}
            </div>

            <Panel
              title="Coverage and last sync"
              note="Every number above is shown with the coverage behind it."
            >
              <TileGrid tiles={data.coverage} />
              <div className="mt-4 space-y-4">
                <EvidenceList kind="assessment" items={data.assessment} />
                <EvidenceList kind="uncertainty" items={data.uncertainty} />
                {data.dataQuality.warnings.length > 0 && (
                  <EvidenceList kind="evidence" items={data.dataQuality.warnings} />
                )}
              </div>
            </Panel>
          </>
        )}
      </div>
    </AppShell>
  );
}
