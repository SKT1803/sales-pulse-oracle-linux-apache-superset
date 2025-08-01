# ---------- Build stage ----------
FROM node:20-alpine AS build

WORKDIR /app

# package* dosyaları client klasöründen kopyala (context kök!)
COPY client/package.json client/package-lock.json* client/pnpm-lock.yaml* client/yarn.lock* ./
RUN npm ci || npm i

# VITE_API_URL build arg (default: /api)
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

# Tüm client kaynaklarını kopyala (context kök, kaynak client/)
COPY client/ ./
RUN npm run build

# ---------- Run stage (Nginx) ----------
FROM nginx:alpine

# Nginx konfigürasyonunu kökteki deploy klasöründen kopyala
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf

# Statik dosyaları yerleştir
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
