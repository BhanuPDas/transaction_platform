import express from 'express';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;

// Serve static files from the Vite build output directory
const distPath = join(__dirname, 'dist');
app.use(express.static(distPath));

// Handle client-side routing, returning index.html for all non-file requests
app.get('/*', (req, res) => {
  res.sendFile(join(distPath, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Trading Platform UI Server running on port ${PORT}`);
});
