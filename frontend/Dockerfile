# --- Étape 1 : construction (Vite) ---
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Fonctions simulées dans cette image (voir .env.example) ; "none" quand tout est branché
ARG VITE_MOCKS=kpis,metrics,models,chat
ARG VITE_SHOW_DEMO_ACCOUNTS=false
ENV VITE_MOCKS=$VITE_MOCKS VITE_SHOW_DEMO_ACCOUNTS=$VITE_SHOW_DEMO_ACCOUNTS
RUN npm run build

# --- Étape 2 : service (nginx) ---
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
