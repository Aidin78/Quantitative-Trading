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
import { api, type ValidationJob } from "@/lib/api";
import {
  clearActiveValidationJobId,
  getActiveValidationJobId,
  setActiveValidationJobId,
} from "@/lib/validationSession";

type ValidationJobContextValue = {
  jobId: string | null;
  setActiveJobId: (id: string) => void;
  clearActiveJob: () => void;
  job: ValidationJob | undefined;
  isActive: boolean;
};

const ValidationJobContext = createContext<ValidationJobContextValue | null>(
  null,
);

function isTerminalStatus(status: string | undefined): boolean {
  return (
    status === "completed" || status === "failed" || status === "cancelled"
  );
}

export function ValidationJobProvider({ children }: { children: ReactNode }) {
  const [jobId, setJobId] = useState<string | null>(null);
  const streamRef = useRef({ streaming: false, failed: false });

  useEffect(() => {
    setJobId(getActiveValidationJobId());
  }, []);

  const setActiveJobId = useCallback((id: string) => {
    setActiveValidationJobId(id);
    setJobId(id);
  }, []);

  const clearActiveJob = useCallback(() => {
    clearActiveValidationJobId();
    setJobId(null);
  }, []);

  const queryKey = useMemo(() => ["validation", jobId] as const, [jobId]);

  const { data: job } = useQuery({
    queryKey,
    queryFn: () => api.validation(jobId!),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      if (isTerminalStatus(status)) return false;
      if (streamRef.current.streaming && !streamRef.current.failed)
        return false;
      return 2000;
    },
  });

  const { streaming, failed } = useJobEventSource({
    kind: "validation",
    id: jobId,
    enabled: !!jobId && !isTerminalStatus(job?.status),
    queryKey,
  });
  streamRef.current = { streaming, failed };

  const isActive = job?.status === "pending" || job?.status === "running";

  const value = useMemo(
    () => ({
      jobId,
      setActiveJobId,
      clearActiveJob,
      job,
      isActive,
    }),
    [jobId, setActiveJobId, clearActiveJob, job, isActive],
  );

  return (
    <ValidationJobContext.Provider value={value}>
      {children}
    </ValidationJobContext.Provider>
  );
}

export function useActiveValidationJob(): ValidationJobContextValue {
  const ctx = useContext(ValidationJobContext);
  if (!ctx) {
    throw new Error(
      "useActiveValidationJob must be used within ValidationJobProvider",
    );
  }
  return ctx;
}
