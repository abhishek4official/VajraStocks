import React, { useEffect, useRef } from 'react';
import { 
  createChart, 
  CandlestickSeries, 
  LineSeries, 
  HistogramSeries 
} from 'lightweight-charts';
import type { 
  LineData, 
  HistogramData
} from 'lightweight-charts';
import { useStockStore } from '../store/useStockStore';

type ChartTimeframe = '1W' | '1M' | '3M' | '6M' | '1Y' | 'MAX';
type ChartOverlay = 'sma20' | 'sma50' | 'sma200' | 'ema9' | 'ema21' | 'bb' | 'sr' | 'nifty';

interface PriceChartProps {
  indicatorToShow: 'RSI' | 'MACD' | 'NONE';
  timeframe?: ChartTimeframe;
  overlays?: Set<ChartOverlay>;
  niftyCandles?: import('../services/api').CandleData[];
}

/** Detect pivot highs/lows and return clustered S/R price levels. */
function detectSRLevels(candles: { high: number; low: number; close: number }[], window = 3, maxLevels = 8): number[] {
  if (candles.length < window * 2 + 1) return [];
  const pivotHighs: number[] = [];
  const pivotLows: number[] = [];

  for (let i = window; i < candles.length - window; i++) {
    const slice = candles.slice(i - window, i + window + 1);
    const isHigh = candles[i].high === Math.max(...slice.map(c => c.high));
    const isLow  = candles[i].low  === Math.min(...slice.map(c => c.low));
    if (isHigh) pivotHighs.push(candles[i].high);
    if (isLow)  pivotLows.push(candles[i].low);
  }

  // Cluster levels within 0.5% of each other, keep the most-touched
  const all = [...pivotHighs, ...pivotLows];
  const clusters: number[] = [];
  for (const lvl of all) {
    const nearby = clusters.find(c => Math.abs(c - lvl) / lvl < 0.005);
    if (!nearby) clusters.push(lvl);
  }

  // Sort by distance from last close and return top N
  const lastClose = candles[candles.length - 1]?.close ?? 0;
  return clusters
    .sort((a, b) => Math.abs(a - lastClose) - Math.abs(b - lastClose))
    .slice(0, maxLevels);
}

/** Returns a UTC unix timestamp (seconds) for N days before today. */
function daysAgoUTC(days: number): number {
  const d = new Date();
  d.setUTCHours(0, 0, 0, 0);
  d.setUTCDate(d.getUTCDate() - days);
  return d.getTime() / 1000;
}

