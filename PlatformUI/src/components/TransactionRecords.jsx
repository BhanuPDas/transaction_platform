import { useState, useEffect } from 'react';
import './TransactionRecords.css';

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Renders an object's key-value pairs as labelled rows (no raw JSON).
 *  Nested objects are rendered as indented sub-sections. */
function InfoFields({ data, depth = 0 }) {
  if (!data || typeof data !== 'object') return <span className="tx-detail-value">—</span>;
  const entries = Object.entries(data).filter(([, v]) => v != null);
  if (entries.length === 0) return <span className="tx-detail-value">—</span>;
  return (
    <div className="info-fields" style={depth > 0 ? { paddingLeft: '12px', borderLeft: '2px solid rgba(255,255,255,0.1)', marginTop: '4px' } : {}}>
      {entries.map(([k, v]) => {
        if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
          return (
            <div className="info-field-row info-field-group" key={k}>
              <span className="info-field-key">{k.replace(/_/g, ' ')}</span>
              <InfoFields data={v} depth={depth + 1} />
            </div>
          );
        }
        const display = typeof v === 'boolean' ? (v ? 'Yes' : 'No') : String(v);
        return (
          <div className="info-field-row" key={k}>
            <span className="info-field-key">{k.replace(/_/g, ' ')}</span>
            <span className="info-field-val">{display}</span>
          </div>
        );
      })}
    </div>
  );
}

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
  if (s === 'expired') return 'expired';
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
  const [currentPage, setCurrentPage] = useState(1);

  const PAGE_SIZE = 10;

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
        // Ongoing (TxEndUnix=0) floats to top; rest sorted newest-first
        records.sort((a, b) => {
          const aOngoing = a.Status?.toLowerCase() === 'ongoing';
          const bOngoing = b.Status?.toLowerCase() === 'ongoing';
          if (aOngoing && !bOngoing) return -1;  // a comes first
          if (!aOngoing && bOngoing) return 1;   // b comes first
          // Both same status → sort by end time descending
          return (b.TxEndUnix || 0) - (a.TxEndUnix || 0);
        });
        setData(records);
        setCurrentPage(1); // reset to first page on fresh fetch
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
      ) : (() => {
        const totalPages = Math.ceil(data.length / PAGE_SIZE);
        const startIdx = (currentPage - 1) * PAGE_SIZE;
        const pageData = data.slice(startIdx, startIdx + PAGE_SIZE);

        return (
          <>
            <div className="tx-list">
              {pageData.map((record, i) => {
                const tx = record.Tx ?? {};
                const sc = statusClass(record.Status);

                return (
                  <div className={`tx-card status-${sc}`} key={record.TxHash || i}>

                    {/* ── Card header ── */}
                    <div className="tx-card-header">
                      <div className="tx-hash-group">
                        <span className="tx-hash-label">Tx ID</span>
                        <span className="tx-hash-value">{record.TxHash || '—'}</span>
                      </div>
                      <StatusBadge status={record.Status} />
                    </div>

                    {/* ── Detail grid ── */}
                    <div className="tx-details-grid">

                      {/* Buyer Information */}
                      <div className="tx-detail-item" style={{ gridColumn: '1 / -1' }}>
                        <span className="tx-detail-label">Buyer Information</span>
                        <div className="tx-detail-value highlight">
                          {tx.buyer
                            ? (() => { const { resource, ...rest } = tx.buyer; return <InfoFields data={rest} />; })()
                            : '—'}
                        </div>
                      </div>

                      {/* Buyer's Demand */}
                      <div className="tx-detail-item" style={{ gridColumn: '1 / -1' }}>
                        <span className="tx-detail-label">Buyer's Demand</span>
                        <div className="tx-detail-value">
                          <InfoFields data={tx.buyer?.resource} />
                        </div>
                      </div>

                      {/* Seller Information */}
                      <div className="tx-detail-item" style={{ gridColumn: '1 / -1' }}>
                        <span className="tx-detail-label">Seller Information</span>
                        <div className="tx-detail-value highlight">
                          <InfoFields data={tx.seller} />
                        </div>
                      </div>

                      {/* Other tx properties (excluding type, buyer, seller) */}
                      {Object.entries(tx).map(([k, v]) => {
                        if (k === 'buyer' || k === 'seller' || k === 'type') return null;
                        let displayValue = String(v);
                        let cls = "tx-detail-value";
                        if (k === 'amount' && v != null) { displayValue = `€${v}`; cls += " green"; }
                        else if (k === 'lease_duration' && v != null) { displayValue = `${v}s`; }
                        else if (k.endsWith('_ts') && v != null) { displayValue = formatTs(v); }
                        else if (typeof v === 'object' && v !== null) { displayValue = JSON.stringify(v); }
                        return (
                          <div className="tx-detail-item" key={k}>
                            <span className="tx-detail-label">{k.replace(/_/g, ' ')}</span>
                            <span className={cls}>{displayValue}</span>
                          </div>
                        );
                      })}

                      {/* Other record fields */}
                      {Object.entries(record).map(([k, v]) => {
                        if (['Tx', 'Status', 'Log', 'TxHash', 'TxEndUnix', 'type'].includes(k)) return null;
                        let displayValue = v;
                        if (k.endsWith('Ts') && v != null) displayValue = formatTs(v);
                        else if (typeof v === 'object' && v !== null) displayValue = JSON.stringify(v);
                        else if (v != null) displayValue = String(v);
                        return (
                          <div className="tx-detail-item" key={k}>
                            <span className="tx-detail-label">{k === 'TxEndTs' ? 'Tx End' : k.replace(/_/g, ' ')}</span>
                            <span className="tx-detail-value">{displayValue || '—'}</span>
                          </div>
                        );
                      })}

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

            {/* ── Pagination Controls ── */}
            {totalPages > 1 && (
              <div className="tx-pagination">
                <button
                  id="tx-page-prev"
                  className="tx-page-btn"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage(p => p - 1)}
                >
                  ‹ Prev
                </button>

                <div className="tx-page-info">
                  <span className="tx-page-current">{currentPage}</span>
                  <span className="tx-page-sep">/</span>
                  <span className="tx-page-total">{totalPages}</span>
                  <span className="tx-page-records">({data.length} records)</span>
                </div>

                <button
                  id="tx-page-next"
                  className="tx-page-btn"
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage(p => p + 1)}
                >
                  Next ›
                </button>
              </div>
            )}
          </>
        );
      })()}

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
