"use client";

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

const WS_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const MAX_RECONNECT_DELAY_MS = 30_000;
const BASE_RECONNECT_DELAY_MS = 1_000;

export type WsDecisionEvent = {
  event: string;
  data: {
    id: string;
    symbol: string;
    correlation_id: string;
    result: string;
    side?: string;
    confidence?: number;
    reason?: string;
    rejection_stage?: string;
  };
};

export function useDecisionWebSocket(enabled = true) {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) return;

    let closedByEffect = false;
    let reconnectAttempt = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      const wsUrl = WS_BASE.replace(/^http/, "ws") + "/ws/decisions";
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttempt = 0;
      };

      ws.onmessage = (msg) => {
        try {
          const parsed = JSON.parse(msg.data) as WsDecisionEvent;
          if (parsed.event?.startsWith("decision.")) {
            queryClient.invalidateQueries({ queryKey: ["decisions"] });
            queryClient.invalidateQueries({ queryKey: ["engine-stats"] });
            queryClient.invalidateQueries({ queryKey: ["signals"] });
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        if (closedByEffect) return;
        const delay = Math.min(
          BASE_RECONNECT_DELAY_MS * 2 ** reconnectAttempt,
          MAX_RECONNECT_DELAY_MS,
        );
        reconnectAttempt += 1;
        reconnectTimer = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      closedByEffect = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [enabled, queryClient]);
}
