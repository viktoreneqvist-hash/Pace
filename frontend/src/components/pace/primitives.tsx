import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function PageHeader({
  eyebrow,
  title,
  lede,
}: {
  eyebrow: string;
  title: string;
  lede: string;
}) {
  return (
    <div className="border-b-2 border-rule-strong pb-4">
      <p className="label-micro text-forest">{eyebrow}</p>
      <div className="mt-2 flex flex-col gap-2 md:flex-row md:items-end md:justify-between md:gap-10">
        <h1 className="text-4xl font-extrabold tracking-tight md:text-5xl">{title}</h1>
        <p className="max-w-md text-sm text-muted-foreground">{lede}</p>
      </div>
    </div>
  );
}

export function Panel({
  title,
  note,
  aside,
  children,
  className,
}: {
  title?: string;
  note?: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("border border-rule bg-surface", className)}>
      {(title || aside) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-rule px-4 py-3">
          <div>
            {title && <h2 className="text-base font-bold">{title}</h2>}
            {note && <p className="mt-1 text-xs text-muted-foreground">{note}</p>}
          </div>
          {aside}
        </header>
      )}
      <div className="px-4 py-4">{children}</div>
    </section>
  );
}

export function StatTile({
  label,
  value,
  detail,
  unit,
}: {
  label: string;
  value: string | null;
  detail?: string | undefined;
  unit?: string | undefined;
}) {
  const unknown = value === null;
  return (
    <div className="border border-rule bg-surface px-3 py-3">
      <p className="label-micro">{label}</p>
      <p
        className={cn(
          "mt-1.5 text-lg font-bold tabular-nums",
          unknown && "text-unknown font-mono text-sm font-medium uppercase tracking-wide",
        )}
      >
        {unknown ? "Unknown" : value}
        {!unknown && unit ? (
          <span className="ml-1 text-xs font-medium text-muted-foreground">{unit}</span>
        ) : null}
      </p>
      {detail && <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{detail}</p>}
    </div>
  );
}

export function Rule() {
  return <hr className="my-4 border-t border-rule" />;
}

export function EvidenceList({
  kind,
  items,
}: {
  kind: "evidence" | "assessment" | "uncertainty";
  items: string[];
}) {
  const meta = {
    evidence: { title: "Observed facts", className: "border-l-2 border-l-run" },
    assessment: { title: "Coach assessment", className: "border-l-2 border-l-forest" },
    uncertainty: { title: "Not known", className: "border-l-2 border-l-warning" },
  }[kind];

  return (
    <div className={cn("pl-3", meta.className)}>
      <p className="label-micro-strong">{meta.title}</p>
      <ul className="mt-1.5 space-y-1 text-sm leading-relaxed">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span aria-hidden className="text-muted-foreground">
              -
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
