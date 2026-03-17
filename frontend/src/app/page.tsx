'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createChart, ColorType, IChartApi, ISeriesApi, CandlestickSeries, LineSeries, HistogramSeries, BaselineSeries, Time, LogicalRange } from 'lightweight-charts';

// Define a type for our signal object
interface Signal {
  pair: string;
  type: string;
  time: string;
  reason: string;
}

// Define the bot data structure
interface BotData {
  status: string;
  last_check: string;
  signals: Signal[];
  active_settings?: {
    strategy?: string | null;
    strategies?: string[];
    timeframe: string;
    repeat_alerts: boolean;
  };
  metrics: Record<string, { mso: number; macd: number; trend: string; price: number } | undefined>;
}

interface AlertConfigData {
  telegram_token: string;
  telegram_chat_id: string;
  active_strategies: string[];
  timeframe: string;
  repeat_alerts: boolean;
}

interface ChartRow {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  ema9: number | null;
  ema18: number | null;
  mso: number | null;
  macdLine: number | null;
  macdSignal: number | null;
  cycleHist: number | null;
}

const API_BASE_URL = 'http://localhost:8000';

const STRATEGY_OPTIONS = [
  { id: 'ema_cross_9_18', label: 'EMA Cross 9/18' },
  { id: 'macd_cross', label: 'MACD Cross' },
  { id: 'market_structure_85_15', label: 'Market Structure Oscillator 85/15' },
];

const ALERT_TIMEFRAME_OPTIONS = ['1m', '5m', '15m', '1h', '4h'];

const getStrategyLabel = (strategyId?: string) => {
  if (!strategyId) {
    return '--';
  }
  const matched = STRATEGY_OPTIONS.find((strategy) => strategy.id === strategyId);
  return matched ? matched.label : strategyId;
};

