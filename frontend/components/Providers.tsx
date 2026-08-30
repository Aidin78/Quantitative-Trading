"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError } from "@/lib/api";

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Don't hammer a backend that's down — a connectivity failure won't
        // fix itself on retry, so surface it immediately. Retry real HTTP
        // errors once.
        retry: (count, err) =>
          !(err instanceof ApiError && err.connectivity) && count < 1,
        retryDelay: 800,
        refetchOnWindowFocus: false,
        staleTime: 10_000,
      },
    },
  });
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(makeClient);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
