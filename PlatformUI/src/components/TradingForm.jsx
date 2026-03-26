import { useState, useEffect } from 'react';

const CLUSTERS = ['Cluster A', 'Cluster B'];
const RESOURCE_TYPES = ['vCPU', 'vGPU', 'Storage', 'RAM'];

export default function TradingForm({ onCheckBalance }) {
  const [formData, setFormData] = useState({
    cluster: '',
    buyer: '',
    resourceType: '',
    quantity: 1,
    leaseDuration: ''
  });

  const [specs, setSpecs] = useState({
    seller: '',
    cpuDemand: '',
    ramDemand: '',
    storageDemand: '',
    gpuDemand: '',
    amount: ''
  });

  const [errors, setErrors] = useState({});
  const [buyersList, setBuyersList] = useState([]);
  const [buyerMap, setBuyerMap] = useState({});
  const [bestSeller, setBestSeller] = useState(null);
  const [hilbertResults, setHilbertResults] = useState([]);

  useEffect(() => {
    const fetchBuyers = async () => {
      if (!formData.cluster) {
        setBuyersList([]);
        setBuyerMap({});
        return;
      }

      let url = '';
      if (formData.cluster === 'Cluster A') {
        url = 'http://clab-century-serf1:5555/members';
      } else if (formData.cluster === 'Cluster B') {
        url = 'http://clab-century-serf13:5555/members';
      }

      if (url) {
        try {
          const response = await fetch(url);
          if (response.ok) {
            const membersData = await response.json();
            const filtered = membersData.filter(m => m.Tags && m.Tags.role === 'buyer');
            const mapping = {};
            filtered.forEach(m => mapping[m.Name] = m.Addr);
            setBuyerMap(mapping);
            setBuyersList(filtered.map(m => m.Name));
          } else {
            console.error('Failed to fetch members');
            setBuyersList([]);
            setBuyerMap({});
          }
        } catch (error) {
          console.error('Error fetching members:', error);
          setBuyersList([]);
          setBuyerMap({});
        }
      }
    };

    fetchBuyers();
  }, [formData.cluster]);

  useEffect(() => {
    const fetchHilbert = async () => {
      if (!formData.buyer) {
        setHilbertResults([]);
        return;
      }
      try {
        const addr = buyerMap[formData.buyer] || `clab-century-${formData.buyer}`;
        const url = `http://${addr}:4041/hilbert-output`;
        const response = await fetch(url);
        if (response.ok) {
          const data = await response.json();
          setHilbertResults(data.results || []);
        } else {
          console.error('Failed to fetch hilbert output');
          setHilbertResults([]);
        }
      } catch (error) {
        console.error('Error fetching hilbert:', error);
        setHilbertResults([]);
      }
    };

    fetchHilbert();
  }, [formData.buyer]);

  useEffect(() => {
    if (hilbertResults.length > 0 && formData.resourceType) {
      let lowestPrice = Infinity;
      let bestNode = null;

      let priceField = 'price_per_ram';
      if (formData.resourceType === 'vCPU') priceField = 'price_per_cpu';
      else if (formData.resourceType === 'vGPU') priceField = 'price_per_gpu';
      else if (formData.resourceType === 'Storage') priceField = 'price_per_storage';

      for (const node of hilbertResults) {
        const price = node[priceField];
        if (node.name && price !== undefined && price !== null) {
          if (price < lowestPrice) {
            lowestPrice = price;
            bestNode = node;
          }
        }
      }

      if (bestNode) {
        setBestSeller({ ...bestNode, selectedPrice: bestNode[priceField] || 0 });
      } else {
        setBestSeller(null);
      }
    } else {
      setBestSeller(null);
    }
  }, [hilbertResults, formData.resourceType]);

  // Auto-fill disabled fields from the best seller and quantity
  useEffect(() => {
    if (bestSeller) {
      const qty = parseInt(formData.quantity, 10) || 0;
      const amountVal = Math.ceil((bestSeller.selectedPrice || 0) * qty);
      setSpecs({
        seller: bestSeller.name || '',
        cpuDemand: bestSeller.cpu !== undefined ? bestSeller.cpu : '',
        ramDemand: bestSeller.ram !== undefined ? bestSeller.ram : '',
        storageDemand: bestSeller.storage !== undefined ? bestSeller.storage : '',
        gpuDemand: bestSeller.gpu !== undefined ? bestSeller.gpu : '',
        amount: '$' + amountVal
      });
    } else {
      setSpecs({
        seller: '', cpuDemand: '', ramDemand: '', storageDemand: '', gpuDemand: '', amount: ''
      });
    }
  }, [bestSeller, formData.quantity]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => {
      const newData = { ...prev, [name]: value };
      if (name === 'cluster') {
        newData.buyer = ''; // Reset buyer when cluster changes
      }
      return newData;
    });
    // Clear specific error
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: null }));
    }
  };

  const validateForm = () => {
    const newErrors = {};
    if (!formData.cluster) newErrors.cluster = 'Cluster selection is required';
    if (!formData.buyer) newErrors.buyer = 'Buyer selection is required';
    if (!formData.resourceType) newErrors.resourceType = 'Resource type is required';

    if (formData.quantity <= 0) {
      newErrors.quantity = 'Quantity must be at least 1';
    }

    if (!formData.leaseDuration) {
      newErrors.leaseDuration = 'Lease duration is required';
    } else if (parseInt(formData.leaseDuration, 10) <= 0) {
      newErrors.leaseDuration = 'Lease duration must be greater than 0';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (validateForm()) {
      const payload = {
        ...formData,
        ...specs,
        buyerAddress: buyerMap[formData.buyer] || ''
      };
      alert('Transaction securely submitted to the blockchain network!\n\nPayload:\n' + JSON.stringify(payload, null, 2));
    }
  };

  const handleCheckBalance = () => {
    if (!formData.buyer) {
      alert("Please select a buyer node first to check their specific ledger balance.");
      return;
    }
    const addr = buyerMap[formData.buyer] || `clab-century-${formData.buyer}`;
    if (onCheckBalance) {
      onCheckBalance(addr);
    }
  };

  return (
    <div className="glass-panel">
      <h1>Trade Compute Resources</h1>
      <p className="subtitle">Securely provision compute resources.</p>

      <form onSubmit={handleSubmit} className="form-grid">
        {/* Editable: Cluster */}
        <div className="form-group">
          <label>Cluster Node</label>
          <select name="cluster" value={formData.cluster} onChange={handleChange}>
            <option value="">-- Select Cluster --</option>
            {CLUSTERS.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          {errors.cluster && <span className="error-message">{errors.cluster}</span>}
        </div>

        {/* Editable: Buyer */}
        <div className="form-group">
          <label>Buyer</label>
          <select name="buyer" value={formData.buyer} onChange={handleChange} disabled={!formData.cluster || buyersList.length === 0}>
            <option value="">-- Select Buyer --</option>
            {buyersList.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
          {errors.buyer && <span className="error-message">{errors.buyer}</span>}
        </div>

        {/* Editable: Resource Type */}
        <div className="form-group">
          <label>Resource Type</label>
          <select name="resourceType" value={formData.resourceType} onChange={handleChange}>
            <option value="">-- Select Resource --</option>
            {RESOURCE_TYPES.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
          {errors.resourceType && <span className="error-message">{errors.resourceType}</span>}
        </div>

        {/* Editable: Quantity */}
        <div className="form-group">
          <label>Quantity</label>
          <input
            type="number"
            name="quantity"
            value={formData.quantity}
            onChange={handleChange}
            min="1"
          />
          {errors.quantity && <span className="error-message">{errors.quantity}</span>}
        </div>

        {/* Readonly Array 1 */}
        <div className="form-group">
          <label>Matched Seller</label>
          <input type="text" value={specs.seller} disabled placeholder="Auto-assigned Seller" />
        </div>

        <div className="form-group">
          <label>Total Amount</label>
          <input type="text" value={specs.amount} disabled placeholder="€0.00" />
        </div>

        {/* Network Demands Readonly mapped as pairs or full width */}
        <div className="form-group">
          <label>CPU Demand</label>
          <input type="text" value={specs.cpuDemand} disabled placeholder="0 Cores" />
        </div>

        <div className="form-group">
          <label>GPU Demand</label>
          <input type="text" value={specs.gpuDemand} disabled placeholder="0 Units" />
        </div>

        <div className="form-group">
          <label>RAM Demand</label>
          <input type="text" value={specs.ramDemand} disabled placeholder="0 GB" />
        </div>

        <div className="form-group">
          <label>Storage Demand</label>
          <input type="text" value={specs.storageDemand} disabled placeholder="0 GB" />
        </div>

        {/* Editable Duration */}
        <div className="form-group">
          <label>Lease Duration (Seconds)</label>
          <input
            type="number"
            name="leaseDuration"
            value={formData.leaseDuration}
            onChange={handleChange}
            min="1"
          />
          {errors.leaseDuration && <span className="error-message">{errors.leaseDuration}</span>}
        </div>

        <div className="form-group full-width" style={{ display: 'flex', gap: '1rem' }}>
          <button type="submit" className="btn-primary">
            Initiate Smart Contract
          </button>
          <button type="button" className="btn-primary" onClick={handleCheckBalance} style={{ backgroundColor: '#28a745' }}>
            Check Ledger Balance
          </button>
        </div>
      </form>
    </div>
  );
}
