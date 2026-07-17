"use client";

import { AlertTriangle } from "lucide-react";
import type { FeatureDrift } from "@/lib/api";

type Props = {
  featureDrift: FeatureDrift;
};

export function ReplayDriftBanner({ featureDrift }: Props) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-warning/30 bg-[var(--warning-dim)] p-4">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
      <div>
        <p className="font-medium text-warning">Feature drift detected</p>
        <p className="mt-1 text-sm text-muted">
          {featureDrift.reason ?? "Stored features differ from current config."}
        </p>
        {featureDrift.drifted_features?.length ? (
          <p className="mt-2 font-mono text-xs text-muted">
            {featureDrift.drifted_features.join(", ")}
          </p>
        ) : null}
      </div>
    </div>
  );
}
