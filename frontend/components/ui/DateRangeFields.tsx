"use client";

import {
  DATE_RANGE_PRESETS,
  type DateRangePreset,
  dateRangeForPreset,
} from "@/lib/dateRange";

type Props = {
  startDate: string;
  endDate: string;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  layout?: "stacked" | "grid";
};

export function DateRangeFields({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  layout = "stacked",
}: Props) {
  function applyPreset(preset: DateRangePreset) {
    const range = dateRangeForPreset(preset);
    onStartDateChange(range.start);
    onEndDateChange(range.end);
  }

  const fields =
    layout === "grid" ? (
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="text-xs font-medium uppercase tracking-wider text-muted">
            Start Date
          </label>
          <input
            type="date"
            className="input-field mt-2"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
          />
        </div>
        <div>
          <label className="text-xs font-medium uppercase tracking-wider text-muted">
            End Date
          </label>
          <input
            type="date"
            className="input-field mt-2"
            value={endDate}
            onChange={(e) => onEndDateChange(e.target.value)}
          />
        </div>
      </div>
    ) : (
      <>
        <div>
          <label className="text-xs font-medium uppercase tracking-wider text-muted">
            Start Date
          </label>
          <input
            type="date"
            className="input-field mt-2"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
          />
        </div>
        <div>
          <label className="text-xs font-medium uppercase tracking-wider text-muted">
            End Date
          </label>
          <input
            type="date"
            className="input-field mt-2"
            value={endDate}
            onChange={(e) => onEndDateChange(e.target.value)}
          />
        </div>
      </>
    );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {DATE_RANGE_PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            className="btn-secondary px-2.5 py-1 text-xs"
            onClick={() => applyPreset(preset.id)}
          >
            {preset.label}
          </button>
        ))}
      </div>
      {fields}
    </div>
  );
}
