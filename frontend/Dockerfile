FROM node:20-alpine AS base

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

FROM base AS deps

COPY package.json package-lock.json ./
RUN npm ci

FROM base AS development

ENV NODE_ENV=development

COPY package.json package-lock.json ./
RUN npm ci

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]

FROM base AS builder

ENV NODE_ENV=production

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN mkdir -p public \
    && npm run build

FROM base AS runner

ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000

RUN addgroup -S nodejs \
    && adduser -S nextjs -G nodejs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
