import type { BlockPhase, TimelineWeek } from "@/lib/pace/types";

const PHASE_LABEL: Record<BlockPhase, string> = {
  base: "Base",
  specific: "Specific",
  sharpen: "Sharpen",
  taper: "Taper",
  race: "Race",
};

export function BlockTimeline({ weeks }: { weeks: TimelineWeek[] }) {
  return (
    <div>
      <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        {weeks.map((week) => (
          <li
            key={week.id}
            className={
              "border px-3 py-2 " +
              (week.race
                ? "border-forest bg-forest-soft/60"
                : week.current
                  ? "border-rule-strong bg-background"
                  : "border-rule bg-background")
            }
          >
            <div className="flex items-center justify-between gap-2">
              <span className="label-micro-strong">{week.label}</span>
              <span className="font-mono text-[0.62rem] uppercase tracking-[0.08em] text-muted-foreground">
                {PHASE_LABEL[week.phase]}
              </span>
            </div>
            <p className="mt-1 font-mono text-xs">{week.range}</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{week.focus}</p>
            <div className="mt-2 flex flex-wrap gap-1">
              {week.current && (
                <span className="border border-rule-strong px-1.5 py-0.5 font-mono text-[0.6rem] uppercase tracking-[0.08em]">
                  This week
                </span>
              )}
              {week.detailed && (
                <span className="border border-run px-1.5 py-0.5 font-mono text-[0.6rem] uppercase tracking-[0.08em] text-run">
                  Detailed
                </span>
              )}
              {!week.detailed && !week.race && (
                <span className="border border-rule px-1.5 py-0.5 font-mono text-[0.6rem] uppercase tracking-[0.08em] text-muted-foreground">
                  Outline
                </span>
              )}
            </div>
            {week.race && (
              <p className="mt-2 border-t border-forest/40 pt-2 text-xs font-semibold text-forest">
                Race {week.race.date} - priority {week.race.priority}
                <span className="mt-0.5 block font-normal">{week.race.label}</span>
              </p>
            )}
          </li>
        ))}
      </ol>
      <p className="mt-3 text-xs text-muted-foreground">
        Timeline runs from today to race day. Only weeks marked Detailed contain prescribed
        sessions; the rest is an outline until the next window is generated.
      </p>
    </div>
  );
}
