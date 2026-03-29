import { useState } from 'react';
import TradingForm        from './components/TradingForm';
import LedgerBalance      from './components/LedgerBalance';
import TransactionRecords from './components/TransactionRecords';

function App() {
  const [currentPage, setCurrentPage]           = useState('form');
  const [selectedBuyerAddr, setSelectedBuyerAddr] = useState(null);
  const [selectedBuyerName, setSelectedBuyerName] = useState(null);

  const navigateToLedger = (buyerAddr) => {
    setSelectedBuyerAddr(buyerAddr);
    setCurrentPage('ledger');
  };

  const navigateToTransactions = (buyerName) => {
    setSelectedBuyerName(buyerName);
    setCurrentPage('transactions');
  };

  const navigateToForm = () => {
    setCurrentPage('form');
  };

  return (
    <div className="app-container">
      {currentPage === 'form' ? (
        <TradingForm
          onCheckBalance={navigateToLedger}
          onShowTransactions={navigateToTransactions}
        />
      ) : currentPage === 'ledger' ? (
        <LedgerBalance buyerAddr={selectedBuyerAddr} onBack={navigateToForm} />
      ) : (
        <TransactionRecords buyerName={selectedBuyerName} onBack={navigateToForm} />
      )}
    </div>
  );
}

export default App;
