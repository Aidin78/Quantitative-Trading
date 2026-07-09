"use client";

import { useQuery } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
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

export function OptimizationSweepProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [sweepId, setSweepId] = useState<string | null>(null);

  useEffect(() => {
    setSweepId(getActiveOptimizationSweepId());
  }, []);

  const setActiveSweepId = useCallback((id: string) => {
    setActiveOptimizationSweepId(id);
    setSweepId(id);
  }, []);

  const { data: sweep } = useQuery({
    queryKey: ["optimization", sweepId],
    queryFn: () => api.optimization(sweepId!),
    enabled: !!sweepId,
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      if (status === "completed" || status === "failed") return false;
      return 2000;
    },
  });

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
