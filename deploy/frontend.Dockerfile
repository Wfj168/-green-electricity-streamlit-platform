FROM node:22-alpine AS build

WORKDIR /app
RUN corepack enable

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
ARG VITE_AUTH_REQUIRED=true
ENV VITE_AUTH_REQUIRED=${VITE_AUTH_REQUIRED} \
    VITE_API_BASE_URL=""
RUN pnpm run build

FROM nginx:1.27-alpine
COPY deploy/nginx.v2.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD wget -q -O - http://127.0.0.1:8080/health >/dev/null || exit 1
