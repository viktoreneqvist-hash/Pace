import type { PlannedSession, SessionBlock } from "@/lib/pace/types";
import { StatusBadge } from "./states";

const BLOCK_LABEL: Record<SessionBlock["kind"], string> = {
  warmup: "Warm-up",
  steady: "Steady",
  intervals: "Intervals",
  recovery: "Recovery",
  cooldown: "Cooldown",
};

function SportTag({ sport }: { sport: PlannedSession["sport"] }) {
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

export function SessionCard({ session }: { session: PlannedSession }) {
  const feedback = session.feedback;

  return (
    <article className="border border-rule-strong bg-surface">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-rule px-4 py-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs tracking-wide">{session.date}</span>
            <SportTag sport={session.sport} />
          </div>
          <h3 className="mt-1.5 text-lg font-bold leading-snug">{session.title}</h3>
        </div>
        {feedback ? (
          <StatusBadge
            kind="completed"
            label={
              feedback.outcome === "completed"
                ? "Completed"
                : feedback.outcome === "limited"
                  ? "Limited"
                  : "Skipped"
            }
          />
        ) : (
          <StatusBadge kind="empty" label="No outcome yet" />
        )}
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
          <p className="label-micro">Reported outcome</p>
          <p className="mt-1 text-sm font-medium">
            {feedback
              ? `${feedback.outcome === "limited" ? "Completed with limitations" : feedback.outcome === "skipped" ? "Skipped" : "Completed"}${
                  feedback.rpe !== null ? ` - RPE ${feedback.rpe}/10` : ""
                }`
              : "Unknown until you report it"}
          </p>
        </div>
      </div>

      <div className="px-4 py-3">
        <p className="text-sm leading-relaxed">{session.purpose}</p>
        <p className="label-micro mt-3">
          Session blocks - each block is an actual part of the session
        </p>
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
              <p className="mt-1 text-base font-bold">{block.amount}</p>
              <p className="mt-0.5 text-sm font-semibold text-forest">{block.target}</p>
              {block.recovery && (
                <p className="mt-2 border-t border-rule pt-2 text-sm">
                  <span className="label-micro">Recovery </span>
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
    </article>
  );
}
