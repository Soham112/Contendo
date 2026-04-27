"use client";

import { useCallback } from "react";
import { useApi } from "./api";

export type TrackingEventType =
  | "page_view"
  | "button_click"
  | "feature_start"
  | "feature_complete"
  | "feature_abandon";

export interface LogEventPayload {
  event_type: TrackingEventType;
  page_url?: string;
  button_name?: string;
  metadata?: Record<string, unknown>;
}

/**
 * Fire-and-forget analytics hook.
 * logEvent never throws and never blocks the caller.
 */
export function useTracking() {
  const api = useApi();

  const logEvent = useCallback(
    (payload: LogEventPayload) => {
      api
        .logEvent(payload)
        .catch((err) => {
          console.warn("[Analytics] Failed to log event:", err);
        });
    },
    [api]
  );

  return { logEvent };
}
