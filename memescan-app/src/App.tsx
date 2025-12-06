import { useState, useEffect, useCallback } from 'react';
import './App.css';

// API base URL - use env variable or default to production
const API_BASE = import.meta.env.VITE_API_BASE || 'https://notaryton.com';

// Types
interface Token {
  address: string;
  symbol: string;
  name: string;
  price_usd: number;
  price_change_24h?: number;
  volume_24h_usd?: number;
  liquidity_usd: number;
  created_at?: string;
}

interface Pool {
  address: string;
  pair: string;
  dex: string;
  token0_symbol: string;
  token1_symbol: string;
  liquidity_usd: number;
  volume_24h: number;
}

interface SafetyResult {
  address: string;
  symbol: string;
  name: string;
  holder_count: number;
  dev_wallet_percent: number;
  safety_level: 'safe' | 'warning' | 'danger' | 'unknown';
  safety_warnings: string[];
}

type TabType = 'trending' | 'new' | 'check' | 'pools';

// Utility functions
function formatNumber(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toFixed(0);
}

function formatChange(n: number): string {
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(1)}%`;
}

function formatAge(isoDate: string): string {
  const now = new Date();
  const created = new Date(isoDate);
  const seconds = (now.getTime() - created.getTime()) / 1000;

  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

// Initialize Telegram WebApp
declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        ready: () => void;
        expand: () => void;
        close: () => void;
        MainButton: {
          show: () => void;
          hide: () => void;
          setText: (text: string) => void;
          onClick: (callback: () => void) => void;
        };
        themeParams: {
          bg_color?: string;
          text_color?: string;
          hint_color?: string;
          link_color?: string;
          button_color?: string;
          button_text_color?: string;
        };
        initDataUnsafe?: {
          user?: {
            id: number;
            first_name: string;
            username?: string;
          };
        };
      };
    };
  }
}

function App() {
  const [activeTab, setActiveTab] = useState<TabType>('trending');
  const [trendingTokens, setTrendingTokens] = useState<Token[]>([]);
  const [newTokens, setNewTokens] = useState<Token[]>([]);
  const [pools, setPools] = useState<Pool[]>([]);
  const [safetyResult, setSafetyResult] = useState<SafetyResult | null>(null);
  const [checkAddress, setCheckAddress] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initialize Telegram WebApp
  useEffect(() => {
    if (window.Telegram?.WebApp) {
      window.Telegram.WebApp.ready();
      window.Telegram.WebApp.expand();
    }
    // TG Analytics is initialized in index.html via onload callback
  }, []);

  // Fetch data based on active tab
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      if (activeTab === 'trending' && trendingTokens.length === 0) {
        const res = await fetch(`${API_BASE}/api/v1/memescan/trending`);
        const data = await res.json();
        if (data.success) {
          setTrendingTokens(data.tokens);
        } else {
          setError(data.error || 'Failed to fetch trending tokens');
        }
      } else if (activeTab === 'new' && newTokens.length === 0) {
        const res = await fetch(`${API_BASE}/api/v1/memescan/new`);
        const data = await res.json();
        if (data.success) {
          setNewTokens(data.tokens);
        } else {
          setError(data.error || 'Failed to fetch new tokens');
        }
      } else if (activeTab === 'pools' && pools.length === 0) {
        const res = await fetch(`${API_BASE}/api/v1/memescan/pools`);
        const data = await res.json();
        if (data.success) {
          setPools(data.pools);
        } else {
          setError(data.error || 'Failed to fetch pools');
        }
      }
    } catch (err) {
      setError('Network error. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [activeTab, trendingTokens.length, newTokens.length, pools.length]);

  useEffect(() => {
    if (activeTab !== 'check') {
      fetchData();
    }
  }, [activeTab, fetchData]);

  // Check token safety
  const checkSafety = async () => {
    if (!checkAddress.trim()) return;

    setLoading(true);
    setError(null);
    setSafetyResult(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/memescan/check/${checkAddress.trim()}`);
      const data = await res.json();
      if (data.success) {
        setSafetyResult(data.token);
      } else {
        setError(data.error || 'Failed to analyze token');
      }
    } catch (err) {
      setError('Network error. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Get safety icon
  const getSafetyIcon = (level: string) => {
    switch (level) {
      case 'safe': return '✅';
      case 'warning': return '⚠️';
      case 'danger': return '🚨';
      default: return '❓';
    }
  };

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-top">
          <div className="logo">
            <span className="logo-icon">🐸</span>
            <span className="logo-text">MEMESCAN</span>
            <span className="version">v1.0</span>
          </div>
          <div className="header-status">
            <span className="status-dot"></span>
            <span>LIVE</span>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <nav className="tabs">
        <button
          className={`tab ${activeTab === 'trending' ? 'active' : ''}`}
          onClick={() => setActiveTab('trending')}
        >
          🔥 TRENDING
        </button>
        <button
          className={`tab ${activeTab === 'new' ? 'active' : ''}`}
          onClick={() => setActiveTab('new')}
        >
          🆕 NEW
        </button>
        <button
          className={`tab ${activeTab === 'check' ? 'active' : ''}`}
          onClick={() => setActiveTab('check')}
        >
          🔍 CHECK
        </button>
        <button
          className={`tab ${activeTab === 'pools' ? 'active' : ''}`}
          onClick={() => setActiveTab('pools')}
        >
          💧 POOLS
        </button>
      </nav>

      {/* Content */}
      <main className="content">
        {/* Loading State */}
        {loading && (
          <div className="loading">
            <div className="spinner"></div>
            <span className="loading-text">Scanning markets...</span>
          </div>
        )}

        {/* Error State */}
        {error && !loading && (
          <div className="error">
            <div className="error-text">❌ {error}</div>
          </div>
        )}

        {/* Trending Tokens */}
        {activeTab === 'trending' && !loading && !error && (
          <div className="token-list">
            {trendingTokens.length === 0 ? (
              <div className="empty">
                <div className="empty-icon">📊</div>
                <div className="empty-text">No trending tokens found</div>
              </div>
            ) : (
              trendingTokens.map((token, i) => (
                <div key={token.address || i} className="token-item">
                  <span className="token-rank">{i + 1}</span>
                  <div className="token-info">
                    <div className="token-symbol">{token.symbol}</div>
                    <div className="token-name">{token.name}</div>
                  </div>
                  <div className="token-metrics">
                    <span className={`token-change ${(token.price_change_24h || 0) >= 0 ? 'positive' : 'negative'}`}>
                      {formatChange(token.price_change_24h || 0)}
                    </span>
                    <span className="token-volume">
                      ${formatNumber(token.volume_24h_usd || 0)} vol
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* New Tokens */}
        {activeTab === 'new' && !loading && !error && (
          <div className="token-list">
            {newTokens.length === 0 ? (
              <div className="empty">
                <div className="empty-icon">🚀</div>
                <div className="empty-text">No new launches found</div>
              </div>
            ) : (
              newTokens.map((token, i) => (
                <div key={token.address || i} className="token-item">
                  <span className="token-rank">{i + 1}</span>
                  <div className="token-info">
                    <div className="token-symbol">{token.symbol}</div>
                    <div className="token-name">
                      {token.created_at ? formatAge(token.created_at) + ' ago' : token.name}
                    </div>
                  </div>
                  <div className="token-metrics">
                    <span className="token-volume">
                      ${formatNumber(token.liquidity_usd)} liq
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Safety Check */}
        {activeTab === 'check' && (
          <>
            <div className="check-input-container">
              <input
                type="text"
                className="check-input"
                placeholder="Enter token address (EQ...)"
                value={checkAddress}
                onChange={(e) => setCheckAddress(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && checkSafety()}
              />
              <button
                className="check-button"
                onClick={checkSafety}
                disabled={loading || !checkAddress.trim()}
              >
                SCAN
              </button>
            </div>

            {!loading && safetyResult && (
              <div className="safety-result">
                <div className="safety-header">
                  <span className="safety-icon">
                    {getSafetyIcon(safetyResult.safety_level)}
                  </span>
                  <div className="safety-title">
                    <div className="safety-symbol">{safetyResult.symbol}</div>
                    <div className="safety-name">{safetyResult.name}</div>
                  </div>
                  <span className={`safety-level ${safetyResult.safety_level}`}>
                    {safetyResult.safety_level}
                  </span>
                </div>

                <div className="safety-stats">
                  <div className="safety-stat">
                    <div className="safety-stat-label">HOLDERS</div>
                    <div className="safety-stat-value">
                      {safetyResult.holder_count.toLocaleString()}
                    </div>
                  </div>
                  <div className="safety-stat">
                    <div className="safety-stat-label">TOP WALLET</div>
                    <div className="safety-stat-value">
                      {safetyResult.dev_wallet_percent.toFixed(1)}%
                    </div>
                  </div>
                </div>

                {safetyResult.safety_warnings.length > 0 && (
                  <div className="safety-warnings">
                    {safetyResult.safety_warnings.map((warning, i) => (
                      <div key={i} className="safety-warning">{warning}</div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {!loading && !safetyResult && !error && (
              <div className="empty">
                <div className="empty-icon">🔍</div>
                <div className="empty-text">
                  Paste a token address to check its safety
                </div>
              </div>
            )}
          </>
        )}

        {/* Pools */}
        {activeTab === 'pools' && !loading && !error && (
          <div className="token-list">
            {pools.length === 0 ? (
              <div className="empty">
                <div className="empty-icon">💧</div>
                <div className="empty-text">No pools found</div>
              </div>
            ) : (
              pools.map((pool, i) => (
                <div key={pool.address || i} className="pool-item">
                  <span className="token-rank">{i + 1}</span>
                  <div className="token-info">
                    <div className="pool-pair">{pool.pair}</div>
                    <span className="pool-dex">{pool.dex}</span>
                  </div>
                  <div className="pool-metrics">
                    <span className="pool-tvl">${formatNumber(pool.liquidity_usd)}</span>
                    <span className="pool-volume">${formatNumber(pool.volume_24h)} 24h</span>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </main>

      {/* CRT overlay effect */}
      <div className="crt-overlay"></div>
    </div>
  );
}

export default App;
