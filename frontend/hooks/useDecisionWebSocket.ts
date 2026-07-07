"use client";

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

const WS_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
    const wsUrl = WS_BASE.replace(/^http/, "ws") + "/ws/decisions";
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

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

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [enabled, queryClient]);
}
