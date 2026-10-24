import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { IS_PROTOTYPE_DATA } from "@/lib/pace/client";

const NAV = [
  { to: "/", label: "Coach" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/plan", label: "Plan" },
  { to: "/weekly-review", label: "Weekly Review" },
  { to: "/races", label: "Races" },
  { to: "/settings", label: "Settings" },
  { to: "/onboarding", label: "Onboarding" },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-surface focus:px-3 focus:py-2 focus:text-sm focus:font-medium"
      >
        Skip to content
      </a>

      <header className="border-b border-rule-strong bg-surface">
        <div className="mx-auto flex w-full max-w-[1180px] flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:justify-between md:gap-6 md:px-6">
          <div className="flex items-baseline gap-3">
            <Link to="/" className="text-xl font-extrabold tracking-tight">
              PACE
            </Link>
            <span className="label-micro hidden sm:inline">Local coaching system</span>
          </div>

          <nav aria-label="Main" className="-mx-1 overflow-x-auto">
            <ul className="flex items-center gap-1 whitespace-nowrap">
              {NAV.map((item) => (
                <li key={item.to}>
                  <Link
                    to={item.to}
                    activeOptions={{ exact: item.to === "/" }}
                    className="block border border-transparent px-2.5 py-1.5 font-mono text-[0.72rem] uppercase tracking-[0.08em] text-muted-foreground transition-colors hover:border-rule hover:text-foreground"
                    activeProps={{
                      className:
                        "block border border-rule-strong bg-accent px-2.5 py-1.5 font-mono text-[0.72rem] uppercase tracking-[0.08em] text-accent-foreground",
                    }}
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div className="flex items-center gap-3 font-mono text-[0.7rem] uppercase tracking-[0.08em] text-muted-foreground">
            <span>{new Intl.DateTimeFormat("en-CA").format(new Date())}</span>
            <span className="border border-rule px-1.5 py-0.5 text-foreground">Local only</span>
          </div>
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-[1180px] px-4 py-8 md:px-6 md:py-10">
        {children}
      </main>

      <footer className="border-t border-rule">
        <div className="mx-auto w-full max-w-[1180px] px-4 py-5 md:px-6">
          <p className="label-micro">
            {IS_PROTOTYPE_DATA
              ? "Synthetic prototype. Refreshing resets the demo."
              : "Local-first Pace. Garmin and OpenAI are contacted only through explicit local actions."}
          </p>
        </div>
      </footer>
    </div>
  );
}
