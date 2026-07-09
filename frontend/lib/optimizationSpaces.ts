/** Optimization search-space presets and provider-combo helpers. */

export type SweepMode = "baseline" | "discovery";

export const BASELINE_TUNING_SPACE: Record<string, (number | string)[]> = {
  min_confidence: [0.6, 0.7, 0.78],
  min_risk_reward: [1.0, 1.5, 2.0],
  min_agreeing_providers: [1],
  sl_atr_mult: [1.0, 1.5, 2.0],
  tp_atr_mult: [2.0, 3.0, 4.0],
  max_bars_in_trade: [12, 24, 48],
  oversold: [25, 30, 35],
  overbought: [65, 70, 75],
  risk_pct_per_trade: [0.5, 1.0, 1.5],
  min_atr_pct: [0.1, 0.3, 0.5],
  session_preset: ["all", "eu_us"],
  max_signals_per_day: [5, 10, 20],
  ema_fast: [10, 12, 14],
  ema_slow: [24, 26, 30],
  rsi_period: [12, 14, 16],
  ema_weight: [1.0],
  rsi_weight: [1.0],
  ema_enabled: [1],
  rsi_enabled: [1],
  macd_fast: [10, 12, 14],
  macd_slow: [24, 26, 30],
  macd_signal_period: [7, 9, 11],
  macd_weight: [1.0],
  macd_enabled: [1],
  require_signal_align: [1, 0],
  min_histogram_slope: [0.0],
  adx_period: [12, 14, 16],
  adx_weight: [1.0],
  adx_enabled: [0],
  min_adx: [20, 25, 30],
  min_di_spread: [3, 5, 8],
  adx_require_trend: [0],
  bb_period: [18, 20, 22],
  bb_std: [1.5, 2.0, 2.5],
  bb_weight: [1.0],
  bb_enabled: [0],
  bb_avoid_high_vol: [1],
  bb_max_adx: [0, 25],
  st_period: [7, 10, 14],
  st_multiplier: [2.0, 3.0, 4.0],
  st_weight: [1.0],
  st_enabled: [0],
  st_require_trend: [0],
  vol_period: [14, 20, 26],
  vol_weight: [1.0],
  vol_enabled: [0],
  min_cmf: [0.03, 0.05, 0.08],
  min_volume_ratio: [1.0, 1.2, 1.5],
  vol_require_price_align: [0, 1],
  ms_pivot_bars: [3, 5, 7],
  ms_weight: [1.0],
  ms_enabled: [0],
  ms_require_bos: [0, 1],
  ms_require_trend: [0],
};

/** Search which providers are on/off; other params fixed at defaults. */
export const PROVIDER_DISCOVERY_SPACE: Record<string, (number | string)[]> = {
  min_confidence: [0.65],
  min_risk_reward: [1.2],
  min_agreeing_providers: [1, 2, 3],
  sl_atr_mult: [1.5],
  tp_atr_mult: [3.0],
  max_bars_in_trade: [24],
  oversold: [30],
  overbought: [70],
  risk_pct_per_trade: [1.0],
  min_atr_pct: [0.3],
  session_preset: ["all"],
  max_signals_per_day: [10],
  ema_fast: [12],
  ema_slow: [26],
  rsi_period: [14],
  ema_weight: [1.0],
  rsi_weight: [1.0],
  ema_enabled: [0, 1],
  rsi_enabled: [0, 1],
  macd_fast: [12],
  macd_slow: [26],
  macd_signal_period: [9],
  macd_weight: [1.0],
  macd_enabled: [0, 1],
  require_signal_align: [1],
  min_histogram_slope: [0.0],
  adx_period: [14],
  adx_weight: [1.0],
  adx_enabled: [0, 1],
  min_adx: [25],
  min_di_spread: [5],
  adx_require_trend: [0],
  bb_period: [20],
  bb_std: [2.0],
  bb_weight: [1.0],
  bb_enabled: [0, 1],
  bb_avoid_high_vol: [1],
  bb_max_adx: [0],
  st_period: [10],
  st_multiplier: [3.0],
  st_weight: [1.0],
  st_enabled: [0, 1],
  st_require_trend: [0],
  vol_period: [20],
  vol_weight: [1.0],
  vol_enabled: [0, 1],
  min_cmf: [0.05],
  min_volume_ratio: [1.2],
  vol_require_price_align: [1],
  ms_pivot_bars: [5],
  ms_weight: [1.0],
  ms_enabled: [0, 1],
  ms_require_bos: [1],
  ms_require_trend: [0],
};

const PROVIDER_CHIP_LABELS: Record<string, string> = {
  ema_enabled: "EMA",
  rsi_enabled: "RSI",
  macd_enabled: "MACD",
  adx_enabled: "ADX",
  bb_enabled: "BB",
  st_enabled: "ST",
  vol_enabled: "VOL",
  ms_enabled: "MS",
};

export function enabledProviderChips(
  params: Record<string, number | string>,
): string[] {
  return Object.entries(PROVIDER_CHIP_LABELS)
    .filter(([key]) => Number(params[key] ?? 0) === 1)
    .map(([, label]) => label);
}

export function fmtParamsWithoutEnabled(
  params: Record<string, number | string>,
): string {
  return Object.entries(params)
    .filter(([k]) => !k.endsWith("_enabled"))
    .map(([k, v]) => `${k.replace(/_/g, " ")}=${v}`)
    .join(" · ");
}

export function spaceForMode(
  mode: SweepMode,
): Record<string, (number | string)[]> {
  return mode === "discovery"
    ? PROVIDER_DISCOVERY_SPACE
    : BASELINE_TUNING_SPACE;
}
