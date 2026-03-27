import { useState, useEffect } from 'react';
import './LedgerBalance.css';

export default function LedgerBalance({ buyerAddr, onBack }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!buyerAddr) {
        setError("No buyer address provided.");
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

        // Decode base64 and parse JSON
        const decoded_str = window.atob(encoded_value);
        const decoded_json = JSON.parse(decoded_str);

        // Sort items by extracting number from the key
        const sortedItems = Object.entries(decoded_json).sort((a, b) => {
          const numA = parseInt((a[0].match(/\d+/) || [0])[0], 10) || 0;
          const numB = parseInt((b[0].match(/\d+/) || [0])[0], 10) || 0;
          return numA - numB;
        }).map(([key, value]) => ({ account: key, balance: Number(value) }));

        setData(sortedItems);
      } catch (err) {
        console.error('Failed to fetch ledger balance', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [buyerAddr]);

  const maxBalance = Math.max(...data.map(d => d.balance), 1);

  return (
    <div className="glass-panel ledger-container">
      <div className="ledger-header">
        <h1>Ledger Balance Tracker</h1>
        <p className="subtitle">Real-time balances provided by ABCI</p>
      </div>

      {loading ? (
        <div className="loader-container">
          <div className="spinner"></div>
          <p>Querying ABCI node...</p>
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
        <div className="chart-wrapper">
          <div className="bar-chart">
            {data.map((item, i) => {
              const heightRatio = (item.balance / maxBalance) * 100;
              const delay = i * 0.1; // Staggered animation

              return (
                <div className="bar-column" key={item.account}>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{
                        height: `${heightRatio}%`,
                        animationDelay: `${delay}s`
                      }}
                    >
                      <span className="bar-value">{item.balance}</span>
                    </div>
                  </div>
                  <div className="bar-label">{item.account}</div>
                </div>
              );
            })}
          </div>
        </div>
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
