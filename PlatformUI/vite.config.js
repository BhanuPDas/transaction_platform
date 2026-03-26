import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import dns from 'dns'

// Force Node.js to prioritize IPv4 when resolving DNS in Vite dev server
dns.setDefaultResultOrder('ipv4first')

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Ensure Vite binds to IPv4 interfaces
    proxy: {
      '/api/clusterA': {
        target: 'http://clab-century-serf1:5555',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/clusterA/, '')
      },
      '/api/clusterB': {
        target: 'http://clab-century-serf13:5555',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/clusterB/, '')
      },
      '/api/hilbert': {
        target: 'http://localhost:4041', // Dynamic target, handled by router func
        changeOrigin: true,
        router: (req) => {
          try {
            // Need a base URL just to parse the search params securely
            const baseUrl = `http://${req.headers.host || 'localhost'}`;
            const url = new URL(req.url, baseUrl);
            let targetAddr = url.searchParams.get('targetAddr');
            if (targetAddr) {
                targetAddr = targetAddr.split(':')[0];
                return `http://${targetAddr}:4041`;
            }
          } catch (e) {
            console.error("Vite Proxy Router Error:", e);
          }
          return 'http://localhost:4041';
        },
        rewrite: (path) => path.replace(/^\/api\/hilbert/, '/hilbert-output')
      },
      '/api/ledger': {
        target: 'http://localhost:26657', // Dynamic target, handled by router func
        changeOrigin: true,
        router: (req) => {
          try {
            const baseUrl = `http://${req.headers.host || 'localhost'}`;
            const url = new URL(req.url, baseUrl);
            let targetAddr = url.searchParams.get('targetAddr');
            if (targetAddr) {
                targetAddr = targetAddr.split(':')[0];
                return `http://${targetAddr}:26657`;
            }
          } catch (e) {
            console.error("Vite Proxy Router Error:", e);
          }
          return 'http://localhost:26657';
        },
        rewrite: (path) => path.replace(/^\/api\/ledger/, '/abci_query')
      }
    }
  }
})
