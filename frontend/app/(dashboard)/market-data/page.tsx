"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { MarketDataCacheCard } from "@/components/market-data/MarketDataCacheCard";
import { MarketDataDownloadCard } from "@/components/market-data/MarketDataDownloadCard";
import { MarketDataHowItWorksCard } from "@/components/market-data/MarketDataHowItWorksCard";
import { api } from "@/lib/api";
import { dateRangeForPreset } from "@/lib/dateRange";

export default function MarketDataPage() {
  const queryClient = useQueryClient();
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [months, setMonths] = useState(3);
  const [useCustomRange, setUseCustomRange] = useState(false);
  const [startDate, setStartDate] = useState(
    () => dateRangeForPreset("90d").start,
  );
  const [endDate, setEndDate] = useState(() => dateRangeForPreset("90d").end);
  const [force, setForce] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const {
    data: cache,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["market-data-cache"],
    queryFn: () => api.marketDataCache(),
    retry: 1,
  });

  const download = useMutation({
    mutationFn: () =>
      api.downloadMarketData({
        symbol,
        timeframe,
        months: useCustomRange ? undefined : months,
        start_date: useCustomRange ? startDate : undefined,
        end_date: useCustomRange ? endDate : undefined,
        force,
      }),
    onSuccess: (res) => {
      setLastResult(
        res.refreshed
          ? `Downloaded ${res.rows.toLocaleString()} bars → ${res.filename}`
          : `Used cached file (${res.rows.toLocaleString()} bars) → ${res.filename}`,
      );
      queryClient.invalidateQueries({ queryKey: ["market-data-cache"] });
    },
  });

  return (
    <div className="page-container">
      <PageHeader
        title="Market Data"
        description="Download OHLCV from Binance once and cache it as CSV for validation and optimization."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <MarketDataDownloadCard
          symbol={symbol}
          onSymbolChange={setSymbol}
          timeframe={timeframe}
          onTimeframeChange={setTimeframe}
          useCustomRange={useCustomRange}
          onUseCustomRangeChange={setUseCustomRange}
          months={months}
          onMonthsChange={setMonths}
          startDate={startDate}
          endDate={endDate}
          onStartDateChange={setStartDate}
          onEndDateChange={setEndDate}
          force={force}
          onForceChange={setForce}
          downloadError={download.error}
          lastResult={lastResult}
          isPending={download.isPending}
          onDownload={() => download.mutate()}
        />
        <MarketDataHowItWorksCard />
      </div>

      <MarketDataCacheCard
        items={cache?.items}
        isLoading={isLoading}
        isError={isError}
        error={error}
        isFetching={isFetching}
        onRefetch={() => refetch()}
      />
    </div>
  );
}
