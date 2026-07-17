"use client";

import { Loader2, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { DateRangeFields } from "@/components/ui/DateRangeFields";
import { FieldLabel } from "@/components/ui/FieldLabel";
import { FORM_TOOLTIPS } from "@/lib/formTooltips";

type Props = {
  symbol: string;
  onSymbolChange: (value: string) => void;
  startDate: string;
  endDate: string;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  trainRatio: number;
  onTrainRatioChange: (value: number) => void;
  initialCapital: number;
  onInitialCapitalChange: (value: number) => void;
  maxTrials: number;
  onMaxTrialsChange: (value: number) => void;
  topK: number;
  onTopKChange: (value: number) => void;
  minTrades: number;
  onMinTradesChange: (value: number) => void;
  walkForwardWindows: number;
  onWalkForwardWindowsChange: (value: number) => void;
  holdoutRatio: number;
  onHoldoutRatioChange: (value: number) => void;
  searchMethod: "grid" | "optuna";
  onSearchMethodChange: (value: "grid" | "optuna") => void;
  walkForwardMode: "fixed" | "anchored";
  onWalkForwardModeChange: (value: "fixed" | "anchored") => void;
  runError: Error | null;
  isRunPending: boolean;
  isSweepActive: boolean;
  onRun: () => void;
};

export function OptimizationFormCard({
  symbol,
  onSymbolChange,
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  trainRatio,
  onTrainRatioChange,
  initialCapital,
  onInitialCapitalChange,
  maxTrials,
  onMaxTrialsChange,
  topK,
  onTopKChange,
  minTrades,
  onMinTradesChange,
  walkForwardWindows,
  onWalkForwardWindowsChange,
  holdoutRatio,
  onHoldoutRatioChange,
  searchMethod,
  onSearchMethodChange,
  walkForwardMode,
  onWalkForwardModeChange,
  runError,
  isRunPending,
  isSweepActive,
  onRun,
}: Props) {
  return (
    <Card
      title="Sweep Configuration"
      subtitle="Train/test split with walk-forward folds"
    >
      <div className="space-y-4">
        <div>
          <FieldLabel label="Symbol" tooltip={FORM_TOOLTIPS.symbol} />
          <input
            className="input-field mt-2"
            value={symbol}
            onChange={(e) => onSymbolChange(e.target.value)}
          />
        </div>
        <DateRangeFields
          layout="grid"
          startDate={startDate}
          endDate={endDate}
          onStartDateChange={onStartDateChange}
          onEndDateChange={onEndDateChange}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <FieldLabel
              label="Train Ratio"
              tooltip={FORM_TOOLTIPS.trainRatio}
            />
            <input
              type="number"
              min={0.1}
              max={0.9}
              step={0.05}
              className="input-field mt-2"
              value={trainRatio}
              onChange={(e) => onTrainRatioChange(Number(e.target.value))}
            />
          </div>
          <div>
            <FieldLabel
              label="Initial Capital"
              tooltip={FORM_TOOLTIPS.initialCapital}
            />
            <input
              type="number"
              className="input-field mt-2"
              value={initialCapital}
              onChange={(e) => onInitialCapitalChange(Number(e.target.value))}
            />
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <FieldLabel label="Max Trials" tooltip={FORM_TOOLTIPS.maxTrials} />
            <input
              type="number"
              min={1}
              max={200}
              className="input-field mt-2"
              value={maxTrials}
              onChange={(e) => onMaxTrialsChange(Number(e.target.value))}
            />
          </div>
          <div>
            <FieldLabel label="Top K (test)" tooltip={FORM_TOOLTIPS.topK} />
            <input
              type="number"
              min={1}
              max={20}
              className="input-field mt-2"
              value={topK}
              onChange={(e) => onTopKChange(Number(e.target.value))}
            />
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <FieldLabel label="Min Trades" tooltip={FORM_TOOLTIPS.minTrades} />
            <input
              type="number"
              min={0}
              className="input-field mt-2"
              value={minTrades}
              onChange={(e) => onMinTradesChange(Number(e.target.value))}
            />
          </div>
          <div>
            <FieldLabel
              label="WF Windows"
              tooltip={FORM_TOOLTIPS.walkForwardWindows}
            />
            <input
              type="number"
              min={1}
              max={6}
              className="input-field mt-2"
              value={walkForwardWindows}
              onChange={(e) =>
                onWalkForwardWindowsChange(Number(e.target.value))
              }
            />
          </div>
          <div>
            <FieldLabel
              label="Holdout Ratio"
              tooltip={FORM_TOOLTIPS.holdoutRatio}
            />
            <input
              type="number"
              min={0}
              max={0.4}
              step={0.05}
              className="input-field mt-2"
              value={holdoutRatio}
              onChange={(e) => onHoldoutRatioChange(Number(e.target.value))}
            />
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <FieldLabel
              label="Search Method"
              tooltip={FORM_TOOLTIPS.searchMethod}
            />
            <select
              className="input-field mt-2"
              value={searchMethod}
              onChange={(e) =>
                onSearchMethodChange(e.target.value as "grid" | "optuna")
              }
            >
              <option value="grid">Grid (random sample)</option>
              <option value="optuna">Optuna (TPE)</option>
            </select>
          </div>
          <div>
            <FieldLabel
              label="WF Mode"
              tooltip={FORM_TOOLTIPS.walkForwardMode}
            />
            <select
              className="input-field mt-2"
              value={walkForwardMode}
              onChange={(e) =>
                onWalkForwardModeChange(e.target.value as "fixed" | "anchored")
              }
              disabled={walkForwardWindows <= 1}
            >
              <option value="anchored">Anchored</option>
              <option value="fixed">Fixed rolling</option>
            </select>
          </div>
        </div>
        <p className="text-xs text-muted">
          Last {Math.round(holdoutRatio * 100)}% is reserved as holdout and
          auto-evaluated on the best config after selection.
        </p>
        {runError && (
          <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger">
            {runError.message || "Optimization failed to start"}
          </p>
        )}
        <button
          type="button"
          onClick={onRun}
          disabled={isRunPending || isSweepActive}
          className="btn-primary w-full"
        >
          {isRunPending || isSweepActive ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          {isSweepActive ? "Optimization running…" : "Run Optimization"}
        </button>
      </div>
    </Card>
  );
}
