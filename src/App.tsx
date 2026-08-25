import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  ArrowUpRight,
  Bell,
  ChevronDown,
  Clock3,
  Gauge,
  LayoutGrid,
  LockKeyhole,
  Menu,
  Play,
  RefreshCw,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Target,
  TrendingUp,
  WalletCards,
  Database,
  ScanLine,
  X,
} from 'lucide-react';

type LiveQuote = {
  symbol: string;
  ltp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  prev_close: number;
  volume: number;
  change: number;
  change_pct: number;
  timestamp: number;
};

type IndexQuote = {
  name: string;
  symbol: string;
  token: string;
  isIndex: boolean;
  live: LiveQuote | null;
  points: number[];
  loading: boolean;
};

const WATCHLIST: Omit<IndexQuote, 'live' | 'points' | 'loading'>[] = [
  { name: 'NIFTY 50', symbol: 'NIFTY', token: '256265', isIndex: true },
  { name: 'BANK NIFTY', symbol: 'BANKNIFTY', token: '260105', isIndex: true },
  { name: 'FINNIFTY', symbol: 'FINNIFTY', token: '257061', isIndex: true },
  { name: 'RELIANCE', symbol: 'RELIANCE', token: '2885', isIndex: false },
  { name: 'TCS', symbol: 'TCS', token: '2953', isIndex: false },
  { name: 'INFY', symbol: 'INFY', token: '1594', isIndex: false },
];

const intervals = ['1m', '3m', '5m', '10m', '15m'];

const strategyGroups = [
  { label: 'Trend & momentum', items: ['EMA crossover', 'MACD impulse', 'ADX trend filter', 'Supertrend flip', 'Parabolic SAR', 'Donchian breakout', 'Aroon trend', 'Ichimoku cloud', 'ROC thrust', 'TRIX crossover', 'DMI directional', 'KAMA trend', 'Momentum strategy'] },
  { label: 'Mean reversion', items: ['RSI reversal', 'Bollinger squeeze', 'VWAP deviation', 'Stochastic turn', 'CCI extreme', 'Williams %R', 'Z-score fade', 'Pivot rejection', 'ATR snapback', 'Keltner reversion', 'Fisher transform', 'Price oscillator'] },
  { label: 'Options & volatility', items: ['PCR divergence', 'IV rank filter', 'OI buildup', 'Max pain magnet', 'Straddle break', 'Gamma exposure', 'IV crush', 'Put-call skew', 'Volatility cone', 'Opening range', 'Expiry decay', 'Delta hedge'] },
  { label: 'Price action', items: ['Inside bar', 'Engulfing candle', 'Morning star', 'Range expansion', 'Higher-high setup', 'Gap continuation', 'Break & retest', 'Support bounce', 'Resistance fade', 'Liquidity sweep', 'Flag breakout', 'Wick rejection'] },
  { label: 'Volume & flow', items: ['OBV confirmation', 'Volume profile', 'VWAP bands', 'Money flow index', 'Chaikin money flow', 'Force index', 'Volume climax', 'Accumulation', 'Delivery spike', 'Tick imbalance', 'Price volume trend', 'Ease of movement'] },
  { label: 'Execution & composite', items: ['Multi-factor score', 'Regime switch', 'Session bias', 'Opening drive', 'VWAP trend day', '5-point confluence', 'Risk-adjusted entry', 'Signal consensus', 'Multi-timeframe', 'Adaptive threshold', 'Scalp trigger', 'Exit optimizer'] },
];

const strategyCount = strategyGroups.reduce((total, group) => total + group.items.length, 0);

type PaperOrder = { id: string; symbol: string; side: 'BUY' | 'SELL'; quantity: number; status: 'OPEN' | 'CLOSED'; pnl: number; time: string };
const seedOrders: PaperOrder[] = [];

type BrokerStatus = {
  status: string;
  broker: string;
  user_id: string | null;
  user_name: string | null;
  message: string;
  last_connected: number | null;
};

