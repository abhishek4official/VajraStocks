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

interface PriceChartProps {
  indicatorToShow: 'RSI' | 'MACD' | 'NONE';
}

export const PriceChart: React.FC<PriceChartProps> = ({ indicatorToShow }) => {
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

    // 6. Draw SMAs overlay on Price chart (only for Candlesticks and Heikin-Ashi)
    let sma20Series: any = null;
    let sma50Series: any = null;
    let sma200Series: any = null;

    if (!isRenko && !isLineBreak && indicators.length > 0) {
      const sma20Data: LineData[] = indicators
        .filter(ind => ind.sma_20 !== null && ind.sma_20 !== undefined && timeMap.has(ind.time))
        .map(ind => ({
          time: timeMap.get(ind.time) as any,
          value: Number(ind.sma_20)
        }));
      
      const sma50Data: LineData[] = indicators
        .filter(ind => ind.sma_50 !== null && ind.sma_50 !== undefined && timeMap.has(ind.time))
        .map(ind => ({
          time: timeMap.get(ind.time) as any,
          value: Number(ind.sma_50)
        }));

      const sma200Data: LineData[] = indicators
        .filter(ind => ind.sma_200 !== null && ind.sma_200 !== undefined && timeMap.has(ind.time))
        .map(ind => ({
          time: timeMap.get(ind.time) as any,
          value: Number(ind.sma_200)
        }));

      if (sma20Data.length > 0) {
        sma20Series = mainChart.addSeries(LineSeries, {
          color: '#3b82f6', // sleek blue
          lineWidth: 1.5,
          title: 'SMA 20',
          priceLineVisible: false
        });
        sma20Series.setData(sma20Data);
      }

      if (sma50Data.length > 0) {
        sma50Series = mainChart.addSeries(LineSeries, {
          color: '#f59e0b', // warm amber
          lineWidth: 1.5,
          title: 'SMA 50',
          priceLineVisible: false
        });
        sma50Series.setData(sma50Data);
      }

      if (sma200Data.length > 0) {
        sma200Series = mainChart.addSeries(LineSeries, {
          color: '#ec4899', // hot pink
          lineWidth: 2.0,
          title: 'SMA 200',
          priceLineVisible: false
        });
        sma200Series.setData(sma200Data);
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

  }, [
    chartType, 
    candles, 
    heikinAshi, 
    renkoBricks, 
    lineBreakLines, 
    indicators, 
    indicatorToShow,
    activeSymbol
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
