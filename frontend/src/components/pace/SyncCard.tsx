import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { getPaceClient } from "@/lib/pace/client";
import { paceKeys, syncQuery } from "@/lib/pace/queries";
import type { SyncState } from "@/lib/pace/types";

import { Busy, FailedState, LoadingState, NoticeState, StatusBadge } from "./states";
import { Panel } from "./primitives";

function badgeKind(phase: SyncState["phase"]) {
  switch (phase) {
    case "completed":
      return "current" as const;
    case "partial":
      return "partial" as const;
    case "running":
      return "loading" as const;
    case "idle":
      return "empty" as const;
    default:
      return "failed" as const;
  }
}

export function SyncCard() {
  const queryClient = useQueryClient();
  const { data: sync, isPending } = useQuery(syncQuery());

  const running = sync?.phase === "running";

  // Poll only while a sync is actually running. No automatic sync is ever started.
  useEffect(() => {
    if (!running) return;
    let cancelled = false;
    const tick = async () => {
      const next = await getPaceClient().pollSync();
      if (!cancelled) queryClient.setQueryData(paceKeys.sync, next);
    };
    const id = setInterval(() => void tick(), 700);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [running, queryClient]);

  const start = useMutation({
    mutationFn: (window: 7 | 80) => getPaceClient().startSync(window),
    onSuccess: (next) => queryClient.setQueryData(paceKeys.sync, next),
  });

  if (isPending || !sync) {
    return (
      <Panel title="Garmin sync">
        <LoadingState label="Reading local sync state" />
      </Panel>
    );
  }

  const busy = running || start.isPending;

  return (
    <Panel
      title="Garmin sync"
      note="Sync runs only when you start it. Nothing is fetched in the background."
      aside={<StatusBadge kind={badgeKind(sync.phase)} label={sync.phase.replace("_", " ")} />}
    >
      <div className="space-y-3">
        <div>
          <p className="text-sm font-medium">{sync.message}</p>
          {sync.detail && (
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{sync.detail}</p>
          )}
        </div>

        {running && (
          <div>
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={sync.progress ?? 0}
              aria-label={`Sync progress for the last ${sync.window} days`}
              className="h-2 w-full border border-rule bg-surface-sunken"
            >
              <div
                className="h-full bg-forest transition-[width] duration-500"
                style={{ width: `${sync.progress ?? 0}%` }}
              />
            </div>
            <p className="label-micro mt-1.5">{sync.progress ?? 0}% of the window processed</p>
          </div>
        )}

        {sync.phase === "partial" && (
          <NoticeState
            kind="partial"
            title="Some days are still unknown"
            description="Days without recovery data stay unknown rather than being counted as zero."
          />
        )}

        {sync.phase === "rate_limited" && (
          <FailedState
            title="Rate limited by Garmin"
            description="No day was imported on this attempt. Retrying later is safe; nothing was written."
          />
        )}

        {sync.phase === "auth_required" && (
          <FailedState
            title="Connection needs re-authorisation"
            description="Reconnect from Settings. This prototype accepts synthetic demo values only and never asks for real credentials."
          />
        )}

        {sync.phase === "failed" && (
          <FailedState
            title="Sync failed"
            description="The local job stopped before importing anything. Your stored history is unchanged."
          />
        )}

        <dl className="grid grid-cols-2 gap-3 border-t border-rule pt-3 text-sm">
          <div>
            <dt className="label-micro">Last completed sync</dt>
            <dd className="mt-1 font-medium tabular-nums">
              {sync.lastSyncAt ? new Date(sync.lastSyncAt).toLocaleString("en-GB") : "Unknown"}
            </dd>
          </div>
          <div>
            <dt className="label-micro">Days covered</dt>
            <dd className="mt-1 font-medium tabular-nums">
              {sync.daysCovered === null ? "Unknown" : `${sync.daysCovered} days`}
            </dd>
          </div>
        </dl>

        <div className="flex flex-wrap items-center gap-2 border-t border-rule pt-3">
          <button
            type="button"
            disabled={busy}
            onClick={() => start.mutate(7)}
            className="border border-rule-strong bg-foreground px-3 py-1.5 font-mono text-[0.72rem] uppercase tracking-[0.08em] text-background transition-opacity disabled:opacity-50"
          >
            Sync 7 days
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => start.mutate(80)}
            className="border border-rule-strong px-3 py-1.5 font-mono text-[0.72rem] uppercase tracking-[0.08em] transition-colors hover:bg-surface-sunken disabled:opacity-50"
          >
            Sync 80 days
          </button>
          {busy && <Busy label="Sync running" />}
        </div>
      </div>
    </Panel>
  );
}
