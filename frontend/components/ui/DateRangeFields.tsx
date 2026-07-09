"use client";

import {
  DATE_RANGE_PRESETS,
  type DateRangePreset,
  dateRangeForPreset,
} from "@/lib/dateRange";
import { FORM_TOOLTIPS } from "@/lib/formTooltips";
import { FieldLabel } from "@/components/ui/FieldLabel";

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
          <FieldLabel label="Start Date" tooltip={FORM_TOOLTIPS.startDate} />
          <input
            type="date"
            className="input-field mt-2"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
          />
        </div>
        <div>
          <FieldLabel label="End Date" tooltip={FORM_TOOLTIPS.endDate} />
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
          <FieldLabel label="Start Date" tooltip={FORM_TOOLTIPS.startDate} />
          <input
            type="date"
            className="input-field mt-2"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
          />
        </div>
        <div>
          <FieldLabel label="End Date" tooltip={FORM_TOOLTIPS.endDate} />
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
      <div className="flex flex-wrap items-center gap-2">
        <FieldLabel
          label="Quick range"
          tooltip={FORM_TOOLTIPS.datePresets}
          className="mr-1"
        />
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
