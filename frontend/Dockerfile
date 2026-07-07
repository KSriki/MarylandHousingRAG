# syntax=docker/dockerfile:1
# Build the static frontend, then hand the built assets to a volume nginx serves.

# ---- build stage ----
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---- export stage ----
# Minimal image whose only job is to hold /dist so compose can copy it into the
# shared policy_web_dist volume on startup.
FROM busybox:1.36
WORKDIR /web
COPY --from=build /app/dist /web/dist
# On start, sync built assets into the mounted volume, then idle.
CMD ["sh", "-c", "cp -r /web/dist/* /usr/share/nginx/html/ && echo 'frontend assets published' && sleep infinity"]
