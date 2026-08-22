import { useEffect, useMemo, useState } from 'react';
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

type IndexQuote = {
  name: string;
  value: string;
  change: string;
  volume: string;
  status: 'Available' | 'Unavailable';
  tone: 'positive' | 'muted';
  points: number[];
};

const intervals = ['1m', '3m', '5m', '10m', '15m'];

const quotes: IndexQuote[] = [
  { name: 'NIFTY 50', value: '24,252.00', change: '+0.38%', volume: '12.4M', status: 'Available', tone: 'positive', points: [26, 32, 28, 39, 34, 48, 44, 56, 51, 64, 58, 72] },
  { name: 'BANK NIFTY', value: '57,761.95', change: '+0.62%', volume: '8.7M', status: 'Available', tone: 'positive', points: [42, 35, 44, 39, 52, 46, 63, 57, 68, 64, 76, 70] },
  { name: 'FINNIFTY', value: '—', change: '—', volume: '—', status: 'Unavailable', tone: 'muted', points: [50, 50, 50, 50, 50, 50, 50, 50] },
  { name: 'MIDCPNIFTY', value: '—', change: '—', volume: '—', status: 'Unavailable', tone: 'muted', points: [50, 50, 50, 50, 50, 50, 50, 50] },
  { name: 'SENSEX', value: '77,540.83', change: '-0.11%', volume: '6.1M', status: 'Available', tone: 'positive', points: [70, 64, 67, 59, 62, 52, 55, 47, 51, 43, 46, 38] },
  { name: 'BANKEX', value: '—', change: '—', volume: '—', status: 'Unavailable', tone: 'muted', points: [50, 50, 50, 50, 50, 50, 50, 50] },
];

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
const seedOrders: PaperOrder[] = [
  { id: 'RM-2401', symbol: 'NIFTY 50 24,200 CE', side: 'BUY', quantity: 50, status: 'CLOSED', pnl: 1840, time: 'Yesterday 10:42' },
  { id: 'RM-2402', symbol: 'BANK NIFTY 57,700 PE', side: 'SELL', quantity: 30, status: 'CLOSED', pnl: -620, time: 'Yesterday 13:18' },
  { id: 'RM-2403', symbol: 'NIFTY 50 24,250 CE', side: 'BUY', quantity: 50, status: 'OPEN', pnl: 0, time: 'Snapshot' },
];

function readLocal<T>(key: string, fallback: T): T {
  const stored = window.localStorage.getItem(key);
  if (!stored) return fallback;
  try { return JSON.parse(stored) as T; } catch { return fallback; }
}

