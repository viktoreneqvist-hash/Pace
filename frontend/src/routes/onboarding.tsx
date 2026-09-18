import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";

import { AppShell } from "@/components/pace/AppShell";
import { PageHeader, Panel } from "@/components/pace/primitives";
import {
  Busy,
  FailedState,
  LoadingState,
  NoticeState,
  StatusBadge,
} from "@/components/pace/states";
import { getPaceClient } from "@/lib/pace/client";
import { onboardingQuery, paceKeys } from "@/lib/pace/queries";
import type { MutationResult, OnboardingStep, StepState } from "@/lib/pace/types";

export const Route = createFileRoute("/onboarding")({
  head: () => ({
    meta: [
      { title: "Onboarding - Pace local coaching system" },
      {
        name: "description",
        content:
          "A resumable local setup sequence: privacy check, coaching key, Garmin connection, sport role, availability, cycling zones, 80-day history and the first plan.",
      },
      { property: "og:title", content: "Onboarding - Pace local coaching system" },
      {
        property: "og:description",
        content: "Resumable setup showing complete, in-progress, blocked and optional steps.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: OnboardingPage,
});

const BUTTON =
  "border border-rule-strong px-3 py-2 font-mono text-[0.72rem] uppercase tracking-[0.08em] disabled:cursor-not-allowed disabled:opacity-50";

const STATE_BADGE: Record<
  StepState,
  { kind: Parameters<typeof StatusBadge>[0]["kind"]; label: string }
> = {
  complete: { kind: "completed", label: "Complete" },
  in_progress: { kind: "pending", label: "In progress" },
  blocked: { kind: "stale", label: "Blocked" },
  optional: { kind: "empty", label: "Optional" },
  todo: { kind: "pending", label: "Ready" },
};

function ResultNotice({ result, title }: { result: MutationResult; title: string }) {
  return result.status === "saved" ? (
    <NoticeState kind="completed" title={result.message} description={result.detail} />
  ) : (
    <FailedState title={title} description={`${result.message} ${result.detail}`} />
  );
}

function StepRow({ step, isResume }: { step: OnboardingStep; isResume: boolean }) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);

  const complete = useMutation({
    mutationFn: () => getPaceClient().completeOnboardingStep(step.id),
    onSuccess: () => {
      setConfirming(false);
      void queryClient.invalidateQueries({ queryKey: paceKeys.onboarding });
    },
  });

  const badge = STATE_BADGE[step.state];

  return (
    <li
      className={`border bg-surface px-4 py-3 ${isResume ? "border-rule-strong" : "border-rule"}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold">{step.title}</p>
          <p className="mt-0.5 max-w-prose text-sm text-muted-foreground">{step.description}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isResume && <StatusBadge kind="current" label="Resume here" />}
          <StatusBadge kind={badge.kind} label={badge.label} />
        </div>
      </div>

      <p className="mt-2 text-sm">{step.detail}</p>

      {step.state !== "complete" && step.actionLabel && (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-rule pt-3">
          {step.state === "blocked" ? (
            <p className="text-sm text-muted-foreground">
              This step unlocks when the step it depends on is complete.
            </p>
          ) : confirming ? (
            <>
              <span className="text-sm">Run this step now?</span>
              <button
                type="button"
                className={BUTTON}
                disabled={complete.isPending}
                onClick={() => complete.mutate()}
              >
                Confirm
              </button>
              <button
                type="button"
                className={BUTTON}
                disabled={complete.isPending}
                onClick={() => setConfirming(false)}
              >
                Not now
              </button>
            </>
          ) : (
            <button
              type="button"
              className={BUTTON}
              disabled={complete.isPending}
              onClick={() => setConfirming(true)}
            >
              {step.actionLabel}
            </button>
          )}
          {complete.isPending && <Busy label="Running this step locally" />}
        </div>
      )}

      {complete.data && !complete.isPending && (
        <div className="mt-3">
          <ResultNotice result={complete.data} title="This step did not complete" />
        </div>
      )}
    </li>
  );
}

function OnboardingPage() {
  const { data, isPending, isError, refetch } = useQuery(onboardingQuery());

  return (
    <AppShell>
      <PageHeader
        eyebrow="Local setup"
        title="Onboarding"
        lede="Everything runs on this machine. Leave whenever you like; completed steps stay completed for this session."
      />

      <div className="mt-6 space-y-6">
        {isPending && (
          <Panel title="Reading setup state">
            <LoadingState label="Loading onboarding progress" />
          </Panel>
        )}

        {isError && (
          <FailedState
            title="Setup state could not be read"
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
            <Panel
              title="Progress"
              note={data.note}
              aside={
                <StatusBadge
                  kind={data.requiredComplete === data.requiredTotal ? "completed" : "pending"}
                  label={`${data.requiredComplete} of ${data.requiredTotal} required steps`}
                />
              }
            >
              <div
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={data.requiredTotal}
                aria-valuenow={data.requiredComplete}
                aria-label="Required onboarding steps complete"
                className="h-2 w-full border border-rule bg-surface-sunken"
              >
                <div
                  className="h-full bg-forest"
                  style={{ width: `${(data.requiredComplete / data.requiredTotal) * 100}%` }}
                />
              </div>
              <p className="mt-3 text-sm text-muted-foreground">
                Optional steps do not block the first plan. A first plan may be created as soon as
                you choose a target and local validation passes.
              </p>
              <a
                href="/legacy/setup"
                className="mt-4 inline-block border border-rule-strong bg-foreground px-3 py-2 font-mono text-[0.72rem] uppercase tracking-[0.08em] text-background"
              >
                Open secure local setup
              </a>
            </Panel>

            <Panel
              title="Steps"
              note="Required, optional and blocked steps are shown together so nothing is hidden."
            >
              <ul className="space-y-3">
                {data.steps.map((step) => (
                  <StepRow key={step.id} step={step} isResume={step.id === data.resumeStepId} />
                ))}
              </ul>
            </Panel>

            <Panel
              title="What happens next"
              note="Onboarding never starts a sync, a plan or a coach call by itself."
            >
              <ul className="space-y-2 text-sm">
                <li>
                  Availability and zones live in{" "}
                  <Link to="/settings" className="underline">
                    Settings
                  </Link>{" "}
                  once onboarding is done.
                </li>
                <li>
                  Races are registered in{" "}
                  <Link to="/races" className="underline">
                    Races
                  </Link>
                  . Registering never selects a plan target.
                </li>
                <li>
                  The accepted plan appears in{" "}
                  <Link to="/plan" className="underline">
                    Plan
                  </Link>{" "}
                  with only the next 14 days detailed.
                </li>
              </ul>
            </Panel>
          </>
        )}
      </div>
    </AppShell>
  );
}