export default function Dashboard() {
  const [mounted, setMounted] = useState(false);
  const [botData, setBotData] = useState<BotData | null>(null);
  const [activePair, setActivePair] = useState('ETH/USDT');
  const [chartTimeframe, setChartTimeframe] = useState('1h');
  const [alertConfig, setAlertConfig] = useState<AlertConfigData>({
    telegram_token: '',
    telegram_chat_id: '',
    active_strategies: ['ema_cross_9_18'],
    timeframe: '1h',
    repeat_alerts: false,
  });
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const [configNotice, setConfigNotice] = useState<string | null>(null);
  
  const priceChartContainerRef = useRef<HTMLDivElement>(null);
  const oscillatorChartContainerRef = useRef<HTMLDivElement>(null);

  const priceChartRef = useRef<IChartApi | null>(null);
  const oscillatorChartRef = useRef<IChartApi | null>(null);

  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const ema9Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ema18Ref = useRef<ISeriesApi<"Line"> | null>(null);

  const msoRef = useRef<ISeriesApi<"Line"> | null>(null);
  const msoAreaRef = useRef<ISeriesApi<"Baseline"> | null>(null);
  const macdLineRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdSignalRef = useRef<ISeriesApi<"Line"> | null>(null);
  const cycleHistRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const topZoneRef = useRef<ISeriesApi<"Baseline"> | null>(null);
  const bottomZoneRef = useRef<ISeriesApi<"Baseline"> | null>(null);
  const oscUpperBandRef = useRef<ISeriesApi<"Line"> | null>(null);
  const oscMidBandRef = useRef<ISeriesApi<"Line"> | null>(null);
  const oscLowerBandRef = useRef<ISeriesApi<"Line"> | null>(null);

  // Fetch bot general state
  const fetchState = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/state`);
      if (res.ok) {
        const data = await res.json();
        setBotData(data);
      }
    } catch (err) {
      console.error("Failed to connect to Bot API", err);
    }
  }, []);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/config`);
      if (!res.ok) {
        return;
      }

      const payload = await res.json();
      if (payload.status === 'success' && payload.data) {
        const activeStrategies = Array.isArray(payload.data.active_strategies)
          ? payload.data.active_strategies.filter((value: unknown): value is string => typeof value === 'string')
          : (typeof payload.data.active_strategy === 'string' ? [payload.data.active_strategy] : []);

        setAlertConfig({
          telegram_token: payload.data.telegram_token ?? '',
          telegram_chat_id: payload.data.telegram_chat_id ?? '',
          active_strategies: activeStrategies.length > 0 ? activeStrategies : ['ema_cross_9_18'],
          timeframe: payload.data.timeframe ?? '1h',
          repeat_alerts: Boolean(payload.data.repeat_alerts),
        });
      }
    } catch (err) {
      console.error('Failed to fetch alert config', err);
    }
  }, []);

  const saveAlertConfig = useCallback(async () => {
    if (alertConfig.active_strategies.length === 0) {
      setConfigNotice('Wybierz co najmniej jedną strategię.');
      return;
    }

    setIsSavingConfig(true);
    setConfigNotice(null);

    try {
      const res = await fetch(`${API_BASE_URL}/api/config`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(alertConfig),
      });

      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        throw new Error(payload?.detail || 'Nie udało się zapisać konfiguracji alertów.');
      }

      const payload = await res.json();
      if (payload.status === 'success' && payload.data) {
        const activeStrategies = Array.isArray(payload.data.active_strategies)
          ? payload.data.active_strategies.filter((value: unknown): value is string => typeof value === 'string')
          : (typeof payload.data.active_strategy === 'string' ? [payload.data.active_strategy] : []);

        setAlertConfig({
          telegram_token: payload.data.telegram_token ?? '',
          telegram_chat_id: payload.data.telegram_chat_id ?? '',
          active_strategies: activeStrategies.length > 0 ? activeStrategies : alertConfig.active_strategies,
          timeframe: payload.data.timeframe ?? alertConfig.timeframe,
          repeat_alerts: Boolean(payload.data.repeat_alerts),
        });
      }

      setConfigNotice('Konfiguracja alertów została zapisana.');
      fetchState();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Błąd zapisu konfiguracji alertów.';
      setConfigNotice(message);
    } finally {
      setIsSavingConfig(false);
    }
  }, [alertConfig, fetchState]);

  const toggleStrategy = useCallback((strategyId: string, enabled: boolean) => {
    setAlertConfig((prev) => {
      if (enabled) {
        if (prev.active_strategies.includes(strategyId)) {
          return prev;
        }
        return { ...prev, active_strategies: [...prev.active_strategies, strategyId] };
      }

      if (!prev.active_strategies.includes(strategyId) || prev.active_strategies.length === 1) {
        return prev;
      }

      return {
        ...prev,
        active_strategies: prev.active_strategies.filter((id) => id !== strategyId),
      };
    });
  }, []);

  // Fetch specific chart data
  const fetchChartData = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/chart?symbol=${activePair.replace('/', '%2F')}&timeframe=${chartTimeframe}`);
      if (res.ok) {
        const payload = await res.json();
        if (payload.status === "success" && Array.isArray(payload.data)) {
          const data = payload.data as ChartRow[];
          const toTime = (timestamp: number): Time => timestamp as Time;

          const chartBars = data.map((d) => ({
            time: toTime(d.time),
            open: d.open,
            high: d.high,
            low: d.low,
            close: d.close,
          }));

          const ema9Data = data
            .filter((d) => d.ema9 !== null)
            .map((d) => ({ time: toTime(d.time), value: d.ema9 as number }));

          const ema18Data = data
            .filter((d) => d.ema18 !== null)
            .map((d) => ({ time: toTime(d.time), value: d.ema18 as number }));

          const msoData = data
            .filter((d) => d.mso !== null)
            .map((d) => ({ time: toTime(d.time), value: d.mso as number }));

          const msoAreaData = msoData;

          const macdLineData = data
            .filter((d) => d.macdLine !== null)
            .map((d) => ({ time: toTime(d.time), value: d.macdLine as number }));

          const macdSignalData = data
            .filter((d) => d.macdSignal !== null)
            .map((d) => ({ time: toTime(d.time), value: d.macdSignal as number }));

          const cycleHistBase = data
            .filter((d) => d.cycleHist !== null)
            .map((d) => ({ time: toTime(d.time), value: d.cycleHist as number }));

          const cycleHistData = cycleHistBase.map((point, index) => {
            const prevValue = index > 0 ? cycleHistBase[index - 1].value : point.value;
            const rising = point.value >= prevValue;
            const color = point.value >= 50
              ? (rising ? 'rgba(193, 230, 214, 0.85)' : 'rgba(143, 199, 178, 0.78)')
              : (rising ? 'rgba(217, 165, 177, 0.80)' : 'rgba(201, 125, 147, 0.82)');

            return {
              time: point.time,
              value: point.value,
              color,
            };
          });

          const oscUpperBand = data.map((d) => ({ time: toTime(d.time), value: 85 }));
          const oscMidBand = data.map((d) => ({ time: toTime(d.time), value: 50 }));
          const oscLowerBand = data.map((d) => ({ time: toTime(d.time), value: 15 }));
          const topZoneData = data.map((d) => ({ time: toTime(d.time), value: 100 }));
          const bottomZoneData = data.map((d) => ({ time: toTime(d.time), value: 0 }));
          
          if (seriesRef.current) {
            seriesRef.current.setData(chartBars);
          }
          if (ema9Ref.current) {
            ema9Ref.current.setData(ema9Data);
          }
          if (ema18Ref.current) {
            ema18Ref.current.setData(ema18Data);
          }
          if (msoRef.current) {
            msoRef.current.setData(msoData);
          }
          if (msoAreaRef.current) {
            msoAreaRef.current.setData(msoAreaData);
          }
          if (macdLineRef.current) {
            macdLineRef.current.setData(macdLineData);
          }
          if (macdSignalRef.current) {
            macdSignalRef.current.setData(macdSignalData);
          }
          if (cycleHistRef.current) {
            cycleHistRef.current.setData(cycleHistData);
          }
          if (oscUpperBandRef.current) {
            oscUpperBandRef.current.setData(oscUpperBand);
          }
          if (oscMidBandRef.current) {
            oscMidBandRef.current.setData(oscMidBand);
          }
          if (oscLowerBandRef.current) {
            oscLowerBandRef.current.setData(oscLowerBand);
          }
          if (topZoneRef.current) {
            topZoneRef.current.setData(topZoneData);
          }
          if (bottomZoneRef.current) {
            bottomZoneRef.current.setData(bottomZoneData);
          }
        }
      }
    } catch (err) {
      console.error("Failed to fetch chart data", err);
    }
  }, [activePair, chartTimeframe]);

  // Init
  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    fetchConfig();
  }, [mounted, fetchConfig]);

  useEffect(() => {
    if (!mounted) return;
    fetchState();
    
    // Auto-refresh data and chart
    const interval = setInterval(() => {
        fetchState();
        fetchChartData();
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchState, fetchChartData, mounted]);

  // Handle Chart Structure and Resize (re-runs when Pair or Timeframe changes to properly flush/re-init)
  useEffect(() => {
    if (!mounted || !priceChartContainerRef.current || !oscillatorChartContainerRef.current) return;

    if (priceChartRef.current) {
      try {
        priceChartRef.current.remove();
      } catch {
        // Ignore already disposed errors
      }
      priceChartRef.current = null;
    }

    if (oscillatorChartRef.current) {
      try {
        oscillatorChartRef.current.remove();
      } catch {
        // Ignore already disposed errors
      }
      oscillatorChartRef.current = null;
    }

    const priceChart = createChart(priceChartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#8b949e',
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
      },
      rightPriceScale: {
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
      leftPriceScale: {
        visible: false,
      },
      width: priceChartContainerRef.current.clientWidth,
      height: 320,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const oscillatorChart = createChart(oscillatorChartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#8b949e',
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.03)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.06)' },
      },
      rightPriceScale: {
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
      leftPriceScale: {
        visible: false,
      },
      width: oscillatorChartContainerRef.current.clientWidth,
      height: 220,
      handleScroll: false,
      handleScale: false,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
    });

    priceChartRef.current = priceChart;
    oscillatorChartRef.current = oscillatorChart;

    const candlestickSeries = priceChart.addSeries(CandlestickSeries, {
      upColor: '#3fb950',
      downColor: '#f85149',
      borderVisible: false,
      wickUpColor: '#3fb950',
      wickDownColor: '#f85149',
      priceLineVisible: false,
      lastValueVisible: true,
    });

    const ema9Series = priceChart.addSeries(LineSeries, {
        color: '#3b82f6',
        lineWidth: 1,
        crosshairMarkerVisible: false,
        priceLineVisible: false,
        lastValueVisible: false,
    });

    const ema18Series = priceChart.addSeries(LineSeries, {
        color: '#f59e0b',
        lineWidth: 1,
        crosshairMarkerVisible: false,
        priceLineVisible: false,
        lastValueVisible: false,
    });

    const topZoneSeries = oscillatorChart.addSeries(BaselineSeries, {
      baseValue: { type: 'price', price: 85 },
      topFillColor1: 'rgba(177, 53, 75, 0.36)',
      topFillColor2: 'rgba(104, 32, 44, 0.04)',
      topLineColor: 'rgba(177, 53, 75, 0.04)',
      bottomFillColor1: 'rgba(0, 0, 0, 0)',
      bottomFillColor2: 'rgba(0, 0, 0, 0)',
      bottomLineColor: 'rgba(0, 0, 0, 0)',
      lineWidth: 1,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const bottomZoneSeries = oscillatorChart.addSeries(BaselineSeries, {
      baseValue: { type: 'price', price: 15 },
      topFillColor1: 'rgba(0, 0, 0, 0)',
      topFillColor2: 'rgba(0, 0, 0, 0)',
      topLineColor: 'rgba(0, 0, 0, 0)',
      bottomFillColor1: 'rgba(38, 149, 129, 0.30)',
      bottomFillColor2: 'rgba(20, 80, 69, 0.04)',
      bottomLineColor: 'rgba(38, 149, 129, 0.04)',
      lineWidth: 1,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const cycleHistogramSeries = oscillatorChart.addSeries(HistogramSeries, {
      priceFormat: {
        type: 'price',
        precision: 2,
        minMove: 0.01,
      }, 
      base: 50,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const msoAreaSeries = oscillatorChart.addSeries(BaselineSeries, {
      baseValue: { type: 'price', price: 50 },
      topFillColor1: 'rgba(109, 224, 205, 0.30)',
      topFillColor2: 'rgba(109, 224, 205, 0.03)',
      topLineColor: 'rgba(130, 235, 219, 0.70)',
      bottomFillColor1: 'rgba(238, 98, 126, 0.28)',
      bottomFillColor2: 'rgba(238, 98, 126, 0.03)',
      bottomLineColor: 'rgba(247, 146, 166, 0.64)',
      lineWidth: 1,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const msoSeries = oscillatorChart.addSeries(LineSeries, {
      color: 'rgba(182, 239, 227, 0.88)',
      lineWidth: 1,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const macdLineSeries = oscillatorChart.addSeries(LineSeries, {
      color: '#1e63ff',
      lineWidth: 2,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const macdSignalSeries = oscillatorChart.addSeries(LineSeries, {
      color: '#ff8a00',
      lineWidth: 2,
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const upperBandSeries = oscillatorChart.addSeries(LineSeries, {
      color: 'rgba(190, 84, 95, 0.38)',
        lineWidth: 1,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
    });

    const midBandSeries = oscillatorChart.addSeries(LineSeries, {
      color: 'rgba(218, 224, 236, 0.40)',
        lineWidth: 1,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
    });

    const lowerBandSeries = oscillatorChart.addSeries(LineSeries, {
      color: 'rgba(79, 171, 151, 0.38)',
        lineWidth: 1,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
    });

    seriesRef.current = candlestickSeries as ISeriesApi<"Candlestick">;
    ema9Ref.current = ema9Series as ISeriesApi<"Line">;
    ema18Ref.current = ema18Series as ISeriesApi<"Line">;
    topZoneRef.current = topZoneSeries as ISeriesApi<"Baseline">;
    bottomZoneRef.current = bottomZoneSeries as ISeriesApi<"Baseline">;
    cycleHistRef.current = cycleHistogramSeries as ISeriesApi<"Histogram">;
    msoAreaRef.current = msoAreaSeries as ISeriesApi<"Baseline">;
    msoRef.current = msoSeries as ISeriesApi<"Line">;
    macdLineRef.current = macdLineSeries as ISeriesApi<"Line">;
    macdSignalRef.current = macdSignalSeries as ISeriesApi<"Line">;
    oscUpperBandRef.current = upperBandSeries as ISeriesApi<"Line">;
    oscMidBandRef.current = midBandSeries as ISeriesApi<"Line">;
    oscLowerBandRef.current = lowerBandSeries as ISeriesApi<"Line">;

    const syncRange = (range: LogicalRange | null) => {
      if (range) {
        oscillatorChart.timeScale().setVisibleLogicalRange(range);
      }
    };

    priceChart.timeScale().subscribeVisibleLogicalRangeChange(syncRange);

    // Fetch initial chart data
    fetchChartData();

    const handleResize = () => {
      if (priceChartContainerRef.current) {
        priceChart.applyOptions({ width: priceChartContainerRef.current.clientWidth });
      }
      if (oscillatorChartContainerRef.current) {
        oscillatorChart.applyOptions({ width: oscillatorChartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);

      try {
        priceChart.timeScale().unsubscribeVisibleLogicalRangeChange(syncRange);
      } catch {
        // Ignore cleanup errors
      }

      try {
        priceChart.remove();
      } catch {
        // Ignore already disposed errors
      }

      try {
        oscillatorChart.remove();
      } catch {
        // Ignore already disposed errors
      }

      if (priceChartRef.current === priceChart) {
        priceChartRef.current = null;
      }
      if (oscillatorChartRef.current === oscillatorChart) {
        oscillatorChartRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted, activePair, chartTimeframe]); 

  const activeBotStrategies = botData?.active_settings?.strategies && botData.active_settings.strategies.length > 0
    ? botData.active_settings.strategies
    : (botData?.active_settings?.strategy ? [botData.active_settings.strategy] : []);

  if (!mounted) return null;

  return (
    <div className="dashboard-container">
      <header className="header fade-in">
        <h1>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
          </svg>
          AI Trading Crypto Bot
        </h1>
        <div className="flex gap-4 items-center">
            {botData ? (
                <div className="status-badge">
                <div className="status-dot"></div>
                {botData.status}
                </div>
            ) : (
                <div className="status-badge" style={{ background: 'rgba(248, 81, 73, 0.1)', color: 'var(--danger)', borderColor: 'rgba(248, 81, 73, 0.2)'}}>
                <div className="status-dot" style={{ background: 'var(--danger)', boxShadow: '0 0 8px var(--danger)' }}></div>
                Brak połączenia z API
                </div>
            )}
        </div>
      </header>

      <div className="dashboard-grid">
        
        {/* Data & Chart Panel */}
        <div className="glass-panel col-span-8 fade-in" style={{ animationDelay: '0.1s' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
                <h2 className="panel-title" style={{ marginBottom: 0 }}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                    <line x1="8" y1="21" x2="16" y2="21"></line>
                    <line x1="12" y1="17" x2="12" y2="21"></line>
                    </svg>
                    Live ByBit
                </h2>
                <div style={{ display: 'flex', gap: '20px', alignItems: 'center', flexWrap: 'wrap' }}>
                    
                    <div style={{ display: 'flex', gap: '5px', background: 'rgba(0,0,0,0.2)', padding: '4px', borderRadius: '8px' }}>
                        {['1m', '5m', '15m', '1h', '4h', '1d'].map(tf => (
                            <button 
                                key={tf}
                          onClick={() => setChartTimeframe(tf)}
                                style={{
                            background: chartTimeframe === tf ? 'rgba(63, 185, 80, 0.1)' : 'transparent',
                                    border: 'none',
                            color: chartTimeframe === tf ? 'var(--success)' : 'var(--text-secondary)',
                                    padding: '0.3rem 0.6rem',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    fontSize: '0.85rem',
                            fontWeight: chartTimeframe === tf ? 600 : 400,
                                    transition: 'all 0.2s'
                                }}
                            >
                                {tf}
                            </button>
                        ))}
                    </div>

                    <div style={{ display: 'flex', gap: '5px' }}>
                        {['ETH/USDT', 'BTC/USDT'].map(pair => (
                            <button 
                                key={pair}
                                onClick={() => setActivePair(pair)}
                                style={{
                                    background: activePair === pair ? 'var(--accent-glow)' : 'rgba(0,0,0,0.2)',
                                    border: `1px solid ${activePair === pair ? 'var(--accent-color)' : 'var(--panel-border)'}`,
                                    color: activePair === pair ? 'var(--accent-color)' : 'var(--text-secondary)',
                                    padding: '0.3rem 0.8rem',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    fontSize: '0.9rem',
                                    fontWeight: activePair === pair ? 600 : 400
                                }}
                            >
                                {pair}
                            </button>
                        ))}
                    </div>
                </div>
            </div>
          
            {/* Chart Container */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
               <div ref={priceChartContainerRef} style={{ width: '100%', height: '320px', borderRadius: '8px', overflow: 'hidden' }} />
               <div ref={oscillatorChartContainerRef} style={{ width: '100%', height: '220px', borderRadius: '8px', overflow: 'hidden' }} />
              </div>
            
            {/* Legend for chart */}
              <div style={{ display: 'flex', gap: '15px', marginTop: '10px', fontSize: '0.8rem', color: 'var(--text-secondary)', flexWrap: 'wrap' }}>
                 <div style={{display: 'flex', alignItems: 'center', gap: '5px'}}><span style={{display: 'inline-block', width: '10px', height: '2px', background: '#3b82f6'}}></span> EMA 9</div>
                 <div style={{display: 'flex', alignItems: 'center', gap: '5px'}}><span style={{display: 'inline-block', width: '10px', height: '2px', background: '#f59e0b'}}></span> EMA 18</div>
                <div style={{display: 'flex', alignItems: 'center', gap: '5px'}}><span style={{display: 'inline-block', width: '10px', height: '2px', background: '#b6efe3'}}></span> MSO (panel dolny)</div>
                <div style={{display: 'flex', alignItems: 'center', gap: '5px'}}><span style={{display: 'inline-block', width: '10px', height: '2px', background: '#1e63ff'}}></span> MACD line</div>
                <div style={{display: 'flex', alignItems: 'center', gap: '5px'}}><span style={{display: 'inline-block', width: '10px', height: '2px', background: '#ff8a00'}}></span> Signal line</div>
                <div style={{display: 'flex', alignItems: 'center', gap: '5px'}}><span style={{display: 'inline-block', width: '10px', height: '8px', background: '#9ad4c6'}}></span> Cycle histogram (LuxAlgo)</div>
            </div>

            <div className="dashboard-grid" style={{ marginTop: '1.5rem', marginBottom: '1.5rem' }}>
                <div className="glass-panel col-span-6" style={{ padding: '1rem', background: 'rgba(0,0,0,0.2)' }}>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Market Structure Oscillator (MSO) <span style={{fontSize: '0.7rem', fontWeight: 400}}>(bot logic status)</span></div>
                    <div style={{ 
                        fontSize: '1.8rem', 
                        fontWeight: 600, 
                        color: botData?.metrics[activePair]?.mso !== undefined ? (botData.metrics[activePair]!.mso > 50 ? 'var(--success)' : 'var(--danger)') : 'inherit',
                        marginTop: '0.5rem' 
                    }}>
                        {botData?.metrics[activePair]?.mso !== undefined ? botData.metrics[activePair]!.mso.toFixed(1) : '--'}
                    </div>
                </div>
                <div className="glass-panel col-span-6" style={{ padding: '1rem', background: 'rgba(0,0,0,0.2)' }}>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Norm MACD & Trend <span style={{fontSize: '0.7rem', fontWeight: 400}}>(bot logic status)</span></div>
                    <div style={{ 
                        fontSize: '1.8rem', 
                        fontWeight: 600, 
                        color: botData?.metrics[activePair]?.trend === 'Byczy' ? 'var(--success)' : 'var(--danger)',
                        marginTop: '0.5rem',
                        display: 'flex',
                        alignItems: 'baseline',
                        gap: '10px'
                    }}>
                        {botData?.metrics[activePair]?.macd !== undefined ? botData.metrics[activePair]!.macd.toFixed(1) : '--'}
                        <span style={{ fontSize: '1rem', fontWeight: 400 }}>({botData?.metrics[activePair]?.trend || '--'})</span>
                    </div>
                </div>
            </div>

         </div>

        {/* Signals Sidebar */}
        <div className="col-span-4 fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', animationDelay: '0.2s' }}>

          {/* Alert Settings Panel */}
          <div className="glass-panel">
            <h2 className="panel-title">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 1v22"></path>
                <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7H14a3.5 3.5 0 0 1 0 7H6"></path>
              </svg>
              Ustawienia Alertów
            </h2>

            <div className="form-group">
              <label>Aktywne strategie</label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {STRATEGY_OPTIONS.map((strategy) => (
                  <label
                    key={strategy.id}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}
                  >
                    <input
                      type="checkbox"
                      checked={alertConfig.active_strategies.includes(strategy.id)}
                      onChange={(event) => toggleStrategy(strategy.id, event.target.checked)}
                    />
                    {strategy.label}
                  </label>
                ))}
              </div>
              <div style={{ marginTop: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                Możesz mieć aktywnych kilka strategii jednocześnie.
              </div>
            </div>

            <div className="form-group">
              <label>Timeframe alertów</label>
              <select
                className="form-input"
                value={alertConfig.timeframe}
                onChange={(event) => setAlertConfig((prev) => ({ ...prev, timeframe: event.target.value }))}
              >
                {ALERT_TIMEFRAME_OPTIONS.map((tf) => (
                  <option key={tf} value={tf}>
                    {tf}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label>Telegram Bot Token</label>
              <input
                className="form-input"
                type="password"
                placeholder="Wklej token bota"
                value={alertConfig.telegram_token}
                onChange={(event) => setAlertConfig((prev) => ({ ...prev, telegram_token: event.target.value }))}
              />
            </div>

            <div className="form-group">
              <label>Telegram Chat ID</label>
              <input
                className="form-input"
                type="text"
                placeholder="Np. 123456789"
                value={alertConfig.telegram_chat_id}
                onChange={(event) => setAlertConfig((prev) => ({ ...prev, telegram_chat_id: event.target.value }))}
              />
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              <input
                type="checkbox"
                checked={alertConfig.repeat_alerts}
                onChange={(event) => setAlertConfig((prev) => ({ ...prev, repeat_alerts: event.target.checked }))}
              />
              Ponawiaj alerty, gdy warunek trwa przez kolejne świece
            </label>

            <button
              className="btn-primary"
              onClick={saveAlertConfig}
              disabled={isSavingConfig}
              style={{ opacity: isSavingConfig ? 0.7 : 1, cursor: isSavingConfig ? 'wait' : 'pointer' }}
            >
              {isSavingConfig ? 'Zapisywanie...' : 'Zapisz ustawienia'}
            </button>

            {configNotice && (
              <div style={{ marginTop: '0.75rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                {configNotice}
              </div>
            )}

            {botData?.active_settings && (
              <div style={{ marginTop: '0.75rem', fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                <div>Aktywne po stronie bota: {activeBotStrategies.length > 0 ? activeBotStrategies.map((strategyId) => getStrategyLabel(strategyId)).join(', ') : '--'}</div>
                <div>Timeframe: {botData.active_settings.timeframe}</div>
                <div>Ponawianie: {botData.active_settings.repeat_alerts ? 'ON' : 'OFF'}</div>
              </div>
            )}
          </div>
            
            {/* Signals Panel */}
            <div className="glass-panel" style={{ flexGrow: 1 }}>
                <h2 className="panel-title">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M22 12h-4l-3 9L9 3l-3 9H2"></path>
                    </svg>
                    Ostatnie Sygnały {botData?.last_check && <span style={{fontSize: '0.8rem', fontWeight:400}}>(Check: {botData.last_check})</span>}
                </h2>
                
                <div style={{ maxHeight: 'calc(100vh - 250px)', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {botData?.signals && botData.signals.length > 0 ? (
                        botData.signals.map((sig: Signal, i: number) => (
                            <div key={i} style={{ padding: '0.75rem', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', borderLeft: `3px solid ${sig.type === 'LONG' ? 'var(--success)' : 'var(--danger)'}` }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                    <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{sig.pair}</span>
                                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>{sig.time}</span>
                                </div>
                                <div style={{ fontSize: '0.85rem' }}>{sig.reason}</div>
                            </div>
                        ))
                    ) : (
                        <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '2rem 0' }}>Brak nowych sygnałów.</div>
                    )}
                </div>
            </div>
            
        </div>
      </div>
    </div>
  );
}
