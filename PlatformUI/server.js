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
  router: (req) => {
    // The targetAddr is passed by the frontend
    const addr = req.query.targetAddr;
    if (!addr) {
      return 'http://localhost:4041'; // fallback
    }
    return `http://${addr}:4041`;
  },
  changeOrigin: true,
  pathRewrite: { '^/api/hilbert': '/hilbert-output' }
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
