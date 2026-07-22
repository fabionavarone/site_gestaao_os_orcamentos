FROM node:22-alpine AS build
WORKDIR /src
COPY frontend-web/package*.json ./
RUN npm ci
COPY frontend-web/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /src/dist /usr/share/nginx/html
COPY infra/web-nginx.conf /etc/nginx/conf.d/default.conf
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
