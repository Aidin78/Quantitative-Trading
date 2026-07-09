export const FORM_TOOLTIPS = {
  symbol:
    "Trading pair to backtest or optimize, e.g. BTC/USDT. Must match a symbol available on the exchange cache.",
  timeframe:
    "Candle size for OHLCV data. 1h is the default strategy timeframe; 4h uses fewer bars over the same calendar range.",
  startDate:
    "First calendar day included in the backtest or download. Indicator warm-up needs extra bars before this date.",
  endDate:
    "Last calendar day included. For exchange data, bars through the latest cached timestamp are used.",
  datePresets:
    "Quick ranges relative to today. Longer ranges usually produce more trades and more stable optimizer scores.",
  initialCapital:
    "Starting portfolio cash for simulated execution. Position sizing is based on this amount and risk per trade.",
  trainRatio:
    "Fraction of each window used for in-sample training. The remainder is held out for test evaluation.",
  maxTrials:
    "How many parameter combinations to evaluate per sweep. Higher values explore more configs but take longer.",
  topK: "Number of best train candidates re-tested on held-out data after the coarse search finishes.",
  minTrades:
    "Minimum closed trades required on test data for a config to be eligible as best. Filters lucky short samples.",
  walkForwardWindows:
    "Split the date range into rolling folds. Each fold trains and tests separately; scores are averaged for robustness.",
  holdoutRatio:
    "Reserve the final slice of the date range for manual validation only. The optimizer never sees this data.",
  rangeMode:
    "Download by rolling months from today, or pick explicit start/end dates for the CSV cache file.",
  period:
    "How many calendar months of OHLCV to fetch ending today. Cached files are reused until force refresh.",
  forceRedownload:
    "Ignore an existing cache file and fetch fresh OHLCV from Binance even if a matching CSV already exists.",
  minConfidence:
    "Minimum provider confidence required before the engine approves a trade. Higher values mean fewer entries.",
  minAgreeingProviders:
    "How many signal providers must agree on the same side. 2 requires both EMA and RSI to align — often very strict.",
  minAtrPct:
    "Minimum ATR as % of price to allow trading. Filters out very quiet periods with little movement.",
  wfWindows:
    "Number of rolling validation windows. More windows stress-test stability across different market segments.",
  wfTrainRatio:
    "Within each walk-forward window, the fraction used for training before evaluating on the remaining bars.",
  compareRunA:
    "First saved validation run to compare. Pick runs with the same symbol/timeframe for a fair comparison.",
  compareRunB:
    "Second validation run to compare against Run A. Metrics and deltas are shown side by side.",
  correlationId:
    "Decision cycle identifier from the Signals or Decisions feed. Used to load the full event timeline.",
  replayMode:
    "Strict replay shows recorded events. Re-execute re-runs the decision engine with optional config revision.",
  revisionId:
    "Config revision to use when re-executing. Leave empty to use the revision stored with the original cycle.",
  filterResult:
    "Show only approved or rejected decisions. Approved means the engine accepted the trade signal.",
  filterSide:
    "Filter by trade direction: BUY, SELL, or HOLD signals from providers.",
  filterRejectionReason:
    "Substring match on why a decision was rejected, e.g. low_confidence or min_agreeing_providers.",
  filterProvider:
    "Show decisions where a specific signal provider contributed, e.g. ema_crossover or rsi_divergence.",
  optTrialParams:
    "Hyperparameter combination evaluated in this trial (engine, providers, and feature settings).",
  optTrialTrain:
    "Optimization score on in-sample (train) data. All trials are ranked by this before Top-K re-test.",
  optTrialTest:
    "Score on held-out test data. Only the best Top-K train candidates receive a test backtest.",
  optTrialReturn:
    "Portfolio return % over the evaluated period. Test return is shown for finalists; others show train return only.",
  optTrialTrades:
    "Number of closed simulated trades in the period. Test trades apply only to finalists.",
  optTrialComposite:
    "Final selection score: 60% test score + 25% stability + 15% return − fold variance penalty. Shown only for test finalists.",
  optTrialStability:
    "Share of months with positive PnL on test data. Higher values suggest more consistent performance.",
} as const;
