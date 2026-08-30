# syntax=docker/dockerfile:1
FROM node:22-alpine AS deps
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=development
COPY --from=deps /app/node_modules ./node_modules
COPY apps/web/ ./
EXPOSE 3000
# Dev server rather than a production build: Phase 1 only has to boot and serve
# /health. The optimized multi-stage build lands with Phase 16 (production
# polish), where there is something worth optimizing.
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]
