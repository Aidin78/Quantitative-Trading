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
};

export function requiredFeaturesForProvider(providerId: string): string[] {
  return PROVIDER_REQUIRED_FEATURES[providerId] ?? [];
}
