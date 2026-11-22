FROM oven/bun:1-alpine AS base

WORKDIR /app

# ===================================================================
# Dependencies stage
# ===================================================================
FROM base AS deps
WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

# ===================================================================
# Build stage
# ===================================================================
FROM deps AS build
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN bun run build

# ===================================================================
# Production stage
# ===================================================================
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production

COPY --from=build /app/.output ./ .output

EXPOSE 3000
ENV HOST=0.0.0.0 PORT=3000

CMD ["bun", ".output/server/index.mjs"]
