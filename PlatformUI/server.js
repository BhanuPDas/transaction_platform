import express from 'express';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { createProxyMiddleware } from 'http-proxy-middleware';
import dns from 'dns';

// This will now actually work reliably on node:20 (Debian)
dns.setDefaultResultOrder('ipv4first');

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;

// --- PROXY DEFINITIONS ---

// Proxy Cluster A
app.use('/api/clusterA', createProxyMiddleware({
  target: 'http://clab-century-serf1:5555',
  changeOrigin: true,
  pathRewrite: { '^/api/clusterA': '' }
}));

// Proxy Cluster B
app.use('/api/clusterB', createProxyMiddleware({
  target: 'http://clab-century-serf13:5555',
  changeOrigin: true,
  pathRewrite: { '^/api/clusterB': '' }
}));

// Proxy Hilbert (Dynamic)
app.use('/api/hilbert', createProxyMiddleware({
  target: 'http://localhost:4041', // Placeholder target
  router: (req) => {
    const url = new URL(req.url, `http://${req.headers.host}`);
    const targetAddr = url.searchParams.get('targetAddr');
    if (targetAddr) {
      const host = targetAddr.split(':')[0];
      return `http://${host}:4041`;
    }
    return 'http://localhost:4041';
  },
  changeOrigin: true,
  pathRewrite: { '^/api/hilbert': '/hilbert-output' }
}));

// Proxy Ledger (Dynamic)
app.use('/api/ledger', createProxyMiddleware({
  target: 'http://localhost:26657',
  router: (req) => {
    const url = new URL(req.url, `http://${req.headers.host}`);
    const targetAddr = url.searchParams.get('targetAddr');
    if (targetAddr) {
      const host = targetAddr.split(':')[0];
      return `http://${host}:26657`;
    }
    return 'http://localhost:26657';
  },
  changeOrigin: true,
  pathRewrite: { '^/api/ledger': '/abci_query' }
}));

// --- STATIC FILES & ROUTING ---

const distPath = join(__dirname, 'dist');
app.use(express.static(distPath));

// Important: ensure API calls don't get swallowed by the SPA catch-all
app.use((req, res, next) => {
  if (req.path.startsWith('/api')) {
    return next();
  }
  res.sendFile(join(distPath, 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`UI Server running on http://0.0.0.0:${PORT}`);
});