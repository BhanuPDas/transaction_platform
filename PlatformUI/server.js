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

// Proxy API requests to Cluster A Backends
app.use('/api/clusterA', createProxyMiddleware({
  target: 'http://clab-century-serf1:5555',
  changeOrigin: true,
  pathRewrite: { '^/api/clusterA': '' }
}));

// Proxy API requests to Cluster B Backends
app.use('/api/clusterB', createProxyMiddleware({
  target: 'http://clab-century-serf13:5555',
  changeOrigin: true,
  pathRewrite: { '^/api/clusterB': '' }
}));

// Proxy dynamic Hilbert requests based on node address
app.use('/api/hilbert', createProxyMiddleware({
  target: 'http://localhost:4041', // Placeholder
  router: (req) => {
    const targetAddr = req.query.targetAddr;
    if (targetAddr) {
      // Strips ports if accidentally passed
      const host = targetAddr.split(':')[0];
      return `http://${host}:4041`;
    }
  },
  changeOrigin: true,
  // This function is the "Magic Bullet"
  // It ignores the original path/query and forces ONLY the correct string
  pathRewrite: (path, req) => {
    console.log(`[Proxy] Cleaning path for ${req.query.targetAddr}`);
    return '/hilbert-output';
  },
  onProxyRes: (proxyRes, req, res) => {
    console.log(`[Target Response] Status: ${proxyRes.statusCode} from ${req.query.targetAddr}`);
  },
  onError: (err, req, res) => {
    console.error('[Proxy Error]:', err);
    res.status(502).send('Proxy could not reach the backend container.');
  }
}));

// Proxy Smart Contract initiate_tx POST to the buyer's container
app.use('/api/initiate_tx', createProxyMiddleware({
  target: 'http://localhost:5000', // placeholder, overridden by router
  router: (req) => {
    const buyer = req.query.targetBuyer;
    if (!buyer) return 'http://localhost:5000';
    return `http://clab-century-${buyer.split(':')[0]}:5665`;
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
