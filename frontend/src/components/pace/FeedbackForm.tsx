/**
 * Explicit session feedback. Nothing is stored before the simulated local write
 * returns, duplicate submissions are blocked, and the private note is withheld
 * from the coaching model unless the athlete allows it.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Panel } from "@/components/pace/primitives";
import { Busy, FailedState, NoticeState, StatusBadge } from "@/components/pace/states";
import { getPaceClient } from "@/lib/pace/client";
import { paceKeys } from "@/lib/pace/queries";
import type { FeedbackDraft, SessionFeedback, SessionOutcome } from "@/lib/pace/types";

const BUTTON =
  "border border-rule-strong px-3 py-2 font-mono text-[0.72rem] uppercase tracking-[0.08em] disabled:cursor-not-allowed disabled:opacity-50";
const FIELD = "mt-1 w-full border border-rule bg-surface px-2 py-1.5 text-sm";

const OUTCOMES: { value: SessionOutcome; label: string; detail: string }[] = [
  { value: "completed", label: "Completed", detail: "Done as prescribed." },
  {
    value: "limited",
    label: "Completed with limitations",
    detail: "Done, but shortened or altered. A reason is required.",
  },
  { value: "skipped", label: "Skipped", detail: "Not done at all. A reason is required." },
];

export function FeedbackForm({
  sessionId,
  existing,
  note,
}: {
  sessionId: string;
  existing?: SessionFeedback | undefined;
  note: string;
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<FeedbackDraft>({
    outcome: existing?.outcome ?? "completed",
    rpe: existing?.rpe ?? null,
    reason: existing?.reason ?? "",
    privateNote: existing?.privateNote ?? "",
    shareWithAi: existing?.shareWithAi ?? false,
  });
  const [confirming, setConfirming] = useState(false);

  const save = useMutation({
    mutationFn: (value: FeedbackDraft) => getPaceClient().saveSessionFeedback(sessionId, value),
    onSuccess: (result) => {
      setConfirming(false);
      if (result.status === "saved") {
        void queryClient.invalidateQueries({ queryKey: paceKeys.session(sessionId) });
        void queryClient.invalidateQueries({ queryKey: paceKeys.plan });
        void queryClient.invalidateQueries({ queryKey: paceKeys.today });
      }
    },
  });

  const reasonRequired = draft.outcome !== "completed";
  const saved = save.data?.status === "saved";

  return (
    <Panel
      title={existing ? "Update session feedback" : "Report session feedback"}
      note="Your explicit report is the durable outcome of a session. A matched Garmin activity never replaces it."
      aside={
        existing ? (
          <StatusBadge kind="completed" label="Outcome reported" />
        ) : (
          <StatusBadge kind="pending" label="Not reported" />
        )
      }
    >
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (save.isPending) return;
          if (!confirming) {
            setConfirming(true);
            return;
          }
          save.mutate(draft);
        }}
      >
        <fieldset className="space-y-2">
          <legend className="label-micro">Outcome</legend>
          {OUTCOMES.map((option) => (
            <label
              key={option.value}
              className="flex items-start gap-3 border border-rule px-3 py-2 text-sm"
            >
              <input
                type="radio"
                name="outcome"
                className="mt-1"
                checked={draft.outcome === option.value}
                onChange={() => {
                  setDraft({ ...draft, outcome: option.value });
                  setConfirming(false);
                }}
              />
              <span>
                <span className="font-semibold">{option.label}</span>
                <span className="mt-0.5 block text-muted-foreground">{option.detail}</span>
              </span>
            </label>
          ))}
        </fieldset>

        <div className="grid gap-3 md:grid-cols-2">
          <label className="block text-sm">
            <span className="label-micro">Reported RPE (optional, 1-10)</span>
            <input
              type="number"
              min={1}
              max={10}
              className={FIELD}
              placeholder="Leave empty if unknown"
              value={draft.rpe ?? ""}
              onChange={(event) => {
                setDraft({
                  ...draft,
                  rpe: event.target.value === "" ? null : Number(event.target.value),
                });
                setConfirming(false);
              }}
            />
            <span className="mt-1 block text-xs text-muted-foreground">
              An empty field stays unknown. It is never recorded as zero.
            </span>
          </label>

          <label className="block text-sm">
            <span className="label-micro">
              Reason{reasonRequired ? " (required)" : " (optional)"}
            </span>
            <input
              className={FIELD}
              aria-describedby="reason-help"
              placeholder={
                reasonRequired
                  ? "What limited or prevented the session?"
                  : "Anything worth recording"
              }
              value={draft.reason}
              onChange={(event) => {
                setDraft({ ...draft, reason: event.target.value });
                setConfirming(false);
              }}
            />
            <span id="reason-help" className="mt-1 block text-xs text-muted-foreground">
              {reasonRequired
                ? "Local validation rejects a limited or skipped session without a reason."
                : "Optional for a completed session."}
            </span>
          </label>
        </div>

        <label className="block text-sm">
          <span className="label-micro">Private note</span>
          <textarea
            className={`${FIELD} min-h-20`}
            placeholder="Stored locally. Only sent to the coach if you allow it below."
            value={draft.privateNote}
            onChange={(event) => {
              setDraft({ ...draft, privateNote: event.target.value });
              setConfirming(false);
            }}
          />
        </label>

        <label className="flex items-start gap-3 border border-rule px-3 py-2 text-sm">
          <input
            type="checkbox"
            className="mt-1"
            checked={draft.shareWithAi}
            onChange={(event) => {
              setDraft({ ...draft, shareWithAi: event.target.checked });
              setConfirming(false);
            }}
          />
          <span>
            <span className="font-semibold">Share the private note with the coach</span>
            <span className="mt-0.5 block text-muted-foreground">
              Off by default. The outcome, RPE and reason are always available to the coach; the
              private note is not.
            </span>
          </span>
        </label>

        <p className="text-xs text-muted-foreground">{note}</p>

        <div className="flex flex-wrap items-center gap-3 border-t border-rule pt-3">
          {confirming && !save.isPending && (
            <p className="text-sm">
              Save this outcome locally as{" "}
              <strong>{OUTCOMES.find((o) => o.value === draft.outcome)?.label}</strong>?
            </p>
          )}
          <button type="submit" className={BUTTON} disabled={save.isPending}>
            {save.isPending
              ? "Saving"
              : confirming
                ? "Confirm and save"
                : existing
                  ? "Review update"
                  : "Review feedback"}
          </button>
          {confirming && !save.isPending && (
            <button type="button" className={BUTTON} onClick={() => setConfirming(false)}>
              Keep editing
            </button>
          )}
          {save.isPending && <Busy label="Validating and writing locally" />}
        </div>

        {save.data &&
          !save.isPending &&
          (saved ? (
            <NoticeState
              kind="completed"
              title={save.data.message}
              description={save.data.detail}
            />
          ) : (
            <FailedState
              title="Nothing was saved"
              description={`${save.data.message} ${save.data.detail}`}
            />
          ))}
      </form>
    </Panel>
  );
}
