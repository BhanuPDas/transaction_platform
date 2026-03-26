# Build Stage
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci || npm install

# Copy source and build
COPY . .
RUN npm run build

# Production Stage
FROM node:20-alpine AS production

WORKDIR /app

# Install production dependencies for the Express server
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev || npm install --omit=dev

# Copy the server file and built static assets
COPY server.js ./
COPY --from=builder /app/dist ./dist

EXPOSE 3000

# Require type module in package.json will allow this simple start
CMD ["node", "server.js"]
