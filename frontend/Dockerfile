# filepath: frontend/Dockerfile
# ── Stage 1: Dependencies ────────────────────────────────────────
FROM node:20-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --ignore-scripts

# ── Stage 2: Build ───────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build-time env vars (defaults; override at build with --build-arg)
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_LLM_MODEL=gpt-4o-mini
ARG NEXT_PUBLIC_EMBEDDING_MODEL=text-embedding-3-large
ARG NEXT_PUBLIC_CHUNK_SIZE=512
ARG NEXT_PUBLIC_CHUNK_OVERLAP=50
ARG NEXT_PUBLIC_DEFAULT_TOP_K=15
ARG NEXT_PUBLIC_SCORE_THRESHOLD=0.65

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_LLM_MODEL=$NEXT_PUBLIC_LLM_MODEL
ENV NEXT_PUBLIC_EMBEDDING_MODEL=$NEXT_PUBLIC_EMBEDDING_MODEL
ENV NEXT_PUBLIC_CHUNK_SIZE=$NEXT_PUBLIC_CHUNK_SIZE
ENV NEXT_PUBLIC_CHUNK_OVERLAP=$NEXT_PUBLIC_CHUNK_OVERLAP
ENV NEXT_PUBLIC_DEFAULT_TOP_K=$NEXT_PUBLIC_DEFAULT_TOP_K
ENV NEXT_PUBLIC_SCORE_THRESHOLD=$NEXT_PUBLIC_SCORE_THRESHOLD

# Disable telemetry during build
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# ── Stage 3: Runtime ─────────────────────────────────────────────
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy standalone output (requires output: "standalone" in next.config)
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
