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

export function ValidationJobProvider({ children }: { children: ReactNode }) {
  const [jobId, setJobId] = useState<string | null>(null);

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

  const { data: job } = useQuery({
    queryKey: ["validation", jobId],
    queryFn: () => api.validation(jobId!),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      if (status === "completed" || status === "failed") return false;
      return 2000;
    },
  });

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
