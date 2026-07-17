"use client";

import { useQuery } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useJobEventSource } from "@/hooks/useJobEventSource";
import { api, type OptimizationSweep } from "@/lib/api";
import {
  getActiveOptimizationSweepId,
  setActiveOptimizationSweepId,
} from "@/lib/optimizationSession";

type OptimizationSweepContextValue = {
  sweepId: string | null;
  setActiveSweepId: (id: string) => void;
  sweep: OptimizationSweep | undefined;
  isActive: boolean;
};

const OptimizationSweepContext =
  createContext<OptimizationSweepContextValue | null>(null);

function isTerminalStatus(status: string | undefined): boolean {
  return (
    status === "completed" || status === "failed" || status === "cancelled"
  );
}

export function OptimizationSweepProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [sweepId, setSweepId] = useState<string | null>(null);
  const streamRef = useRef({ streaming: false, failed: false });

  useEffect(() => {
    setSweepId(getActiveOptimizationSweepId());
  }, []);

  const setActiveSweepId = useCallback((id: string) => {
    setActiveOptimizationSweepId(id);
    setSweepId(id);
  }, []);

  const queryKey = useMemo(() => ["optimization", sweepId] as const, [sweepId]);

  const { data: sweep } = useQuery({
    queryKey,
    queryFn: () => api.optimization(sweepId!),
    enabled: !!sweepId,
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      if (isTerminalStatus(status)) return false;
      if (streamRef.current.streaming && !streamRef.current.failed)
        return false;
      return 2000;
    },
  });

  const { streaming, failed } = useJobEventSource({
    kind: "optimization",
    id: sweepId,
    enabled: !!sweepId && !isTerminalStatus(sweep?.status),
    queryKey,
  });
  streamRef.current = { streaming, failed };

  const isActive = sweep?.status === "pending" || sweep?.status === "running";

  const value = useMemo(
    () => ({
      sweepId,
      setActiveSweepId,
      sweep,
      isActive,
    }),
    [sweepId, setActiveSweepId, sweep, isActive],
  );

  return (
    <OptimizationSweepContext.Provider value={value}>
      {children}
    </OptimizationSweepContext.Provider>
  );
}

export function useActiveOptimizationSweep(): OptimizationSweepContextValue {
  const ctx = useContext(OptimizationSweepContext);
  if (!ctx) {
    throw new Error(
      "useActiveOptimizationSweep must be used within OptimizationSweepProvider",
    );
  }
  return ctx;
}
