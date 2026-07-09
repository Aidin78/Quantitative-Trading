/** Display metadata for built-in signal providers (chips + labels). */
export const PROVIDER_REQUIRED_FEATURES: Record<string, string[]> = {
  ema_crossover: ["ema_cross_bullish", "ema_cross_bearish"],
  rsi_divergence: ["rsi_14"],
  macd_momentum: [
    "macd",
    "macd_signal",
    "macd_histogram",
    "macd_histogram_slope",
  ],
  adx_trend_strength: ["adx_14", "plus_di_14", "minus_di_14"],
  bollinger_reversion: ["bb_upper", "bb_lower", "bb_middle"],
  supertrend_trend: ["supertrend", "supertrend_direction"],
  volume_order_flow: ["cmf_20", "volume_ratio_20", "close_delta"],
  market_structure: ["ms_bias", "ms_bos"],
};

export function requiredFeaturesForProvider(providerId: string): string[] {
  return PROVIDER_REQUIRED_FEATURES[providerId] ?? [];
}
