"use client";

import { FieldLabel } from "@/components/ui/FieldLabel";
import type { DecisionFilters as Filters } from "@/lib/api";
import { FORM_TOOLTIPS } from "@/lib/formTooltips";

type Props = {
  filters: Filters;
  providers: string[];
  onChange: (next: Filters) => void;
};

export function DecisionFiltersBar({ filters, providers, onChange }: Props) {
  return (
    <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <div>
        <FieldLabel label="Result" tooltip={FORM_TOOLTIPS.filterResult} />
        <select
          className="input-field mt-2"
          value={filters.result ?? ""}
          onChange={(e) =>
            onChange({ ...filters, result: e.target.value || undefined })
          }
        >
          <option value="">All</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>
      <div>
        <FieldLabel label="Side" tooltip={FORM_TOOLTIPS.filterSide} />
        <select
          className="input-field mt-2"
          value={filters.side ?? ""}
          onChange={(e) =>
            onChange({ ...filters, side: e.target.value || undefined })
          }
        >
          <option value="">All</option>
          <option value="BUY">BUY</option>
          <option value="SELL">SELL</option>
          <option value="HOLD">HOLD</option>
        </select>
      </div>
      <div>
        <FieldLabel
          label="Rejection reason"
          tooltip={FORM_TOOLTIPS.filterRejectionReason}
        />
        <input
          className="input-field mt-2"
          placeholder="e.g. low_confidence"
          value={filters.rejection_reason ?? ""}
          onChange={(e) =>
            onChange({
              ...filters,
              rejection_reason: e.target.value || undefined,
            })
          }
        />
      </div>
      <div>
        <FieldLabel label="Provider" tooltip={FORM_TOOLTIPS.filterProvider} />
        <select
          className="input-field mt-2"
          value={filters.provider ?? ""}
          onChange={(e) =>
            onChange({ ...filters, provider: e.target.value || undefined })
          }
        >
          <option value="">All</option>
          {providers.map((p) => (
            <option key={p} value={p}>
              {p.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