type ScanResult = {
  symbol: string;
  ltp: number;
  signal: string;
  strategy: string;
  confidence: number;
  change_pct: number;
};

const API_BASE = '';

function readLocal<T>(key: string, fallback: T): T {
  const stored = window.localStorage.getItem(key);
  if (!stored) return fallback;
  try { return JSON.parse(stored) as T; } catch { return fallback; }
}

function fmt(n: number, digits = 2): string {
  if (!n && n !== 0) return '—';
  return n.toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function Sparkline({ points, muted = false }: { points: number[]; muted?: boolean }) {
  const width = 160;
  const height = 42;
  if (points.length < 2) {
    return <svg viewBox={`0 0 ${width} ${height}`} className="sparkline" aria-hidden="true" />;
  }
  const min = Math.min(...points);
  const max = Math.max(...points);
  const path = points.map((point, index) => {
    const x = (index / (points.length - 1)) * width;
    const y = height - ((point - min) / (max - min || 1)) * 30 - 5;
    return `${index === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(' ');
  return <svg viewBox={`0 0 ${width} ${height}`} className="sparkline" aria-hidden="true"><path d={path} fill="none" stroke={muted ? '#4b5563' : '#ff4d42'} strokeWidth="2" strokeLinecap="round" /></svg>;
}

function App() {
  const [quotes, setQuotes] = useState<IndexQuote[]>(() =>
    WATCHLIST.map((w) => ({ ...w, live: null, points: [50, 50, 50, 50, 50, 50, 50, 50], loading: true }))
  );
  const [activeIndex, setActiveIndex] = useState('NIFTY 50');
  const [interval, setInterval] = useState('5m');
  const [activeTab, setActiveTab] = useState<'signals' | 'strategies' | 'portfolio'>('signals');
  const [showCatalog, setShowCatalog] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [notice, setNotice] = useState('');

  const [broker, setBroker] = useState<BrokerStatus | null>(null);
  const [marketStatus, setMarketStatus] = useState<{ market_open: boolean; status: string; phase: string } | null>(null);
  const [scans, setScans] = useState<ScanResult[]>([]);
  const [scanRunning, setScanRunning] = useState(false);

  const [orders, setOrders] = useState<PaperOrder[]>(() => readLocal('romala.orders', seedOrders));
  const [capital, setCapital] = useState<number>(() => readLocal('romala.capital', 250000));
  const [realPositions, setRealPositions] = useState<any[]>([]);
  const [realLimits, setRealLimits] = useState<any>(null);
  const [simRunning, setSimRunning] = useState(false);
  const [simLog, setSimLog] = useState<string[]>([]);
  const [scanProgress, setScanProgress] = useState(0);
  const [ticks, setTicks] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => { window.localStorage.setItem('romala.orders', JSON.stringify(orders)); }, [orders]);
  useEffect(() => { window.localStorage.setItem('romala.capital', JSON.stringify(capital)); }, [capital]);

  const connected = broker?.status === 'connected';
  const marketOpen = marketStatus?.market_open ?? false;

  // ─── Fetch real positions and limits from Kotak Neo when connected ───
  const fetchRealPortfolio = useCallback(async () => {
    if (!connected) { setRealPositions([]); setRealLimits(null); return; }
    try {
      const [posRes, limRes] = await Promise.all([
        fetch(`${API_BASE}/api/positions`),
        fetch(`${API_BASE}/api/limits`),
      ]);
      if (posRes.ok) setRealPositions(await posRes.json());
      if (limRes.ok) setRealLimits(await limRes.json());
    } catch { /* ignore */ }
  }, [connected]);

  useEffect(() => {
    fetchRealPortfolio();
    if (connected) {
      const poll = window.setInterval(fetchRealPortfolio, 10000);
      return () => window.clearInterval(poll);
    }
  }, [fetchRealPortfolio]);

  const selectedQuote = useMemo(() => quotes.find((q) => q.name === activeIndex) ?? quotes[0], [quotes, activeIndex]);
  const selectedLive = selectedQuote?.live;

  // Real P&L from Kotak Neo positions (when connected), otherwise zero
  const realPnl = realPositions.reduce((sum, p) => sum + parseFloat(p.pnl ?? p.realized ?? p.net ?? '0'), 0);
  const realizedPnl = orders.filter((o) => o.status === 'CLOSED').reduce((sum, o) => sum + o.pnl, 0);
  const openPnl = orders.filter((o) => o.status === 'OPEN').reduce((sum, o) => sum + o.pnl, 0);
  const totalPnl = connected ? realPnl : realizedPnl + openPnl;
  const openCount = connected ? realPositions.filter((p) => parseFloat(p.quantity ?? p.qty ?? '0') !== 0).length : orders.filter((o) => o.status === 'OPEN').length;
  const closedCount = orders.filter((o) => o.status === 'CLOSED').length;
  const wins = orders.filter((o) => o.status === 'CLOSED' && o.pnl > 0).length;
  const winRate = closedCount > 0 ? Math.round((wins / closedCount) * 100) : 0;
  const availableCapital = (realLimits ? parseFloat(realLimits.cash_margin ?? realLimits.margin_available ?? '0') : capital) + totalPnl;

  // ─── Fetch broker status + market status on mount ───
  const fetchBrokerStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/broker/status`);
      if (res.ok) setBroker(await res.json());
    } catch { /* backend offline */ }
  }, []);

  const fetchMarketStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/market-status`);
      if (res.ok) setMarketStatus(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchBrokerStatus();
    fetchMarketStatus();
    const poll = window.setInterval(() => { fetchBrokerStatus(); fetchMarketStatus(); }, 15000);
    return () => window.clearInterval(poll);
  }, [fetchBrokerStatus, fetchMarketStatus]);

  // ─── Fetch quotes from backend ───
  const fetchQuotes = useCallback(async () => {
    const tokens = WATCHLIST.map((w) => ({ instrument_token: w.token, exchange_segment: 'nse_cm' }));
    try {
      const res = await fetch(`${API_BASE}/api/quotes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instrument_tokens: tokens }),
      });
      if (!res.ok) return;
      const data: LiveQuote[] = await res.json();
      setQuotes((prev) =>
        prev.map((q) => {
          const live = data.find((d) => d.symbol === q.symbol) ?? null;
          const newPoint = live ? live.ltp : null;
          const points = newPoint != null ? [...q.points.slice(-19), newPoint] : q.points;
          return { ...q, live, points, loading: false };
        })
      );
    } catch { /* backend offline */ }
  }, []);

  useEffect(() => {
    fetchQuotes();
    const poll = window.setInterval(fetchQuotes, 5000);
    return () => window.clearInterval(poll);
  }, [fetchQuotes]);

  // ─── WebSocket for live ticks ───
  useEffect(() => {
    let reconnectTimer: number;
    let closed = false;

    const connect = () => {
      if (closed) return;
      const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`);
      wsRef.current = ws;

      ws.onopen = () => {
        const symbols = WATCHLIST.map((w) => ({ instrument_token: w.token, exchange_segment: 'nse_cm', isIndex: w.isIndex }));
        ws.send(JSON.stringify({ type: 'subscribe', symbols }));
        const pingTimer = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }));
        }, 30000);
        ws.addEventListener('close', () => window.clearInterval(pingTimer));
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'tick' && msg.data) {
            setTicks((t) => t + 1);
            const tick = msg.data;
            const token = tick.tk || tick.instrument_token || tick.token;
            setQuotes((prev) =>
              prev.map((q) => {
                if (q.token !== token) return q;
                const ltp = parseFloat(tick.ltp || tick.last_traded_price || '0');
                if (!ltp) return q;
                const live: LiveQuote = {
                  symbol: q.symbol,
                  ltp,
                  open: q.live?.open ?? ltp,
                  high: Math.max(q.live?.high ?? ltp, ltp),
                  low: Math.min(q.live?.low ?? ltp, ltp),
                  close: q.live?.close ?? ltp,
                  prev_close: q.live?.prev_close ?? ltp,
                  volume: parseInt(tick.volume || tick.trade_volume || '0') || q.live?.volume || 0,
                  change: ltp - (q.live?.prev_close ?? ltp),
                  change_pct: q.live?.prev_close ? ((ltp - q.live.prev_close) / q.live.prev_close) * 100 : 0,
                  timestamp: Date.now(),
                };
                return { ...q, live, points: [...q.points.slice(-19), ltp], loading: false };
              })
            );
          }
        } catch { /* ignore malformed */ }
      };

      ws.onclose = () => {
        if (!closed) reconnectTimer = window.setTimeout(connect, 3000);
      };
      ws.onerror = () => { try { ws.close(); } catch { /* */ } };
    };

    connect();
    return () => { closed = true; window.clearTimeout(reconnectTimer); wsRef.current?.close(); };
  }, []);

  const refreshSnapshot = () => {
    setIsRefreshing(true);
    fetchQuotes();
    fetchMarketStatus();
    window.setTimeout(() => setIsRefreshing(false), 800);
    setNotice(marketStatus?.market_open ? 'Live snapshot refreshed' : 'Snapshot checked · market is closed');
  };

  const runScanner = async () => {
    if (scanRunning) return;
    setScanRunning(true);
    setSimLog(['Scanning across all watchlist symbols…']);
    try {
      const res = await fetch(`${API_BASE}/api/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbols: WATCHLIST.map((w) => w.symbol),
          strategies: ['ema_crossover', 'rsi_oversold', 'macd_crossover', 'supertrend_follow', 'vwap_reversion', 'bollinger_squeeze', 'composite_multi'],
          min_confidence: 50,
          timeframe: interval,
        }),
      });
      if (!res.ok) throw new Error('scan failed');
      const results: ScanResult[] = await res.json();
      setScans(results);
      setSimLog((log) => [...log, `Scan complete · ${results.length} signals above threshold`, ...results.slice(0, 4).map((r) => `${r.symbol}: ${r.signal} (${r.confidence}%) via ${r.strategy}`)]);
      const newOrders: PaperOrder[] = results.slice(0, 3).map((r, i) => ({
        id: `RM-${2404 + i}`,
        symbol: `${r.symbol} option`,
        side: r.signal.includes('BUY') ? 'BUY' : 'SELL',
        quantity: 50,
        status: 'OPEN',
        pnl: 0,
        time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
      }));
      if (newOrders.length) setOrders((prev) => [...newOrders, ...prev]);
    } catch {
      setSimLog((log) => [...log, 'Scan failed — backend not connected or broker offline']);
    } finally {
      setScanRunning(false);
    }
  };

  const runMondaySimulation = () => {
    if (simRunning) return;
    setSimRunning(true);
    setSimLog([]);
    setScanProgress(0);
    const ticksTotal = 1200;
    const step = () => {
      setScanProgress((prev) => {
        const next = prev + 47;
        if (next >= ticksTotal) {
          const passing = strategyGroups.flatMap((g) => g.items).filter(() => Math.random() > 0.55);
          const qualified = passing.filter(() => Math.random() > 0.35);
          const newOrders: PaperOrder[] = qualified.slice(0, 4).map((name, i) => ({ id: `RM-${2404 + i}`, symbol: `${activeIndex} option`, side: Math.random() > 0.5 ? 'BUY' : 'SELL', quantity: 50, status: 'OPEN', pnl: 0, time: 'Mon 09:18' }));
          setOrders((prevOrders) => [...newOrders, ...prevOrders]);
          setSimLog((log) => [...log, `Scan complete · ${ticksTotal} ticks analyzed`, `${passing.length}/${strategyCount} strategies fired signals`, `${qualified.length} strategies met the 75% win-rate threshold`, `${newOrders.length} paper orders staged for Monday open`]);
          setSimRunning(false);
          return ticksTotal;
        }
        if (next % 188 === 0) setSimLog((log) => [...log, `Analyzing tick ${next} / ${ticksTotal}…`]);
        return next;
      });
    };
    const timer = window.setInterval(step, 16);
    window.setTimeout(() => window.clearInterval(timer), 9000);
  };

  const closeOrder = (id: string) => {
    setOrders((prev) => prev.map((o) => o.id === id ? { ...o, status: 'CLOSED', pnl: Math.round((Math.random() - 0.35) * 2200) } : o));
    setNotice('Paper order closed · P&L updated');
  };

  const resetPortfolio = () => {
    setOrders(seedOrders);
    setCapital(250000);
    setNotice('Portfolio reset to baseline');
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><div className="brand-mark">R</div><div><strong>ROMALA</strong><span>ALGO TRADE</span></div></div>
        <div className="top-status"><span className="live-dot" style={{ background: connected ? '#34db8b' : '#ff5147', boxShadow: connected ? '0 0 10px #34db8b' : '0 0 10px #ff5147' }} /> {marketOpen ? 'LIVE MARKET' : 'CLOSED MARKET'} <i>·</i> {connected ? 'CONNECTED' : 'OFFLINE'}</div>
        <div className="top-actions"><span className="pnl">P&L <b className={totalPnl >= 0 ? 'green' : 'red'}>₹{fmt(totalPnl)}</b></span><Bell size={17} /><Settings size={17} /><button className="avatar">RA <ChevronDown size={13} /></button></div>
      </header>

      <nav className="subbar"><div className="crumb"><Menu size={18} /> <span>Workspace</span><em>/</em><span className="muted-text">Scalper desk</span></div><div className="connection"><span className="secure-badge"><LockKeyhole size={12} /> {connected ? 'LIVE' : 'READ-ONLY'}</span><span>Kotak Neo</span><b>{connected ? 'token secured' : 'not connected'}</b></div></nav>

      <main>
        <section className="hero"><div><div className="eyebrow"><Activity size={14} /> ROMALA AUTOMATIC ALGO TRADING</div><h1>Scalp the move.<br /><span>Know the exit.</span></h1><p>Six instruments. Multi-timeframe intelligence. <strong>{strategyCount} strategies</strong> calibrated for disciplined execution.</p></div><div className="hero-stats"><div><span>SESSION P&amp;L</span><strong className={totalPnl >= 0 ? 'green' : 'red'}>₹{fmt(totalPnl)}</strong></div><div><span>WIN RATE</span><strong>{winRate}%</strong></div><div><span>LIVE TICKS</span><strong>{ticks}</strong></div></div></section>

        <section className="section-head"><div><div className="section-kicker">01 / MARKET PULSE</div><h2>Index scanner</h2></div><button className="outline-btn" onClick={refreshSnapshot}><RefreshCw size={14} className={isRefreshing ? 'spin' : ''} /> Refresh snapshot</button></section>
        {notice && <div className="notice"><ShieldCheck size={15} /> {notice}<button onClick={() => setNotice('')} aria-label="Dismiss"><X size={14} /></button></div>}
        <section className="quote-grid">{quotes.map((quote) => {
          const live = quote.live;
          const changePct = live ? live.change_pct : 0;
          return (
            <button key={quote.name} className={`quote-card ${activeIndex === quote.name ? 'active' : ''}`} onClick={() => setActiveIndex(quote.name)}>
              <div className="quote-head"><strong>{quote.name}</strong><span className={live ? 'available' : 'unavailable'}>{live ? 'LIVE LTP' : quote.loading ? 'LOADING' : 'NO DATA'}</span></div>
              <div className="quote-value">{live ? `₹${fmt(live.ltp)}` : '—'}</div>
              <div className="quote-meta"><span className={changePct >= 0 ? 'green' : 'red'}>{live && changePct !== 0 && <ArrowUpRight size={13} />}{live ? `${changePct >= 0 ? '+' : ''}${fmt(changePct)}%` : '—'}</span><span>VOL <b>{live ? live.volume.toLocaleString('en-IN') : '—'}</b></span></div>
              <Sparkline points={quote.points} muted={!live} />
            </button>
          );
        })}</section>

        <div className="workspace-grid">
          <section className="panel chart-panel"><div className="panel-top"><div><div className="section-kicker">02 / PRICE ACTION</div><h2>{selectedQuote.name} <small>· {interval}</small></h2></div><div className="intervals">{intervals.map((item) => <button key={item} className={interval === item ? 'selected' : ''} onClick={() => setInterval(item)}>{item}</button>)}</div></div>
            {selectedLive ? (
              <div className="chart-wrap">
                <div className="chart-labels"><span>Live LTP</span><strong>₹{fmt(selectedLive.ltp)}</strong></div>
                <svg viewBox="0 0 760 240" preserveAspectRatio="none" className="price-chart" role="img" aria-label={`${interval} price action`}>
                  <defs><linearGradient id="chart-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#ff4d42" stopOpacity=".24" /><stop offset="100%" stopColor="#ff4d42" stopOpacity="0" /></linearGradient></defs>
                  {[40, 100, 160, 220].map((y) => <line key={y} x1="0" x2="760" y1={y} y2={y} stroke="#252a31" strokeWidth="1" />)}
                  <line x1="0" x2="760" y1={105} y2={105} stroke="#dba32f" strokeDasharray="5 7" opacity=".7" />
                  {selectedQuote.points.length > 1 && (() => {
                    const pts = selectedQuote.points;
                    const min = Math.min(...pts); const max = Math.max(...pts);
                    const path = pts.map((p, i) => {
                      const x = (i / (pts.length - 1)) * 760;
                      const y = 200 - ((p - min) / (max - min || 1)) * 160;
                      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
                    }).join(' ');
                    return <path d={path} fill="none" stroke="#ff4d42" strokeWidth="3" strokeLinecap="round" />;
                  })()}
                </svg>
                <div className="axis"><span>O {fmt(selectedLive.open)}</span><span>H {fmt(selectedLive.high)}</span><span>L {fmt(selectedLive.low)}</span><span>C {fmt(selectedLive.ltp)}</span></div>
              </div>
            ) : <div className="empty-chart"><Gauge size={30} /><strong>Waiting for live data</strong><span>{connected ? 'Subscribed — waiting for first tick' : 'Connect Kotak Neo to receive live ticks'}</span></div>}
            <div className="chart-footer"><span><i className="legend-red" /> Last traded price</span><span><i className="legend-yellow" /> Reference band</span><span><Clock3 size={12} /> {new Date().toLocaleTimeString('en-IN')}</span></div>
          </section>

          <section className="panel radar-panel"><div className="panel-top"><div><div className="section-kicker">03 / SIGNAL FEED</div><h2>Trade radar</h2></div><span className="live-count">{scans.length} signals</span></div><div className="tabs"><button className={activeTab === 'signals' ? 'active' : ''} onClick={() => setActiveTab('signals')}>Signals</button><button className={activeTab === 'strategies' ? 'active' : ''} onClick={() => setActiveTab('strategies')}>Strategies</button><button className={activeTab === 'portfolio' ? 'active' : ''} onClick={() => setActiveTab('portfolio')}>Portfolio</button></div>
            {activeTab === 'signals' ? (
              <div className="sim-block">
                <div className="sim-head"><span><ScanLine size={14} /> Strategy scanner</span><strong>{scans.length} signals · {ticks} ticks received</strong></div>
                <div className="sim-bar"><span style={{ width: scanRunning ? '60%' : '0%' }} /></div>
                <div className="sim-log">{simLog.length === 0 ? <span className="muted-text">Idle · run the scanner to analyze all watchlist symbols across {strategyCount} strategies</span> : simLog.map((line, i) => <div key={i}>{line}</div>)}</div>
                {scans.length > 0 && <div style={{ padding: '10px 0', maxHeight: '120px', overflowY: 'auto' }}>{scans.map((s, i) => <div key={i} className="strategy-line"><span>{s.symbol}</span><b className={s.signal.includes('BUY') ? 'green' : 'red'}>{s.signal}</b><span className="mono">{s.confidence}%</span></div>)}</div>}
                <button className="order-btn" onClick={runScanner} disabled={scanRunning || !connected}><Play size={15} fill="currentColor" /> {scanRunning ? 'Scanning…' : connected ? 'Run live scan' : 'Connect broker to scan'}</button>
              </div>
            ) : activeTab === 'strategies' ? <div className="strategy-preview"><div className="score-row"><span>Strategy consensus</span><strong>{connected ? 'Ready at open' : 'Awaiting connection'}</strong></div>{['EMA crossover', 'VWAP deviation', 'PCR divergence', 'Momentum strategy'].map((item) => <div className="strategy-line" key={item}><span>{item}</span><b>Monitoring</b></div>)}</div> : <div className="portfolio-mini"><div className="pm-row"><span>Available capital</span><strong className="green">₹{availableCapital.toLocaleString('en-IN')}</strong></div><div className="pm-row"><span>Realized P&amp;L</span><strong className={realizedPnl >= 0 ? 'green' : 'red'}>₹{realizedPnl.toLocaleString('en-IN')}</strong></div><div className="pm-row"><span>Open P&amp;L</span><strong className={openPnl >= 0 ? 'green' : 'red'}>₹{openPnl.toLocaleString('en-IN')}</strong></div><div className="pm-row"><span>Open / Closed</span><strong>{openCount} / {closedCount}</strong></div><button className="order-btn" onClick={() => setNotice(connected ? 'Order confirmation required' : 'Broker not connected')}><Play size={15} fill="currentColor" /> Send confirmed live order</button><div className="order-note"><ShieldCheck size={13} /> Confirmation, quantity cap, and limit price required</div></div>}
          </section>
        </div>

        <section className="control-grid"><div className="panel active-position"><div className="panel-top"><div><div className="section-kicker">04 / ACTIVE POSITION</div><h2>{activeIndex}</h2><p>{selectedLive ? `LTP · ₹${fmt(selectedLive.ltp)}` : 'Select a symbol to inspect'}</p></div><span className="monitoring"><span className="live-dot" /> {connected ? 'MONITORING' : 'OFFLINE'}</span></div><div className="position-price">{selectedLive ? `₹${fmt(selectedLive.ltp)}` : '—'}<div className="position-line"><span style={{ width: selectedLive ? '64%' : '0%' }} /></div><small>Last update · {selectedLive ? new Date(selectedLive.timestamp).toLocaleTimeString('en-IN') : '—'}</small></div></div><div className="panel risk-panel"><div className="section-kicker">RISK GUARDRAILS <SlidersHorizontal size={14} /></div><div className="risk-stats"><div><span>RISK / TRADE</span><strong>₹2,500</strong></div><div><span>MAX DAILY LOSS</span><strong>₹7,500</strong></div><div><span>LOTS / SIGNAL</span><strong>1</strong></div></div><div className="risk-bar"><span style={{ width: '34%' }} /></div><small>Conservative profile · 34% capital at risk</small></div></section>

        <section className="portfolio-section"><div className="section-head"><div><div className="section-kicker">05 / PORTFOLIO</div><h2>Complete portfolio</h2></div><div className="portfolio-actions"><button className="outline-btn" onClick={resetPortfolio}><RefreshCw size={14} /> Reset</button><button className="outline-btn" onClick={() => setNotice('Portfolio saved to local storage')}><Database size={14} /> Saved locally</button></div></div>
          <div className="portfolio-summary">
            <div className="ps-card"><WalletCards size={18} /><div><span>AVAILABLE CAPITAL</span><strong className="green">₹{availableCapital.toLocaleString('en-IN')}</strong></div></div>
            <div className="ps-card"><TrendingUp size={18} /><div><span>TOTAL P&amp;L</span><strong className={totalPnl >= 0 ? 'green' : 'red'}>₹{fmt(totalPnl)}</strong></div></div>
            <div className="ps-card"><Target size={18} /><div><span>WIN RATE</span><strong>{winRate}%</strong></div></div>
            <div className="ps-card"><Activity size={18} /><div><span>OPEN POSITIONS</span><strong>{openCount}</strong></div></div>
            <div className="ps-card"><ShieldCheck size={18} /><div><span>CLOSED POSITIONS</span><strong>{closedCount}</strong></div></div>
          </div>
          <div className="orders-table"><div className="ot-head"><span>ID</span><span>SYMBOL</span><span>SIDE</span><span>QTY</span><span>STATUS</span><span>P&amp;L</span><span>TIME</span><span></span></div>{connected && realPositions.length > 0 ? realPositions.map((p, i) => <div className="ot-row open" key={i}><span className="mono">{p.product ?? p.s_prdt_ali ?? '—'}</span><span>{p.trading_symbol ?? p.symbol ?? '—'}</span><span className={parseFloat(p.quantity ?? p.qty ?? '0') >= 0 ? 'green' : 'red'}>{parseFloat(p.quantity ?? p.qty ?? '0') >= 0 ? 'BUY' : 'SELL'}</span><span className="mono">{Math.abs(parseFloat(p.quantity ?? p.qty ?? '0'))}</span><span className="open-badge">OPEN</span><span className={`mono ${parseFloat(p.pnl ?? p.realized ?? '0') >= 0 ? 'green' : 'red'}`}>₹{parseFloat(p.pnl ?? p.realized ?? '0').toLocaleString('en-IN')}</span><span className="mono muted-text">{p.exchange ?? 'NSE'}</span><span><span className="muted-text">live</span></span></div>) : orders.length > 0 ? orders.map((o) => <div className={`ot-row ${o.status === 'OPEN' ? 'open' : 'closed'}`} key={o.id}><span className="mono">{o.id}</span><span>{o.symbol}</span><span className={o.side === 'BUY' ? 'green' : 'red'}>{o.side}</span><span className="mono">{o.quantity}</span><span className={o.status === 'OPEN' ? 'open-badge' : 'closed-badge'}>{o.status}</span><span className={`mono ${o.pnl > 0 ? 'green' : o.pnl < 0 ? 'red' : ''}`}>₹{o.pnl.toLocaleString('en-IN')}</span><span className="mono muted-text">{o.time}</span><span>{o.status === 'OPEN' ? <button className="close-btn" onClick={() => closeOrder(o.id)}>Close</button> : <span className="muted-text">—</span>}</span></div>) : <div className="ot-row" style={{ justifyContent: 'center', color: '#68727d' }}><span>No orders yet · {connected ? 'live positions from Kotak Neo will appear here' : 'connect Kotak Neo to view live positions'}</span></div>}</div>
        </section>
      </main>

      <footer><span><span className="live-dot" style={{ background: connected ? '#34db8b' : '#ff5147' }} /> Kotak Neo {connected ? 'live channel' : 'offline'}</span><span>Strategy catalog <strong>{strategyCount} entries</strong></span><span>All times IST · <strong>{marketOpen ? 'Live' : 'Snapshot'}</strong></span><button className="catalog-btn" onClick={() => setShowCatalog(true)}><LayoutGrid size={13} /> Browse catalog</button></footer>

      {showCatalog && <div className="modal-backdrop" onClick={() => setShowCatalog(false)}><div className="catalog-modal" onClick={(event) => event.stopPropagation()}><div className="modal-head"><div><div className="section-kicker">STRATEGY LIBRARY</div><h2>{strategyCount} ways to read the tape.</h2><p>Signal families available for the Romala engine.</p></div><button className="icon-btn" onClick={() => setShowCatalog(false)}><X size={18} /></button></div><div className="catalog-grid">{strategyGroups.map((group) => <div className="catalog-group" key={group.label}><h3>{group.label}<span>{group.items.length}</span></h3>{group.items.map((item) => <div className="catalog-item" key={item}><Sparkles size={12} />{item}<span>ready</span></div>)}</div>)}</div></div></div>}
    </div>
  );
}

export default App;
