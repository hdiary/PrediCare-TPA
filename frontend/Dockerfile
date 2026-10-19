<<<<<<< HEAD
FROM node:22-alpine

=======
# --- Étape 1 : construction (Vite) ---
FROM node:22-alpine AS build
>>>>>>> 267f47592c0e953b7f9bf5d1f51cddae4ce4ddc3
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
<<<<<<< HEAD

ARG VITE_API_URL=http://localhost:8000
ARG VITE_USE_MOCKS=true
ARG VITE_USE_MOCK_AUTH=false
ARG VITE_USE_MOCK_CHAT=false
ENV VITE_API_URL=$VITE_API_URL VITE_USE_MOCKS=$VITE_USE_MOCKS \
    VITE_USE_MOCK_AUTH=$VITE_USE_MOCK_AUTH VITE_USE_MOCK_CHAT=$VITE_USE_MOCK_CHAT

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
=======
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
>>>>>>> 267f47592c0e953b7f9bf5d1f51cddae4ce4ddc3
