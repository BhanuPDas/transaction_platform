import { useState, useEffect } from 'react';
import './TransactionRecords.css';

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatTs(ts) {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch {
    return ts;
  }
}

function statusClass(status) {
  if (!status) return 'default';
  const s = status.toLowerCase();
  if (s === 'completed') return 'completed';
  if (s === 'ongoing') return 'ongoing';
  if (s === 'failed') return 'failed';
  return 'default';
}

function StatusBadge({ status }) {
  const cls = statusClass(status);
  return (
    <span className={`tx-status-badge ${cls}`}>
      {cls === 'ongoing' && <span className="pulse-dot" />}
      {status || 'Unknown'}
    </span>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function TransactionRecords({ buyerName, onBack }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!buyerName) {
        setError('No buyer selected.');
        setLoading(false);
        return;
      }

      try {
        const url = `/api/tx_records?targetBuyer=${encodeURIComponent(buyerName)}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Network error: ${response.status}`);

        const q_data = await response.json();
        const encoded_value = q_data?.result?.response?.value;
        if (!encoded_value) throw new Error('No encoded value in response');

        const decoded_str = window.atob(encoded_value);
        const decoded_json = JSON.parse(decoded_str);

        // Support both array and single-object responses
        const records = Array.isArray(decoded_json) ? decoded_json : [decoded_json];
        // Newest first: sort by TxEndUnix descending (OnGoing = 0 → top)
        records.sort((a, b) => (b.TxEndUnix || 0) - (a.TxEndUnix || 0));
        setData(records);
      } catch (err) {
        console.error('Failed to fetch transaction records', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [buyerName]);

  return (
    <div className="glass-panel tx-container">
      {/* Header */}
      <div className="tx-header">
        <h1>Transaction Records</h1>
        <p className="subtitle">
          On-chain trade transactions
        </p>
        {!loading && !error && (
          <div>
            <span className="tx-count-badge">
              📋 {data.length} record{data.length !== 1 ? 's' : ''} found
            </span>
          </div>
        )}
      </div>

      {/* Body */}
      {loading ? (
        <div className="tx-loader-container">
          <div className="tx-spinner" />
          <p>Querying ABCI node…</p>
        </div>
      ) : error ? (
        <div className="tx-error-container">
          <p className="tx-error-text">Failed to fetch records: {error}</p>
          <button className="btn-secondary" onClick={onBack}>Return</button>
        </div>
      ) : data.length === 0 ? (
        <div className="tx-empty-state">
          <p>No transaction records found for this node.</p>
        </div>
      ) : (
        <div className="tx-list">
          {data.map((record, i) => {
            const tx = record.TxObj ?? record.Tx ?? {};
            const sc = statusClass(record.Status);

            return (
              <div className={`tx-card status-${sc}`} key={record.TxHash || i}>

                {/* ── Card header ── */}
                <div className="tx-card-header">
                  <div className="tx-hash-group">
                    <span className="tx-hash-label">Tx Hash</span>
                    <span className="tx-hash-value">{record.TxHash || '—'}</span>
                  </div>
                  <StatusBadge status={record.Status} />
                </div>

                {/* ── Detail grid ── */}
                <div className="tx-details-grid">

                  {/* Parties */}
                  <div className="tx-detail-item">
                    <span className="tx-detail-label">Buyer</span>
                    <span className="tx-detail-value highlight">{tx.buyer || '—'}</span>
                  </div>
                  <div className="tx-detail-item">
                    <span className="tx-detail-label">Seller</span>
                    <span className="tx-detail-value highlight">{tx.seller || '—'}</span>
                  </div>

                  {/* Resource */}
                  <div className="tx-detail-item">
                    <span className="tx-detail-label">Resource Type</span>
                    <span className="tx-detail-value">{tx.resource_type || '—'}</span>
                  </div>
                  <div className="tx-detail-item">
                    <span className="tx-detail-label">Quantity</span>
                    <span className="tx-detail-value">{tx.quantity ?? '—'}</span>
                  </div>

                  {/* Financials */}
                  <div className="tx-detail-item">
                    <span className="tx-detail-label">Amount</span>
                    <span className="tx-detail-value green">€{tx.amount ?? '—'}</span>
                  </div>
                  <div className="tx-detail-item">
                    <span className="tx-detail-label">Price / Unit</span>
                    <span className="tx-detail-value green">€{tx.price ?? '—'}</span>
                  </div>

                  {/* Score */}
                  <div className="tx-detail-item">
                    <span className="tx-detail-label">Score</span>
                    <span className="tx-detail-value amber">{tx.score ?? '—'}</span>
                  </div>

                  {/* Tx Type */}
                  <div className="tx-detail-item">
                    <span className="tx-detail-label">Type</span>
                    <span className="tx-detail-value">{tx.type || '—'}</span>
                  </div>

                  {/* Lease duration */}
                  <div className="tx-detail-item">
                    <span className="tx-detail-label">Lease Duration</span>
                    <span className="tx-detail-value">{tx.lease_duration ? `${tx.lease_duration}s` : '—'}</span>
                  </div>

                  {/* Seller Energy */}
                  <div className="tx-detail-item">
                    <span className="tx-detail-label">Seller Energy</span>
                    <span className="tx-detail-value">{tx.seller_energy ?? '—'}</span>
                  </div>

                  {/* Timestamps */}
                  <div className="tx-detail-item">
                    <span className="tx-detail-label">Tx Start</span>
                    <span className="tx-detail-value">{formatTs(tx.tx_start_ts)}</span>
                  </div>
                  <div className="tx-detail-item">
                    <span className="tx-detail-label">Tx End</span>
                    <span className="tx-detail-value">{formatTs(record.TxEndTs)}</span>
                  </div>

                </div>

                {/* ── Log ── */}
                {record.Log && (
                  <div className="tx-log-row">
                    📝 {record.Log}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Back action */}
      <div className="tx-actions">
        <button type="button" className="btn-secondary back-btn" onClick={onBack}>
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor"
            viewBox="0 0 16 16" style={{ marginRight: '8px' }}>
            <path fillRule="evenodd"
              d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0
                 .708l4 4a.5.5 0 0 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z" />
          </svg>
          Back to Trading Form
        </button>
      </div>
    </div>
  );
}
