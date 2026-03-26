import { useState } from 'react';
import TradingForm from './components/TradingForm';
import LedgerBalance from './components/LedgerBalance';

function App() {
  const [currentPage, setCurrentPage] = useState('form');
  const [selectedBuyerAddr, setSelectedBuyerAddr] = useState(null);

  const navigateToLedger = (buyerAddr) => {
    setSelectedBuyerAddr(buyerAddr);
    setCurrentPage('ledger');
  };

  const navigateToForm = () => {
    setCurrentPage('form');
  };

  return (
    <div className="app-container">
      {currentPage === 'form' ? (
        <TradingForm onCheckBalance={navigateToLedger} />
      ) : (
        <LedgerBalance buyerAddr={selectedBuyerAddr} onBack={navigateToForm} />
      )}
    </div>
  );
}

export default App;
