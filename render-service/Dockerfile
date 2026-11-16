FROM node:22-bookworm-slim

# Install Chromium and FFmpeg for HyperFrames and Remotion rendering
RUN apt-get update && \
    apt-get install -y --no-install-recommends chromium ffmpeg && \
    rm -rf /var/lib/apt/lists/*

ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV CHROME_BIN=/usr/bin/chromium
ENV OUTPUT_DIR=/output
ENV TEMPLATES_DIR=/app/templates
ENV RENDER_ENGINE=hyperframes

WORKDIR /app

# Install HyperFrames CLI
RUN npm install -g hyperframes@^0.9.54

# Copy render service source
COPY render-service/package.json render-service/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY render-service/tsconfig.json ./
COPY render-service/src/ ./src/

# Copy shared composition templates
COPY templates/ /app/templates/

# Optional: Copy remotion source for fallback compatibility
COPY remotion/package.json remotion/package-lock.json /app/remotion/
COPY remotion/tsconfig.json /app/remotion/tsconfig.json
COPY remotion/src/ /app/remotion/src/
COPY remotion/public/ /app/remotion/public/
RUN cd /app/remotion && npm ci --no-audit --no-fund

# Build TypeScript
RUN npm run build

EXPOSE 3100
CMD ["node", "dist/server.js"]
