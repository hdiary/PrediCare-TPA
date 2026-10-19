# Build the Vite application, then serve the immutable bundle with nginx.
FROM node:22-alpine AS build

WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .

ARG VITE_API_URL=/api
ARG VITE_MOCKS=kpis,metrics,models,chat
ARG VITE_SHOW_DEMO_ACCOUNTS=false
ENV VITE_API_URL=$VITE_API_URL \
    VITE_MOCKS=$VITE_MOCKS \
    VITE_SHOW_DEMO_ACCOUNTS=$VITE_SHOW_DEMO_ACCOUNTS
RUN pnpm build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
