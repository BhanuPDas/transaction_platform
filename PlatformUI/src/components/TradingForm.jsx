import { useState, useEffect } from 'react';

const CLUSTERS = ['Cluster A', 'Cluster B'];

// Canonical resource keys that map directly to the POST body JSON
const ALL_RESOURCE_TYPES = ['vcpu', 'ram', 'storage', 'vgpu'];

// Human-friendly labels for the dropdown
const RESOURCE_LABELS = {
  vcpu: 'vCPU',
  ram: 'RAM',
  storage: 'Storage',
  vgpu: 'vGPU',
};

const DEFAULT_ROW = () => ({ type: '', demand_per_unit: '', score: '', budget: '' });

export default function TradingForm({ onCheckBalance, onShowTransactions }) {
  const [formData, setFormData] = useState({
    cluster: '',
    buyer: '',
    leaseDuration: '',
  });

  const [errors, setErrors] = useState({});
  const [buyersList, setBuyersList] = useState([]);
  const [buyerMap, setBuyerMap] = useState({});
  const [txStatus, setTxStatus] = useState(null); // null | 'loading' | 'success' | 'error'
  const [txMessage, setTxMessage] = useState('');

  // Resource rows – start with a single empty row
  const [resourceRows, setResourceRows] = useState([DEFAULT_ROW()]);

  // ── Fetch buyers when cluster changes ─────────────────────────────────────
  useEffect(() => {
    const fetchBuyers = async () => {
      if (!formData.cluster) {
        setBuyersList([]);
        setBuyerMap({});
        return;
      }

      let url = '';
      if (formData.cluster === 'Cluster A') url = '/api/clusterA/members';
      else if (formData.cluster === 'Cluster B') url = '/api/clusterB/members';

      if (url) {
        try {
          const response = await fetch(url);
          if (response.ok) {
            const membersData = await response.json();
            const filtered = membersData.filter(m => m.Tags && m.Tags.role === 'buyer');
            const mapping = {};
            filtered.forEach(m => (mapping[m.Name] = m.Addr));
            setBuyerMap(mapping);
            setBuyersList(filtered.map(m => m.Name).sort((a, b) => a.localeCompare(b)));
          } else {
            setBuyersList([]);
            setBuyerMap({});
          }
        } catch {
          setBuyersList([]);
          setBuyerMap({});
        }
      }
    };

    fetchBuyers();
  }, [formData.cluster]);

  // ── Helpers ───────────────────────────────────────────────────────────────
  const selectedTypes = resourceRows.map(r => r.type).filter(Boolean);

  const availableTypesForRow = (rowIndex) =>
    ALL_RESOURCE_TYPES.filter(
      t => !selectedTypes.includes(t) || resourceRows[rowIndex].type === t
    );

  const handleFormChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => {
      const next = { ...prev, [name]: value };
      if (name === 'cluster') next.buyer = '';
      return next;
    });
    if (errors[name]) setErrors(prev => ({ ...prev, [name]: null }));
  };

  const handleRowChange = (index, field, value) => {
    setResourceRows(prev => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  };

  const addRow = () => {
    if (resourceRows.length < ALL_RESOURCE_TYPES.length) {
      setResourceRows(prev => [...prev, DEFAULT_ROW()]);
    }
  };

  const removeRow = (index) => {
    setResourceRows(prev => prev.filter((_, i) => i !== index));
  };

  // ── Validation ────────────────────────────────────────────────────────────
  const validateForm = () => {
    const newErrors = {};
    if (!formData.cluster) newErrors.cluster = 'Cluster selection is required';
    if (!formData.buyer) newErrors.buyer = 'Buyer selection is required';

    if (!formData.leaseDuration) {
      newErrors.leaseDuration = 'Lease duration is required';
    } else if (parseInt(formData.leaseDuration, 10) <= 0) {
      newErrors.leaseDuration = 'Lease duration must be greater than 0';
    }

    // Each row must have a type selected
    resourceRows.forEach((row, i) => {
      if (!row.type) newErrors[`row_type_${i}`] = 'Select a resource type';
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // ── Build resources payload ───────────────────────────────────────────────
  const buildResourcesPayload = () => {
    // Start with zeros for every resource type
    const payload = {};
    ALL_RESOURCE_TYPES.forEach(t => {
      payload[t] = { demand_per_unit: 0, score: 0.0, budget: 0.0 };
    });

    // Override with values from non-empty rows
    resourceRows.forEach(row => {
      if (row.type) {
        payload[row.type] = {
          demand_per_unit: parseInt(row.demand_per_unit, 10) || 0,
          score: parseFloat(row.score) || 0.0,
          budget: parseFloat(row.budget) || 0.0,
        };
      }
    });

    return payload;
  };

  // ── Submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;

    const buyerIp = buyerMap[formData.buyer] || '';

    const body = {
      ip: buyerIp,
      lease_duration: parseInt(formData.leaseDuration, 10) || 0,
      resources: buildResourcesPayload(),
    };

    setTxStatus('loading');
    setTxMessage('');

    try {
      const response = await fetch(
        `/api/initiate_tx?targetBuyer=${encodeURIComponent(formData.buyer)}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }
      );

      if (response.ok) {
        const result = await response.json().catch(() => ({}));
        setTimeout(() => {
          setTxStatus('success');
          setTxMessage(result.message || 'Transaction successfully submitted to the blockchain network!');
        }, 1000);
      } else {
        const errData = await response.json().catch(() => ({}));
        setTimeout(() => {
          setTxStatus('error');
          setTxMessage(errData.error || `Request failed with status ${response.status}`);
        }, 1000);
      }
    } catch (err) {
      console.error('initiate_tx error:', err);
      setTimeout(() => {
        setTxStatus('error');
        setTxMessage('Network error: could not reach the buyer container.');
      }, 1000);
    }
  };

  const handleCheckBalance = () => {
    if (!formData.buyer) {
      alert('Please select a buyer node first to check their specific ledger balance.');
      return;
    }
    if (onCheckBalance) onCheckBalance(`clab-century-${formData.buyer}`);
  };

  const handleShowTransactions = () => {
    if (!formData.buyer) {
      alert('Please select a buyer node first to view their transaction records.');
      return;
    }
    if (onShowTransactions) onShowTransactions(formData.buyer);
  };

  const canAddRow = resourceRows.length < ALL_RESOURCE_TYPES.length;

  return (
    <div className="glass-panel">
      <h1>Trade Compute Resources</h1>
      <p className="subtitle">Specify the resources you want to trade.</p>

      <form onSubmit={handleSubmit} className="form-grid">

        {/* ── Cluster ────────────────────────────────────── */}
        <div className="form-group">
          <label>Cluster Node</label>
          <select name="cluster" value={formData.cluster} onChange={handleFormChange}>
            <option value="">-- Select Cluster --</option>
            {CLUSTERS.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          {errors.cluster && <span className="error-message">{errors.cluster}</span>}
        </div>

        {/* ── Buyer ──────────────────────────────────────── */}
        <div className="form-group">
          <label>Buyer</label>
          <select
            name="buyer"
            value={formData.buyer}
            onChange={handleFormChange}
            disabled={!formData.cluster || buyersList.length === 0}
          >
            <option value="">-- Select Buyer --</option>
            {buyersList.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
          {errors.buyer && <span className="error-message">{errors.buyer}</span>}
        </div>

        {/* ── Lease Duration ─────────────────────────────── */}
        <div className="form-group">
          <label>Lease Duration (Seconds)</label>
          <input
            type="number"
            name="leaseDuration"
            value={formData.leaseDuration}
            onChange={handleFormChange}
            min="1"
          />
          {errors.leaseDuration && <span className="error-message">{errors.leaseDuration}</span>}
        </div>

        {/* ── Resource Rows ──────────────────────────────── */}
        <div className="form-group full-width">
          <label style={{ marginBottom: '0.75rem', display: 'block' }}>Resources</label>

          {/* Header */}
          <div className="resource-table-header">
            <span>Resource Type</span>
            <span>Demand / Unit</span>
            <span>Score</span>
            <span>Budget</span>
            <span>{/* remove btn column */}</span>
          </div>

          {resourceRows.map((row, index) => (
            <div key={index} className="resource-table-row">
              {/* Resource Type dropdown – hides already-picked items */}
              <div className="resource-cell">
                <select
                  value={row.type}
                  onChange={e => handleRowChange(index, 'type', e.target.value)}
                  className={errors[`row_type_${index}`] ? 'input-error' : ''}
                >
                  <option value="">-- Type --</option>
                  {availableTypesForRow(index).map(t => (
                    <option key={t} value={t}>{RESOURCE_LABELS[t]}</option>
                  ))}
                </select>
                {errors[`row_type_${index}`] && (
                  <span className="error-message">{errors[`row_type_${index}`]}</span>
                )}
              </div>

              <div className="resource-cell">
                <input
                  type="number"
                  min="0"
                  placeholder="0"
                  value={row.demand_per_unit}
                  onChange={e => handleRowChange(index, 'demand_per_unit', e.target.value)}
                />
              </div>

              <div className="resource-cell">
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                  value={row.score}
                  onChange={e => handleRowChange(index, 'score', e.target.value)}
                />
              </div>

              <div className="resource-cell">
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                  value={row.budget}
                  onChange={e => handleRowChange(index, 'budget', e.target.value)}
                />
              </div>

              {/* Remove row – only show when there's more than 1 row */}
              <div className="resource-cell resource-cell-action">
                {resourceRows.length > 1 && (
                  <button
                    type="button"
                    className="btn-remove-row"
                    title="Remove row"
                    onClick={() => removeRow(index)}
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>
          ))}

          {/* Add row button */}
          {canAddRow && (
            <button
              type="button"
              className="btn-add-row"
              onClick={addRow}
              title="Add resource"
            >
              + Add Resource
            </button>
          )}
        </div>

        {/* ── Action Buttons ─────────────────────────────── */}
        <div className="form-group full-width" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <button type="submit" className="btn-primary" disabled={txStatus === 'loading'}>
            {txStatus === 'loading' ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '0.6rem' }}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18" height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ animation: 'spin-ring 0.75s linear infinite', flexShrink: 0 }}
                >
                  <circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.25)" strokeWidth="2.5" fill="none" />
                  <path d="M12 2 a10 10 0 0 1 10 10" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
                </svg>
                Submitting…
              </span>
            ) : 'Initiate Smart Contract'}
          </button>

          <button
            type="button"
            className="btn-primary"
            onClick={handleCheckBalance}
            style={{ backgroundColor: '#28a745' }}
          >
            Check Ledger Balance
          </button>

          <button
            type="button"
            className="btn-primary"
            onClick={handleShowTransactions}
            style={{ backgroundColor: '#7c3aed' }}
          >
            Show Transaction Records
          </button>
        </div>

        {/* ── TX Feedback ────────────────────────────────── */}
        {txStatus === 'success' && (
          <div className="form-group full-width" style={{ color: '#28a745', fontWeight: 600 }}>
            ✅ {txMessage}
          </div>
        )}
        {txStatus === 'error' && (
          <div className="form-group full-width" style={{ color: '#e74c3c', fontWeight: 600 }}>
            ❌ {txMessage}
          </div>
        )}
      </form>
    </div>
  );
}
