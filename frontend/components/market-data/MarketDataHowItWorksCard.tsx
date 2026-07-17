"use client";

import { Card } from "@/components/ui/Card";

export function MarketDataHowItWorksCard() {
  return (
    <Card
      title="How it works"
      subtitle="Cached files are reused by Validation and Optimizer"
    >
      <div className="space-y-3 text-sm text-muted">
        <p>
          Pick a symbol and range, then send one request. The backend pulls
          OHLCV from Binance (paginated) and writes a CSV under{" "}
          <code className="text-xs text-foreground">backend/data/cache/</code>.
        </p>
        <p>
          When you run Validation or Auto Optimizer with{" "}
          <strong className="text-foreground">Exchange</strong> as the data
          source, the same cache file is reused — no repeat download unless you
          force refresh or change the date range.
        </p>
      </div>
    </Card>
  );
}
