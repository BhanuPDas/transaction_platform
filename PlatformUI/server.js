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
app.use(createProxyMiddleware('/api/clusterA', {
  target: 'http://clab-century-serf1:5555',
  changeOrigin: true,
  pathRewrite: { '^/api/clusterA': '' }
}));

// Proxy API requests to Cluster B Backends
app.use(createProxyMiddleware('/api/clusterB', {
  target: 'http://clab-century-serf13:5555',
  changeOrigin: true,
  pathRewrite: { '^/api/clusterB': '' }
}));

// Proxy dynamic Hilbert requests based on node address
app.use(createProxyMiddleware('/api/hilbert', {
  target: 'http://localhost:4041', // Must provide default target
  router: (req) => {
    // The targetAddr is passed by the frontend
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    let addr = url.searchParams.get('targetAddr');
    if (!addr) {
      return 'http://localhost:4041'; // fallback
    }
    // Remove port if included in the addr (e.g. 172.20.20.2:5555 -> 172.20.20.2)
    addr = addr.split(':')[0];
    return `http://${addr}:4041`;
  },
  changeOrigin: true,
  pathRewrite: { '^/api/hilbert': '/hilbert-output' }
}));

// Proxy dynamic Ledger requests based on node address
app.use(createProxyMiddleware('/api/ledger', {
  target: 'http://localhost:26657', // Must provide default target
  router: (req) => {
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    let addr = url.searchParams.get('targetAddr');
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
