import { Link } from "@tanstack/react-router";

import type { PlanSession, SessionBlock } from "@/lib/pace/types";
import { EvidenceList } from "./primitives";
import { StatusBadge } from "./states";

const BLOCK_LABEL: Record<SessionBlock["kind"], string> = {
  warmup: "Warm-up",
  steady: "Steady block",
  intervals: "Work",
  recovery: "Recovery",
  cooldown: "Cooldown",
};

const OUTCOME_LABEL = {
  completed: "Completed",
  limited: "Completed with limitations",
  skipped: "Skipped",
} as const;

function SportTag({ sport }: { sport: PlanSession["sport"] }) {
  const isRun = sport === "running";
  return (
    <span
      className={
        "inline-flex items-center border px-1.5 py-0.5 font-mono text-[0.68rem] uppercase tracking-[0.08em] " +
        (isRun ? "border-run text-run" : "border-ride text-ride")
      }
    >
      {isRun ? "Running" : "Cycling"}
    </span>
  );
}

function SectionLabel({ children }: { children: string }) {
  return <p className="label-micro-strong">{children}</p>;
}

export function PlanSessionCard({ session }: { session: PlanSession }) {
  const feedback = session.feedback;
  const single = session.blocks.length === 1;

  return (
    <article className="border border-rule-strong bg-surface">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-rule px-4 py-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs tracking-wide">{session.date}</span>
            <SportTag sport={session.sport} />
            {single && (
              <span className="font-mono text-[0.68rem] uppercase tracking-[0.08em] text-muted-foreground">
                Single block
              </span>
            )}
          </div>
          <h3 className="mt-1.5 break-words text-lg font-bold leading-snug">{session.title}</h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {feedback ? (
            <StatusBadge
              kind={feedback.outcome === "completed" ? "completed" : "partial"}
              label={
                feedback.outcome === "completed" ? "Completed" : OUTCOME_LABEL[feedback.outcome]
              }
            />
          ) : (
            <StatusBadge kind="empty" label="No outcome yet" />
          )}
          <Link
            to="/sessions/$sessionId"
            params={{ sessionId: session.id }}
            className="border border-rule px-2 py-1 font-mono text-[0.68rem] uppercase tracking-[0.08em] hover:border-rule-strong"
          >
            {feedback ? "Open session" : "Open and report"}
          </Link>
        </div>
      </header>

      <div className="grid gap-3 border-b border-rule px-4 py-3 sm:grid-cols-3">
        <div>
          <p className="label-micro">Scope</p>
          <p className="mt-1 text-sm font-medium">{session.scope}</p>
        </div>
        <div>
          <p className="label-micro">Main target</p>
          <p className="mt-1 text-sm font-medium">{session.mainTarget}</p>
        </div>
        <div>
          <p className="label-micro">Purpose</p>
          <p className="mt-1 text-sm font-medium">{session.purpose}</p>
        </div>
      </div>

      {/* 1. Prescribed session */}
      <div className="border-b border-rule px-4 py-3">
        <SectionLabel>Prescribed session</SectionLabel>
        <ol className="mt-2 grid gap-2 md:grid-cols-2">
          {session.blocks.map((block) => (
            <li
              key={block.id}
              className={
                "border px-3 py-3 " +
                (block.kind === "intervals"
                  ? "border-warning/70 bg-warning-soft/50"
                  : "border-rule bg-background")
              }
            >
              <p className="label-micro">{BLOCK_LABEL[block.kind]}</p>
              <p className="mt-1 break-words text-base font-bold">{block.amount}</p>
              <p className="mt-0.5 text-sm font-semibold text-forest">{block.target}</p>
              {block.recovery && (
                <p className="mt-2 border-t border-rule pt-2 text-sm">
                  <span className="label-micro">Recovery between repetitions </span>
                  {block.recovery.amount} - {block.recovery.target}
                </p>
              )}
              {block.note && (
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{block.note}</p>
              )}
            </li>
          ))}
        </ol>
      </div>

      {/* 2. Observed Garmin comparison */}
      <div className="border-b border-rule px-4 py-3">
        <SectionLabel>Observed by Garmin</SectionLabel>
        {session.observed ? (
          <>
            <dl className="mt-2 grid gap-x-6 sm:grid-cols-2">
              {session.observed.rows.map((row) => (
                <div
                  key={row.label}
                  className="flex justify-between gap-3 border-b border-rule py-1.5"
                >
                  <dt className="text-sm text-muted-foreground">{row.label}</dt>
                  <dd
                    className={
                      row.value === null
                        ? "font-mono text-xs uppercase tracking-wide text-unknown"
                        : "text-sm font-semibold tabular-nums"
                    }
                  >
                    {row.value ?? "Unknown"}
                  </dd>
                </div>
              ))}
            </dl>
            <p className="mt-2 border-l-2 border-l-warning pl-3 text-xs leading-relaxed text-muted-foreground">
              {session.observed.matchNote}
            </p>
          </>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">
            No matched activity. This is unknown, not zero.
          </p>
        )}
      </div>

      {/* 3. Athlete feedback */}
      <div className="border-b border-rule px-4 py-3">
        <SectionLabel>Athlete feedback</SectionLabel>
        {feedback ? (
          <div className="mt-2 grid gap-3 sm:grid-cols-3">
            <div>
              <p className="label-micro">Outcome</p>
              <p className="mt-1 text-sm font-semibold">{OUTCOME_LABEL[feedback.outcome]}</p>
            </div>
            <div>
              <p className="label-micro">Reported RPE</p>
              <p className="mt-1 text-sm font-semibold tabular-nums">
                {feedback.rpe === null ? (
                  <span className="font-mono text-xs uppercase text-unknown">Unknown</span>
                ) : (
                  `${feedback.rpe}/10`
                )}
              </p>
            </div>
            <div>
              <p className="label-micro">Note</p>
              <p className="mt-1 text-sm">{feedback.reason ?? feedback.note ?? "-"}</p>
              {feedback.privateNote && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Private note stored locally.{" "}
                  {feedback.shareWithAi ? "Shared with the coach." : "Withheld from the coach."}
                </p>
              )}
            </div>
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">
            Not reported. Your explicit feedback is the durable outcome, so this stays unknown until
            you record it.
          </p>
        )}
      </div>

      {/* 4. Coach reasoning, kept separate from facts */}
      <div className="space-y-3 px-4 py-3">
        <div className="border-l-2 border-l-forest pl-3">
          <p className="label-micro-strong">Why this day</p>
          <p className="mt-1 text-sm leading-relaxed">{session.rationale}</p>
        </div>
        {session.assessment && <EvidenceList kind="assessment" items={session.assessment} />}
        {session.uncertainty && <EvidenceList kind="uncertainty" items={session.uncertainty} />}
      </div>
    </article>
  );
}
