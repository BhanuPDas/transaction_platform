import express from 'express';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { createProxyMiddleware } from 'http-proxy-middleware';
import dns from 'dns';

// Force Node.js to prioritize IPv4 when resolving DNS to avoid 'Host Unreachable' errors
dns.setDefaultResultOrder('ipv4first');

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
app.use(express.json());
const PORT = process.env.PORT || 3000;

// Cluster topology: maps cluster number to the first serf node in that cluster
// Used to determine which backend node to proxy API requests to
const CLUSTER_ENTRY_NODES = {
  1: 'clab-nebula-extended-serf1',
  2: 'clab-nebula-extended-serf18',
  3: 'clab-nebula-extended-serf33',
  4: 'clab-nebula-extended-serf43',
  5: 'clab-nebula-extended-serf66',
  6: 'clab-nebula-extended-serf96',
  7: 'clab-nebula-extended-serf127',
  8: 'clab-nebula-extended-serf51',
};

// Proxy API requests to each cluster's entry node backend
for (const [num, host] of Object.entries(CLUSTER_ENTRY_NODES)) {
  app.use(
    `/api/cluster${num}`,
    createProxyMiddleware({
      target: `http://${host}:5555`,
      changeOrigin: true,
      pathRewrite: { [`^/api/cluster${num}`]: '' },
    })
  );
}

// Proxy Smart Contract initiate_tx POST to the buyer's container
app.use('/api/initiate_tx', createProxyMiddleware({
  target: 'http://localhost:5000', // placeholder, overridden by router
  router: (req) => {
    const buyer = req.query.targetBuyer;
    if (!buyer) return 'http://localhost:5000';
    return `http://clab-nebula-extended-${buyer.split(':')[0]}:5665`;
  },
  changeOrigin: true,
  pathRewrite: () => '/initiate_tx',
  on: {
    proxyReq: (proxyReq, req) => {
      if (req.body) {
        const body = JSON.stringify(req.body);
        proxyReq.setHeader('Content-Type', 'application/json');
        proxyReq.setHeader('Content-Length', Buffer.byteLength(body));
        proxyReq.write(body);
      }
    }
  },
  onError: (err, req, res) => {
    console.error('[initiate_tx Proxy Error]:', err);
    res.status(502).json({ error: 'Proxy could not reach the buyer container.' });
  }
}));

// Proxy dynamic Ledger requests based on node address
app.use('/api/ledger', createProxyMiddleware({
  target: 'http://localhost:26657',
  router: (req) => {
    let addr = req.query.targetAddr;
    if (!addr) return 'http://localhost:26657';
    return `http://${addr.split(':')[0]}:26657`;
  },
  changeOrigin: true,
  pathRewrite: (path, req) => {
    const dataParam = req.query.data || '';
    const newPath = `/abci_query?data=${dataParam}`;
    console.log(`[Ledger Proxy] Forwarding to: ${newPath}`);
    return newPath;
  }
}));

// Proxy Transaction Records requests per buyer node
app.use('/api/tx_records', createProxyMiddleware({
  target: 'http://localhost:26657',
  router: (req) => {
    const buyer = req.query.targetBuyer;
    if (!buyer) return 'http://localhost:26657';
    return `http://clab-nebula-extended-${buyer.split(':')[0]}:26657`;
  },
  changeOrigin: true,
  pathRewrite: (path, req) => {
    const newPath = '/abci_query?data=%22tx%22';
    console.log(`[TxRecords Proxy] Forwarding to: ${newPath} for buyer ${req.query.targetBuyer}`);
    return newPath;
  },
  onError: (err, req, res) => {
    console.error('[TxRecords Proxy Error]:', err);
    res.status(502).json({ error: 'Proxy could not reach the buyer container.' });
  }
}));

// Serve static files from the Vite build output directory
const distPath = join(__dirname, 'dist');
app.use(express.static(distPath));

// Handle client-side routing, returning index.html for all non-file requests
app.use((req, res, next) => {
  if (req.path.startsWith('/api')) {
    return next();
  }
  res.sendFile(join(distPath, 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Trading Platform UI Server running on http://0.0.0.0:${PORT}`);
});
