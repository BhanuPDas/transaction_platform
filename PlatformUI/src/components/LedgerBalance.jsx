import { useState, useEffect, useMemo } from 'react';
import './LedgerBalance.css';

export default function LedgerBalance({ buyerAddr, onBack }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [sortOrder, setSortOrder] = useState('account'); // 'account' | 'asc' | 'desc'

  useEffect(() => {
    const fetchData = async () => {
      if (!buyerAddr) {
        setError('No buyer address provided.');
        setLoading(false);
        return;
      }

      try {
        const url = `/api/ledger?targetAddr=${encodeURIComponent(buyerAddr)}&data=%22balance%22`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Network error: ${response.status}`);

        const q_data = await response.json();
        const encoded_value = q_data?.result?.response?.value;
        if (!encoded_value) throw new Error('No encoded value found in response');

        const decoded_str = window.atob(encoded_value);
        const decoded_json = JSON.parse(decoded_str);

        // Sort items by extracting number from the key (account-ordered default)
        const items = Object.entries(decoded_json)
          .map(([key, value]) => ({ account: key, balance: Number(value) }))
          .sort((a, b) => {
            const numA = parseInt((a.account.match(/\d+/) || [0])[0], 10) || 0;
            const numB = parseInt((b.account.match(/\d+/) || [0])[0], 10) || 0;
            return numA - numB;
          });

        setData(items);
      } catch (err) {
        console.error('Failed to fetch ledger balance', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [buyerAddr]);

  // ── Derived display data ───────────────────────────────────────────────────
  const filtered = useMemo(() => {
    let result = data.filter(d =>
      d.account.toLowerCase().includes(search.toLowerCase())
    );
    if (sortOrder === 'asc') result = [...result].sort((a, b) => a.balance - b.balance);
    else if (sortOrder === 'desc') result = [...result].sort((a, b) => b.balance - a.balance);
    // 'account' keeps the original numeric sort from fetch
    return result;
  }, [data, search, sortOrder]);

  const maxBalance = useMemo(() => Math.max(...filtered.map(d => d.balance), 1), [filtered]);

  const stats = useMemo(() => {
    if (!data.length) return null;
    const balances = data.map(d => d.balance);
    const total = balances.reduce((s, v) => s + v, 0);
    return {
      total,
      avg: (total / balances.length).toFixed(2),
      max: Math.max(...balances),
      min: Math.min(...balances),
      count: balances.length,
    };
  }, [data]);

  return (
    <div className="glass-panel ledger-container">
      <div className="ledger-header">
        <h1>Ledger Balance Tracker</h1>
        <p className="subtitle">Real-time balances from ABCI · {buyerAddr}</p>
      </div>

      {loading ? (
        <div className="loader-container">
          <div className="spinner"></div>
          <p>Querying ABCI node…</p>
        </div>
      ) : error ? (
        <div className="error-container">
          <p className="error-text">Failed to fetch data: {error}</p>
          <button className="btn-secondary" onClick={onBack}>Return</button>
        </div>
      ) : data.length === 0 ? (
        <div className="empty-state">
          <p>No account balances found on node.</p>
        </div>
      ) : (
        <>
          {/* ── Summary stats ────────────────────────────── */}
          {stats && (
            <div className="stats-row">
              <div className="stat-card">
                <span className="stat-label">Nodes</span>
                <span className="stat-value">{stats.count}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Total</span>
                <span className="stat-value">{stats.total.toLocaleString()}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Average</span>
                <span className="stat-value">{Number(stats.avg).toLocaleString()}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Max</span>
                <span className="stat-value stat-max">{stats.max.toLocaleString()}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Min</span>
                <span className="stat-value stat-min">{stats.min.toLocaleString()}</span>
              </div>
            </div>
          )}

          {/* ── Controls ─────────────────────────────────── */}
          <div className="controls-row">
            <input
              className="search-input"
              type="text"
              placeholder="Filter accounts…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
            <div className="sort-group">
              <span className="sort-label">Sort:</span>
              {[
                { value: 'account', label: 'Node #' },
                { value: 'desc', label: 'High → Low' },
                { value: 'asc', label: 'Low → High' },
              ].map(opt => (
                <button
                  key={opt.value}
                  className={`sort-btn ${sortOrder === opt.value ? 'active' : ''}`}
                  onClick={() => setSortOrder(opt.value)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <span className="result-count">
              {filtered.length} / {data.length} accounts
            </span>
          </div>

          {/* ── Horizontal bar chart ─────────────────────── */}
          <div className="chart-wrapper">
            <div className="hbar-chart" role="list">
              {filtered.map((item, i) => {
                const widthPct = (item.balance / maxBalance) * 100;
                const delay = Math.min(i * 0.04, 1.5); // cap animation delay at 1.5s for large lists

                return (
                  <div className="hbar-row" key={item.account} role="listitem">
                    <div className="hbar-label" title={item.account}>
                      {item.account}
                    </div>
                    <div className="hbar-track">
                      <div
                        className="hbar-fill"
                        style={{
                          width: `${widthPct}%`,
                          animationDelay: `${delay}s`,
                        }}
                      />
                    </div>
                    <div className="hbar-value">{item.balance.toLocaleString()}</div>
                  </div>
                );
              })}

              {filtered.length === 0 && (
                <div className="no-results">No accounts match your filter.</div>
              )}
            </div>
          </div>
        </>
      )}

      <div className="ledger-actions">
        <button type="button" className="btn-secondary back-btn" onClick={onBack}>
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16" style={{ marginRight: '8px' }}>
            <path fillRule="evenodd" d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 0 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z" />
          </svg>
          Back to Trading Form
        </button>
      </div>
    </div>
  );
}
