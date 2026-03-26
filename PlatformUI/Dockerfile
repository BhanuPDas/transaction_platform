FROM node:20-slim AS builder
WORKDIR /app
# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci || npm install
# Copy source and build
COPY . .
RUN npm run build
# Production Stage
# Using -slim here ensures we use glibc for reliable DNS resolution
FROM node:20-slim AS production
# Set environment to production
ENV NODE_ENV=production
WORKDIR /app
# Install production dependencies for the Express server
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev || npm install --omit=dev
# Copy the server file and built static assets
COPY server.js ./
COPY --from=builder /app/dist ./dist
EXPOSE 3000
# Start the server
CMD ["node", "server.js"]