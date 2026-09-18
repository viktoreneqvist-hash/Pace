/**
 * Shared status vocabulary. Every screen uses these instead of inventing its
 * own loading, empty, stale, partial, failed and completed presentation.
 */

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type StateKind =
  | "loading"
  | "empty"
  | "current"
  | "stale"
  | "partial"
  | "failed"
  | "completed"
  | "unknown"
  | "pending";

const BADGE: Record<StateKind, { label: string; className: string }> = {
  loading: { label: "Loading", className: "border-rule text-muted-foreground" },
  empty: { label: "None yet", className: "border-rule text-muted-foreground" },
  current: { label: "Current", className: "border-forest text-forest" },
  stale: { label: "Stale", className: "border-warning text-warning" },
  partial: { label: "Partial", className: "border-warning text-warning" },
  failed: { label: "Failed", className: "border-destructive text-destructive" },
  completed: { label: "Saved", className: "border-forest bg-forest-soft text-forest" },
  unknown: { label: "Unknown", className: "border-rule text-unknown" },
  pending: { label: "Needs confirmation", className: "border-rule-strong text-foreground" },
};

export function StatusBadge({
  kind,
  label,
  className,
}: {
  kind: StateKind;
  label?: string | undefined;
  className?: string | undefined;
}) {
  const meta = BADGE[kind];
  return (
    <span
      className={cn(
        "inline-flex items-center border px-2 py-0.5 font-mono text-[0.68rem] uppercase tracking-[0.08em]",
        meta.className,
        className,
      )}
    >
      {label ?? meta.label}
    </span>
  );
}

export function LoadingState({ label = "Loading local data" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-2 py-2">
      <p className="label-micro">{label}...</p>
      <div className="space-y-2" aria-hidden>
        <div className="h-3 w-2/3 animate-pulse bg-surface-sunken" />
        <div className="h-3 w-1/2 animate-pulse bg-surface-sunken" />
        <div className="h-3 w-5/6 animate-pulse bg-surface-sunken" />
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="border border-dashed border-rule px-4 py-6">
      <p className="text-sm font-semibold">{title}</p>
      <p className="mt-1 max-w-prose text-sm text-muted-foreground">{description}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function FailedState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div role="alert" className="border border-destructive/60 bg-surface px-4 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge kind="failed" />
        <p className="text-sm font-semibold">{title}</p>
      </div>
      <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">{description}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function NoticeState({
  kind,
  title,
  description,
  action,
  badgeLabel,
}: {
  kind: Extract<StateKind, "stale" | "partial" | "completed" | "pending" | "unknown">;
  title: string;
  description?: string;
  action?: ReactNode;
  badgeLabel?: string;
}) {
  return (
    <div
      className={cn(
        "border px-4 py-3",
        kind === "completed"
          ? "border-forest/50 bg-forest-soft/40"
          : "border-warning/60 bg-warning-soft/50",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge kind={kind} label={badgeLabel} />
        <p className="text-sm font-semibold">{title}</p>
      </div>
      {description && (
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">{description}</p>
      )}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

/** Small inline busy marker for buttons and cards. */
export function Busy({ label }: { label: string }) {
  return (
    <span role="status" aria-live="polite" className="label-micro">
      {label}...
    </span>
  );
}
