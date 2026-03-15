'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createChart, ColorType, IChartApi, ISeriesApi, CandlestickSeries, LineSeries, Time } from 'lightweight-charts';

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
  metrics: Record<string, { mso: number; macd: number; trend: string; price: number } | undefined>;
}

export default function Dashboard() {
  const [mounted, setMounted] = useState(false);
  const [botData, setBotData] = useState<BotData | null>(null);
  const [activePair, setActivePair] = useState('ETH/USDT');
  const [timeframe, setTimeframe] = useState('1h');
  
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const ema9Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ema18Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const msoRef = useRef<ISeriesApi<"Line"> | null>(null);

  // Fetch bot general state
  const fetchState = useCallback(async () => {
    try {
      const res = await fetch('http://localhost:8000/api/state');
      if (res.ok) {
        const data = await res.json();
        setBotData(data);
      }
    } catch (err) {
      console.error("Failed to connect to Bot API", err);
    }
  }, []);

  // Fetch specific chart data
  const fetchChartData = useCallback(async () => {
    try {
      const res = await fetch(`http://localhost:8000/api/chart?symbol=${activePair.replace('/', '%2F')}&timeframe=${timeframe}`);
      if (res.ok) {
        const payload = await res.json();
        if (payload.status === "success" && payload.data) {
          const data = payload.data;
          
          if (seriesRef.current) {
             seriesRef.current.setData(data.map((d: any) => ({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close })));
          }
          if (ema9Ref.current) {
             ema9Ref.current.setData(data.filter((d: any) => d.ema9 !== null).map((d: any) => ({ time: d.time, value: d.ema9 })));
          }
          if (ema18Ref.current) {
             ema18Ref.current.setData(data.filter((d: any) => d.ema18 !== null).map((d: any) => ({ time: d.time, value: d.ema18 })));
          }
          if (msoRef.current) {
             msoRef.current.setData(data.filter((d: any) => d.mso !== null).map((d: any) => ({ time: d.time, value: d.mso })));
          }
        }
      }
    } catch (err) {
      console.error("Failed to fetch chart data", err);
    }
  }, [activePair, timeframe]);

  // Init
  useEffect(() => {
    setMounted(true);
  }, []);

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
    if (!mounted || !chartContainerRef.current) return;
    
    // Destroy previous chart
    if (chartRef.current) {
      try {
        chartRef.current.remove();
      } catch {
        // Ignore already disposed errors
      }
      chartRef.current = null;
    }

    const chart = createChart(chartContainerRef.current, {
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
          bottom: 0.3, // Leave space for MSO at the bottom
        },
      },
      leftPriceScale: {
        visible: true,
        scaleMargins: {
          top: 0.75, // Push MSO to the bottom 25%
          bottom: 0,
        },
      },
      width: chartContainerRef.current.clientWidth,
      height: 480,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      }
    });
    
    chartRef.current = chart;
    
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#3fb950',
      downColor: '#f85149',
      borderVisible: false,
      wickUpColor: '#3fb950',
      wickDownColor: '#f85149',
    });
    
    const ema9Series = chart.addSeries(LineSeries, {
        color: '#3b82f6',
        lineWidth: 1,
        crosshairMarkerVisible: false,
    });

    const ema18Series = chart.addSeries(LineSeries, {
        color: '#f59e0b',
        lineWidth: 1,
        crosshairMarkerVisible: false,
    });

    const msoSeries = chart.addSeries(LineSeries, {
        color: '#a855f7',
        lineWidth: 2,
        priceScaleId: 'left', // Keep on separate scale overlay
        crosshairMarkerVisible: false,
    });
    
    seriesRef.current = candlestickSeries as ISeriesApi<"Candlestick">;
    ema9Ref.current = ema9Series as ISeriesApi<"Line">;
    ema18Ref.current = ema18Series as ISeriesApi<"Line">;
    msoRef.current = msoSeries as ISeriesApi<"Line">;

    // Fetch initial chart data
    fetchChartData();

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      try {
        chart.remove();
      } catch {
        // Ignore already disposed errors
      }
      if (chartRef.current === chart) {
        chartRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted, activePair, timeframe]); 

  if (!mounted) return null;

  return (
    <div className="dashboard-container">
      <header className="header fade-in">
        <h1>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
          </svg>
          Antigravity Crypto Bot
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
                    Live K-lines (ByBit)
                </h2>
                <div style={{ display: 'flex', gap: '20px', alignItems: 'center', flexWrap: 'wrap' }}>
                    
                    <div style={{ display: 'flex', gap: '5px', background: 'rgba(0,0,0,0.2)', padding: '4px', borderRadius: '8px' }}>
                        {['1m', '5m', '15m', '1h', '4h', '1d'].map(tf => (
                            <button 
                                key={tf}
                                onClick={() => setTimeframe(tf)}
                                style={{
                                    background: timeframe === tf ? 'rgba(63, 185, 80, 0.1)' : 'transparent',
                                    border: 'none',
                                    color: timeframe === tf ? 'var(--success)' : 'var(--text-secondary)',
                                    padding: '0.3rem 0.6rem',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    fontSize: '0.85rem',
                                    fontWeight: timeframe === tf ? 600 : 400,
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
            <div ref={chartContainerRef} style={{ width: '100%', height: '480px', borderRadius: '8px', overflow: 'hidden' }} />
            
            {/* Legend for chart */}
            <div style={{ display: 'flex', gap: '15px', marginTop: '10px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                 <div style={{display: 'flex', alignItems: 'center', gap: '5px'}}><span style={{display: 'inline-block', width: '10px', height: '2px', background: '#3b82f6'}}></span> EMA 9</div>
                 <div style={{display: 'flex', alignItems: 'center', gap: '5px'}}><span style={{display: 'inline-block', width: '10px', height: '2px', background: '#f59e0b'}}></span> EMA 18</div>
                 <div style={{display: 'flex', alignItems: 'center', gap: '5px'}}><span style={{display: 'inline-block', width: '10px', height: '2px', background: '#a855f7'}}></span> MSO Oscillator (lewa skala)</div>
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
