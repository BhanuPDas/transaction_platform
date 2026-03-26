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
  target: 'http://localhost:4041', // Default fallback
  router: (req) => {
    // 1. Try to get the address from the query string
    const targetAddr = req.query.targetAddr;

    if (targetAddr) {
      // Clean the address (remove ports if they were sent in the string)
      const host = targetAddr.split(':')[0];
      const finalTarget = `http://${host}:4041`;

      console.log(`[Proxy Success] Routing to: ${finalTarget}`);
      return finalTarget;
    }

    console.warn('[Proxy Warning] No targetAddr found in request query');
    return 'http://localhost:4041';
  },
  changeOrigin: true,
  // This ensures the target container receives "/hilbert-output"
  pathRewrite: { '^/api/hilbert': '/hilbert-output' },
  // Important for debugging!
  onProxyReq: (proxyReq, req, res) => {
    console.log(`[Proxying] ${req.method} ${req.url} -> ${proxyReq.host}`);
  }
}));

// Proxy dynamic Ledger requests based on node address
app.use('/api/ledger', createProxyMiddleware({
  target: 'http://localhost:26657', // Must provide default target
  router: (req) => {
    let addr = req.query.targetAddr;
    if (!addr) {
      return 'http://localhost:26657'; // fallback
    }
    // Remove port if included in the addr
    addr = addr.split(':')[0];
    return `http://${addr}:26657`;
  },
  changeOrigin: true,
  pathRewrite: { '^/api/ledger': '/abci_query' }
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
