"use client";

import { Loader2, Search } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { FieldLabel } from "@/components/ui/FieldLabel";
import { FORM_TOOLTIPS } from "@/lib/formTooltips";

type Props = {
  correlationId: string;
  onCorrelationIdChange: (value: string) => void;
  mode: "strict" | "re_execute";
  onModeChange: (value: "strict" | "re_execute") => void;
  revisionId: string;
  onRevisionIdChange: (value: string) => void;
  isFetching: boolean;
  onLoad: () => void;
};

export function ReplaySearchCard({
  correlationId,
  onCorrelationIdChange,
  mode,
  onModeChange,
  revisionId,
  onRevisionIdChange,
  isFetching,
  onLoad,
}: Props) {
  return (
    <Card
      title="Cycle Search"
      subtitle="Enter a correlation_id from a decision or open from Signals / Monitor"
    >
      <div className="space-y-4">
        <FieldLabel
          label="Correlation ID"
          tooltip={FORM_TOOLTIPS.correlationId}
        />
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            className="input-field flex-1 font-mono text-sm"
            value={correlationId}
            onChange={(e) => onCorrelationIdChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onLoad();
            }}
            placeholder="cycle_btc_1h_..."
          />
          <button
            type="button"
            onClick={onLoad}
            disabled={!correlationId.trim() || isFetching}
            className="btn-primary shrink-0"
          >
            {isFetching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
            Load Timeline
          </button>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <FieldLabel label="Mode" tooltip={FORM_TOOLTIPS.replayMode} />
            <select
              className="input-field mt-2"
              value={mode}
              onChange={(e) =>
                onModeChange(e.target.value as "strict" | "re_execute")
              }
            >
              <option value="strict">Strict replay</option>
              <option value="re_execute">Re-execute</option>
            </select>
          </div>
          {mode === "re_execute" ? (
            <div>
              <FieldLabel
                label="Revision ID (optional)"
                tooltip={FORM_TOOLTIPS.revisionId}
              />
              <input
                className="input-field mt-2 font-mono text-sm"
                value={revisionId}
                onChange={(e) => onRevisionIdChange(e.target.value)}
                placeholder="rev_..."
              />
            </div>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
