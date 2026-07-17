"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { getToken } from "@/lib/api/client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type JobEventKind = "optimization" | "validation";

type UseJobEventSourceArgs = {
  kind: JobEventKind;
  id: string | null;
  /** When false, the stream is not opened (e.g. job already terminal). */
  enabled: boolean;
  queryKey: readonly unknown[];
};

function eventsPath(kind: JobEventKind, id: string): string {
  return kind === "optimization"
    ? `/api/v1/optimization/${id}/events`
    : `/api/v1/validation/${id}/events`;
}

function parseSseChunks(buffer: string): {
  events: Array<{ event: string; data: string }>;
  rest: string;
} {
  const events: Array<{ event: string; data: string }> = [];
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  for (const block of parts) {
    if (!block.trim() || block.startsWith(":")) continue;
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }
    if (dataLines.length) {
      events.push({ event, data: dataLines.join("\n") });
    }
  }
  return { events, rest };
}

/**
 * Subscribe to job SSE progress and write snapshots into React Query cache.
 * Returns whether the stream is live and whether it failed (polling fallback).
 */
export function useJobEventSource({
  kind,
  id,
  enabled,
  queryKey,
}: UseJobEventSourceArgs): { streaming: boolean; failed: boolean } {
  const queryClient = useQueryClient();
  const [streaming, setStreaming] = useState(false);
  const [failed, setFailed] = useState(false);
  const attemptRef = useRef(0);

  useEffect(() => {
    if (!enabled || !id) {
      setStreaming(false);
      return;
    }

    const ac = new AbortController();
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = async () => {
      setFailed(false);
      try {
        const token = getToken();
        const headers: Record<string, string> = {
          Accept: "text/event-stream",
        };
        if (token) headers.Authorization = `Bearer ${token}`;

        const res = await fetch(`${API_BASE}${eventsPath(kind, id)}`, {
          headers,
          signal: ac.signal,
        });
        if (!res.ok || !res.body) {
          if (!cancelled) {
            setFailed(true);
            setStreaming(false);
          }
          return;
        }

        if (!cancelled) {
          setStreaming(true);
          setFailed(false);
          attemptRef.current = 0;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let sawTerminal = false;

        while (!cancelled) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parsed = parseSseChunks(buffer);
          buffer = parsed.rest;
          for (const frame of parsed.events) {
            if (
              frame.event !== "snapshot" &&
              frame.event !== "progress" &&
              frame.event !== "terminal"
            ) {
              continue;
            }
            try {
              const payload = JSON.parse(frame.data) as unknown;
              queryClient.setQueryData(queryKey, payload);
              if (frame.event === "terminal") {
                sawTerminal = true;
                await queryClient.invalidateQueries({ queryKey });
              }
            } catch {
              // ignore malformed JSON frames
            }
          }
          if (sawTerminal) {
            break;
          }
        }

        if (!cancelled) {
          setStreaming(false);
          if (!sawTerminal) {
            // Unexpected close — backoff reconnect, then mark failed for polling.
            attemptRef.current += 1;
            if (attemptRef.current <= 3) {
              const delay = Math.min(
                1000 * 2 ** (attemptRef.current - 1),
                8000,
              );
              reconnectTimer = setTimeout(() => {
                void connect();
              }, delay);
            } else {
              setFailed(true);
            }
          }
        }
      } catch {
        if (!cancelled && !ac.signal.aborted) {
          setStreaming(false);
          attemptRef.current += 1;
          if (attemptRef.current <= 3) {
            const delay = Math.min(1000 * 2 ** (attemptRef.current - 1), 8000);
            reconnectTimer = setTimeout(() => {
              void connect();
            }, delay);
          } else {
            setFailed(true);
          }
        }
      }
    };

    void connect();

    return () => {
      cancelled = true;
      ac.abort();
      if (reconnectTimer) clearTimeout(reconnectTimer);
      setStreaming(false);
    };
  }, [enabled, id, kind, queryClient, queryKey]);

  return { streaming, failed };
}