export const PriceChart: React.FC<PriceChartProps> = ({ indicatorToShow, timeframe = '1Y', overlays = new Set(), niftyCandles = [] }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const indicatorContainerRef = useRef<HTMLDivElement>(null);
  
  const mainChartRef = useRef<any>(null);
  const indChartRef = useRef<any>(null);

  const { 
    chartType, 
    candles, 
    heikinAshi, 
    renkoBricks, 
    lineBreakLines, 
    indicators,
    activeSymbol
  } = useStockStore();

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // 2. Select data series based on chart type
    let primaryData: any[] = [];
    let hasVolume = false;
    let volumeData: any[] = [];

    const isRenko = chartType === 'renko';
    const isLineBreak = chartType === 'line-break';

    // Helper to safely parse date string to UTC timestamp (seconds)
    const parseToTimestamp = (timeStr: string): number => {
      const [year, month, day] = timeStr.split('-').map(Number);
      return Date.UTC(year, month - 1, day) / 1000;
    };

    const timeMap = new Map<string, number>();
    let lastTime = 0;

    if (chartType === 'candles') {
      const uniqueCandles = candles.map(c => {
        let t = parseToTimestamp(c.time);
        if (t <= lastTime) t = lastTime + 1;
        lastTime = t;
        timeMap.set(c.time, t);
        return { ...c, time: t };
      });

      primaryData = uniqueCandles.map(c => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close
      }));
      hasVolume = true;
      volumeData = uniqueCandles.filter(c => c.volume !== undefined).map(c => ({
        time: c.time,
        value: c.volume || 0,
        color: c.close >= c.open ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)'
      }));
    } else if (chartType === 'heikin-ashi') {
      const uniqueHA = heikinAshi.map(c => {
        let t = parseToTimestamp(c.time);
        if (t <= lastTime) t = lastTime + 1;
        lastTime = t;
        timeMap.set(c.time, t);
        return { ...c, time: t };
      });

      primaryData = uniqueHA.map(c => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close
      }));
      hasVolume = true;
      volumeData = uniqueHA.filter(c => c.volume !== undefined).map(c => ({
        time: c.time,
        value: c.volume || 0,
        color: c.close >= c.open ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)'
      }));
    } else if (chartType === 'renko') {
      const uniqueRenko = renkoBricks.map(b => {
        let t = parseToTimestamp(b.time);
        if (t <= lastTime) t = lastTime + 1;
        lastTime = t;
        timeMap.set(b.time, t);
        return { ...b, time: t };
      });

      primaryData = uniqueRenko.map((b) => ({
        time: b.time,
        open: b.open,
        high: Math.max(b.open, b.close),
        low: Math.min(b.open, b.close),
        close: b.close
      }));
    } else if (chartType === 'line-break') {
      const uniqueLB = lineBreakLines.map(l => {
        let t = parseToTimestamp(l.time);
        if (t <= lastTime) t = lastTime + 1;
        lastTime = t;
        timeMap.set(l.time, t);
        return { ...l, time: t };
      });

      primaryData = uniqueLB.map((l) => ({
        time: l.time,
        open: l.open,
        high: Math.max(l.open, l.close),
        low: Math.min(l.open, l.close),
        close: l.close
      }));
    }

    if (primaryData.length === 0) return;

    // 3. Define responsive chart options
    const width = chartContainerRef.current.clientWidth;
    const height = indicatorToShow !== 'NONE' ? 380 : 500;

    const commonChartOptions: any = {
      layout: {
        background: { color: '#101217' },
        textColor: '#9ca3af',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#1e222d' },
        horzLines: { color: '#1e222d' },
      },
      crosshair: {
        mode: 1, // Magnet mode
        vertLine: {
          color: 'rgba(168, 85, 247, 0.4)',
          width: 1,
          style: 3, // dashed
          labelBackgroundColor: '#a855f7',
        },
        horzLine: {
          color: 'rgba(168, 85, 247, 0.4)',
          width: 1,
          style: 3, // dashed
          labelBackgroundColor: '#a855f7',
        },
      },
      timeScale: {
        borderColor: '#252a34',
        timeVisible: true,
        secondsVisible: false,
      },
    };

    // 4. Create main Price chart
    const mainChart: any = createChart(chartContainerRef.current, {
      ...commonChartOptions,
      width: width,
      height: height,
      rightPriceScale: {
        borderColor: '#252a34',
        autoScale: true,
      },
    } as any);
    mainChartRef.current = mainChart;

    // 5. Add custom brick or candle series
    const mainSeries = mainChart.addSeries(CandlestickSeries, {
      upColor: '#10b981',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });
    mainSeries.setData(primaryData);

    // Apply timeframe zoom after data is loaded
    if (timeframe === 'MAX') {
      mainChart.timeScale().fitContent();
    } else {
      const daysMap: Record<ChartTimeframe, number> = {
        '1W': 7, '1M': 30, '3M': 90, '6M': 180, '1Y': 365, 'MAX': 0,
      };
      const fromTs = daysAgoUTC(daysMap[timeframe]);
      const toTs = daysAgoUTC(0) + 86400; // today + 1 day buffer
      try {
        mainChart.timeScale().setVisibleRange({ from: fromTs as any, to: toTs as any });
      } catch { mainChart.timeScale().fitContent(); }
    }

    // 6. Draw SMA overlays (toggleable)
    if (!isRenko && !isLineBreak && indicators.length > 0) {
      const addSMA = (key: 'sma_20' | 'sma_50' | 'sma_200', title: string, color: string, width: number) => {
        const data: LineData[] = indicators
          .filter(ind => ind[key] != null && timeMap.has(ind.time))
          .map(ind => ({ time: timeMap.get(ind.time) as any, value: Number(ind[key]) }));
        if (data.length > 0) {
          const s = mainChart.addSeries(LineSeries, { color, lineWidth: width, title, priceLineVisible: false });
          s.setData(data);
        }
      };

      if (overlays.has('sma20'))  addSMA('sma_20',  'SMA 20',  '#3b82f6', 1.5);
      if (overlays.has('sma50'))  addSMA('sma_50',  'SMA 50',  '#f59e0b', 1.5);
      if (overlays.has('sma200')) addSMA('sma_200', 'SMA 200', '#ec4899', 2.0);
    }

    // 6b. EMA 9 / EMA 21 overlays
    if (overlays.has('ema9') && !isRenko && !isLineBreak && indicators.length > 0) {
      const ema9Data: LineData[] = indicators
        .filter(ind => ind.ema_9 != null && timeMap.has(ind.time))
        .map(ind => ({ time: timeMap.get(ind.time) as any, value: Number(ind.ema_9) }));
      if (ema9Data.length > 0) {
        const s = mainChart.addSeries(LineSeries, { color: '#22d3ee', lineWidth: 1, lineStyle: 1, title: 'EMA 9', priceLineVisible: false });
        s.setData(ema9Data);
      }
    }

    if (overlays.has('ema21') && !isRenko && !isLineBreak && indicators.length > 0) {
      const ema21Data: LineData[] = indicators
        .filter(ind => ind.ema_21 != null && timeMap.has(ind.time))
        .map(ind => ({ time: timeMap.get(ind.time) as any, value: Number(ind.ema_21) }));
      if (ema21Data.length > 0) {
        const s = mainChart.addSeries(LineSeries, { color: '#f97316', lineWidth: 1, lineStyle: 1, title: 'EMA 21', priceLineVisible: false });
        s.setData(ema21Data);
      }
    }

    // 6c. Bollinger Bands overlay
    if (overlays.has('bb') && !isRenko && !isLineBreak && indicators.length > 0) {
      const bbFilter = (key: 'bb_upper' | 'bb_middle' | 'bb_lower') =>
        indicators.filter(ind => ind[key] != null && timeMap.has(ind.time))
          .map(ind => ({ time: timeMap.get(ind.time) as any, value: Number(ind[key]) }));

      const bbUpper = bbFilter('bb_upper');
      const bbMiddle = bbFilter('bb_middle');
      const bbLower = bbFilter('bb_lower');

      if (bbUpper.length > 0) {
        const su = mainChart.addSeries(LineSeries, { color: 'rgba(148,163,184,0.5)', lineWidth: 1, lineStyle: 2, title: 'BB Upper', priceLineVisible: false });
        su.setData(bbUpper);
      }
      if (bbMiddle.length > 0) {
        const sm = mainChart.addSeries(LineSeries, { color: 'rgba(148,163,184,0.3)', lineWidth: 1, lineStyle: 2, title: 'BB Mid', priceLineVisible: false });
        sm.setData(bbMiddle);
      }
      if (bbLower.length > 0) {
        const sl = mainChart.addSeries(LineSeries, { color: 'rgba(148,163,184,0.5)', lineWidth: 1, lineStyle: 2, title: 'BB Lower', priceLineVisible: false });
        sl.setData(bbLower);
      }
    }

    // 6d. Auto Support & Resistance levels
    if (overlays.has('sr') && primaryData.length > 10) {
      const srcCandles = chartType === 'candles' ? candles
        : chartType === 'heikin-ashi' ? heikinAshi : [];
      if (srcCandles.length > 0) {
        const levels = detectSRLevels(srcCandles);
        const lastTs = primaryData[primaryData.length - 1]?.time as number;
        const firstTs = primaryData[0]?.time as number;
        for (const lvl of levels) {
          const srSeries = mainChart.addSeries(LineSeries, {
            color: 'rgba(251, 191, 36, 0.55)',
            lineWidth: 1,
            lineStyle: 1, // dashed
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          srSeries.setData([
            { time: firstTs as any, value: lvl },
            { time: lastTs as any,  value: lvl },
          ]);
        }
      }
    }

    // 6e. NIFTY 50 normalised overlay (% change from first visible candle)
    if (overlays.has('nifty') && niftyCandles.length > 0 && primaryData.length > 0) {
      // Build a map: date-string → nifty close
      const niftyMap = new Map<string, number>(niftyCandles.map(c => [c.time, c.close]));
      // Match NIFTY dates to the stock's timeMap
      const niftyPts: { time: number; close: number }[] = [];
      for (const c of candles) {
        const nc = niftyMap.get(c.time);
        const ts = timeMap.get(c.time);
        if (nc != null && ts != null) niftyPts.push({ time: ts, close: nc });
      }
      if (niftyPts.length > 1) {
        const base = niftyPts[0].close;
        const stockBase = primaryData[0]?.close ?? primaryData[0]?.value ?? (candles[0]?.close ?? 1);
        // Scale NIFTY to same starting price as stock
        const niftyScaled: LineData[] = niftyPts.map(p => ({
          time: p.time as any,
          value: stockBase * (p.close / base),
        }));
        const niftySeries = mainChart.addSeries(LineSeries, {
          color: 'rgba(251,191,36,0.7)',
          lineWidth: 1.5,
          lineStyle: 0,
          title: 'NIFTY',
          priceLineVisible: false,
          lastValueVisible: true,
        });
        niftySeries.setData(niftyScaled);
      }
    }

    // 7. Add Volume overlay histogram on Price chart
    if (hasVolume && volumeData.length > 0) {
      const volumeSeries = mainChart.addSeries(HistogramSeries, {
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: '', // set overlay
      });
      volumeSeries.setData(volumeData);
      
      mainChart.priceScale('').applyOptions({
        scaleMargins: {
          top: 0.75, // volume at bottom
          bottom: 0,
        },
      });
    }

    // 8. Handle dynamic indicator lower pane synchronizer
    let indChart: any = null;

    if (indicatorToShow !== 'NONE' && indicatorContainerRef.current && indicators.length > 0) {
      indChart = createChart(indicatorContainerRef.current, {
        ...commonChartOptions,
        width: width,
        height: 180,
        rightPriceScale: {
          borderColor: '#252a34',
        },
      } as any);
      indChartRef.current = indChart;

      if (indicatorToShow === 'RSI') {
        const rsiData: LineData[] = indicators
          .filter(ind => ind.rsi_14 !== null && ind.rsi_14 !== undefined && timeMap.has(ind.time))
          .map(ind => ({
            time: timeMap.get(ind.time) as any,
            value: Number(ind.rsi_14)
          }));

        if (rsiData.length > 0) {
          const rsiSeries = indChart.addSeries(LineSeries, {
            color: '#a855f7', // purple glow
            lineWidth: 1.5,
            title: 'RSI 14'
          });
          rsiSeries.setData(rsiData);

          // Add overbought / oversold lines at 70 / 30
          const rsiUpper = indChart.addSeries(LineSeries, {
            color: 'rgba(239, 68, 68, 0.3)',
            lineWidth: 1,
            lineStyle: 3,
            priceLineVisible: false
          });
          rsiUpper.setData(rsiData.map(d => ({ time: d.time, value: 70 })));

          const rsiLower = indChart.addSeries(LineSeries, {
            color: 'rgba(16, 185, 129, 0.3)',
            lineWidth: 1,
            lineStyle: 3,
            priceLineVisible: false
          });
          rsiLower.setData(rsiData.map(d => ({ time: d.time, value: 30 })));
        }
      } else if (indicatorToShow === 'MACD') {
        const macdLineData: LineData[] = indicators
          .filter(ind => ind.macd_line !== null && ind.macd_line !== undefined && timeMap.has(ind.time))
          .map(ind => ({
            time: timeMap.get(ind.time) as any,
            value: Number(ind.macd_line)
          }));

        const macdSignalData: LineData[] = indicators
          .filter(ind => ind.macd_signal !== null && ind.macd_signal !== undefined && timeMap.has(ind.time))
          .map(ind => ({
            time: timeMap.get(ind.time) as any,
            value: Number(ind.macd_signal)
          }));

        const macdHistData: HistogramData[] = indicators
          .filter(ind => ind.macd_histogram !== null && ind.macd_histogram !== undefined && timeMap.has(ind.time))
          .map(ind => {
            const val = Number(ind.macd_histogram);
            return {
              time: timeMap.get(ind.time) as any,
              value: val,
              color: val >= 0 ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'
            };
          });

        if (macdLineData.length > 0) {
          const macdLineSeries = indChart.addSeries(LineSeries, {
            color: '#2563eb', // blue
            lineWidth: 1.5,
            title: 'MACD'
          });
          macdLineSeries.setData(macdLineData);

          const signalSeries = indChart.addSeries(LineSeries, {
            color: '#f59e0b', // amber
            lineWidth: 1.5,
            title: 'Signal'
          });
          signalSeries.setData(macdSignalData);

          const histSeries = indChart.addSeries(HistogramSeries, {
            title: 'Histogram'
          });
          histSeries.setData(macdHistData);
        }
      }

      // 9. Synchronize horizontal scrolling time scales
      let isSyncing = false;
      
      const mainTimeScale = mainChart.timeScale();
      const indTimeScale = indChart.timeScale();

      mainTimeScale.subscribeVisibleLogicalRangeChange((range: any) => {
        if (isSyncing) return;
        isSyncing = true;
        if (range) indTimeScale.setVisibleLogicalRange(range);
        isSyncing = false;
      });

      indTimeScale.subscribeVisibleLogicalRangeChange((range: any) => {
        if (isSyncing) return;
        isSyncing = true;
        if (range) mainTimeScale.setVisibleLogicalRange(range);
        isSyncing = false;
      });
    }

    // 10. Handle container resizing smoothly
    const handleResize = () => {
      if (!chartContainerRef.current) return;
      const w = chartContainerRef.current.clientWidth;
      mainChart.resize(w, height);
      if (indChart) indChart.resize(w, 180);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (mainChartRef.current) {
        mainChartRef.current.remove();
        mainChartRef.current = null;
      }
      if (indChartRef.current) {
        indChartRef.current.remove();
        indChartRef.current = null;
      }
    };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    chartType,
    candles,
    heikinAshi,
    renkoBricks,
    lineBreakLines,
    indicators,
    indicatorToShow,
    timeframe,
    overlays,
    niftyCandles,
    activeSymbol,
  ]);

  return (
    <div className="flex flex-col gap-2 w-full">
      <div 
        ref={chartContainerRef} 
        className="w-full rounded-xl overflow-hidden border border-slate-800/80 bg-[#101217]"
      />
      {indicatorToShow !== 'NONE' && (
        <div 
          ref={indicatorContainerRef} 
          className="w-full rounded-xl overflow-hidden border border-slate-800/80 bg-[#101217]"
        />
      )}
    </div>
  );
};
