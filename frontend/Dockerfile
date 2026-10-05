# syntax=docker/dockerfile:1
# ADVAR frontend. Targets:
#   deps   - node_modules only
#   dev    - `next dev` with hot reload (docker compose locally)
#   build  - production build (output: standalone)
#   runner - minimal production image running server.js
ARG NODE_IMAGE=node:22-alpine

FROM ${NODE_IMAGE} AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS dev
ENV NODE_ENV=development \
    NEXT_TELEMETRY_DISABLED=1 \
    WATCHPACK_POLLING=true
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

FROM deps AS build
ENV NEXT_TELEMETRY_DISABLED=1
COPY . .
# Public build-time variables (baked into the client bundle)
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ARG NEXT_PUBLIC_STRIPE_MODE=test
ARG NEXT_PUBLIC_DEFAULT_LOCALE=en
ARG NEXT_PUBLIC_SENTRY_DSN=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_STRIPE_MODE=$NEXT_PUBLIC_STRIPE_MODE \
    NEXT_PUBLIC_DEFAULT_LOCALE=$NEXT_PUBLIC_DEFAULT_LOCALE \
    NEXT_PUBLIC_SENTRY_DSN=$NEXT_PUBLIC_SENTRY_DSN
RUN npm run build

FROM ${NODE_IMAGE} AS runner
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    NEXT_TELEMETRY_DISABLED=1
# Same UID/GID pattern as the backend image: a non-root user that owns the app files.
ARG APP_UID=1001
ARG APP_GID=1001
RUN addgroup -g ${APP_GID} -S advar && adduser -S -u ${APP_UID} -G advar advar
COPY --from=build --chown=advar:advar /app/.next/standalone ./
COPY --from=build --chown=advar:advar /app/.next/static ./.next/static
COPY --from=build --chown=advar:advar /app/public ./public
USER advar
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD wget -qO- http://127.0.0.1:3000/en >/dev/null || exit 1
CMD ["node", "server.js"]
