# syntax=docker/dockerfile:1

# ==========================================================================
# Senobar — Vue 3 built by Vite, served by Nginx
# ==========================================================================

FROM node:22-alpine AS builder

WORKDIR /app

# Copy manifests first so `npm ci` is cached until dependencies change.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Baked in at build time — Vite inlines env vars, so this cannot be changed
# by the running container. Rebuild to point at a different API.
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build


# --- Runtime --------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

RUN rm -rf /usr/share/nginx/html/*
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
