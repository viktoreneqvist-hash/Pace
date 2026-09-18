import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { getPaceClient } from "@/lib/pace/client";
import { conversationQuery, paceKeys, slashCommandsQuery } from "@/lib/pace/queries";
import type { CoachAction, CoachMessage } from "@/lib/pace/types";

import { EvidenceList, Panel } from "./primitives";
import { Busy, EmptyState, FailedState, LoadingState, StatusBadge } from "./states";

function ActionCard({
  action,
  onConfirm,
  busy,
}: {
  action: CoachAction;
  onConfirm: () => void;
  busy: boolean;
}) {
  const saved = action.status === "saved";
  const saving = action.status === "saving" || busy;

  return (
    <div className="mt-3 border border-rule-strong bg-background">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-rule px-3 py-2">
        <p className="text-sm font-bold">{action.title}</p>
        <StatusBadge
          kind={saved ? "completed" : action.status === "failed" ? "failed" : "pending"}
          label={saved ? "Saved locally" : action.status === "saving" ? "Saving" : undefined}
        />
      </header>

      <dl className="divide-y divide-rule">
        {action.fields.map((field) => (
          <div key={field.label} className="grid grid-cols-[9rem_1fr] gap-2 px-3 py-2 text-sm">
            <dt className="label-micro">{field.label}</dt>
            <dd className="font-medium">{field.value}</dd>
          </div>
        ))}
      </dl>

      <div className="border-t border-rule px-3 py-2">
        {saved ? (
          <p className="text-xs text-muted-foreground">
            Written locally at {new Date(action.savedAt ?? "").toLocaleTimeString("en-GB")}. This
            card can no longer be changed; report a correction as a new entry.
          </p>
        ) : (
          <div className="space-y-2">
            {action.status === "failed" && action.error && (
              <FailedState title="Nothing was written" description={action.error} />
            )}
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={onConfirm}
                disabled={saving}
                className="border border-rule-strong bg-foreground px-3 py-1.5 font-mono text-[0.72rem] uppercase tracking-[0.08em] text-background disabled:opacity-50"
              >
                {action.status === "failed" ? "Retry save" : "Confirm and save"}
              </button>
              {saving ? (
                <Busy label="Saving locally" />
              ) : (
                <p className="text-xs text-muted-foreground">
                  Nothing is written until you confirm.
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MessageBlock({
  message,
  onConfirm,
  busyActionId,
}: {
  message: CoachMessage;
  onConfirm: (actionId: string) => void;
  busyActionId: string | null;
}) {
  const isAthlete = message.role === "athlete";

  return (
    <li className="border-t border-rule pt-4 first:border-t-0 first:pt-0">
      <div className="flex items-center justify-between gap-2">
        <p className="label-micro-strong">{isAthlete ? "You" : "Pace coach"}</p>
        <p className="label-micro">{new Date(message.createdAt).toLocaleTimeString("en-GB")}</p>
      </div>

      <div className={isAthlete ? "mt-1.5 border-l-2 border-l-rule-strong pl-3" : "mt-1.5"}>
        {message.paragraphs.map((paragraph) => (
          <p key={paragraph} className="text-sm leading-relaxed">
            {paragraph}
          </p>
        ))}
      </div>

      {(message.evidence || message.assessment || message.uncertainty) && (
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          {message.evidence && <EvidenceList kind="evidence" items={message.evidence} />}
          {message.assessment && <EvidenceList kind="assessment" items={message.assessment} />}
          {message.uncertainty && <EvidenceList kind="uncertainty" items={message.uncertainty} />}
        </div>
      )}

      {message.action && (
        <ActionCard
          action={message.action}
          busy={busyActionId === message.action.id}
          onConfirm={() => onConfirm(message.action!.id)}
        />
      )}
    </li>
  );
}

export function CoachConversation() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [busyActionId, setBusyActionId] = useState<string | null>(null);

  const { data: messages, isPending } = useQuery(conversationQuery());
  const { data: commands } = useQuery(slashCommandsQuery());

  const send = useMutation({
    mutationFn: (text: string) => getPaceClient().sendCoachMessage(text),
    onSuccess: (next) => queryClient.setQueryData(paceKeys.conversation, next),
  });

  const confirm = useMutation({
    mutationFn: (actionId: string) => getPaceClient().confirmAction(actionId),
    onMutate: (actionId) => setBusyActionId(actionId),
    onSuccess: async (next) => {
      queryClient.setQueryData(paceKeys.conversation, next);
      await queryClient.invalidateQueries({ queryKey: paceKeys.today });
    },
    onSettled: () => setBusyActionId(null),
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || send.isPending) return;
    setDraft("");
    send.mutate(text);
  };

  return (
    <Panel
      title="Coach conversation"
      note="Bounded to this session. The conversation is not stored and disappears when the local server stops."
      aside={<StatusBadge kind="current" label="Local only" />}
    >
      {isPending ? (
        <LoadingState label="Reading conversation" />
      ) : !messages || messages.length === 0 ? (
        <EmptyState
          title="No conversation yet"
          description="Ask about today's session, or use a command to report an outcome or context."
        />
      ) : (
        <ul className="space-y-4">
          {messages.map((message) => (
            <MessageBlock
              key={message.id}
              message={message}
              busyActionId={busyActionId}
              onConfirm={(id) => confirm.mutate(id)}
            />
          ))}
        </ul>
      )}

      {send.isPending && (
        <div className="mt-4 border border-rule bg-surface-sunken px-3 py-2">
          <Busy label="Coach is composing a reply from your local facts" />
        </div>
      )}

      {send.isError && (
        <div className="mt-4">
          <FailedState
            title="The reply could not be composed"
            description="Nothing was written. Send the message again."
          />
        </div>
      )}

      <form onSubmit={submit} className="mt-5 border-t border-rule pt-4">
        <label htmlFor="coach-input" className="label-micro-strong">
          Message the coach
        </label>
        <textarea
          id="coach-input"
          rows={3}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="e.g. /feedback completed, RPE 7, last two repetitions were hard"
          className="mt-2 w-full resize-y border border-input bg-background px-3 py-2 text-sm"
        />
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button
            type="submit"
            disabled={send.isPending || draft.trim().length === 0}
            className="border border-rule-strong bg-foreground px-3 py-1.5 font-mono text-[0.72rem] uppercase tracking-[0.08em] text-background disabled:opacity-50"
          >
            Send
          </button>
          {commands?.map((command) => (
            <button
              key={command.command}
              type="button"
              onClick={() => setDraft(`${command.command} `)}
              title={command.description}
              className="border border-rule px-2 py-1 font-mono text-[0.7rem] tracking-wide text-muted-foreground hover:border-rule-strong hover:text-foreground"
            >
              {command.command}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Model replies never write anything. Every change appears as a card you confirm.
        </p>
      </form>
    </Panel>
  );
}