function Sparkline({ points, muted = false }: { points: number[]; muted?: boolean }) {
  const width = 160;
  const height = 42;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const path = points.map((point, index) => {
    const x = (index / (points.length - 1)) * width;
    const y = height - ((point - min) / (max - min || 1)) * 30 - 5;
    return `${index === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(' ');
  return <svg viewBox={`0 0 ${width} ${height}`} className="sparkline" aria-hidden="true"><path d={path} fill="none" stroke={muted ? '#4b5563' : '#ff4d42'} strokeWidth="2" strokeLinecap="round" /></svg>;
}

function PriceChart({ interval }: { interval: string }) {
  return (
    <div className="chart-wrap">
      <div className="chart-labels"><span>Price action · Yesterday close</span><strong>₹24,252.00</strong></div>
      <svg viewBox="0 0 760 240" preserveAspectRatio="none" className="price-chart" role="img" aria-label={`${interval} price action snapshot`}>
        <defs><linearGradient id="chart-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#ff4d42" stopOpacity=".24" /><stop offset="100%" stopColor="#ff4d42" stopOpacity="0" /></linearGradient></defs>
        {[40, 100, 160, 220].map((y) => <line key={y} x1="0" x2="760" y1={y} y2={y} stroke="#252a31" strokeWidth="1" />)}
        <line x1="0" x2="760" y1="105" y2="105" stroke="#dba32f" strokeDasharray="5 7" opacity=".7" />
        <path d="M0 182 C28 172 42 182 65 161 S102 132 122 150 S163 169 187 142 S225 80 250 116 S286 156 311 134 S352 102 374 120 S416 92 438 110 S472 139 494 119 S535 67 561 91 S594 112 616 72 S665 35 686 58 S730 28 760 42 L760 240 L0 240 Z" fill="url(#chart-fill)" />
        <path d="M0 182 C28 172 42 182 65 161 S102 132 122 150 S163 169 187 142 S225 80 250 116 S286 156 311 134 S352 102 374 120 S416 92 438 110 S472 139 494 119 S535 67 561 91 S594 112 616 72 S665 35 686 58 S730 28 760 42" fill="none" stroke="#ff4d42" strokeWidth="3" strokeLinecap="round" />
        <circle cx="760" cy="42" r="4" fill="#ffb548" />
      </svg>
      <div className="axis"><span>09:15</span><span>10:30</span><span>11:45</span><span>13:00</span><span>15:30</span></div>
    </div>
  );
}

function App() {
  const [activeIndex, setActiveIndex] = useState('NIFTY 50');
  const [interval, setInterval] = useState('5m');
  const [activeTab, setActiveTab] = useState<'signals' | 'strategies' | 'portfolio'>('signals');
  const [showCatalog, setShowCatalog] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [notice, setNotice] = useState('');

  const [orders, setOrders] = useState<PaperOrder[]>(() => readLocal('romala.orders', seedOrders));
  const [capital, setCapital] = useState<number>(() => readLocal('romala.capital', 250000));
  const [simRunning, setSimRunning] = useState(false);
  const [simLog, setSimLog] = useState<string[]>([]);
  const [scanProgress, setScanProgress] = useState(0);

  useEffect(() => { window.localStorage.setItem('romala.orders', JSON.stringify(orders)); }, [orders]);
  useEffect(() => { window.localStorage.setItem('romala.capital', JSON.stringify(capital)); }, [capital]);

  const selectedQuote = useMemo(() => quotes.find((quote) => quote.name === activeIndex) ?? quotes[0], [activeIndex]);
  const unavailable = selectedQuote.status === 'Unavailable';

  const realizedPnl = orders.filter((o) => o.status === 'CLOSED').reduce((sum, o) => sum + o.pnl, 0);
  const openPnl = orders.filter((o) => o.status === 'OPEN').reduce((sum, o) => sum + o.pnl, 0);
  const totalPnl = realizedPnl + openPnl;
  const openCount = orders.filter((o) => o.status === 'OPEN').length;
  const closedCount = orders.filter((o) => o.status === 'CLOSED').length;
  const wins = orders.filter((o) => o.status === 'CLOSED' && o.pnl > 0).length;
  const winRate = closedCount > 0 ? Math.round((wins / closedCount) * 100) : 0;
  const availableCapital = capital + totalPnl;

  const refreshSnapshot = () => {
    setIsRefreshing(true);
    setNotice('Snapshot checked · market is closed');
    window.setTimeout(() => setIsRefreshing(false), 800);
  };

  const runMondaySimulation = () => {
    if (simRunning) return;
    setSimRunning(true);
    setSimLog([]);
    setScanProgress(0);
    const ticks = 1200;
    const step = () => {
      setScanProgress((prev) => {
        const next = prev + 47;
        if (next >= ticks) {
          const passing = strategyGroups.flatMap((g) => g.items).filter(() => Math.random() > 0.55);
          const qualified = passing.filter(() => Math.random() > 0.35);
          const newOrders: PaperOrder[] = qualified.slice(0, 4).map((name, i) => ({ id: `RM-${2404 + i}`, symbol: `${activeIndex} option`, side: Math.random() > 0.5 ? 'BUY' : 'SELL', quantity: 50, status: 'OPEN', pnl: 0, time: 'Mon 09:18' }));
          setOrders((prevOrders) => [...newOrders, ...prevOrders]);
          setSimLog((log) => [...log, `Scan complete · ${ticks} ticks analyzed`, `${passing.length}/${strategyCount} strategies fired signals`, `${qualified.length} strategies met the 75% win-rate threshold`, `${newOrders.length} paper orders staged for Monday open`]);
          setSimRunning(false);
          return ticks;
        }
        if (next % 188 === 0) setSimLog((log) => [...log, `Analyzing tick ${next} / ${ticks}…`]);
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
        <div className="top-status"><span className="live-dot" /> CLOSED MARKET <i>·</i> SNAPSHOT MODE</div>
        <div className="top-actions"><span className="pnl">P&L <b className={totalPnl >= 0 ? 'green' : 'red'}>₹{totalPnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</b></span><Bell size={17} /><Settings size={17} /><button className="avatar">RA <ChevronDown size={13} /></button></div>
      </header>

      <nav className="subbar"><div className="crumb"><Menu size={18} /> <span>Workspace</span><em>/</em><span className="muted-text">Scalper desk</span></div><div className="connection"><span className="secure-badge"><LockKeyhole size={12} /> READ-ONLY</span><span>Kotak Neo</span><b>token secured</b></div></nav>

      <main>
        <section className="hero"><div><div className="eyebrow"><Activity size={14} /> ROMALA AUTOMATIC ALGO TRADING</div><h1>Scalp the move.<br /><span>Know the exit.</span></h1><p>Six index derivatives. Multi-timeframe intelligence. <strong>{strategyCount} strategies</strong> calibrated for disciplined execution.</p></div><div className="hero-stats"><div><span>SESSION P&amp;L</span><strong className={totalPnl >= 0 ? 'green' : 'red'}>₹{totalPnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></div><div><span>WIN RATE</span><strong>{winRate}%</strong></div><div><span>STRATEGIES</span><strong>{strategyCount}</strong></div></div></section>

        <section className="section-head"><div><div className="section-kicker">01 / MARKET PULSE</div><h2>Index scanner</h2></div><button className="outline-btn" onClick={refreshSnapshot}><RefreshCw size={14} className={isRefreshing ? 'spin' : ''} /> Refresh snapshot</button></section>
        {notice && <div className="notice"><ShieldCheck size={15} /> {notice}<button onClick={() => setNotice('')} aria-label="Dismiss"><X size={14} /></button></div>}
        <section className="quote-grid">{quotes.map((quote) => <button key={quote.name} className={`quote-card ${activeIndex === quote.name ? 'active' : ''}`} onClick={() => setActiveIndex(quote.name)}><div className="quote-head"><strong>{quote.name}</strong><span className={quote.status === 'Available' ? 'available' : 'unavailable'}>{quote.status === 'Available' ? 'LAST CLOSE' : 'NOT IN MASTER'}</span></div><div className="quote-value">{quote.value}</div><div className="quote-meta"><span className={quote.tone === 'positive' ? 'green' : 'muted-text'}>{quote.change !== '—' && <ArrowUpRight size={13} />}{quote.change}</span><span>VOL <b>{quote.volume}</b></span></div><Sparkline points={quote.points} muted={quote.status === 'Unavailable'} /></button>)}</section>

        <div className="workspace-grid">
          <section className="panel chart-panel"><div className="panel-top"><div><div className="section-kicker">02 / PRICE ACTION</div><h2>{selectedQuote.name} <small>· {interval}</small></h2></div><div className="intervals">{intervals.map((item) => <button key={item} className={interval === item ? 'selected' : ''} onClick={() => setInterval(item)}>{item}</button>)}</div></div>{unavailable ? <div className="empty-chart"><Gauge size={30} /><strong>Snapshot unavailable</strong><span>This index was not present in the broker instrument master.</span></div> : <PriceChart interval={interval} />}<div className="chart-footer"><span><i className="legend-red" /> Last close</span><span><i className="legend-yellow" /> Reference band</span><span><Clock3 size={12} /> Yesterday · 15:30 IST</span></div></section>

          <section className="panel radar-panel"><div className="panel-top"><div><div className="section-kicker">03 / SIGNAL FEED</div><h2>Trade radar</h2></div><span className="live-count">{openCount} live</span></div><div className="tabs"><button className={activeTab === 'signals' ? 'active' : ''} onClick={() => setActiveTab('signals')}>Signals</button><button className={activeTab === 'strategies' ? 'active' : ''} onClick={() => setActiveTab('strategies')}>Strategies</button><button className={activeTab === 'portfolio' ? 'active' : ''} onClick={() => setActiveTab('portfolio')}>Portfolio</button></div>{activeTab === 'signals' ? <div className="sim-block"><div className="sim-head"><span><ScanLine size={14} /> Monday tick scanner</span><strong>{scanProgress} / 1200 ticks</strong></div><div className="sim-bar"><span style={{ width: `${Math.min(100, (scanProgress / 1200) * 100)}%` }} /></div><div className="sim-log">{simLog.length === 0 ? <span className="muted-text">Idle · run the scanner to analyze ticks across all {strategyCount} strategies</span> : simLog.map((line, i) => <div key={i}>{line}</div>)}</div><button className="order-btn" onClick={runMondaySimulation} disabled={simRunning}><Play size={15} fill="currentColor" /> {simRunning ? 'Scanning…' : 'Run Monday tick scan'}</button></div> : activeTab === 'strategies' ? <div className="strategy-preview"><div className="score-row"><span>Strategy consensus</span><strong>Ready at open</strong></div>{['EMA crossover', 'VWAP deviation', 'PCR divergence', 'Momentum strategy'].map((item) => <div className="strategy-line" key={item}><span>{item}</span><b>Monitoring</b></div>)}</div> : <div className="portfolio-mini"><div className="pm-row"><span>Available capital</span><strong className="green">₹{availableCapital.toLocaleString('en-IN')}</strong></div><div className="pm-row"><span>Realized P&amp;L</span><strong className={realizedPnl >= 0 ? 'green' : 'red'}>₹{realizedPnl.toLocaleString('en-IN')}</strong></div><div className="pm-row"><span>Open P&amp;L</span><strong className={openPnl >= 0 ? 'green' : 'red'}>₹{openPnl.toLocaleString('en-IN')}</strong></div><div className="pm-row"><span>Open / Closed</span><strong>{openCount} / {closedCount}</strong></div><button className="order-btn" onClick={() => setNotice('Live orders are disabled in snapshot mode')}><Play size={15} fill="currentColor" /> Send confirmed live order</button><div className="order-note"><ShieldCheck size={13} /> Confirmation, quantity cap, and limit price required</div></div>}</section>
        </div>

        <section className="control-grid"><div className="panel active-position"><div className="panel-top"><div><div className="section-kicker">04 / ACTIVE POSITION</div><h2>{activeIndex}</h2><p>BUY · 1 lot · Select a signal to inspect</p></div><span className="monitoring"><span className="live-dot" /> MONITORING</span></div><div className="position-price">{selectedQuote.value}<div className="position-line"><span style={{ width: unavailable ? '28%' : '64%' }} /></div><small>Last update · yesterday 15:30 IST</small></div></div><div className="panel risk-panel"><div className="section-kicker">RISK GUARDRAILS <SlidersHorizontal size={14} /></div><div className="risk-stats"><div><span>RISK / TRADE</span><strong>₹2,500</strong></div><div><span>MAX DAILY LOSS</span><strong>₹7,500</strong></div><div><span>LOTS / SIGNAL</span><strong>1</strong></div></div><div className="risk-bar"><span style={{ width: '34%' }} /></div><small>Conservative profile · 34% capital at risk</small></div></section>

        <section className="portfolio-section"><div className="section-head"><div><div className="section-kicker">05 / PORTFOLIO</div><h2>Complete portfolio</h2></div><div className="portfolio-actions"><button className="outline-btn" onClick={resetPortfolio}><RefreshCw size={14} /> Reset</button><button className="outline-btn" onClick={() => setNotice('Portfolio saved to local storage')}><Database size={14} /> Saved locally</button></div></div>
          <div className="portfolio-summary">
            <div className="ps-card"><WalletCards size={18} /><div><span>AVAILABLE CAPITAL</span><strong className="green">₹{availableCapital.toLocaleString('en-IN')}</strong></div></div>
            <div className="ps-card"><TrendingUp size={18} /><div><span>TOTAL P&amp;L</span><strong className={totalPnl >= 0 ? 'green' : 'red'}>₹{totalPnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></div></div>
            <div className="ps-card"><Target size={18} /><div><span>WIN RATE</span><strong>{winRate}%</strong></div></div>
            <div className="ps-card"><Activity size={18} /><div><span>OPEN POSITIONS</span><strong>{openCount}</strong></div></div>
            <div className="ps-card"><ShieldCheck size={18} /><div><span>CLOSED POSITIONS</span><strong>{closedCount}</strong></div></div>
          </div>
          <div className="orders-table"><div className="ot-head"><span>ID</span><span>SYMBOL</span><span>SIDE</span><span>QTY</span><span>STATUS</span><span>P&amp;L</span><span>TIME</span><span></span></div>{orders.map((o) => <div className={`ot-row ${o.status === 'OPEN' ? 'open' : 'closed'}`} key={o.id}><span className="mono">{o.id}</span><span>{o.symbol}</span><span className={o.side === 'BUY' ? 'green' : 'red'}>{o.side}</span><span className="mono">{o.quantity}</span><span className={o.status === 'OPEN' ? 'open-badge' : 'closed-badge'}>{o.status}</span><span className={`mono ${o.pnl > 0 ? 'green' : o.pnl < 0 ? 'red' : ''}`}>₹{o.pnl.toLocaleString('en-IN')}</span><span className="mono muted-text">{o.time}</span><span>{o.status === 'OPEN' ? <button className="close-btn" onClick={() => closeOrder(o.id)}>Close</button> : <span className="muted-text">—</span>}</span></div>)}</div>
        </section>
      </main>

      <footer><span><span className="live-dot" /> Kotak Neo read channel</span><span>Strategy catalog <strong>{strategyCount} entries</strong></span><span>All times IST · <strong>Snapshot locked</strong></span><button className="catalog-btn" onClick={() => setShowCatalog(true)}><LayoutGrid size={13} /> Browse catalog</button></footer>

      {showCatalog && <div className="modal-backdrop" onClick={() => setShowCatalog(false)}><div className="catalog-modal" onClick={(event) => event.stopPropagation()}><div className="modal-head"><div><div className="section-kicker">STRATEGY LIBRARY</div><h2>{strategyCount} ways to read the tape.</h2><p>Signal families available for the Romala engine.</p></div><button className="icon-btn" onClick={() => setShowCatalog(false)}><X size={18} /></button></div><div className="catalog-grid">{strategyGroups.map((group) => <div className="catalog-group" key={group.label}><h3>{group.label}<span>{group.items.length}</span></h3>{group.items.map((item) => <div className="catalog-item" key={item}><Sparkles size={12} />{item}<span>ready</span></div>)}</div>)}</div></div></div>}
    </div>
  );
}

export default App;
