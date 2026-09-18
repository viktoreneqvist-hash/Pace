import { queryOptions } from "@tanstack/react-query";

import { getPaceClient } from "./client";
import type { DashboardWindow } from "./types";

export const paceKeys = {
  today: ["pace", "today"] as const,
  conversation: ["pace", "conversation"] as const,
  slashCommands: ["pace", "slash-commands"] as const,
  sync: ["pace", "sync"] as const,
  plan: ["pace", "plan"] as const,
  planHistory: ["pace", "plan-history"] as const,
  dashboard: (window: DashboardWindow) => ["pace", "dashboard", window] as const,
  weeklyReview: ["pace", "weekly-review"] as const,
  races: ["pace", "races"] as const,
  settings: ["pace", "settings"] as const,
  onboarding: ["pace", "onboarding"] as const,
  session: (sessionId: string) => ["pace", "session", sessionId] as const,
};

export const todayQuery = () =>
  queryOptions({
    queryKey: paceKeys.today,
    queryFn: () => getPaceClient().getToday(),
  });

export const conversationQuery = () =>
  queryOptions({
    queryKey: paceKeys.conversation,
    queryFn: () => getPaceClient().getConversation(),
  });

export const slashCommandsQuery = () =>
  queryOptions({
    queryKey: paceKeys.slashCommands,
    queryFn: () => getPaceClient().getSlashCommands(),
    staleTime: Infinity,
  });

export const syncQuery = () =>
  queryOptions({
    queryKey: paceKeys.sync,
    queryFn: () => getPaceClient().getSyncState(),
  });

export const planQuery = () =>
  queryOptions({
    queryKey: paceKeys.plan,
    queryFn: () => getPaceClient().getPlan(),
  });

export const planHistoryQuery = () =>
  queryOptions({
    queryKey: paceKeys.planHistory,
    queryFn: () => getPaceClient().getPlanHistory(),
  });

export const dashboardQuery = (window: DashboardWindow) =>
  queryOptions({
    queryKey: paceKeys.dashboard(window),
    queryFn: () => getPaceClient().getDashboard(window),
  });

/** Read-only. Opening Weekly Review must never regenerate the snapshot. */
export const weeklyReviewQuery = () =>
  queryOptions({
    queryKey: paceKeys.weeklyReview,
    queryFn: () => getPaceClient().getWeeklyReview(),
    staleTime: Infinity,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
  });

export const racesQuery = () =>
  queryOptions({
    queryKey: paceKeys.races,
    queryFn: () => getPaceClient().getRaces(),
  });

export const settingsQuery = () =>
  queryOptions({
    queryKey: paceKeys.settings,
    queryFn: () => getPaceClient().getSettings(),
  });

export const onboardingQuery = () =>
  queryOptions({
    queryKey: paceKeys.onboarding,
    queryFn: () => getPaceClient().getOnboarding(),
  });

export const sessionQuery = (sessionId: string) =>
  queryOptions({
    queryKey: paceKeys.session(sessionId),
    queryFn: () => getPaceClient().getSession(sessionId),
  });
